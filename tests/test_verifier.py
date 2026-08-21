from __future__ import annotations

import hashlib
import unittest
from datetime import UTC, datetime
from typing import Any

import yaml
from pydantic import TypeAdapter

from mantra_provenance.models_v4 import (
    CONTINUATION_STATE,
    MODEL_PARAMETERS,
    ArtifactPointerRef,
    BuildSpec,
    GitFileRef,
    GitSource,
    HuggingFaceFileRef,
    ResolvedArtifactPointerRef,
    ResolvedBuildSpec,
    ResolvedFileRef,
    ResolvedFutureInputRef,
    ResolvedGitFileRef,
    ResolvedRun,
    ResolvedRunSpecRef,
    ResolvedStageRef,
    ResolvedTrainSpec,
    RunAttempt,
    RunSpec,
    RunStageRef,
    SnapshotFileRef,
    StageResultSnapshotRef,
    TrainSpec,
)
from mantra_provenance.verifier import (
    VerificationError,
    read_resolved_file,
    read_snapshot_file,
    verify_future_inputs,
    verify_resolved_run_file,
    verify_resolved_stages,
    verify_stage_plan,
)

GIT_COMMIT = "a" * 40
PLAN_COMMIT = "b" * 40
SNAPSHOT_COMMIT = "c" * 40
REPOSITORY = "https://github.com/example/mantra"
HF_REPOSITORY = "example/mantra-runs"
YAML_ADAPTER = TypeAdapter(Any)


def yaml_bytes(value: object) -> bytes:
    data = YAML_ADAPTER.dump_python(value, mode="json")
    return yaml.safe_dump(data, sort_keys=True).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_file(path: str, *, commit: str = GIT_COMMIT) -> GitFileRef:
    return GitFileRef(
        repository=REPOSITORY,
        commit=commit,
        path=path,
    )


def artifact_pointer(path: str) -> ArtifactPointerRef:
    return ArtifactPointerRef(
        repository=REPOSITORY,
        commit=GIT_COMMIT,
        path=path,
    )


