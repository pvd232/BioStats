from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from pydantic import ValidationError

from mantra_provenance.models_v4 import (
    CONTINUATION_STATE,
    MODEL_PARAMETERS,
    PREDICTIONS,
    CUDABackendContext,
    EvaluateSpec,
    ResolvedBundleArtifact,
    RunAttempt,
    RunSpec,
    TrainSpec,
    VariantSpec,
)
from mantra_provenance.yaml_io import load_resolved_spec, load_spec

SHA_A = "a" * 64
SHA_B = "b" * 64
GIT_COMMIT = "a" * 40
REPOSITORY = "https://github.com/example/mantra"
RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RUN_ROOT = f"experiments/e001_strand/runs/baseline/{RUN_ID}"


def git_file(path: str) -> dict:
    return {
        "kind": "git",
        "repository": REPOSITORY,
        "commit": GIT_COMMIT,
        "path": path,
    }


def environment(*, compute: dict | None = None) -> dict:
    return {
        "kind": "gce",
        "machine_image": {
            "project": "mantra-project",
            "name": "mantra-image",
        },
        "machine_type": "n2-standard-8",
        "compute": compute or {"kind": "cpu"},
        "lockfile": git_file("uv.lock"),
    }


def reproducibility() -> dict:
    return {
        "determinism": {
            "deterministic_algorithms": True,
            "deterministic_warn_only": False,
            "cudnn_deterministic": True,
            "cudnn_benchmark": False,
            "cublas_workspace_config": ":4096:8",
        },
        "precision": {
            "float32_matmul_precision": "highest",
            "cudnn_allow_tf32": False,
            "autocast_enabled": False,
            "autocast_dtype": None,
        },
        "parallelism": {
            "process_count": 1,
            "torch_intraop_threads": 1,
            "torch_interop_threads": 1,
            "dataloader_workers": 0,
        },
    }


def artifact(path: str, loader: str) -> dict:
    return {
        "kind": "file",
        "path": path,
        "loader": loader,
    }


def stored_input(path: str, pointer_path: str) -> dict:
    return {
        "kind": "stored",
        "pointer": git_file(pointer_path),
        "path": path,
    }


def train_payload() -> dict:
    return {
        "kind": "train",
        "script": "src/mantra/models/strand/train.py",
        "inputs": {
            "training_dataset": stored_input(
                "inputs/datasets/replogle/dataset.h5ad",
                "inputs/datasets/replogle/current.pointer.yaml",
            ),
        },
        "params": {
            "epochs": 10,
            "batch_size": 64,
            "learning_rate": 0.001,
        },
        "artifacts": {
            MODEL_PARAMETERS: artifact(
                f"{RUN_ROOT}/artifacts/models/strand/model_parameters.safetensors",
                "model_parameters",
            ),
            CONTINUATION_STATE: artifact(
                f"{RUN_ROOT}/artifacts/models/strand/continuation_state.pt",
                "continuation_state",
            ),
        },
    }


def run_payload() -> dict:
    return {
        "run_id": RUN_ID,
        "experiment_id": "e001_strand",
        "variant_id": "baseline",
        "replicate_id": "replicate_01",
        "seed": 42,
        "source": {
            "kind": "git",
            "repository": REPOSITORY,
            "commit": GIT_COMMIT,
        },
        "environment": environment(),
        "reproducibility": reproducibility(),
        "stages": [
            {
                "stage_id": "train",
                "spec": f"{RUN_ROOT}/stages/train/spec.yaml",
                "sha256": SHA_A,
                "bytes": 100,
            }
        ],
        "estimator": {
            "stage_id": "train",
            "artifact_name": MODEL_PARAMETERS,
        },
    }


