from __future__ import annotations

import unittest

from pydantic import ValidationError

from mantra_provenance.models_v4 import (
    CONTINUATION_STATE,
    MODEL_PARAMETERS,
    PREDICTIONS,
    EvaluateSpec,
    ResolvedBundleArtifact,
    RunSpec,
    TrainSpec,
    VariantSpec,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
GIT_COMMIT = "a" * 40
REPOSITORY = "https://github.com/example/mantra"


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
                "inputs/datasets/replogle.h5ad",
                "inputs/datasets/replogle.pointer.yaml",
            ),
        },
        "params": {
            "epochs": 10,
            "batch_size": 64,
            "learning_rate": 0.001,
        },
        "artifacts": {
            MODEL_PARAMETERS: artifact(
                "artifacts/train/model_parameters.safetensors",
                "model_parameters",
            ),
            CONTINUATION_STATE: artifact(
                "artifacts/train/continuation_state.pt",
                "continuation_state",
            ),
        },
    }


class RunPlanTests(unittest.TestCase):
    def test_run_plan_owns_shared_environment_and_reproducibility(self) -> None:
        run = RunSpec.model_validate(
            {
                "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
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
                        "spec": "stages/train.spec.yaml",
                        "sha256": SHA_A,
                        "bytes": 100,
                    }
                ],
                "estimator": {
                    "stage_id": "train",
                    "artifact_name": MODEL_PARAMETERS,
                },
            }
        )

        self.assertEqual(run.seed, 42)
        self.assertEqual(run.environment.machine_type, "n2-standard-8")
        self.assertEqual(run.estimator.artifact_name, MODEL_PARAMETERS)

    def test_estimator_must_select_model_parameters(self) -> None:
        payload = {
            "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
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
                    "spec": "stages/train.spec.yaml",
                    "sha256": SHA_A,
                    "bytes": 100,
                }
            ],
            "estimator": {
                "stage_id": "train",
                "artifact_name": CONTINUATION_STATE,
            },
        }

        with self.assertRaisesRegex(ValidationError, "model_parameters"):
            RunSpec.model_validate(payload)


class TrainingCheckpointTests(unittest.TestCase):
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
                        "inputs/datasets/replogle_test.h5ad",
                        "inputs/datasets/replogle_test.pointer.yaml",
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
                        "artifacts/evaluate/predictions.parquet",
                        "predictions",
                    )
                },
            }
        )

        self.assertIn(PREDICTIONS, spec.artifacts)

    def test_evaluation_rejects_training_checkpoint_outputs(self) -> None:
        payload = {
            "kind": "evaluate",
            "script": "src/mantra/models/strand/evaluate.py",
            "inputs": {
                "model_parameters": stored_input(
                    "inputs/models/strand.safetensors",
                    "inputs/models/strand.pointer.yaml",
                ),
                "evaluation_dataset": stored_input(
                    "inputs/datasets/replogle_test.h5ad",
                    "inputs/datasets/replogle_test.pointer.yaml",
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
                    "artifacts/evaluate/predictions.parquet",
                    "predictions",
                ),
                MODEL_PARAMETERS: artifact(
                    "artifacts/evaluate/model_parameters.safetensors",
                    "model_parameters",
                ),
            },
        }

        with self.assertRaisesRegex(ValidationError, "checkpoint artifacts"):
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


if __name__ == "__main__":
    unittest.main()
