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
    ArtifactPointer,
    ArtifactPointerRef,
    BaseSpec,
    BuildSpec,
    DownloadSpec,
    EvaluateSpec,
    ExperimentSpec,
    GitFileRef,
    GitSource,
    HuggingFaceFileRef,
    ResolvedArtifactPointerRef,
    ResolvedBuildSpec,
    ResolvedDownloadSpec,
    ResolvedEvaluateSpec,
    ResolvedFileRef,
    ResolvedFutureInputRef,
    ResolvedGitFileRef,
    ResolvedRun,
    ResolvedRunRef,
    ResolvedRunSpecRef,
    ResolvedStageRef,
    ResolvedTrainSpec,
    RunAttempt,
    RunSpec,
    RunStageRef,
    StageResultSnapshotRef,
    StorageModel,
    TrainSpec,
    VariantSpec,
)
from mantra_provenance.verifier import VerificationError, verify_run_result

SOURCE_REPOSITORY = "https://github.com/example/mantra"
ARTIFACT_REPOSITORY = "example/mantra-runs"
PRODUCER_SOURCE_COMMIT = "1" * 40
PRODUCER_PLAN_COMMIT = "2" * 40
PRODUCER_RESULT_COMMIT = "3" * 40
MAIN_SOURCE_COMMIT = "4" * 40
MAIN_PLAN_COMMIT = "5" * 40
MAIN_FILES_COMMIT = "6" * 40
YAML_ADAPTER = TypeAdapter(Any)


def yaml_bytes(value: object) -> bytes:
    data = YAML_ADAPTER.dump_python(value, mode="json")
    return yaml.safe_dump(data, sort_keys=True).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class DocumentStore:
    def __init__(self) -> None:
        self.documents: dict[tuple[str, str, str, str, str], bytes] = {}

    @staticmethod
    def key(location: StorageModel) -> tuple[str, str, str, str, str]:
        repo_type = getattr(location, "repo_type", "")
        return (
            location.kind,
            str(location.repository),
            location.commit,
            str(location.path),
            repo_type,
        )

    def put(self, location: StorageModel, raw: bytes) -> None:
        self.documents[self.key(location)] = raw

    def fetch(self, location: StorageModel) -> bytes:
        return self.documents[self.key(location)]


def git_file(commit: str, path: str) -> GitFileRef:
    return GitFileRef(
        repository=SOURCE_REPOSITORY,
        commit=commit,
        path=path,
    )


def hf_file(commit: str, path: str) -> HuggingFaceFileRef:
    return HuggingFaceFileRef(
        repository=ARTIFACT_REPOSITORY,
        commit=commit,
        path=path,
        repo_type="dataset",
    )


def snapshot(commit: str) -> StageResultSnapshotRef:
    return StageResultSnapshotRef(
        repository=ARTIFACT_REPOSITORY,
        commit=commit,
        repo_type="dataset",
    )


def environment(source_commit: str) -> dict[str, object]:
    return {
        "kind": "gce",
        "machine_image": {"project": "mantra-project", "name": "mantra-image"},
        "machine_type": "n2-standard-8",
        "compute": {"kind": "cpu"},
        "lockfile": git_file(source_commit, "environment.yml"),
    }


def reproducibility() -> dict[str, object]:
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


def execution_context() -> dict[str, object]:
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
            "python_version": "3.14.0",
            "pytorch_version": "2.8.0",
            "numpy_version": "2.3.0",
            "blas": {"implementation": "openblas", "version": "0.3.30"},
            "lapack": {"implementation": "openblas", "version": "0.3.30"},
            "native_thread_pools": [
                {
                    "implementation": "openblas",
                    "version": "0.3.30",
                    "threads": 1,
                }
            ],
        },
        "randomness": {
            "python_seed": 42,
            "numpy_seed": 42,
            "torch_seed": 42,
            "dataloader_seed": 42,
        },
        "determinism": controls["determinism"],
        "precision": controls["precision"],
        "parallelism": controls["parallelism"],
    }


def add_source_file(
    store: DocumentStore,
    source_commit: str,
    path: str,
    raw: bytes,
) -> ResolvedGitFileRef:
    location = git_file(source_commit, path)
    store.put(location, raw)
    return ResolvedGitFileRef(
        sha256=sha256(raw),
        bytes=len(raw),
        stored_at=location,
    )