class RunPlanTests(unittest.TestCase):
    def test_run_plan_owns_shared_environment_and_reproducibility(self) -> None:
        run = RunSpec.model_validate(run_payload())

        self.assertEqual(run.seed, 42)
        self.assertEqual(run.environment.machine_type, "n2-standard-8")
        self.assertEqual(run.estimator.artifact_name, MODEL_PARAMETERS)

    def test_estimator_must_select_model_parameters(self) -> None:
        payload = run_payload()
        payload["estimator"]["artifact_name"] = CONTINUATION_STATE

        with self.assertRaisesRegex(ValidationError, "model_parameters"):
            RunSpec.model_validate(payload)

    def test_stage_spec_reference_uses_canonical_run_path(self) -> None:
        payload = run_payload()
        payload["stages"][0]["spec"] = "stages/train/spec.yaml"

        with self.assertRaisesRegex(ValidationError, "canonical run path"):
            RunSpec.model_validate(payload)

    def test_global_seed_uses_the_shared_generator_range(self) -> None:
        maximum = run_payload()
        maximum["seed"] = 2**32 - 1
        self.assertEqual(RunSpec.model_validate(maximum).seed, 2**32 - 1)

        for invalid_seed in (-1, 2**32):
            with self.subTest(seed=invalid_seed):
                payload = run_payload()
                payload["seed"] = invalid_seed
                with self.assertRaises(ValidationError):
                    RunSpec.model_validate(payload)

    def test_successful_attempt_requires_a_completed_stage(self) -> None:
        with self.assertRaisesRegex(ValidationError, "completed stage"):
            RunAttempt.model_validate(
                {
                    "attempt_id": 1,
                    "status": "succeeded",
                    "started_at": "2026-08-20T20:00:00Z",
                    "completed_at": "2026-08-20T20:01:00Z",
                    "resolved_stages": [],
                    "measurement_files": [],
                    "log_files": [],
                    "failure_reason": None,
                }
            )

    def test_attempt_file_storage_locations_are_unique(self) -> None:
        location = {
            "kind": "huggingface",
            "repository": "example/mantra-runs",
            "commit": GIT_COMMIT,
            "path": f"{RUN_ROOT}/logs/1.train.stdout.log",
            "repo_type": "dataset",
        }
        payload = {
            "attempt_id": 1,
            "status": "failed",
            "started_at": "2026-08-20T20:00:00Z",
            "completed_at": "2026-08-20T20:01:00Z",
            "resolved_stages": [],
            "measurement_files": [],
            "log_files": [
                {"sha256": SHA_A, "bytes": 1, "stored_at": location},
                {"sha256": SHA_B, "bytes": 1, "stored_at": location},
            ],
            "failure_reason": "stage failed",
        }

        with self.assertRaisesRegex(ValidationError, "storage locations"):
            RunAttempt.model_validate(payload)


class RuntimeInvariantTests(unittest.TestCase):
    def test_cuda_device_ordinals_are_unique(self) -> None:
        device = {
            "ordinal": 0,
            "model": "NVIDIA L4",
            "compute_capability_major": 8,
            "compute_capability_minor": 9,
            "memory_bytes": 24_000_000_000,
        }
        with self.assertRaisesRegex(ValidationError, "ordinals"):
            CUDABackendContext.model_validate(
                {
                    "kind": "cuda",
                    "gpu_devices": [device, device],
                    "nvidia_driver_version": "580.65",
                    "pytorch_cuda_version": "12.8",
                    "cudnn_version": "9.10",
                }
            )


