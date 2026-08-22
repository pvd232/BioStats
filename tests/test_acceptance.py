"""End-to-end tests for complete MANTRA provenance chains.

The fixtures publish run plans, stage results, artifacts, measurements, and
resolved runs to an in-memory document store. The tests then exercise the
public verifier against valid chains and deliberately broken relationships.
"""

from __future__ import annotations

import hashlib
import unittest
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import torch
import yaml
from pydantic import HttpUrl, TypeAdapter

from mantra_provenance.models_v4 import (
    CONTINUATION_STATE,
    MODEL_PARAMETERS,
    ArtifactPointer,
    ArtifactPointerRef,
    BaseSpec,
    BenchmarkResult,
    BenchmarkSpec,
    BuildParams,
    BuildSpec,
    BuildVariantStageParams,
    BundleArtifactSpec,
    CPUBackendContext,
    CPUContext,
    DownloadSpec,
    EvaluateParams,
    EvaluateSpec,
    EvaluateVariantStageParams,
    ExecutionContext,
    ExperimentSpec,
    FutureInputRef,
    GCEHostContext,
    GCEMachineImageRef,
    GitFileRef,
    GitSource,
    HuggingFaceFileRef,
    MetricCriterion,
    NativeLibraryContext,
    NativeThreadPoolContext,
    NumericalRuntimeContext,
    RemoteFileRef,
    ReplicateSpec,
    ResolvedArtifactPointerRef,
    ResolvedBenchmarkSpecRef,
    ResolvedBuildSpec,
    ResolvedBundleArtifact,
    ResolvedBundleMember,
    ResolvedDownloadSpec,
    ResolvedEvaluateSpec,
    ResolvedFileRef,
    ResolvedFutureInputRef,
    ResolvedGCEEnvironment,
    ResolvedGCEMachineImageRef,
    ResolvedGitFileRef,
    ResolvedRun,
    ResolvedRunRef,
    ResolvedRunSpecRef,
    ResolvedSingleFileArtifact,
    ResolvedStageRef,
    ResolvedStoredInputRef,
    ResolvedTrainSpec,
    RunAttempt,
    RunSpec,
    RunStageRef,
    StageArtifactRef,
    StageResultSnapshotRef,
    StorageModel,
    StoredInputRef,
    TrainSpec,
    TrainVariantStageParams,
    VariantSpec,
)
from mantra_provenance.verifier import (
    VerificationError,
    verify_benchmark_result,
    verify_promoted_artifact,
    verify_run_result,
)
from tests.test_verifier import (
    CPUComputeSpec,
    DataLoaderConfiguration,
    GCEEnvironmentSpec,
    NumPyRandomnessSpec,
    ParallelismSpec,
    RandomnessContext,
    ReproducibilitySpec,
    SingleFileArtifactSpec,
    SnapshotFileRef,
    TorchDeterminismSpec,
    TorchPrecisionSpec,
    TrainParams,
    continuation_state,
)

SOURCE_REPOSITORY = HttpUrl("https://github.com/example/mantra")
ARTIFACT_REPOSITORY = "example/mantra-runs"
PRODUCER_SOURCE_COMMIT = "1" * 40
PRODUCER_PLAN_COMMIT = "2" * 40
PRODUCER_RESULT_COMMIT = "3" * 40
MAIN_SOURCE_COMMIT = "4" * 40
MAIN_PLAN_COMMIT = "5" * 40
MAIN_FILES_COMMIT = "6" * 40
YAML_ADAPTER = TypeAdapter(Any)


def yaml_bytes(value: object) -> bytes:
    """Serialize one protocol record as deterministic YAML bytes."""

    data = YAML_ADAPTER.dump_python(value, mode="json")
    data_s = yaml.safe_dump(data, sort_keys=True)
    assert isinstance(data_s, str)
    return data_s.encode("utf-8")


def continuation_bytes() -> bytes:
    """Serialize one valid training-continuation artifact."""

    stream = BytesIO()
    torch.save(
        continuation_state().model_dump(mode="python"),
        stream,
    )
    return stream.getvalue()


def sha256(raw: bytes) -> str:
    """Return the SHA-256 identity of stored bytes."""

    return hashlib.sha256(raw).hexdigest()


class DocumentStore:
    """Store immutable test documents by their complete storage identity."""

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