def resolved_environment(
    store: DocumentStore,
    source_commit: str,
) -> dict[str, object]:
    lock_raw = b"name: mantra\n"
    lockfile = add_source_file(store, source_commit, "environment.yml", lock_raw)
    return {
        "kind": "gce",
        "machine_image": {
            "project": "mantra-project",
            "name": "mantra-image",
            "id": "123456789",
        },
        "machine_type": "n2-standard-8",
        "compute": {"kind": "cpu"},
        "lockfile": lockfile,
    }


def add_loader(
    store: DocumentStore,
    source_commit: str,
    loader_id: str,
    *,
    bundle: bool = False,
) -> None:
    if bundle:
        raw = (
            b"def load(path):\n"
            b"    return tuple(p.read_bytes() for p in sorted(path.rglob('*')) "
            b"if p.is_file())\n"
        )
    else:
        raw = b"def load(path):\n    return path.read_bytes()\n"
    store.put(
        git_file(
            source_commit,
            f"src/mantra/artifact_loaders/{loader_id}.py",
        ),
        raw,
    )


def add_plan_records(
    store: DocumentStore,
    *,
    run: RunSpec,
    stage_specs: list[tuple[str, BaseSpec]],
    experiment: ExperimentSpec,
    variant: VariantSpec,
    plan_commit: str,
) -> ResolvedRunSpecRef:
    source_commit = run.source.commit
    store.put(
        git_file(source_commit, f"experiments/{run.experiment_id}/spec.yaml"),
        yaml_bytes(experiment),
    )
    store.put(
        git_file(
            source_commit,
            f"experiments/{run.experiment_id}/variants/{run.variant_id}.spec.yaml",
        ),
        yaml_bytes(variant),
    )

    for run_stage, (_, spec) in zip(run.stages, stage_specs, strict=True):
        store.put(git_file(plan_commit, str(run_stage.spec)), yaml_bytes(spec))

    run_path = (
        f"experiments/{run.experiment_id}/runs/{run.variant_id}/"
        f"{run.run_id}/spec.yaml"
    )
    run_raw = yaml_bytes(run)
    run_location = git_file(plan_commit, run_path)
    store.put(run_location, run_raw)
    return ResolvedRunSpecRef(
        sha256=sha256(run_raw),
        bytes=len(run_raw),
        stored_at=run_location,
    )


def make_run(
    *,
    experiment_id: str,
    run_id: str,
    source_commit: str,
    plan_commit: str,
    stage_specs: list[tuple[str, BaseSpec]],
    estimator_stage_id: str,
) -> RunSpec:
    stage_refs: list[RunStageRef] = []
    for stage_id, spec in stage_specs:
        raw = yaml_bytes(spec)
        path = (
            f"experiments/{experiment_id}/runs/baseline/{run_id}/"
            f"stages/{stage_id}/spec.yaml"
        )
        stage_refs.append(
            RunStageRef(
                stage_id=stage_id,
                spec=path,
                sha256=sha256(raw),
                bytes=len(raw),
            )
        )

    return RunSpec(
        run_id=run_id,
        experiment_id=experiment_id,
        variant_id="baseline",
        replicate_id="replicate_01",
        seed=42,
        source=GitSource(
            repository=SOURCE_REPOSITORY,
            commit=source_commit,
        ),
        environment=environment(source_commit),
        reproducibility=reproducibility(),
        stages=tuple(stage_refs),
        estimator={
            "stage_id": estimator_stage_id,
            "artifact_name": MODEL_PARAMETERS,
        },
    )


def add_single_artifact(
    store: DocumentStore,
    snapshot_commit: str,
    path: str,
    raw: bytes,
) -> dict[str, object]:
    store.put(hf_file(snapshot_commit, path), raw)
    return {
        "kind": "file",
        "file": {"path": path, "sha256": sha256(raw), "bytes": len(raw)},
    }


def add_bundle_artifact(
    store: DocumentStore,
    snapshot_commit: str,
    root: str,
    members: dict[str, bytes],
) -> dict[str, object]:
    resolved_members = []
    for relative_path in sorted(members):
        raw = members[relative_path]
        path = f"{root}/{relative_path}"
        store.put(hf_file(snapshot_commit, path), raw)
        resolved_members.append(
            {
                "relative_path": relative_path,
                "file": {"path": path, "sha256": sha256(raw), "bytes": len(raw)},
            }
        )
    return {"kind": "bundle", "members": resolved_members}