class TrainingCheckpointTests(unittest.TestCase):
    def test_repository_paths_reject_control_characters(self) -> None:
        payload = train_payload()
        payload["script"] = "src/mantra/models/strand/train.py\nother"

        with self.assertRaisesRegex(ValidationError, "control character"):
            TrainSpec.model_validate(payload)

    def test_stage_paths_use_protocol_roots(self) -> None:
        invalid_script = train_payload()
        invalid_script["script"] = "scripts/train.py"
        with self.assertRaisesRegex(ValidationError, "canonical category"):
            TrainSpec.model_validate(invalid_script)

        wrong_script_category = train_payload()
        wrong_script_category["script"] = "src/mantra/priors/strand/train.py"
        with self.assertRaisesRegex(ValidationError, "canonical category"):
            TrainSpec.model_validate(wrong_script_category)

        invalid_input = train_payload()
        invalid_input["inputs"]["training_dataset"]["path"] = "data/train.h5ad"
        with self.assertRaisesRegex(ValidationError, "category and entity ID"):
            TrainSpec.model_validate(invalid_input)

        invalid_pointer = train_payload()
        invalid_pointer["inputs"]["training_dataset"]["pointer"]["path"] = (
            "inputs/datasets/replogle.pointer.yaml"
        )
        with self.assertRaisesRegex(ValidationError, "selection_name"):
            TrainSpec.model_validate(invalid_pointer)

        invalid_artifact = train_payload()
        invalid_artifact["artifacts"][MODEL_PARAMETERS]["path"] = (
            "artifacts/model_parameters.safetensors"
        )
        with self.assertRaisesRegex(ValidationError, "category and entity ID"):
            TrainSpec.model_validate(invalid_artifact)

        wrong_artifact_category = train_payload()
        wrong_artifact_category["artifacts"][MODEL_PARAMETERS]["path"] = (
            f"{RUN_ROOT}/artifacts/priors/strand/model_parameters.safetensors"
        )
        with self.assertRaisesRegex(ValidationError, "category and entity ID"):
            TrainSpec.model_validate(wrong_artifact_category)

    def test_stored_input_path_cannot_overlap_its_pointer_file(self) -> None:
        for path in (
            "inputs/datasets/replogle",
            "inputs/datasets/replogle/current.pointer.yaml/materialized",
            "inputs/datasets/replogle/other.pointer.yaml",
        ):
            with self.subTest(path=path):
                payload = train_payload()
                payload["inputs"]["training_dataset"]["path"] = path

                with self.assertRaisesRegex(ValidationError, "must not"):
                    TrainSpec.model_validate(payload)

    def test_artifact_entity_matches_stage_script_entity(self) -> None:
        payload = train_payload()
        payload["artifacts"][MODEL_PARAMETERS]["path"] = (
            f"{RUN_ROOT}/artifacts/models/other/model_parameters.safetensors"
        )

        with self.assertRaisesRegex(ValidationError, "must match the stage script"):
            TrainSpec.model_validate(payload)

    def test_reserved_artifact_names_are_stage_specific(self) -> None:
        payload = train_payload()
        payload["artifacts"][PREDICTIONS] = artifact(
            f"{RUN_ROOT}/artifacts/models/strand/predictions.parquet",
            "predictions",
        )

        with self.assertRaisesRegex(ValidationError, "reserved for evaluation"):
            TrainSpec.model_validate(payload)

    def test_train_requires_both_terminal_checkpoint_artifacts(self) -> None:
        payload = train_payload()
        del payload["artifacts"][CONTINUATION_STATE]

        with self.assertRaisesRegex(ValidationError, "continuation_state"):
            TrainSpec.model_validate(payload)

    def test_checkpoint_inputs_select_one_producer_and_both_artifacts(self) -> None:
        payload = train_payload()
        payload["inputs"].update(
            {
                "checkpoint_model_parameters": {
                    "kind": "future",
                    "producer_stage_id": "train_01",
                    "producer_artifact": MODEL_PARAMETERS,
                },
                "checkpoint_continuation_state": {
                    "kind": "future",
                    "producer_stage_id": "train_01",
                    "producer_artifact": CONTINUATION_STATE,
                },
            }
        )

        spec = TrainSpec.model_validate(payload)
        self.assertEqual(
            spec.inputs["checkpoint_model_parameters"].producer_stage_id,
            "train_01",
        )

    def test_checkpoint_inputs_must_occur_together(self) -> None:
        payload = train_payload()
        payload["inputs"]["checkpoint_model_parameters"] = {
            "kind": "future",
            "producer_stage_id": "train_01",
            "producer_artifact": MODEL_PARAMETERS,
        }

        with self.assertRaisesRegex(ValidationError, "declared together"):
            TrainSpec.model_validate(payload)

    def test_checkpoint_inputs_must_select_one_producer(self) -> None:
        payload = train_payload()
        payload["inputs"].update(
            {
                "checkpoint_model_parameters": {
                    "kind": "future",
                    "producer_stage_id": "train_01",
                    "producer_artifact": MODEL_PARAMETERS,
                },
                "checkpoint_continuation_state": {
                    "kind": "future",
                    "producer_stage_id": "train_02",
                    "producer_artifact": CONTINUATION_STATE,
                },
            }
        )

        with self.assertRaisesRegex(ValidationError, "one checkpoint-producing"):
            TrainSpec.model_validate(payload)

    def test_stored_checkpoint_inputs_use_model_paths(self) -> None:
        payload = train_payload()
        payload["inputs"].update(
            {
                "checkpoint_model_parameters": stored_input(
                    "inputs/priors/strand/model_parameters.safetensors",
                    "inputs/priors/strand/model_parameters.pointer.yaml",
                ),
                "checkpoint_continuation_state": stored_input(
                    "inputs/priors/strand/continuation_state.pt",
                    "inputs/priors/strand/continuation_state.pointer.yaml",
                ),
            }
        )

        with self.assertRaisesRegex(ValidationError, "inputs/models"):
            TrainSpec.model_validate(payload)