def environment(source_commit: str) -> GCEEnvironmentSpec:
    return GCEEnvironmentSpec(
        kind="gce",
        machine_image=GCEMachineImageRef(project="mantra-project", name="mantra-image"),
        machine_type="n2-standard-8",
        compute=CPUComputeSpec(kind="cpu"),
        lockfile=git_file(source_commit, "environment.yml"),
    )


def reproducibility() -> ReproducibilitySpec:
    return ReproducibilitySpec(
        determinism=TorchDeterminismSpec(
            deterministic_algorithms=True,
            deterministic_warn_only=False,
            cudnn_deterministic=True,
            cudnn_benchmark=False,
            cublas_workspace_config=":4096:8",
        ),
        precision=TorchPrecisionSpec(
            float32_matmul_precision="highest",
            cudnn_allow_tf32=False,
            autocast_enabled=False,
            autocast_dtype=None,
        ),
        parallelism=ParallelismSpec(
            process_count=1,
            torch_intraop_threads=1,
            torch_interop_threads=1,
            dataloader=DataLoaderConfiguration(
                workers=0,
                prefetch_factor=None,
                persistent_workers=False,
                in_order=True,
            ),
        ),
        numpy_randomness=NumPyRandomnessSpec(
            generators={"training": "PCG64"}, capture_legacy_global=True
        ),
    )


def execution_context() -> ExecutionContext:
    controls = reproducibility()
    return ExecutionContext(
        host=GCEHostContext(
            provider="gce",
            machine_type="n2-standard-8",
            zone="us-central1-a",
            guest_os_name="debian",
            guest_os_version="12",
            kernel_release="6.1",
        ),
        cpu=CPUContext(
            architecture="x86_64",
            model="Intel Cascade Lake",
            instruction_features=("avx2",),
        ),
        backend=CPUBackendContext(kind="cpu", device="cpu"),
        numerical_runtime=NumericalRuntimeContext(
            python_version="3.14.0",
            pytorch_version="2.8.0",
            numpy_version="2.3.0",
            blas=NativeLibraryContext(implementation="openblas", version="0.3.30"),
            lapack=NativeLibraryContext(implementation="openblas", version="0.3.30"),
            native_thread_pools=(
                NativeThreadPoolContext(
                    implementation="openblas",
                    version="0.3.30",
                    threads=1,
                ),
            ),
        ),
        randomness=RandomnessContext(
            python_seed=42,
            numpy_seed=42,
            torch_seed=42,
            dataloader_seed=42,
        ),
        determinism=controls.determinism,
        precision=controls.precision,
        parallelism=controls.parallelism,
    )


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
) -> ResolvedGCEEnvironment:
    lock_raw = b"name: mantra\n"
    lockfile = add_source_file(store, source_commit, "environment.yml", lock_raw)
    return ResolvedGCEEnvironment(
        kind="gce",
        machine_image=ResolvedGCEMachineImageRef(
            project="mantra-project",
            name="mantra-image",
            id="123456789",
        ),
        machine_type="n2-standard-8",
        compute=CPUComputeSpec(kind="cpu"),
        lockfile=lockfile,
    )


def add_loader(
    store: DocumentStore,
    source_commit: str,
    loader_id: str,
    *,
    bundle: bool = False,
) -> None:
    """Publish one artifact-loader module into the simulated source commit."""

    if loader_id == "continuation_state":
        raw = (
            b"from mantra_provenance.continuation "
            b"import load_training_continuation\n\n"
            b"def load(path):\n"
            b"    return load_training_continuation(path)\n"
        )
    elif bundle:
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
    benchmark: BenchmarkSpec | None = None,
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
    if benchmark is not None:
        store.put(
            git_file(
                source_commit,
                f"benchmarks/{benchmark.benchmark_id}.spec.yaml",
            ),
            yaml_bytes(benchmark),
        )

    for run_stage, (_, spec) in zip(run.stages, stage_specs, strict=True):
        store.put(git_file(plan_commit, str(run_stage.spec)), yaml_bytes(spec))

    run_path = (
        f"experiments/{run.experiment_id}/runs/{run.variant_id}/{run.run_id}/spec.yaml"
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
        estimator=StageArtifactRef(
            stage_id=estimator_stage_id,
            artifact_name=MODEL_PARAMETERS,
        ),
    )