def publish_resolved_stage(
    store: DocumentStore,
    *,
    run_root_path: str,
    stage_id: str,
    snapshot_commit: str,
    resolved_spec: object,
) -> ResolvedStageRef:
    path = f"{run_root_path}/stages/{stage_id}/resolved.yaml"
    raw = yaml_bytes(resolved_spec)
    store.put(hf_file(snapshot_commit, path), raw)
    return ResolvedStageRef(
        stage_id=stage_id,
        snapshot=snapshot(snapshot_commit),
        resolved_spec={"path": path, "sha256": sha256(raw), "bytes": len(raw)},
    )


def resolved_pointer(
    store: DocumentStore,
    source_commit: str,
    path: str,
    pointer: ArtifactPointer,
) -> ResolvedArtifactPointerRef:
    raw = yaml_bytes(pointer)
    location = ArtifactPointerRef(
        repository=SOURCE_REPOSITORY,
        commit=source_commit,
        path=path,
    )
    store.put(location, raw)
    return ResolvedArtifactPointerRef(
        sha256=sha256(raw),
        bytes=len(raw),
        stored_at=location,
    )


def publish_producer_run(store: DocumentStore) -> tuple[ResolvedRunRef, dict[str, Any]]:
    run_root = "experiments/source_data/runs/baseline/01ARZ3NDEKTSV4RRFFQ69G5FAA"
    download = DownloadSpec(
        script="src/mantra/datasets/toy/download.py",
        inputs={
            "archive": {
                "kind": "remote",
                "url": "https://example.com/toy-v1.tar.gz",
                "version": "v1",
            }
        },
        artifacts={
            "dataset": {
                "kind": "file",
                "path": f"{run_root}/artifacts/datasets/toy/dataset.bin",
                "loader": "bytes_file",
            },
            "split": {
                "kind": "file",
                "path": f"{run_root}/artifacts/datasets/toy/split.json",
                "loader": "bytes_file",
            },
        },
    )
    train = TrainSpec(
        script="src/mantra/models/toy/train.py",
        inputs={
            "training_dataset": {
                "kind": "future",
                "producer_stage_id": "download",
                "producer_artifact": "dataset",
            }
        },
        params={"epochs": 1, "batch_size": 2, "learning_rate": 0.01},
        artifacts={
            MODEL_PARAMETERS: {
                "kind": "file",
                "path": f"{run_root}/artifacts/models/toy/model_parameters.bin",
                "loader": "bytes_file",
            },
            CONTINUATION_STATE: {
                "kind": "file",
                "path": f"{run_root}/artifacts/models/toy/continuation_state.bin",
                "loader": "bytes_file",
            },
        },
    )
    stage_specs: list[tuple[str, BaseSpec]] = [
        ("download", download),
        ("train", train),
    ]
    run = make_run(
        experiment_id="source_data",
        run_id="01ARZ3NDEKTSV4RRFFQ69G5FAA",
        source_commit=PRODUCER_SOURCE_COMMIT,
        plan_commit=PRODUCER_PLAN_COMMIT,
        stage_specs=stage_specs,
        estimator_stage_id="train",
    )
    experiment = ExperimentSpec(
        experiment_id="source_data",
        factors=(),
        variant_ids=("baseline",),
        replicates=({"replicate_id": "replicate_01", "seed": 42},),
        metric_ids=(),
    )
    variant = VariantSpec(
        experiment_id="source_data",
        variant_id="baseline",
        levels={},
        stage_params=(
            {"kind": "train", "stage_id": "train", "params": train.params},
        ),
    )
    run_reference = add_plan_records(
        store,
        run=run,
        stage_specs=stage_specs,
        experiment=experiment,
        variant=variant,
        plan_commit=PRODUCER_PLAN_COMMIT,
    )

    add_loader(store, PRODUCER_SOURCE_COMMIT, "bytes_file")
    resolved_env = resolved_environment(store, PRODUCER_SOURCE_COMMIT)
    download_source = add_source_file(
        store,
        PRODUCER_SOURCE_COMMIT,
        str(download.script),
        b"# download\n",
    )
    train_source = add_source_file(
        store,
        PRODUCER_SOURCE_COMMIT,
        str(train.script),
        b"# train\n",
    )

    download_commit = "7" * 40
    dataset_raw = b"fixed dataset bytes"
    split_raw = b'{"test":[0,1]}\n'
    resolved_download = ResolvedDownloadSpec(
        spec=download,
        source=download_source,
        environment=resolved_env,
        execution_context=execution_context(),
        command=("python", str(download.script), str(run.stages[0].spec)),
        inputs=download.inputs,
        artifacts={
            "dataset": add_single_artifact(
                store,
                download_commit,
                str(download.artifacts["dataset"].path),
                dataset_raw,
            ),
            "split": add_single_artifact(
                store,
                download_commit,
                str(download.artifacts["split"].path),
                split_raw,
            ),
        },
        retrieved_at=datetime(2026, 8, 20, 20, 5, tzinfo=UTC),
        completed_at=datetime(2026, 8, 20, 20, 10, tzinfo=UTC),
    )
    download_stage = publish_resolved_stage(
        store,
        run_root_path=run_root,
        stage_id="download",
        snapshot_commit=download_commit,
        resolved_spec=resolved_download,
    )

    train_commit = "8" * 40
    resolved_train = ResolvedTrainSpec(
        spec=train,
        source=train_source,
        environment=resolved_env,
        execution_context=execution_context(),
        command=("python", str(train.script), str(run.stages[1].spec)),
        inputs={
            "training_dataset": ResolvedFutureInputRef(producer=download_stage),
        },
        artifacts={
            MODEL_PARAMETERS: add_single_artifact(
                store,
                train_commit,
                str(train.artifacts[MODEL_PARAMETERS].path),
                b"producer model",
            ),
            CONTINUATION_STATE: add_single_artifact(
                store,
                train_commit,
                str(train.artifacts[CONTINUATION_STATE].path),
                b"producer continuation",
            ),
        },
        completed_at=datetime(2026, 8, 20, 20, 30, tzinfo=UTC),
    )
    train_stage = publish_resolved_stage(
        store,
        run_root_path=run_root,
        stage_id="train",
        snapshot_commit=train_commit,
        resolved_spec=resolved_train,
    )
    attempt = RunAttempt(
        attempt_id=1,
        status="succeeded",
        started_at=datetime(2026, 8, 20, 20, tzinfo=UTC),
        completed_at=datetime(2026, 8, 20, 20, 35, tzinfo=UTC),
        resolved_stages=(download_stage, train_stage),
        measurement_files=(),
        log_files=(),
        failure_reason=None,
    )
    resolved_run = ResolvedRun(
        spec=run_reference,
        status="succeeded",
        attempts=(attempt,),
        successful_attempt_id=1,
        completed_at=datetime(2026, 8, 20, 20, 36, tzinfo=UTC),
    )
    resolved_run_raw = yaml_bytes(resolved_run)
    resolved_run_location = hf_file(
        PRODUCER_RESULT_COMMIT,
        f"{run_root}/resolved.yaml",
    )
    store.put(resolved_run_location, resolved_run_raw)
    reference = ResolvedRunRef(
        sha256=sha256(resolved_run_raw),
        bytes=len(resolved_run_raw),
        stored_at=resolved_run_location,
    )
    return reference, {
        "dataset": dataset_raw,
        "dataset_ref": download_stage,
        "run": resolved_run,
    }