class EvaluationTests(unittest.TestCase):
    def test_evaluation_requires_fixed_inputs_metrics_and_predictions(self) -> None:
        spec = EvaluateSpec.model_validate(
            {
                "kind": "evaluate",
                "script": "src/mantra/models/strand/evaluate.py",
                "inputs": {
                    "model_parameters": {
                        "kind": "future",
                        "producer_stage_id": "train",
                        "producer_artifact": MODEL_PARAMETERS,
                    },
                    "evaluation_dataset": stored_input(
                        "inputs/datasets/replogle_test/dataset.h5ad",
                        "inputs/datasets/replogle_test/current.pointer.yaml",
                    ),
                    "perturbation_split": stored_input(
                        "inputs/benchmarks/replogle/perturbations.json",
                        "inputs/benchmarks/replogle/perturbations.pointer.yaml",
                    ),
                },
                "params": {
                    "metric_ids": ["pearson_correlation"],
                    "split_inputs": ["perturbation_split"],
                },
                "artifacts": {
                    PREDICTIONS: artifact(
                        f"{RUN_ROOT}/artifacts/evaluations/strand/predictions.parquet",
                        "predictions",
                    )
                },
            }
        )

        self.assertIn(PREDICTIONS, spec.artifacts)

    def test_evaluation_inputs_use_role_specific_paths(self) -> None:
        payload = {
            "kind": "evaluate",
            "script": "src/mantra/models/strand/evaluate.py",
            "inputs": {
                "model_parameters": stored_input(
                    "inputs/priors/strand/model_parameters.safetensors",
                    "inputs/priors/strand/current.pointer.yaml",
                ),
                "evaluation_dataset": stored_input(
                    "inputs/datasets/replogle_test/dataset.h5ad",
                    "inputs/datasets/replogle_test/current.pointer.yaml",
                ),
                "split": stored_input(
                    "inputs/benchmarks/replogle/split.json",
                    "inputs/benchmarks/replogle/split.pointer.yaml",
                ),
            },
            "params": {
                "metric_ids": ["pearson_correlation"],
                "split_inputs": ["split"],
            },
            "artifacts": {
                PREDICTIONS: artifact(
                    f"{RUN_ROOT}/artifacts/evaluations/strand/predictions.parquet",
                    "predictions",
                )
            },
        }

        with self.assertRaisesRegex(ValidationError, "inputs/models"):
            EvaluateSpec.model_validate(payload)

        payload["inputs"]["model_parameters"] = stored_input(
            "inputs/models/strand/model_parameters.safetensors",
            "inputs/models/strand/current.pointer.yaml",
        )
        payload["inputs"]["evaluation_dataset"] = stored_input(
            "inputs/priors/replogle_test/dataset.h5ad",
            "inputs/priors/replogle_test/current.pointer.yaml",
        )
        with self.assertRaisesRegex(ValidationError, "inputs/datasets"):
            EvaluateSpec.model_validate(payload)

        payload["inputs"]["evaluation_dataset"] = stored_input(
            "inputs/datasets/replogle_test/dataset.h5ad",
            "inputs/datasets/replogle_test/current.pointer.yaml",
        )
        payload["inputs"]["split"] = stored_input(
            "inputs/datasets/replogle/split.json",
            "inputs/datasets/replogle/split.pointer.yaml",
        )
        with self.assertRaisesRegex(ValidationError, "inputs/benchmarks"):
            EvaluateSpec.model_validate(payload)

    def test_evaluation_rejects_training_checkpoint_outputs(self) -> None:
        payload = {
            "kind": "evaluate",
            "script": "src/mantra/models/strand/evaluate.py",
            "inputs": {
                "model_parameters": stored_input(
                    "inputs/models/strand/model_parameters.safetensors",
                    "inputs/models/strand/current.pointer.yaml",
                ),
                "evaluation_dataset": stored_input(
                    "inputs/datasets/replogle_test/dataset.h5ad",
                    "inputs/datasets/replogle_test/current.pointer.yaml",
                ),
                "split": stored_input(
                    "inputs/benchmarks/replogle/split.json",
                    "inputs/benchmarks/replogle/split.pointer.yaml",
                ),
            },
            "params": {
                "metric_ids": ["pearson_correlation"],
                "split_inputs": ["split"],
            },
            "artifacts": {
                PREDICTIONS: artifact(
                    f"{RUN_ROOT}/artifacts/evaluations/strand/predictions.parquet",
                    "predictions",
                ),
                MODEL_PARAMETERS: artifact(
                    f"{RUN_ROOT}/artifacts/evaluations/strand/model_parameters.safetensors",
                    "model_parameters",
                ),
            },
        }

        with self.assertRaisesRegex(ValidationError, "reserved for training"):
            EvaluateSpec.model_validate(payload)


