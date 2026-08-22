"""Tests for canonical protocol-file authoring and run-plan freezing."""

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from viper.authoring import (
    RunPlanDraft,
    freeze_run_plan,
    write_experiment_spec,
    write_variant_spec,
)
from viper.protocol import (
    PARAMETERS,
    RESUME_STATE,
    ExperimentSpec,
    FactorSpec,
    MetricParams,
    MetricSpec,
    ReplicateSpec,
    RunSpec,
    TrainParams,
    TrainSpec,
    TrainVariantStageParams,
    VariantSpec,
)
from viper.serialization import parse_yaml_bytes, serialize_record

RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RUN_ROOT = f"experiments/e001_strand/runs/baseline/{RUN_ID}"
COMMIT = "a" * 40


def environment_payload() -> dict[str, object]:
    """Build the shared GCE environment used by an authored run plan."""
    return {
        "kind": "gce",
        "machine_image": {"project": "mantra", "name": "strict-v1"},
        "machine_type": "n2-standard-8",
        "compute": {"kind": "cpu"},
        "lockfile": {
            "kind": "git",
            "repository": "https://github.com/example/viper-project",
            "commit": COMMIT,
            "path": "environment.yml",
        },
    }


def reproducibility_payload() -> dict[str, object]:
    """Build the run-wide controls used by an authored run plan."""
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
            "dataloader": {
                "workers": 0,
                "prefetch_factor": None,
                "persistent_workers": False,
                "in_order": True,
            },
        },
        "numpy_randomness": {
            "generators": {"training": "PCG64"},
            "capture_legacy_global": True,
        },
    }


def training_spec() -> TrainSpec:
    """Build one valid training stage with its terminal checkpoint."""
    return TrainSpec.model_validate(
        {
            "kind": "train",
            "script": "project_code/strand/fit.py",
            "inputs": {
                "training_dataset": {
                    "kind": "stored",
                    "pointer": {
                        "kind": "git",
                        "repository": "https://github.com/example/viper-project",
                        "commit": COMMIT,
                        "path": "inputs/datasets/replogle/current.pointer.yaml",
                    },
                    "path": "inputs/datasets/replogle/dataset.h5ad",
                    "data_role": "training",
                }
            },
            "params": {"schema_version": 1, "epochs": 2},
            "artifacts": {
                PARAMETERS: {
                    "kind": "file",
                    "path": (
                        f"{RUN_ROOT}/artifacts/models/strand/parameters.safetensors"
                    ),
                    "loader": "project_code/loaders/parameters.py",
                    "data_role": "training",
                },
                RESUME_STATE: {
                    "kind": "file",
                    "path": (f"{RUN_ROOT}/artifacts/models/strand/resume_state.pt"),
                    "loader": "project_code/loaders/resume_state.py",
                    "data_role": "training",
                },
            },
        }
    )


class RunPlanAuthoringTests(unittest.TestCase):
    """Verify canonical paths and byte identities written by plan authoring."""

    def test_freeze_run_plan_writes_hash_bound_stage_and_run_files(self) -> None:
        """Write canonical files whose RunStageRef matches exact stage bytes."""
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            draft_stage = root / "drafts/train.yaml"
            draft_stage.parent.mkdir(parents=True)
            draft_stage.write_bytes(serialize_record(training_spec()))
            draft = RunPlanDraft.model_validate(
                {
                    "run_id": RUN_ID,
                    "experiment_id": "e001_strand",
                    "variant_id": "baseline",
                    "replicate_id": "replicate_01",
                    "seed": 42,
                    "source": {
                        "kind": "git",
                        "repository": "https://github.com/example/viper-project",
                        "commit": COMMIT,
                    },
                    "environment": environment_payload(),
                    "reproducibility": reproducibility_payload(),
                    "stages": [
                        {"stage_id": "train", "spec_source": "drafts/train.yaml"}
                    ],
                    "estimator": {
                        "stage_id": "train",
                        "artifact_name": PARAMETERS,
                    },
                }
            )

            frozen = freeze_run_plan(root, draft)
            stage_path, run_path = frozen.files
            stage_raw = stage_path.read_bytes()
            loaded_run = RunSpec.model_validate(parse_yaml_bytes(run_path.read_bytes()))

        self.assertEqual(
            loaded_run.stages[0].sha256,
            hashlib.sha256(stage_raw).hexdigest(),
        )
        self.assertEqual(loaded_run.stages[0].bytes, len(stage_raw))
        self.assertEqual(
            stage_path.relative_to(root).as_posix(),
            f"{RUN_ROOT}/stages/train/spec.yaml",
        )
        self.assertEqual(run_path.relative_to(root).as_posix(), f"{RUN_ROOT}/spec.yaml")

    def test_experiment_and_variant_writers_use_identity_paths(self) -> None:
        """Write experiment and variant records under one experiment identity."""
        metric = MetricSpec(
            metric_id="training_loss",
            kind="training",
            implementation="project_code/metrics/training_loss.py",
            params=MetricParams(),
        )
        experiment = ExperimentSpec(
            experiment_id="e001_strand",
            factors=(FactorSpec(factor_id="rank", levels=("full", "low")),),
            variant_ids=("baseline",),
            replicates=(ReplicateSpec(replicate_id="replicate_01", seed=42),),
            metrics=(metric,),
        )
        variant = VariantSpec(
            experiment_id="e001_strand",
            variant_id="baseline",
            levels={"rank": "full"},
            stage_params=(
                TrainVariantStageParams(
                    stage_id="train",
                    params=TrainParams.model_validate({"epochs": 2}),
                ),
            ),
        )

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            experiment_path = write_experiment_spec(root, experiment)
            variant_path = write_variant_spec(root, variant)

            self.assertTrue(yaml.safe_load(experiment_path.read_text()))
            self.assertTrue(yaml.safe_load(variant_path.read_text()))
            self.assertEqual(
                experiment_path.relative_to(root).as_posix(),
                "experiments/e001_strand/spec.yaml",
            )
            self.assertEqual(
                variant_path.relative_to(root).as_posix(),
                "experiments/e001_strand/variants/baseline.spec.yaml",
            )