def build_complete_fixture() -> tuple[
    ResolvedRun,
    DocumentStore,
    HuggingFaceFileRef,
]:
    store = DocumentStore()
    producer_run_ref, _ = publish_producer_run(store)

    dataset_pointer = ArtifactPointer(
        run=producer_run_ref,
        artifact={"stage_id": "download", "artifact_name": "dataset"},
    )
    split_pointer = ArtifactPointer(
        run=producer_run_ref,
        artifact={"stage_id": "download", "artifact_name": "split"},
    )
    dataset_pointer_path = "inputs/datasets/toy/current.pointer.yaml"
    split_pointer_path = "inputs/datasets/toy/test_split.pointer.yaml"
    resolved_dataset_pointer = resolved_pointer(
        store,
        MAIN_SOURCE_COMMIT,
        dataset_pointer_path,
        dataset_pointer,
    )
    resolved_split_pointer = resolved_pointer(
        store,
        MAIN_SOURCE_COMMIT,
        split_pointer_path,
        split_pointer,
    )

    run_id = "01ARZ3NDEKTSV4RRFFQ69G5FAB"
    run_root = f"experiments/model_eval/runs/baseline/{run_id}"
    build = BuildSpec(
        script="src/mantra/priors/toy/build.py",
        inputs={
            "dataset": {
                "kind": "stored",
                "pointer": resolved_dataset_pointer.stored_at,
                "path": "inputs/datasets/toy/current.bin",
            }
        },
        params={},
        artifacts={
            "prior": {
                "kind": "bundle",
                "path": f"{run_root}/artifacts/priors/toy",
                "loader": "prior_bundle",
            }
        },
    )
    train = TrainSpec(
        script="src/mantra/models/toy/train.py",
        inputs={
            "prior": {
                "kind": "future",
                "producer_stage_id": "build",
                "producer_artifact": "prior",
            }
        },
        params={"epochs": 2, "batch_size": 2, "learning_rate": 0.01},
        artifacts={
            MODEL_PARAMETERS: {
                "kind": "file",
                "path": f"{run_root}/artifacts/models/toy/model_parameters.bin",
                "loader": "bytes_file",
            },
            CONTINUATION_STATE: {
                "kind": "file",
                "path": f"{run_root}/artifacts/models/toy/continuation_state.bin",
                "loader": "bytes_file",
            },
        },
    )
    evaluate = EvaluateSpec(
        script="src/mantra/models/toy/evaluate.py",
        inputs={
            "model_parameters": {
                "kind": "future",
                "producer_stage_id": "train",
                "producer_artifact": MODEL_PARAMETERS,
            },
            "evaluation_dataset": {
                "kind": "stored",
                "pointer": resolved_dataset_pointer.stored_at,
                "path": "inputs/datasets/toy/evaluation.bin",
            },
            "test_split": {
                "kind": "stored",
                "pointer": resolved_split_pointer.stored_at,
                "path": "inputs/datasets/toy/test_split.json",
            },
        },
        params={
            "metric_ids": ["pearson_correlation"],
            "split_inputs": ["test_split"],
        },
        artifacts={
            "predictions": {
                "kind": "file",
                "path": f"{run_root}/artifacts/evaluations/predictions.bin",
                "loader": "bytes_file",
            }
        },
    )
    stage_specs: list[tuple[str, BaseSpec]] = [
        ("build", build),
        ("train", train),
        ("evaluate", evaluate),
    ]
    run = make_run(
        experiment_id="model_eval",
        run_id=run_id,
        source_commit=MAIN_SOURCE_COMMIT,
        plan_commit=MAIN_PLAN_COMMIT,
        stage_specs=stage_specs,
        estimator_stage_id="train",
    )
    experiment = ExperimentSpec(
        experiment_id="model_eval",
        factors=(),
        variant_ids=("baseline",),
        replicates=({"replicate_id": "replicate_01", "seed": 42},),
        metric_ids=("pearson_correlation",),
    )
    variant = VariantSpec(
        experiment_id="model_eval",
        variant_id="baseline",
        levels={},
        stage_params=(
            {"kind": "build", "stage_id": "build", "params": build.params},
            {"kind": "train", "stage_id": "train", "params": train.params},
            {
                "kind": "evaluate",
                "stage_id": "evaluate",
                "params": evaluate.params,
            },
        ),
    )
    run_reference = add_plan_records(
        store,
        run=run,
        stage_specs=stage_specs,
        experiment=experiment,
        variant=variant,
        plan_commit=MAIN_PLAN_COMMIT,
    )

    add_loader(store, MAIN_SOURCE_COMMIT, "prior_bundle", bundle=True)
    add_loader(store, MAIN_SOURCE_COMMIT, "bytes_file")
    resolved_env = resolved_environment(store, MAIN_SOURCE_COMMIT)
    build_source = add_source_file(
        store, MAIN_SOURCE_COMMIT, str(build.script), b"# build\n"
    )
    train_source = add_source_file(
        store, MAIN_SOURCE_COMMIT, str(train.script), b"# train\n"
    )
    evaluate_source = add_source_file(
        store, MAIN_SOURCE_COMMIT, str(evaluate.script), b"# evaluate\n"
    )

    build_commit = "9" * 40
    prior_members = {
        "adjacency.bin": b"adjacency",
        "metadata.json": b'{"genes":2}\n',
    }
    prior_artifact = add_bundle_artifact(
        store,
        build_commit,
        str(build.artifacts["prior"].path),
        prior_members,
    )
    resolved_build = ResolvedBuildSpec(
        spec=build,
        source=build_source,
        environment=resolved_env,
        execution_context=execution_context(),
        command=("python", str(build.script), str(run.stages[0].spec)),
        inputs={
            "dataset": {"kind": "stored", "pointer": resolved_dataset_pointer},
        },
        artifacts={"prior": prior_artifact},
        completed_at=datetime(2026, 8, 20, 21, 10, tzinfo=UTC),
    )
    build_stage = publish_resolved_stage(
        store,
        run_root_path=run_root,
        stage_id="build",
        snapshot_commit=build_commit,
        resolved_spec=resolved_build,
    )

    train_commit = "a" * 40
    resolved_train = ResolvedTrainSpec(
        spec=train,
        source=train_source,
        environment=resolved_env,
        execution_context=execution_context(),
        command=("python", str(train.script), str(run.stages[1].spec)),
        inputs={"prior": ResolvedFutureInputRef(producer=build_stage)},
        artifacts={
            MODEL_PARAMETERS: add_single_artifact(
                store,
                train_commit,
                str(train.artifacts[MODEL_PARAMETERS].path),
                b"final model parameters",
            ),
            CONTINUATION_STATE: add_single_artifact(
                store,
                train_commit,
                str(train.artifacts[CONTINUATION_STATE].path),
                b"optimizer rng batch state",
            ),
        },
        completed_at=datetime(2026, 8, 20, 21, 30, tzinfo=UTC),
    )
    train_stage = publish_resolved_stage(
        store,
        run_root_path=run_root,
        stage_id="train",
        snapshot_commit=train_commit,
        resolved_spec=resolved_train,
    )

    evaluate_commit = "b" * 40
    resolved_evaluate = ResolvedEvaluateSpec(
        spec=evaluate,
        source=evaluate_source,
        environment=resolved_env,
        execution_context=execution_context(),
        command=("python", str(evaluate.script), str(run.stages[2].spec)),
        inputs={
            "model_parameters": ResolvedFutureInputRef(producer=train_stage),
            "evaluation_dataset": {
                "kind": "stored",
                "pointer": resolved_dataset_pointer,
            },
            "test_split": {"kind": "stored", "pointer": resolved_split_pointer},
        },
        artifacts={
            "predictions": add_single_artifact(
                store,
                evaluate_commit,
                str(evaluate.artifacts["predictions"].path),
                b"fixed predictions",
            )
        },
        completed_at=datetime(2026, 8, 20, 21, 40, tzinfo=UTC),
    )
    evaluate_stage = publish_resolved_stage(
        store,
        run_root_path=run_root,
        stage_id="evaluate",
        snapshot_commit=evaluate_commit,
        resolved_spec=resolved_evaluate,
    )

    measurement_raw = (
        b'{"run_id":"01ARZ3NDEKTSV4RRFFQ69G5FAB",'
        b'"attempt_id":1,"stage_id":"evaluate",'
        b'"metric_id":"pearson_correlation","value":0.91,'
        b'"measured_at":"2026-08-20T21:39:00Z"}\n'
    )
    measurement_location = hf_file(
        MAIN_FILES_COMMIT,
        f"{run_root}/measurements/evaluate.pearson_correlation.jsonl",
    )
    store.put(measurement_location, measurement_raw)
    measurement_reference = ResolvedFileRef(
        sha256=sha256(measurement_raw),
        bytes=len(measurement_raw),
        stored_at=measurement_location,
    )
    attempt = RunAttempt(
        attempt_id=1,
        status="succeeded",
        started_at=datetime(2026, 8, 20, 21, tzinfo=UTC),
        completed_at=datetime(2026, 8, 20, 21, 45, tzinfo=UTC),
        resolved_stages=(build_stage, train_stage, evaluate_stage),
        measurement_files=(measurement_reference,),
        log_files=(),
        failure_reason=None,
    )
    resolved_run = ResolvedRun(
        spec=run_reference,
        status="succeeded",
        attempts=(attempt,),
        successful_attempt_id=1,
        completed_at=datetime(2026, 8, 20, 21, 46, tzinfo=UTC),
    )
    tamper_location = hf_file(
        build_commit,
        f"{build.artifacts['prior'].path}/adjacency.bin",
    )
    return resolved_run, store, tamper_location


class CompleteProvenanceAcceptanceTests(unittest.TestCase):
    def test_complete_dummy_run_passes_full_verification(self) -> None:
        resolved_run, store, _ = build_complete_fixture()

        verified = verify_run_result(resolved_run, fetcher=store.fetch)

        self.assertEqual(set(verified.resolved_stages), {"build", "train", "evaluate"})
        self.assertEqual(len(verified.measurements), 1)
        self.assertEqual(verified.measurements[0].value, 0.91)

    def test_complete_verifier_rejects_tampered_referenced_file(self) -> None:
        resolved_run, store, tamper_location = build_complete_fixture()
        store.put(tamper_location, b"Adjacency")

        with self.assertRaisesRegex(VerificationError, "SHA-256 mismatch"):
            verify_run_result(resolved_run, fetcher=store.fetch)


if __name__ == "__main__":
    unittest.main()