class ArtifactAndVariantTests(unittest.TestCase):
    def test_bundle_requires_at_least_two_members(self) -> None:
        with self.assertRaises(ValidationError):
            ResolvedBundleArtifact.model_validate(
                {
                    "kind": "bundle",
                    "members": [
                        {
                            "relative_path": "config.json",
                            "file": {
                                "path": "artifacts/model/config.json",
                                "sha256": SHA_A,
                                "bytes": 10,
                            },
                        }
                    ],
                }
            )

    def test_bundle_member_paths_cannot_overlap(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must not overlap"):
            ResolvedBundleArtifact.model_validate(
                {
                    "kind": "bundle",
                    "members": [
                        {
                            "relative_path": "model",
                            "file": {
                                "path": "artifacts/model",
                                "sha256": SHA_A,
                                "bytes": 10,
                            },
                        },
                        {
                            "relative_path": "model/weights.bin",
                            "file": {
                                "path": "artifacts/model/weights.bin",
                                "sha256": SHA_B,
                                "bytes": 20,
                            },
                        },
                    ],
                }
            )

    def test_variant_stage_ids_are_unique(self) -> None:
        with self.assertRaisesRegex(ValidationError, "stage IDs"):
            VariantSpec.model_validate(
                {
                    "experiment_id": "e001_strand",
                    "variant_id": "baseline",
                    "levels": {"embedding": "learned"},
                    "stage_params": [
                        {
                            "kind": "train",
                            "stage_id": "train",
                            "params": {
                                "epochs": 10,
                                "batch_size": 64,
                                "learning_rate": 0.001,
                            },
                        },
                        {
                            "kind": "train",
                            "stage_id": "train",
                            "params": {
                                "epochs": 20,
                                "batch_size": 64,
                                "learning_rate": 0.001,
                            },
                        },
                    ],
                }
            )

    def test_variant_requires_stage_parameters(self) -> None:
        with self.assertRaisesRegex(ValidationError, "at least 1 item"):
            VariantSpec.model_validate(
                {
                    "experiment_id": "e001_strand",
                    "variant_id": "baseline",
                    "levels": {},
                    "stage_params": [],
                }
            )


class YAMLLoadingTests(unittest.TestCase):
    def test_active_examples_load_through_v4_unions(self) -> None:
        examples = (
            ("download.spec.yaml", load_spec),
            ("build.spec.yaml", load_spec),
            ("download.fixture.resolved.spec.yaml", load_resolved_spec),
            ("build.fixture.resolved.spec.yaml", load_resolved_spec),
        )
        example_root = (
            Path(__file__).parents[1]
            / "mantra_provenance"
            / "examples"
            / "provenance"
        )

        for filename, loader in examples:
            with self.subTest(filename=filename):
                loader(example_root / filename)

    def test_stage_spec_loads_through_the_v4_union(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "train.spec.yaml"
            path.write_text(yaml.safe_dump(train_payload()), encoding="utf-8")

            loaded = load_spec(path)

        self.assertIsInstance(loaded, TrainSpec)

    def test_duplicate_yaml_keys_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.yaml"
            path.write_text("kind: train\nkind: evaluate\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate YAML key"):
                load_spec(path)

    def test_unhashable_yaml_keys_are_rejected_as_validation_errors(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "unhashable.yaml"
            path.write_text("? [kind, train]\n: invalid\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "mapping keys must be scalar"):
                load_spec(path)


if __name__ == "__main__":
    unittest.main()
