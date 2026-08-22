"""Tests for complete local-plan preflight and same-run input paths."""

import hashlib
from pathlib import Path

from viper.materialization import future_input_paths
from viper.preflight import preflight_local_plan
from viper.protocol import (
    PARAMETERS,
    RESUME_STATE,
    BuildParams,
    BuildSpec,
    DownloadSpec,
    FutureInputRef,
    RemoteFileRef,
    RunSpec,
    RunStageRef,
    SingleFileArtifactSpec,
    TrainParams,
    TrainSpec,
)
from viper.serialization import serialize_document


def _artifact(path: str) -> SingleFileArtifactSpec:
    """Build one training-role file artifact for local preflight tests."""
    return SingleFileArtifactSpec(
        path=path,
        loader="project/loaders/bytes_file.py",
        data_role="training",
    )


def test_preflight_reports_all_plan_failures(tmp_path: Path) -> None:
    """Return every independent plan, source, environment, and stage failure."""
    run_root = "experiments/example/runs/baseline/01JABCDEFGHJKMNPQRSTVWXYZ0"
    stage = TrainSpec(
        script="project/build.py",
        inputs={
            "dataset": FutureInputRef(
                producer_stage_id="download",
                producer_artifact="dataset",
            )
        },
        artifacts={
            PARAMETERS: _artifact(f"{run_root}/artifacts/models/main/parameters.bin"),
            RESUME_STATE: _artifact(
                f"{run_root}/artifacts/models/main/resume_state.bin"
            ),
        },
        params=TrainParams(),
    )
    stage_path = f"{run_root}/stages/train/spec.yaml"
    raw = serialize_document(stage)
    target = tmp_path / stage_path
    target.parent.mkdir(parents=True)
    target.write_bytes(raw)
    run = RunSpec.model_validate(
        {
            "run_id": "01JABCDEFGHJKMNPQRSTVWXYZ0",
            "experiment_id": "example",
            "variant_id": "baseline",
            "replicate_id": "replicate_01",
            "seed": 42,
            "source": {
                "kind": "git",
                "repository": "https://github.com/example/project",
                "commit": "a" * 40,
            },
            "environment": {
                "kind": "gce",
                "machine_image": {"project": "example", "name": "image"},
                "machine_type": "n2-standard-8",
                "compute": {"kind": "cpu"},
                "lockfile": {
                    "kind": "git",
                    "repository": "https://github.com/example/project",
                    "commit": "a" * 40,
                    "path": "environment.yml",
                },
            },
            "reproducibility": {
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
            },
            "stages": [
                RunStageRef(
                    stage_id="train",
                    spec=stage_path,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    bytes=len(raw),
                )
            ],
            "estimator": {
                "stage_id": "train",
                "artifact_name": PARAMETERS,
            },
        }
    )
    run_path = tmp_path / run_root / "spec.yaml"
    run_path.write_bytes(serialize_document(run))

    report = preflight_local_plan(tmp_path, run_path)

    failures = {check.code for check in report.checks if check.status == "failure"}
    assert failures == {
        "artifact.loader",
        "environment.local",
        "input.future",
        "metric.implementation",
        "plan.git_identity",
        "plan.records",
        "plan.relationships",
        "source.repository",
        "stage.script",
    }
    assert not report.ready


def test_future_input_uses_canonical_producer_path(tmp_path: Path) -> None:
    """Resolve one consumer input to the materialized producer artifact."""
    producer = DownloadSpec(
        script="project/download.py",
        inputs={
            "remote": RemoteFileRef.model_validate(
                {
                    "url": "https://example.com/data",
                    "version": "v1",
                }
            )
        },
        artifacts={
            "dataset": _artifact(
                "experiments/example/runs/baseline/01JABCDEFGHJKMNPQRSTVWXYZ0/"
                "artifacts/datasets/main/data.bin"
            )
        },
    )
    consumer = BuildSpec(
        script="project/build.py",
        inputs={
            "dataset": FutureInputRef(
                producer_stage_id="download",
                producer_artifact="dataset",
            )
        },
        artifacts={
            "prior": _artifact(
                "experiments/example/runs/baseline/01JABCDEFGHJKMNPQRSTVWXYZ0/"
                "artifacts/priors/main/prior.bin"
            )
        },
        params=BuildParams(),
    )
    path = tmp_path / producer.artifacts["dataset"].path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"dataset")

    inputs = future_input_paths(tmp_path, consumer, {"download": producer})

    assert inputs["dataset"] == path