def environment() -> dict:
    return {
        "kind": "gce",
        "machine_image": {
            "project": "mantra-project",
            "name": "mantra-image",
        },
        "machine_type": "n2-standard-8",
        "compute": {"kind": "cpu"},
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


def execution_context(seed: int = 42) -> dict:
    controls = reproducibility()
    return {
        "host": {
            "provider": "gce",
            "machine_type": "n2-standard-8",
            "zone": "us-central1-a",
            "guest_os_name": "debian",
            "guest_os_version": "12",
            "kernel_release": "6.1",
        },
        "cpu": {
            "architecture": "x86_64",
            "model": "Intel Cascade Lake",
            "instruction_features": ["avx2"],
        },
        "backend": {"kind": "cpu", "device": "cpu"},
        "numerical_runtime": {
            "python_version": "3.12.4",
            "pytorch_version": "2.7.1",
            "numpy_version": "2.2.6",
            "blas": {"implementation": "openblas", "version": "0.3.29"},
            "lapack": {"implementation": "openblas", "version": "0.3.29"},
            "native_thread_pools": [
                {
                    "implementation": "openblas",
                    "version": "0.3.29",
                    "threads": 1,
                }
            ],
        },
        "randomness": {
            "python_seed": seed,
            "numpy_seed": seed,
            "torch_seed": seed,
            "dataloader_seed": seed,
        },
        "determinism": controls["determinism"],
        "precision": controls["precision"],
        "parallelism": controls["parallelism"],
    }


def resolved_git(raw: bytes, path: str) -> ResolvedGitFileRef:
    return ResolvedGitFileRef(
        sha256=sha256(raw),
        bytes=len(raw),
        stored_at=git_file(path),
    )


def resolved_pointer(path: str) -> ResolvedArtifactPointerRef:
    raw = b"pointer"
    return ResolvedArtifactPointerRef(
        sha256=sha256(raw),
        bytes=len(raw),
        stored_at=artifact_pointer(path),
    )


def snapshot() -> StageResultSnapshotRef:
    return StageResultSnapshotRef(
        repository=HF_REPOSITORY,
        commit=SNAPSHOT_COMMIT,
        repo_type="dataset",
    )


def run_spec(stage_specs: list[tuple[str, object]]) -> tuple[RunSpec, dict[str, bytes]]:
    documents: dict[str, bytes] = {}
    stage_refs = []

    for stage_id, spec in stage_specs:
        path = f"stages/{stage_id}.spec.yaml"
        raw = yaml_bytes(spec)
        documents[path] = raw
        stage_refs.append(
            RunStageRef(
                stage_id=stage_id,
                spec=path,
                sha256=sha256(raw),
                bytes=len(raw),
            )
        )

    run = RunSpec(
        run_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        experiment_id="e001_strand",
        variant_id="baseline",
        replicate_id="replicate_01",
        seed=42,
        source=GitSource(repository=REPOSITORY, commit=GIT_COMMIT),
        environment=environment(),
        reproducibility=reproducibility(),
        stages=tuple(stage_refs),
        estimator={
            "stage_id": "train",
            "artifact_name": MODEL_PARAMETERS,
        },
    )
    return run, documents


def train_spec(*, future_prior: bool = False) -> TrainSpec:
    inputs: dict[str, dict] = {}
    if future_prior:
        inputs["prior"] = {
            "kind": "future",
            "producer_stage_id": "build",
            "producer_artifact": "prior",
        }
    else:
        inputs["training_dataset"] = {
            "kind": "stored",
            "pointer": artifact_pointer("inputs/datasets/replogle.pointer.yaml"),
            "path": "inputs/datasets/replogle.h5ad",
        }

    return TrainSpec(
        script="src/mantra/models/strand/train.py",
        inputs=inputs,
        params={"epochs": 10, "batch_size": 64, "learning_rate": 0.001},
        artifacts={
            MODEL_PARAMETERS: {
                "kind": "file",
                "path": "artifacts/train/model_parameters.safetensors",
                "loader": "model_parameters",
            },
            CONTINUATION_STATE: {
                "kind": "file",
                "path": "artifacts/train/continuation_state.pt",
                "loader": "continuation_state",
            },
        },
    )


def build_spec() -> BuildSpec:
    return BuildSpec(
        script="src/mantra/priors/depmap/build.py",
        inputs={
            "depmap": {
                "kind": "stored",
                "pointer": artifact_pointer("inputs/priors/depmap.pointer.yaml"),
                "path": "inputs/priors/depmap.parquet",
            }
        },
        params={},
        artifacts={
            "prior": {
                "kind": "file",
                "path": "artifacts/build/prior.pt",
                "loader": "prior",
            }
        },
    )


def resolved_environment(lock_raw: bytes) -> dict:
    return {
        "kind": "gce",
        "machine_image": {
            "project": "mantra-project",
            "name": "mantra-image",
            "id": "123456",
        },
        "machine_type": "n2-standard-8",
        "compute": {"kind": "cpu"},
        "lockfile": resolved_git(lock_raw, "uv.lock"),
    }


class FileVerificationTests(unittest.TestCase):
    def test_resolved_file_requires_matching_bytes(self) -> None:
        raw = b"exact bytes"
        reference = ResolvedFileRef(
            sha256=sha256(raw),
            bytes=len(raw),
            stored_at=git_file("records/value.bin"),
        )

        self.assertEqual(read_resolved_file(reference, fetcher=lambda _: raw), raw)

        with self.assertRaisesRegex(VerificationError, "byte-count mismatch"):
            read_resolved_file(
                reference.model_copy(update={"bytes": len(raw) + 1}),
                fetcher=lambda _: raw,
            )

    def test_snapshot_file_uses_snapshot_commit_and_exact_identity(self) -> None:
        raw = b"snapshot bytes"
        reference = {
            "path": "artifacts/train/model_parameters.safetensors",
            "sha256": sha256(raw),
            "bytes": len(raw),
        }
        seen: list[HuggingFaceFileRef] = []

        def fetcher(location: object) -> bytes:
            self.assertIsInstance(location, HuggingFaceFileRef)
            seen.append(location)
            return raw

        content = read_snapshot_file(
            snapshot(),
            SnapshotFileRef.model_validate(reference),
            fetcher=fetcher,
        )

        self.assertEqual(content, raw)
        self.assertEqual(seen[0].commit, SNAPSHOT_COMMIT)


class RunAndStageVerificationTests(unittest.TestCase):
    def test_resolved_run_spec_is_loaded_from_its_reference(self) -> None:
        spec = train_spec()
        run, _ = run_spec([("train", spec)])
        raw = yaml_bytes(run)
        run_reference = ResolvedRunSpecRef(
            sha256=sha256(raw),
            bytes=len(raw),
            stored_at=git_file("experiments/e001_strand/runs/run/spec.yaml"),
        )
        record = ResolvedRun.model_construct(spec=run_reference)

        self.assertEqual(
            verify_resolved_run_file(record, fetcher=lambda _: raw),
            run,
        )

    def test_stage_plan_loads_named_future_artifact(self) -> None:
        build = build_spec()
        train = train_spec(future_prior=True)
        run, documents = run_spec([("build", build), ("train", train)])
        run_reference = ResolvedRunSpecRef(
            sha256="f" * 64,
            bytes=1,
            stored_at=git_file("experiments/e001_strand/runs/run/spec.yaml"),
        )

        loaded = verify_stage_plan(
            run,
            run_reference,
            fetcher=lambda location: documents[location.path],
        )

        self.assertEqual(set(loaded), {"build", "train"})
        self.assertIn("prior", loaded["build"].artifacts)

    def test_resolved_stage_checks_run_controls_and_snapshot_files(self) -> None:
        spec = train_spec()
        run, _ = run_spec([("train", spec)])
        source_raw = b"print('train')\n"
        lock_raw = b"lockfile"
        model_raw = b"model parameters"
        continuation_raw = b"optimizer rng sampler"

        resolved = ResolvedTrainSpec(
            spec=spec,
            source=resolved_git(source_raw, str(spec.script)),
            environment=resolved_environment(lock_raw),
            execution_context=execution_context(),
            command=("python", str(spec.script), "stages/train.spec.yaml"),
            inputs={
                "training_dataset": {
                    "kind": "stored",
                    "pointer": resolved_pointer(
                        "inputs/datasets/replogle.pointer.yaml"
                    ),
                }
            },
            artifacts={
                MODEL_PARAMETERS: {
                    "kind": "file",
                    "file": {
                        "path": "artifacts/train/model_parameters.safetensors",
                        "sha256": sha256(model_raw),
                        "bytes": len(model_raw),
                    },
                },
                CONTINUATION_STATE: {
                    "kind": "file",
                    "file": {
                        "path": "artifacts/train/continuation_state.pt",
                        "sha256": sha256(continuation_raw),
                        "bytes": len(continuation_raw),
                    },
                },
            },
            completed_at=datetime(2026, 8, 21, 12, 30, tzinfo=UTC),
        )
        resolved_raw = yaml_bytes(resolved)
        stage = ResolvedStageRef(
            stage_id="train",
            snapshot=snapshot(),
            resolved_spec={
                "path": "stages/train.spec.resolved.yaml",
                "sha256": sha256(resolved_raw),
                "bytes": len(resolved_raw),
            },
        )
        attempt = RunAttempt(
            attempt_id=1,
            status="succeeded",
            started_at=datetime(2026, 8, 21, 12, tzinfo=UTC),
            completed_at=datetime(2026, 8, 21, 13, tzinfo=UTC),
            resolved_stages=(stage,),
            measurement_files=(),
            log_files=(),
            failure_reason=None,
        )
        run_raw = yaml_bytes(run)
        record = ResolvedRun(
            spec=ResolvedRunSpecRef(
                sha256=sha256(run_raw),
                bytes=len(run_raw),
                stored_at=git_file("experiments/e001_strand/runs/run/spec.yaml"),
            ),
            status="succeeded",
            attempts=(attempt,),
            successful_attempt_id=1,
            completed_at=datetime(2026, 8, 21, 13, 1, tzinfo=UTC),
        )
        documents = {
            "stages/train.spec.resolved.yaml": resolved_raw,
            str(spec.script): source_raw,
            "uv.lock": lock_raw,
            "artifacts/train/model_parameters.safetensors": model_raw,
            "artifacts/train/continuation_state.pt": continuation_raw,
        }

        verified = verify_resolved_stages(
            record,
            run,
            {"train": spec},
            fetcher=lambda location: documents[location.path],
        )

        self.assertEqual(verified["train"], resolved)


class FutureInputVerificationTests(unittest.TestCase):
    def test_future_input_selects_named_artifact_from_recorded_producer(self) -> None:
        build = build_spec()
        train = train_spec(future_prior=True)
        run, _ = run_spec([("build", build), ("train", train)])
        lock_raw = b"lockfile"
        prior_raw = b"prior tensor"
        source_raw = b"source"

        producer_stage = ResolvedStageRef(
            stage_id="build",
            snapshot=snapshot(),
            resolved_spec={
                "path": "stages/build.spec.resolved.yaml",
                "sha256": "e" * 64,
                "bytes": 100,
            },
        )
        consumer_stage = ResolvedStageRef(
            stage_id="train",
            snapshot=snapshot(),
            resolved_spec={
                "path": "stages/train.spec.resolved.yaml",
                "sha256": "f" * 64,
                "bytes": 100,
            },
        )

        resolved_build = ResolvedBuildSpec(
            spec=build,
            source=resolved_git(source_raw, str(build.script)),
            environment=resolved_environment(lock_raw),
            execution_context=execution_context(),
            command=("python", str(build.script), "stages/build.spec.yaml"),
            inputs={
                "depmap": {
                    "kind": "stored",
                    "pointer": resolved_pointer("inputs/priors/depmap.pointer.yaml"),
                }
            },
            artifacts={
                "prior": {
                    "kind": "file",
                    "file": {
                        "path": "artifacts/build/prior.pt",
                        "sha256": sha256(prior_raw),
                        "bytes": len(prior_raw),
                    },
                }
            },
            completed_at=datetime(2026, 8, 21, 12, 20, tzinfo=UTC),
        )
        resolved_train = ResolvedTrainSpec(
            spec=train,
            source=resolved_git(source_raw, str(train.script)),
            environment=resolved_environment(lock_raw),
            execution_context=execution_context(),
            command=("python", str(train.script), "stages/train.spec.yaml"),
            inputs={
                "prior": ResolvedFutureInputRef(producer=producer_stage),
            },
            artifacts={
                MODEL_PARAMETERS: {
                    "kind": "file",
                    "file": {
                        "path": "artifacts/train/model_parameters.safetensors",
                        "sha256": "1" * 64,
                        "bytes": 1,
                    },
                },
                CONTINUATION_STATE: {
                    "kind": "file",
                    "file": {
                        "path": "artifacts/train/continuation_state.pt",
                        "sha256": "2" * 64,
                        "bytes": 1,
                    },
                },
            },
            completed_at=datetime(2026, 8, 21, 12, 40, tzinfo=UTC),
        )
        attempt = RunAttempt(
            attempt_id=1,
            status="succeeded",
            started_at=datetime(2026, 8, 21, 12, tzinfo=UTC),
            completed_at=datetime(2026, 8, 21, 13, tzinfo=UTC),
            resolved_stages=(producer_stage, consumer_stage),
            measurement_files=(),
            log_files=(),
            failure_reason=None,
        )
        run_raw = yaml_bytes(run)
        record = ResolvedRun(
            spec=ResolvedRunSpecRef(
                sha256=sha256(run_raw),
                bytes=len(run_raw),
                stored_at=git_file("experiments/e001_strand/runs/run/spec.yaml"),
            ),
            status="succeeded",
            attempts=(attempt,),
            successful_attempt_id=1,
            completed_at=datetime(2026, 8, 21, 13, 1, tzinfo=UTC),
        )

        verified = verify_future_inputs(
            record,
            run,
            {"build": resolved_build, "train": resolved_train},
            fetcher=lambda location: {"artifacts/build/prior.pt": prior_raw}[
                location.path
            ],
        )

        self.assertEqual(
            verified["train"]["prior"].files[0].content,
            prior_raw,
        )

        wrong_producer = producer_stage.model_copy(update={"stage_id": "other"})
        mismatched_train = resolved_train.model_copy(
            update={
                "inputs": {
                    "prior": ResolvedFutureInputRef(producer=wrong_producer),
                }
            }
        )
        with self.assertRaisesRegex(VerificationError, "completed producer"):
            verify_future_inputs(
                record,
                run,
                {"build": resolved_build, "train": mismatched_train},
                fetcher=lambda location: prior_raw,
            )


if __name__ == "__main__":
    unittest.main()