def add_single_artifact(
    store: DocumentStore,
    snapshot_commit: str,
    path: str,
    raw: bytes,
) -> ResolvedSingleFileArtifact:
    store.put(hf_file(snapshot_commit, path), raw)
    return ResolvedSingleFileArtifact(
        kind="file",
        file=SnapshotFileRef(path=path, sha256=sha256(raw), bytes=len(raw)),
    )


def add_bundle_artifact(
    store: DocumentStore,
    snapshot_commit: str,
    root: str,
    members: dict[str, bytes],
) -> ResolvedBundleArtifact:
    resolved_members = []
    for relative_path in sorted(members):
        raw = members[relative_path]
        path = f"{root}/{relative_path}"
        store.put(hf_file(snapshot_commit, path), raw)
        resolved_members.append(
            ResolvedBundleMember(
                relative_path=relative_path,
                file=SnapshotFileRef(path=path, sha256=sha256(raw), bytes=len(raw)),
            )
        )
    return ResolvedBundleArtifact(kind="bundle", members=tuple(resolved_members))


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
        resolved_spec=SnapshotFileRef(path=path, sha256=sha256(raw), bytes=len(raw)),
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
            "archive": RemoteFileRef(
                kind="remote",
                url=HttpUrl("https://example.com/toy-v1.tar.gz"),
                version="v1",
            )
        },
        artifacts={
            "dataset": SingleFileArtifactSpec(
                kind="file",
                path=f"{run_root}/artifacts/datasets/toy/dataset.bin",
                loader="bytes_file",
            ),
            "split": SingleFileArtifactSpec(
                kind="file",
                path=f"{run_root}/artifacts/datasets/toy/split.json",
                loader="bytes_file",
            ),
        },
    )
    train = TrainSpec(
        script="src/mantra/models/toy/train.py",
        inputs={
            "training_dataset": FutureInputRef(
                kind="future",
                producer_stage_id="download",
                producer_artifact="dataset",
            )
        },
        params=TrainParams(epochs=1, batch_size=2, learning_rate=0.01),
        artifacts={
            MODEL_PARAMETERS: SingleFileArtifactSpec(
                kind="file",
                path=f"{run_root}/artifacts/models/toy/model_parameters.bin",
                loader="bytes_file",
            ),
            CONTINUATION_STATE: SingleFileArtifactSpec(
                kind="file",
                path=f"{run_root}/artifacts/models/toy/continuation_state.bin",
                loader="continuation_state",
            ),
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
        replicates=(ReplicateSpec(replicate_id="replicate_01", seed=42),),
        metric_ids=(),
    )
    variant = VariantSpec(
        experiment_id="source_data",
        variant_id="baseline",
        levels={},
        stage_params=(
            TrainVariantStageParams(
                kind="train", stage_id="train", params=train.params
            ),
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
    add_loader(store, PRODUCER_SOURCE_COMMIT, "continuation_state")
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
                continuation_bytes(),
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


def build_complete_fixture(
    *,
    benchmark_enabled: bool = False,
) -> tuple[
    ResolvedRun,
    DocumentStore,
    HuggingFaceFileRef,
]:
    store = DocumentStore()
    producer_run_ref, _ = publish_producer_run(store)

    dataset_pointer = ArtifactPointer(
        run=producer_run_ref,
        artifact=StageArtifactRef(stage_id="download", artifact_name="dataset"),
    )
    split_pointer = ArtifactPointer(
        run=producer_run_ref,
        artifact=StageArtifactRef(stage_id="download", artifact_name="split"),
    )
    dataset_pointer_path = "inputs/datasets/toy/current.pointer.yaml"
    split_pointer_path = "inputs/benchmarks/toy/test_split.pointer.yaml"
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
            "dataset": StoredInputRef(
                kind="stored",
                pointer=resolved_dataset_pointer.stored_at,
                path="inputs/datasets/toy/current.bin",
            )
        },
        params=BuildParams(),
        artifacts={
            "prior": BundleArtifactSpec(
                kind="bundle",
                path=f"{run_root}/artifacts/priors/toy",
                loader="prior_bundle",
            )
        },
    )
    train = TrainSpec(
        script="src/mantra/models/toy/train.py",
        inputs={
            "prior": FutureInputRef(
                kind="future",
                producer_stage_id="build",
                producer_artifact="prior",
            )
        },
        params=TrainParams(epochs=2, batch_size=2, learning_rate=0.01),
        artifacts={
            MODEL_PARAMETERS: SingleFileArtifactSpec(
                kind="file",
                path=f"{run_root}/artifacts/models/toy/model_parameters.bin",
                loader="bytes_file",
            ),
            CONTINUATION_STATE: SingleFileArtifactSpec(
                kind="file",
                path=f"{run_root}/artifacts/models/toy/continuation_state.bin",
                loader="continuation_state",
            ),
        },
    )
    evaluate = EvaluateSpec(
        script="src/mantra/models/toy/evaluate.py",
        inputs={
            "model_parameters": FutureInputRef(
                kind="future",
                producer_stage_id="train",
                producer_artifact=MODEL_PARAMETERS,
            ),
            "evaluation_dataset": StoredInputRef(
                kind="stored",
                pointer=resolved_dataset_pointer.stored_at,
                path="inputs/datasets/toy/evaluation.bin",
            ),
            "test_split": StoredInputRef(
                kind="stored",
                pointer=resolved_split_pointer.stored_at,
                path="inputs/benchmarks/toy/test_split.json",
            ),
        },
        params=EvaluateParams(
            metric_ids=("pearson_correlation",),
            split_inputs=("test_split",),
        ),
        artifacts={
            "predictions": SingleFileArtifactSpec(
                kind="file",
                path=f"{run_root}/artifacts/evaluations/toy_strict/predictions.bin",
                loader="bytes_file",
            )
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
    benchmark = None
    if benchmark_enabled:
        benchmark = BenchmarkSpec(
            benchmark_id="toy_strict",
            evaluation_dataset=resolved_dataset_pointer.stored_at,
            splits={"test_split": resolved_split_pointer.stored_at},
            metrics=(
                MetricCriterion(
                    metric_id="pearson_correlation",
                    comparison="ge",
                    threshold=0.9,
                ),
            ),
        )
        run = run.model_copy(update={"benchmark_id": benchmark.benchmark_id})
    experiment = ExperimentSpec(
        experiment_id="model_eval",
        factors=(),
        variant_ids=("baseline",),
        replicates=(ReplicateSpec(replicate_id="replicate_01", seed=42),),
        metric_ids=("pearson_correlation",),
    )
    variant = VariantSpec(
        experiment_id="model_eval",
        variant_id="baseline",
        levels={},
        stage_params=(
            BuildVariantStageParams(
                kind="build", stage_id="build", params=build.params
            ),
            TrainVariantStageParams(
                kind="train", stage_id="train", params=train.params
            ),
            EvaluateVariantStageParams(
                kind="evaluate",
                stage_id="evaluate",
                params=evaluate.params,
            ),
        ),
    )
    run_reference = add_plan_records(
        store,
        run=run,
        stage_specs=stage_specs,
        experiment=experiment,
        variant=variant,
        plan_commit=MAIN_PLAN_COMMIT,
        benchmark=benchmark,
    )

    add_loader(store, MAIN_SOURCE_COMMIT, "prior_bundle", bundle=True)
    add_loader(store, MAIN_SOURCE_COMMIT, "bytes_file")
    add_loader(store, MAIN_SOURCE_COMMIT, "continuation_state")
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
            "dataset": ResolvedStoredInputRef(
                kind="stored", pointer=resolved_dataset_pointer
            ),
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
                continuation_bytes(),
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
            "evaluation_dataset": ResolvedStoredInputRef(
                kind="stored",
                pointer=resolved_dataset_pointer,
            ),
            "test_split": ResolvedStoredInputRef(
                kind="stored", pointer=resolved_split_pointer
            ),
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


def copy_snapshot_files(
    store: DocumentStore,
    source_commit: str,
    target_commit: str,
) -> None:
    for key, raw in tuple(store.documents.items()):
        kind, repository, commit, path, repo_type = key
        if (
            kind == "huggingface"
            and repository == ARTIFACT_REPOSITORY
            and commit == source_commit
            and repo_type == "dataset"
        ):
            store.put(hf_file(target_commit, path), raw)


def build_benchmark_fixture() -> tuple[
    BenchmarkResult,
    ResolvedRun,
    DocumentStore,
]:
    resolved_run, store, _ = build_complete_fixture(benchmark_enabled=True)
    selected_attempt = resolved_run.attempts[-1]
    run_root = str(resolved_run.spec.stored_at.path).removesuffix("/spec.yaml")

    original_build, original_train, original_evaluate = selected_attempt.resolved_stages
    build_commit = "c" * 40
    train_commit = "d" * 40
    evaluate_commit = "e" * 40

    copy_snapshot_files(store, original_build.snapshot.commit, build_commit)
    resolved_build = ResolvedBuildSpec.model_validate(
        yaml.safe_load(
            store.fetch(
                hf_file(
                    original_build.snapshot.commit,
                    str(original_build.resolved_spec.path),
                )
            )
        )
    )
    confirmation_build = publish_resolved_stage(
        store,
        run_root_path=run_root,
        stage_id="build",
        snapshot_commit=build_commit,
        resolved_spec=resolved_build,
    )

    copy_snapshot_files(store, original_train.snapshot.commit, train_commit)
    resolved_train = ResolvedTrainSpec.model_validate(
        yaml.safe_load(
            store.fetch(
                hf_file(
                    original_train.snapshot.commit,
                    str(original_train.resolved_spec.path),
                )
            )
        )
    )
    resolved_train = resolved_train.model_copy(
        update={
            "inputs": {"prior": ResolvedFutureInputRef(producer=confirmation_build)}
        }
    )
    confirmation_train = publish_resolved_stage(
        store,
        run_root_path=run_root,
        stage_id="train",
        snapshot_commit=train_commit,
        resolved_spec=resolved_train,
    )

    copy_snapshot_files(store, original_evaluate.snapshot.commit, evaluate_commit)
    resolved_evaluate = ResolvedEvaluateSpec.model_validate(
        yaml.safe_load(
            store.fetch(
                hf_file(
                    original_evaluate.snapshot.commit,
                    str(original_evaluate.resolved_spec.path),
                )
            )
        )
    )
    resolved_evaluate = resolved_evaluate.model_copy(
        update={
            "inputs": {
                **resolved_evaluate.inputs,
                "model_parameters": ResolvedFutureInputRef(producer=confirmation_train),
            }
        }
    )
    confirmation_evaluate = publish_resolved_stage(
        store,
        run_root_path=run_root,
        stage_id="evaluate",
        snapshot_commit=evaluate_commit,
        resolved_spec=resolved_evaluate,
    )

    measurement_raw = (
        b'{"run_id":"01ARZ3NDEKTSV4RRFFQ69G5FAB",'
        b'"attempt_id":2,"stage_id":"evaluate",'
        b'"metric_id":"pearson_correlation","value":0.91,'
        b'"measured_at":"2026-08-20T21:39:00Z"}\n'
    )
    measurement_location = hf_file(
        "f" * 40,
        f"{run_root}/measurements/evaluate.pearson_correlation.jsonl",
    )
    store.put(measurement_location, measurement_raw)
    confirmation = RunAttempt(
        attempt_id=2,
        status="succeeded",
        started_at=datetime(2026, 8, 20, 21, tzinfo=UTC),
        completed_at=datetime(2026, 8, 20, 21, 45, tzinfo=UTC),
        resolved_stages=(
            confirmation_build,
            confirmation_train,
            confirmation_evaluate,
        ),
        measurement_files=(
            ResolvedFileRef(
                sha256=sha256(measurement_raw),
                bytes=len(measurement_raw),
                stored_at=measurement_location,
            ),
        ),
        log_files=(),
        failure_reason=None,
    )

    resolved_run_raw = yaml_bytes(resolved_run)
    resolved_run_location = hf_file("0" * 40, f"{run_root}/resolved.yaml")
    store.put(resolved_run_location, resolved_run_raw)
    run_reference = ResolvedRunRef(
        sha256=sha256(resolved_run_raw),
        bytes=len(resolved_run_raw),
        stored_at=resolved_run_location,
    )

    benchmark_path = "benchmarks/toy_strict.spec.yaml"
    benchmark_location = git_file(MAIN_SOURCE_COMMIT, benchmark_path)
    benchmark_raw = store.fetch(benchmark_location)
    benchmark_reference = ResolvedBenchmarkSpecRef(
        sha256=sha256(benchmark_raw),
        bytes=len(benchmark_raw),
        stored_at=benchmark_location,
    )
    result = BenchmarkResult(
        benchmark=benchmark_reference,
        run=run_reference,
        confirmation=confirmation,
        status="passed",
        completed_at=datetime(2026, 8, 20, 21, 50, tzinfo=UTC),
    )
    return result, resolved_run, store


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

    def test_measurement_cannot_follow_its_named_stage(self) -> None:
        resolved_run, store, _ = build_complete_fixture()
        attempt = resolved_run.attempts[0]
        measurement_raw = (
            b'{"run_id":"01ARZ3NDEKTSV4RRFFQ69G5FAB",'
            b'"attempt_id":1,"stage_id":"evaluate",'
            b'"metric_id":"pearson_correlation","value":0.91,'
            b'"measured_at":"2026-08-20T21:44:00Z"}\n'
        )
        reference = attempt.measurement_files[0].model_copy(
            update={
                "sha256": sha256(measurement_raw),
                "bytes": len(measurement_raw),
            }
        )
        store.put(reference.stored_at, measurement_raw)
        invalid_attempt = attempt.model_copy(update={"measurement_files": (reference,)})
        invalid_run = resolved_run.model_copy(update={"attempts": (invalid_attempt,)})

        with self.assertRaisesRegex(VerificationError, "stage completion"):
            verify_run_result(invalid_run, fetcher=store.fetch)

    def test_run_rejects_stage_snapshot_reused_by_a_retry(self) -> None:
        resolved_run, store, _ = build_complete_fixture()
        successful_attempt = resolved_run.attempts[0].model_copy(
            update={"attempt_id": 2}
        )
        failed_attempt = RunAttempt(
            attempt_id=1,
            status="failed",
            started_at=datetime(2026, 8, 20, 19, tzinfo=UTC),
            completed_at=datetime(2026, 8, 20, 20, tzinfo=UTC),
            resolved_stages=(successful_attempt.resolved_stages[0],),
            measurement_files=(),
            log_files=(),
            failure_reason="retry required",
        )
        retried_run = resolved_run.model_copy(
            update={
                "attempts": (failed_attempt, successful_attempt),
                "successful_attempt_id": 2,
            }
        )

        with self.assertRaisesRegex(VerificationError, "stage-result snapshots"):
            verify_run_result(retried_run, fetcher=store.fetch)

    def test_run_rejects_attempt_file_snapshot_reused_by_a_retry(self) -> None:
        resolved_run, store, _ = build_complete_fixture()
        successful_attempt = resolved_run.attempts[0].model_copy(
            update={"attempt_id": 2}
        )
        failed_attempt = RunAttempt(
            attempt_id=1,
            status="failed",
            started_at=datetime(2026, 8, 20, 19, tzinfo=UTC),
            completed_at=datetime(2026, 8, 20, 20, tzinfo=UTC),
            resolved_stages=(),
            measurement_files=successful_attempt.measurement_files,
            log_files=(),
            failure_reason="retry required",
        )
        retried_run = resolved_run.model_copy(
            update={
                "attempts": (failed_attempt, successful_attempt),
                "successful_attempt_id": 2,
            }
        )

        with self.assertRaisesRegex(
            VerificationError,
            "measurement and log snapshots",
        ):
            verify_run_result(retried_run, fetcher=store.fetch)

    def test_run_separates_stage_results_from_attempt_files(self) -> None:
        resolved_run, store, _ = build_complete_fixture()
        attempt = resolved_run.attempts[0]
        measurement = attempt.measurement_files[0]
        reused_snapshot_measurement = measurement.model_copy(
            update={
                "stored_at": measurement.stored_at.model_copy(
                    update={"commit": attempt.resolved_stages[0].snapshot.commit}
                )
            }
        )
        invalid_attempt = attempt.model_copy(
            update={"measurement_files": (reused_snapshot_measurement,)}
        )
        invalid_run = resolved_run.model_copy(update={"attempts": (invalid_attempt,)})

        with self.assertRaisesRegex(
            VerificationError,
            "stage-result and attempt-file snapshots",
        ):
            verify_run_result(invalid_run, fetcher=store.fetch)

    def test_strict_benchmark_passes_two_execution_verification(self) -> None:
        result, _, store = build_benchmark_fixture()

        verified = verify_benchmark_result(result, fetcher=store.fetch)

        self.assertEqual(verified.result.status, "passed")
        self.assertEqual(verified.confirmation_measurements[0].value, 0.91)

    def test_strict_benchmark_rejects_reused_stage_snapshots(self) -> None:
        result, resolved_run, store = build_benchmark_fixture()
        reused_confirmation = result.confirmation.model_copy(
            update={"resolved_stages": resolved_run.attempts[-1].resolved_stages}
        )
        reused_result = result.model_copy(update={"confirmation": reused_confirmation})

        with self.assertRaisesRegex(VerificationError, "new stage-result snapshots"):
            verify_benchmark_result(reused_result, fetcher=store.fetch)

    def test_strict_benchmark_rejects_reused_attempt_file_snapshot(self) -> None:
        result, resolved_run, store = build_benchmark_fixture()
        reused_confirmation = result.confirmation.model_copy(
            update={"measurement_files": resolved_run.attempts[-1].measurement_files}
        )

        with self.assertRaisesRegex(
            VerificationError,
            "new measurement and log snapshot",
        ):
            verify_benchmark_result(
                result.model_copy(update={"confirmation": reused_confirmation}),
                fetcher=store.fetch,
            )

    def test_confirmation_separates_stage_results_from_attempt_files(self) -> None:
        result, _, store = build_benchmark_fixture()
        measurement = result.confirmation.measurement_files[0]
        reused_snapshot_measurement = measurement.model_copy(
            update={
                "stored_at": measurement.stored_at.model_copy(
                    update={
                        "commit": result.confirmation.resolved_stages[0].snapshot.commit
                    }
                )
            }
        )
        invalid_confirmation = result.confirmation.model_copy(
            update={"measurement_files": (reused_snapshot_measurement,)}
        )

        with self.assertRaisesRegex(
            VerificationError,
            "stage-result and attempt-file snapshots",
        ):
            verify_benchmark_result(
                result.model_copy(update={"confirmation": invalid_confirmation}),
                fetcher=store.fetch,
            )

    def test_strict_benchmark_verifies_confirmation_input_lineage(self) -> None:
        result, resolved_run, store = build_benchmark_fixture()
        confirmation_build, confirmation_train, confirmation_evaluate = (
            result.confirmation.resolved_stages
        )
        original_build = resolved_run.attempts[-1].resolved_stages[0]

        resolved_train = ResolvedTrainSpec.model_validate(
            yaml.safe_load(
                store.fetch(
                    hf_file(
                        confirmation_train.snapshot.commit,
                        str(confirmation_train.resolved_spec.path),
                    )
                )
            )
        ).model_copy(
            update={
                "inputs": {"prior": ResolvedFutureInputRef(producer=original_build)}
            }
        )
        tampered_train = publish_resolved_stage(
            store,
            run_root_path=str(result.run.stored_at.path).removesuffix("/resolved.yaml"),
            stage_id="train",
            snapshot_commit=confirmation_train.snapshot.commit,
            resolved_spec=resolved_train,
        )

        resolved_evaluate = ResolvedEvaluateSpec.model_validate(
            yaml.safe_load(
                store.fetch(
                    hf_file(
                        confirmation_evaluate.snapshot.commit,
                        str(confirmation_evaluate.resolved_spec.path),
                    )
                )
            )
        )
        resolved_evaluate = resolved_evaluate.model_copy(
            update={
                "inputs": {
                    **resolved_evaluate.inputs,
                    "model_parameters": ResolvedFutureInputRef(producer=tampered_train),
                }
            }
        )
        updated_evaluate = publish_resolved_stage(
            store,
            run_root_path=str(result.run.stored_at.path).removesuffix("/resolved.yaml"),
            stage_id="evaluate",
            snapshot_commit=confirmation_evaluate.snapshot.commit,
            resolved_spec=resolved_evaluate,
        )
        confirmation = result.confirmation.model_copy(
            update={
                "resolved_stages": (
                    confirmation_build,
                    tampered_train,
                    updated_evaluate,
                )
            }
        )

        with self.assertRaisesRegex(
            VerificationError,
            "does not identify the completed producer stage",
        ):
            verify_benchmark_result(
                result.model_copy(update={"confirmation": confirmation}),
                fetcher=store.fetch,
            )

    def test_strict_benchmark_verifies_confirmation_stored_inputs(self) -> None:
        result, _, store = build_benchmark_fixture()
        confirmation_build, confirmation_train, confirmation_evaluate = (
            result.confirmation.resolved_stages
        )
        resolved_evaluate = ResolvedEvaluateSpec.model_validate(
            yaml.safe_load(
                store.fetch(
                    hf_file(
                        confirmation_evaluate.snapshot.commit,
                        str(confirmation_evaluate.resolved_spec.path),
                    )
                )
            )
        )
        evaluation_dataset = resolved_evaluate.inputs["evaluation_dataset"]
        self.assertEqual(evaluation_dataset.kind, "stored")
        assert isinstance(evaluation_dataset, ResolvedStoredInputRef)
        tampered_dataset = evaluation_dataset.model_copy(
            update={
                "pointer": evaluation_dataset.pointer.model_copy(
                    update={"sha256": "0" * 64}
                )
            }
        )
        tampered_evaluate_spec = resolved_evaluate.model_copy(
            update={
                "inputs": {
                    **resolved_evaluate.inputs,
                    "evaluation_dataset": tampered_dataset,
                }
            }
        )
        tampered_evaluate = publish_resolved_stage(
            store,
            run_root_path=str(result.run.stored_at.path).removesuffix("/resolved.yaml"),
            stage_id="evaluate",
            snapshot_commit=confirmation_evaluate.snapshot.commit,
            resolved_spec=tampered_evaluate_spec,
        )
        confirmation = result.confirmation.model_copy(
            update={
                "resolved_stages": (
                    confirmation_build,
                    confirmation_train,
                    tampered_evaluate,
                )
            }
        )

        with self.assertRaisesRegex(VerificationError, "SHA-256 mismatch"):
            verify_benchmark_result(
                result.model_copy(update={"confirmation": confirmation}),
                fetcher=store.fetch,
            )

    def test_promoted_artifact_verifies_producer_input_lineage(self) -> None:
        store = DocumentStore()
        run_reference, records = publish_producer_run(store)
        resolved_run = records["run"]
        download_stage, train_stage = resolved_run.attempts[0].resolved_stages
        resolved_train = ResolvedTrainSpec.model_validate(
            yaml.safe_load(
                store.fetch(
                    hf_file(
                        train_stage.snapshot.commit,
                        str(train_stage.resolved_spec.path),
                    )
                )
            )
        ).model_copy(
            update={
                "inputs": {
                    "training_dataset": ResolvedFutureInputRef(producer=train_stage)
                }
            }
        )
        tampered_train = publish_resolved_stage(
            store,
            run_root_path=str(run_reference.stored_at.path).removesuffix(
                "/resolved.yaml"
            ),
            stage_id="train",
            snapshot_commit=train_stage.snapshot.commit,
            resolved_spec=resolved_train,
        )
        tampered_attempt = resolved_run.attempts[0].model_copy(
            update={"resolved_stages": (download_stage, tampered_train)}
        )
        tampered_run = resolved_run.model_copy(update={"attempts": (tampered_attempt,)})
        tampered_raw = yaml_bytes(tampered_run)
        store.put(run_reference.stored_at, tampered_raw)
        pointer = ArtifactPointer(
            run=run_reference.model_copy(
                update={"sha256": sha256(tampered_raw), "bytes": len(tampered_raw)}
            ),
            artifact=StageArtifactRef(stage_id="train", artifact_name=MODEL_PARAMETERS),
        )

        with self.assertRaisesRegex(
            VerificationError,
            "does not identify the completed producer stage",
        ):
            verify_promoted_artifact(pointer, fetcher=store.fetch)

    def test_benchmarked_estimator_requires_benchmark_result(self) -> None:
        result, _, store = build_benchmark_fixture()
        pointer = ArtifactPointer(
            run=result.run,
            artifact=StageArtifactRef(stage_id="train", artifact_name=MODEL_PARAMETERS),
        )

        with self.assertRaisesRegex(VerificationError, "requires a benchmark result"):
            verify_promoted_artifact(pointer, fetcher=store.fetch)

    def test_benchmark_result_follows_selected_run_completion(self) -> None:
        result, resolved_run, store = build_benchmark_fixture()
        premature = result.model_copy(
            update={
                "completed_at": resolved_run.completed_at.replace(
                    minute=45,
                    second=30,
                )
            }
        )

        with self.assertRaisesRegex(VerificationError, "selected run completion"):
            verify_benchmark_result(premature, fetcher=store.fetch)


if __name__ == "__main__":
    unittest.main()
