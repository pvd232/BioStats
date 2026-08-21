"""Fourth draft of the Pydantic models for the MANTRA provenance protocol.

This version separates execution requests, verified data artifacts,
the exact Git source tree, requested environments, observed execution
conditions, and immutable stage-result snapshots.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)

from .ids import (
    ExperimentId,
    FactorId,
    HumanId,
    InputName,
    LevelId,
    MetricId,
    ReplicateId,
    RunId,
    StageId,
    VariantId,
)


def validate_repo_rel_path(value: str) -> str:
    """Validate a normalized, POSIX, repository-relative path."""
    if not value:
        raise ValueError("expected nonempty repository-relative path")
    if "\\" in value:
        raise ValueError("expected POSIX repository-relative path")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError("expected repository-relative path")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("repository-relative path contains an invalid component")
    return value


def repo_file_paths_overlap(left: str, right: str) -> bool:
    """Return whether either file path equals or sits below the other."""
    return left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

RepoRelPath = Annotated[str, AfterValidator(validate_repo_rel_path)]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmptyStr = Annotated[str, Field(min_length=1)]
GitCommit = Annotated[
    str,
    Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"),
]
ArtifactName = HumanId
ArtifactLoaderId = HumanId
BenchmarkId = HumanId
SelectionName = HumanId

MODEL_PARAMETERS: ArtifactName = "model_parameters"
CONTINUATION_STATE: ArtifactName = "continuation_state"
CHECKPOINT_MODEL_INPUT: InputName = "checkpoint_model_parameters"
CHECKPOINT_STATE_INPUT: InputName = "checkpoint_continuation_state"
EVALUATION_MODEL_INPUT: InputName = "model_parameters"
EVALUATION_DATASET_INPUT: InputName = "evaluation_dataset"
PREDICTIONS: ArtifactName = "predictions"


class ProtocolModel(BaseModel):
    """Closed, frozen protocol object."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# File locations
# ---------------------------------------------------------------------------


class RemoteFileRef(ProtocolModel):
    """A mutable or externally controlled source URL."""

    kind: Literal["remote"] = "remote"
    url: HttpUrl
    version: NonEmptyStr


class GitSource(ProtocolModel):
    """A repository snapshot identified by an exact Git commit."""

    kind: Literal["git"] = "git"
    repository: HttpUrl
    commit: GitCommit


class GitFileRef(GitSource):
    """A file stored at an exact Git revision."""

    path: RepoRelPath


class ArtifactPointerRef(GitFileRef):
    """A Git reference to the pointer selecting a promoted artifact."""


class HuggingFaceFileRef(ProtocolModel):
    """A file stored at an exact Hugging Face repository revision."""

    kind: Literal["huggingface"] = "huggingface"
    repository: str = Field(min_length=1)
    commit: GitCommit
    path: RepoRelPath
    repo_type: Literal["model", "dataset", "space"]


class StageResultSnapshotRef(ProtocolModel):
    """The immutable repository revision containing one completed stage."""

    kind: Literal["huggingface"] = "huggingface"
    repository: NonEmptyStr
    commit: GitCommit
    repo_type: Literal["model", "dataset", "space"]


StorageModel = GitFileRef | HuggingFaceFileRef

StorageRef = Annotated[
    StorageModel,
    Field(discriminator="kind"),
]

FileRef = Annotated[
    RemoteFileRef | StorageModel,
    Field(discriminator="kind"),
]

# ---------------------------------------------------------------------------
# Verified files and code
# ---------------------------------------------------------------------------


class ResolvedFileRef(ProtocolModel):
    """
    An exact file whose bytes have been hashed.

    sha256 identifies the file contents.
    bytes records the file length.
    stored_at says where those exact bytes can be retrieved.
    """

    sha256: SHA256
    bytes: int = Field(ge=0)
    stored_at: StorageRef


class SnapshotFileRef(ProtocolModel):
    """One exact file within a stage-result snapshot."""

    path: RepoRelPath
    sha256: SHA256
    bytes: int = Field(ge=0)


class ResolvedGitFileRef(ResolvedFileRef):
    """An exact, verified file stored at an immutable Git revision."""

    stored_at: GitFileRef  # pyright: ignore[reportIncompatibleVariableOverride]


class ResolvedArtifactPointerRef(ResolvedFileRef):
    kind: Literal["artifact_pointer"] = "artifact_pointer"
    stored_at: ArtifactPointerRef  # pyright: ignore[reportIncompatibleVariableOverride]


# ---------------------------------------------------------------------------
# Artifact selectors
# ---------------------------------------------------------------------------


class ResolvedRunSpecRef(ResolvedFileRef):
    """Identifies the exact RunSpec file governing one run."""

    kind: Literal["run_spec"] = "run_spec"
    stored_at: GitFileRef  # pyright: ignore[reportIncompatibleVariableOverride]


class ResolvedRunRef(ResolvedFileRef):
    """Identifies one terminal ResolvedRun file."""

    kind: Literal["resolved_run"] = "resolved_run"
    stored_at: HuggingFaceFileRef  # pyright: ignore[reportIncompatibleVariableOverride]


class ResolvedBenchmarkSpecRef(ResolvedFileRef):
    """Identifies the exact benchmark specification applied to a run."""

    kind: Literal["benchmark_spec"] = "benchmark_spec"
    stored_at: GitFileRef  # pyright: ignore[reportIncompatibleVariableOverride]


class ResolvedBenchmarkResultRef(ResolvedFileRef):
    """Identifies one completed benchmark result."""

    kind: Literal["benchmark_result"] = "benchmark_result"
    stored_at: HuggingFaceFileRef  # pyright: ignore[reportIncompatibleVariableOverride]


class StageArtifactRef(ProtocolModel):
    """Selects one named artifact produced by one stage."""

    stage_id: StageId
    artifact_name: ArtifactName


class ArtifactPointer(ProtocolModel):
    """Selects one artifact accepted as a reusable input."""

    schema_version: Literal[1] = 1
    run: ResolvedRunRef
    artifact: StageArtifactRef
    benchmark_result: ResolvedBenchmarkResultRef | None = None


# ---------------------------------------------------------------------------
# Requested and resolved GCE environment
# ---------------------------------------------------------------------------


class GCEMachineImageRef(ProtocolModel):
    project: str = Field(min_length=1)
    name: str = Field(min_length=1)


class ResolvedGCEMachineImageRef(GCEMachineImageRef):
    id: str = Field(min_length=1)


class CPUComputeSpec(ProtocolModel):
    kind: Literal["cpu"] = "cpu"


class CUDAComputeSpec(ProtocolModel):
    kind: Literal["cuda"] = "cuda"
    model: NonEmptyStr
    count: int = Field(ge=1)


ComputeSpec = Annotated[
    CPUComputeSpec | CUDAComputeSpec,
    Field(discriminator="kind"),
]


class GCEEnvironmentSpec(ProtocolModel):
    kind: Literal["gce"] = "gce"
    machine_image: GCEMachineImageRef
    machine_type: NonEmptyStr
    compute: ComputeSpec
    lockfile: GitFileRef


class ResolvedGCEEnvironment(ProtocolModel):
    kind: Literal["gce"] = "gce"
    machine_image: ResolvedGCEMachineImageRef
    machine_type: NonEmptyStr
    compute: ComputeSpec
    lockfile: ResolvedGitFileRef


# ---------------------------------------------------------------------------
# Determinism, precision, and parallelism
# ---------------------------------------------------------------------------


class TorchDeterminismSpec(ProtocolModel):
    """PyTorch, cuDNN, and cuBLAS determinism controls."""

    deterministic_algorithms: bool
    deterministic_warn_only: bool
    cudnn_deterministic: bool
    cudnn_benchmark: bool
    cublas_workspace_config: Literal[":16:8", ":4096:8"] | None


class TorchPrecisionSpec(ProtocolModel):
    """PyTorch numerical-precision controls that can affect output values."""

    float32_matmul_precision: Literal["highest", "high", "medium"]
    cudnn_allow_tf32: bool

    autocast_enabled: bool
    autocast_dtype: Literal["float16", "bfloat16"] | None

    @model_validator(mode="after")
    def validate_autocast(self) -> TorchPrecisionSpec:
        if self.autocast_enabled and self.autocast_dtype is None:
            raise ValueError("autocast_dtype is required when autocast_enabled is true")

        if not self.autocast_enabled and self.autocast_dtype is not None:
            raise ValueError(
                "autocast_dtype must be null when autocast_enabled is false"
            )

        return self


class ParallelismSpec(ProtocolModel):
    process_count: int = Field(ge=1)
    torch_intraop_threads: int = Field(ge=1)
    torch_interop_threads: int = Field(ge=1)
    dataloader_workers: int = Field(ge=0)


class ReproducibilitySpec(ProtocolModel):
    """Numerical controls applied to every stage in a run."""

    determinism: TorchDeterminismSpec
    precision: TorchPrecisionSpec
    parallelism: ParallelismSpec


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


class Measurement(ProtocolModel):
    """One observed metric value produced during a run stage."""

    run_id: RunId
    attempt_id: int = Field(ge=1)
    stage_id: StageId
    metric_id: MetricId

    value: float = Field(allow_inf_nan=False)
    measured_at: AwareDatetime

    epoch: int | None = Field(default=None, ge=0)
    step: int | None = Field(default=None, ge=0)


class MetricCriterion(ProtocolModel):
    metric_id: MetricId
    comparison: Literal["ge", "le"]
    threshold: float = Field(allow_inf_nan=False)


class BenchmarkSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    benchmark_id: BenchmarkId
    evaluation_dataset: ArtifactPointerRef
    splits: dict[InputName, ArtifactPointerRef] = Field(min_length=1)
    metrics: tuple[MetricCriterion, ...] = Field(min_length=1)
    confirmation_count: Literal[2] = 2

    @model_validator(mode="after")
    def validate_unique_metrics(self) -> BenchmarkSpec:
        metric_ids = tuple(criterion.metric_id for criterion in self.metrics)
        if len(set(metric_ids)) != len(metric_ids):
            raise ValueError("benchmark metric IDs must be unique")
        return self


# ---------------------------------------------------------------------------
# Experiment Specs
# ---------------------------------------------------------------------------

"""
Factors and levels
→ describe the available experimental dimensions

Variants
→ explicitly select the combinations we actually want to test

E.g., imagine the following ->

factors:
  - factor_id: aggregation
    levels:
      - dense
      - low_rank
      - attention

  - factor_id: rank
    levels:
      - not_applicable
      - rank_32
      - rank_64

  - factor_id: optimizer
    levels:
      - adamw
      - lion

  - factor_id: dropout
    levels:
      - dropout_0
      - dropout_01

The cartesian product would be 3 x 3 x 2 x 2 = 36 combinations. The plan
declares four meaningful variants:

variants:
  - baseline
  - low_rank_32
  - low_rank_64
  - attention_adamw

"""


class FactorSpec(ProtocolModel):
    factor_id: FactorId
    levels: tuple[LevelId, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_levels(self) -> FactorSpec:
        if len(set(self.levels)) != len(self.levels):
            raise ValueError("level IDs must be unique within a factor")
        return self


class ReplicateSpec(ProtocolModel):
    replicate_id: ReplicateId
    seed: int


class ExperimentSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    experiment_id: ExperimentId

    factors: tuple[FactorSpec, ...]
    variant_ids: tuple[VariantId, ...] = Field(min_length=1)
    replicates: tuple[ReplicateSpec, ...] = Field(min_length=1)
    metric_ids: tuple[MetricId, ...]

    @model_validator(mode="after")
    def validate_common_invariants(self) -> ExperimentSpec:
        factor_ids = tuple(factor.factor_id for factor in self.factors)
        if len(set(factor_ids)) != len(factor_ids):
            raise ValueError("factor IDs must be unique")

        if len(set(self.variant_ids)) != len(self.variant_ids):
            raise ValueError("variant IDs must be unique")

        replicate_ids = tuple(replicate.replicate_id for replicate in self.replicates)
        if len(set(replicate_ids)) != len(replicate_ids):
            raise ValueError("replicate IDs must be unique")

        replicate_seeds = tuple(replicate.seed for replicate in self.replicates)
        if len(set(replicate_seeds)) != len(replicate_seeds):
            raise ValueError("replicate seeds must be unique")

        if len(set(self.metric_ids)) != len(self.metric_ids):
            raise ValueError("metric IDs must be unique")

        return self


# ---------------------------------------------------------------------------
# Run primitives
# ---------------------------------------------------------------------------

AttemptStatus = Literal[
    "succeeded",
    "failed",
    "preempted",
    "cancelled",
]


class ResolvedStageRef(ProtocolModel):
    """Binds one completed stage to its immutable stage-result snapshot."""

    stage_id: StageId
    snapshot: StageResultSnapshotRef
    resolved_spec: SnapshotFileRef


class RunAttempt(ProtocolModel):
    attempt_id: int = Field(ge=1)
    status: AttemptStatus

    started_at: AwareDatetime
    completed_at: AwareDatetime

    resolved_stages: tuple[ResolvedStageRef, ...]
    measurement_files: tuple[ResolvedFileRef, ...]
    log_files: tuple[ResolvedFileRef, ...]

    failure_reason: str | None

    @model_validator(mode="after")
    def validate_common_invariants(self) -> RunAttempt:
        if self.status == "succeeded" and self.failure_reason is not None:
            raise ValueError("successful attempts must not have a failure reason")

        if self.status != "succeeded" and (
            self.failure_reason is None or not self.failure_reason.strip()
        ):
            raise ValueError(
                "failed, preempted, and cancelled attempts require a nonempty "
                "failure reason"
            )

        if self.completed_at <= self.started_at:
            raise ValueError("attempt completion must be after attempt start")

        unique = set()
        snapshots: set[StageResultSnapshotRef] = set()
        for stage in self.resolved_stages:
            if stage.stage_id in unique:
                raise ValueError("resolved stage IDs must be unique")
            unique.add(stage.stage_id)

            if stage.snapshot in snapshots:
                raise ValueError("resolved stages must use distinct snapshots")
            snapshots.add(stage.snapshot)

        if len(set(self.measurement_files)) != len(self.measurement_files):
            raise ValueError("measurement file references must be unique")

        if len(set(self.log_files)) != len(self.log_files):
            raise ValueError("log file references must be unique")

        if set(self.measurement_files) & set(self.log_files):
            raise ValueError("measurement and log file references must be disjoint")

        return self


class RunStageRef(ProtocolModel):
    """Identifies and verifies one stage spec in a run-plan snapshot."""

    stage_id: StageId
    spec: RepoRelPath
    sha256: SHA256
    bytes: int = Field(ge=0)


class RunSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    run_id: RunId
    experiment_id: ExperimentId
    variant_id: VariantId
    replicate_id: ReplicateId
    benchmark_id: BenchmarkId | None = None

    seed: int
    source: GitSource
    environment: GCEEnvironmentSpec
    reproducibility: ReproducibilitySpec

    stages: tuple[RunStageRef, ...] = Field(min_length=1)
    estimator: StageArtifactRef

    @model_validator(mode="after")
    def validate_common_invariants(self) -> RunSpec:
        stage_ids = tuple(stage.stage_id for stage in self.stages)
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("stage IDs must be unique")

        stage_spec_paths = tuple(stage.spec for stage in self.stages)
        if len(set(stage_spec_paths)) != len(stage_spec_paths):
            raise ValueError("stage spec paths must be unique")

        if self.estimator.stage_id not in set(stage_ids):
            raise ValueError("estimator must select a declared run stage")

        if self.estimator.artifact_name != MODEL_PARAMETERS:
            raise ValueError("estimator must select the model_parameters artifact")

        return self


class ResolvedRun(ProtocolModel):
    schema_version: Literal[1] = 1

    spec: ResolvedRunSpecRef

    status: Literal["succeeded", "failed", "cancelled"]

    attempts: tuple[RunAttempt, ...] = Field(min_length=1)
    successful_attempt_id: int | None

    completed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_common_invariants(self) -> ResolvedRun:
        unique_attempt_ids = set()
        successful_attempts = []
        previous_attempt: RunAttempt | None = None

        for index, attempt in enumerate(self.attempts):
            if attempt.attempt_id in unique_attempt_ids:
                raise ValueError("attempt IDs must be unique")
            unique_attempt_ids.add(attempt.attempt_id)

            if (
                previous_attempt is not None
                and attempt.attempt_id <= previous_attempt.attempt_id
            ):
                raise ValueError("attempt IDs must increase in execution order")

            if (
                previous_attempt is not None
                and attempt.started_at < previous_attempt.completed_at
            ):
                raise ValueError(
                    "an attempt cannot begin before the previous attempt finishes"
                )

            if attempt.status == "succeeded":
                successful_attempts.append(attempt)
                if index != len(self.attempts) - 1:
                    raise ValueError("no attempt may occur after a successful attempt")

            previous_attempt = attempt

        if any(self.completed_at < attempt.completed_at for attempt in self.attempts):
            raise ValueError(
                "resolved run cannot complete before one of its attempts completes"
            )

        if self.status == "succeeded":
            if len(successful_attempts) != 1:
                raise ValueError("A succeeded run requires one successful attempt")

            successful_attempt = successful_attempts[0]
            if self.successful_attempt_id != successful_attempt.attempt_id:
                raise ValueError(
                    "successful_attempt_id must identify the successful attempt"
                )

        else:
            if successful_attempts:
                raise ValueError("A failed or cancelled run cannot have a success")
            if self.successful_attempt_id is not None:
                raise ValueError(
                    "successful_attempt_id must be null without a successful attempt"
                )

        return self


class BenchmarkResult(ProtocolModel):
    schema_version: Literal[1] = 1
    benchmark: ResolvedBenchmarkSpecRef
    run: ResolvedRunRef
    confirmation: RunAttempt
    status: Literal["passed", "failed"]
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_confirmation(self) -> BenchmarkResult:
        if self.confirmation.status != "succeeded":
            raise ValueError("benchmark confirmation attempt must succeed")
        if self.completed_at < self.confirmation.completed_at:
            raise ValueError(
                "benchmark completion cannot precede confirmation completion"
            )
        return self


# ---------------------------------------------------------------------------
# Observed execution context
# ---------------------------------------------------------------------------


class GCEHostContext(ProtocolModel):
    provider: Literal["gce"] = "gce"

    machine_type: NonEmptyStr
    zone: NonEmptyStr

    guest_os_name: NonEmptyStr
    guest_os_version: NonEmptyStr
    kernel_release: NonEmptyStr


class CPUContext(ProtocolModel):
    """
    The CPU available to the execution, including instruction sets that can
    change numerical-library implementation choices.
    """

    architecture: NonEmptyStr
    model: NonEmptyStr
    instruction_features: tuple[NonEmptyStr, ...] = Field(min_length=1)


class CPUBackendContext(ProtocolModel):
    """Records that PyTorch executed without a GPU backend."""

    kind: Literal["cpu"] = "cpu"
    device: Literal["cpu"] = "cpu"


class CUDADeviceContext(ProtocolModel):
    ordinal: int = Field(ge=0)
    model: NonEmptyStr

    compute_capability_major: int = Field(ge=0)
    compute_capability_minor: int = Field(ge=0)

    memory_bytes: int = Field(gt=0)


class CUDABackendContext(ProtocolModel):
    """The CUDA backend and devices observed during execution."""

    kind: Literal["cuda"] = "cuda"

    gpu_devices: tuple[CUDADeviceContext, ...] = Field(min_length=1)

    nvidia_driver_version: NonEmptyStr
    pytorch_cuda_version: NonEmptyStr
    cudnn_version: NonEmptyStr


ComputeBackendContext = Annotated[
    CPUBackendContext | CUDABackendContext,
    Field(discriminator="kind"),
]


class NativeLibraryContext(ProtocolModel):
    implementation: NonEmptyStr
    version: NonEmptyStr


class NativeThreadPoolContext(NativeLibraryContext):
    threads: int = Field(ge=1)


class NumericalRuntimeContext(ProtocolModel):
    python_version: NonEmptyStr
    pytorch_version: NonEmptyStr
    numpy_version: NonEmptyStr

    blas: NativeLibraryContext
    lapack: NativeLibraryContext
    native_thread_pools: tuple[NativeThreadPoolContext, ...]


class RandomnessContext(ProtocolModel):
    python_seed: int
    numpy_seed: int
    torch_seed: int
    dataloader_seed: int

    @model_validator(mode="after")
    def validate_shared_seed(self) -> RandomnessContext:
        seeds = {
            self.python_seed,
            self.numpy_seed,
            self.torch_seed,
            self.dataloader_seed,
        }
        if len(seeds) != 1:
            raise ValueError("all recorded random-number generators must use one seed")
        return self


class ExecutionContext(ProtocolModel):
    """
    Facts observed from the host and running process.

    The GCE environment records the machine image and dependency lockfile
    supplied to the execution. This class records the host and runtime
    conditions under which it ran.
    """

    host: GCEHostContext
    cpu: CPUContext
    backend: ComputeBackendContext
    numerical_runtime: NumericalRuntimeContext
    randomness: RandomnessContext
    determinism: TorchDeterminismSpec
    precision: TorchPrecisionSpec
    parallelism: ParallelismSpec


# ---------------------------------------------------------------------------
# Stage input references
# ---------------------------------------------------------------------------


class StoredInputRef(ProtocolModel):
    """A promoted artifact selected before the run begins."""

    kind: Literal["stored"] = "stored"
    pointer: ArtifactPointerRef
    path: RepoRelPath


class FutureInputRef(ProtocolModel):
    """One named artifact produced by an earlier stage in the same run."""

    kind: Literal["future"] = "future"
    producer_stage_id: StageId
    producer_artifact: ArtifactName


InternalInputRef = Annotated[
    StoredInputRef | FutureInputRef,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Stage specifications
# ---------------------------------------------------------------------------


class SingleFileArtifactSpec(ProtocolModel):
    """Declares one named artifact written as one file."""

    kind: Literal["file"] = "file"
    path: RepoRelPath
    loader: ArtifactLoaderId


class BundleArtifactSpec(ProtocolModel):
    """Declares one named artifact written beneath one directory root."""

    kind: Literal["bundle"] = "bundle"
    path: RepoRelPath
    loader: ArtifactLoaderId


ArtifactSpec = Annotated[
    SingleFileArtifactSpec | BundleArtifactSpec,
    Field(discriminator="kind"),
]


class BaseSpec(ProtocolModel):
    """Execution request recorded before a stage runs."""

    kind: str
    schema_version: Literal[1] = 1

    script: RepoRelPath

    environment: GCEEnvironmentSpec | None = None

    artifacts: dict[ArtifactName, ArtifactSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_artifact_paths(self) -> BaseSpec:
        artifact_roots: dict[RepoRelPath, ArtifactName] = {}

        for name, artifact in self.artifacts.items():
            if repo_file_paths_overlap(artifact.path, self.script):
                raise ValueError(
                    f"artifact {name!r} path collides with the stage script"
                )

            for previous_path, previous_name in artifact_roots.items():
                if repo_file_paths_overlap(artifact.path, previous_path):
                    raise ValueError(
                        f"artifact roots for {previous_name!r} and {name!r} "
                        f"overlap: {previous_path} and {artifact.path}"
                    )

            artifact_roots[artifact.path] = name

        return self


class DownloadSpec(BaseSpec):
    kind: Literal["download"] = "download"  # pyright: ignore[reportIncompatibleVariableOverride]
    inputs: dict[InputName, RemoteFileRef] = Field(min_length=1, max_length=1)


class InternalSpec(BaseSpec):
    inputs: dict[InputName, InternalInputRef] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_local_path_collisions(self) -> InternalSpec:
        stored_inputs = {
            name: ref for name, ref in self.inputs.items() if ref.kind == "stored"
        }

        materialization_paths: dict[RepoRelPath, InputName] = {}

        for name, ref in stored_inputs.items():
            for previous_path, previous_name in materialization_paths.items():
                if repo_file_paths_overlap(ref.path, previous_path):
                    raise ValueError(
                        f"input materialization paths for {previous_name!r} and "
                        f"{name!r} collide: {previous_path} and {ref.path}"
                    )

            materialization_paths[ref.path] = name

            if repo_file_paths_overlap(ref.path, self.script):
                raise ValueError(f"input {name!r} path collides with the stage script")

            for artifact_name, artifact in self.artifacts.items():
                if repo_file_paths_overlap(artifact.path, ref.path):
                    raise ValueError(
                        f"artifact {artifact_name!r} path collides with input {name!r}"
                    )

        return self


class BuildParams(ProtocolModel):
    pass


class EmbedParams(ProtocolModel):
    pass


class TrainParams(ProtocolModel):
    epochs: int = Field(ge=1)
    batch_size: int = Field(ge=1)
    learning_rate: float = Field(gt=0)


class EvaluateParams(ProtocolModel):
    metric_ids: tuple[MetricId, ...] = Field(min_length=1)
    split_inputs: tuple[InputName, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_names(self) -> EvaluateParams:
        if len(set(self.metric_ids)) != len(self.metric_ids):
            raise ValueError("evaluation metric IDs must be unique")
        if len(set(self.split_inputs)) != len(self.split_inputs):
            raise ValueError("evaluation split input names must be unique")
        return self


class BuildSpec(InternalSpec):
    kind: Literal["build"] = "build"  # pyright: ignore[reportIncompatibleVariableOverride]
    params: BuildParams


class EmbedSpec(InternalSpec):
    kind: Literal["embed"] = "embed"  # pyright: ignore[reportIncompatibleVariableOverride]
    params: EmbedParams


class TrainSpec(InternalSpec):
    kind: Literal["train"] = "train"  # pyright: ignore[reportIncompatibleVariableOverride]
    params: TrainParams

    @model_validator(mode="after")
    def validate_terminal_checkpoint(self) -> TrainSpec:
        required_artifacts = {MODEL_PARAMETERS, CONTINUATION_STATE}
        missing_artifacts = required_artifacts - set(self.artifacts)
        if missing_artifacts:
            missing = ", ".join(sorted(missing_artifacts))
            raise ValueError(
                f"training stages must declare terminal checkpoint artifacts: {missing}"
            )

        model_input = self.inputs.get(CHECKPOINT_MODEL_INPUT)
        state_input = self.inputs.get(CHECKPOINT_STATE_INPUT)

        if (model_input is None) != (state_input is None):
            raise ValueError("checkpoint inputs must be declared together")

        if model_input is None or state_input is None:
            return self

        if model_input.kind != state_input.kind:
            raise ValueError("checkpoint inputs must use the same input kind")

        if model_input.kind == "future" and state_input.kind == "future":
            if model_input.producer_stage_id != state_input.producer_stage_id:
                raise ValueError(
                    "checkpoint inputs must select one checkpoint-producing stage"
                )
            if model_input.producer_artifact != MODEL_PARAMETERS:
                raise ValueError(
                    "checkpoint_model_parameters must select model_parameters"
                )
            if state_input.producer_artifact != CONTINUATION_STATE:
                raise ValueError(
                    "checkpoint_continuation_state must select continuation_state"
                )

        return self


class EvaluateSpec(InternalSpec):
    kind: Literal["evaluate"] = "evaluate"  # pyright: ignore[reportIncompatibleVariableOverride]
    params: EvaluateParams

    @model_validator(mode="after")
    def validate_evaluation_contract(self) -> EvaluateSpec:
        model_input = self.inputs.get(EVALUATION_MODEL_INPUT)
        if model_input is None:
            raise ValueError("evaluation requires a model_parameters input")

        dataset_input = self.inputs.get(EVALUATION_DATASET_INPUT)
        if dataset_input is None:
            raise ValueError("evaluation requires an evaluation_dataset input")
        if dataset_input.kind != "stored":
            raise ValueError("evaluation_dataset must be a stored input")

        reserved_inputs = {EVALUATION_MODEL_INPUT, EVALUATION_DATASET_INPUT}
        if reserved_inputs & set(self.params.split_inputs):
            raise ValueError(
                "evaluation split inputs must differ from reserved input names"
            )

        missing_splits = set(self.params.split_inputs) - set(self.inputs)
        if missing_splits:
            missing = ", ".join(sorted(missing_splits))
            raise ValueError(f"evaluation split inputs are undeclared: {missing}")

        for split_name in self.params.split_inputs:
            if self.inputs[split_name].kind != "stored":
                raise ValueError(
                    f"evaluation split input {split_name!r} must be stored"
                )

        if model_input.kind == "future":
            if model_input.producer_artifact != MODEL_PARAMETERS:
                raise ValueError("same-run evaluation must consume model_parameters")

        if PREDICTIONS not in self.artifacts:
            raise ValueError("evaluation must declare a predictions artifact")

        forbidden_outputs = {MODEL_PARAMETERS, CONTINUATION_STATE} & set(self.artifacts)
        if forbidden_outputs:
            raise ValueError("evaluation cannot publish training checkpoint artifacts")

        return self


class BuildVariantStageParams(ProtocolModel):
    kind: Literal["build"] = "build"
    stage_id: StageId
    params: BuildParams


class EmbedVariantStageParams(ProtocolModel):
    kind: Literal["embed"] = "embed"
    stage_id: StageId
    params: EmbedParams


class TrainVariantStageParams(ProtocolModel):
    kind: Literal["train"] = "train"
    stage_id: StageId
    params: TrainParams


class EvaluateVariantStageParams(ProtocolModel):
    kind: Literal["evaluate"] = "evaluate"
    stage_id: StageId
    params: EvaluateParams


VariantStageParams = Annotated[
    BuildVariantStageParams
    | EmbedVariantStageParams
    | TrainVariantStageParams
    | EvaluateVariantStageParams,
    Field(discriminator="kind"),
]


class VariantSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    experiment_id: ExperimentId
    variant_id: VariantId
    levels: dict[FactorId, LevelId]
    stage_params: tuple[VariantStageParams, ...] = ()

    @model_validator(mode="after")
    def validate_unique_stage_ids(self) -> VariantSpec:
        stage_ids = tuple(stage.stage_id for stage in self.stage_params)
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("variant stage IDs must be unique")
        return self


Spec = Annotated[
    DownloadSpec | BuildSpec | EmbedSpec | TrainSpec | EvaluateSpec,
    Field(discriminator="kind"),
]

# ---------------------------------------------------------------------------
# Resolved input refs
# ---------------------------------------------------------------------------


class ResolvedStoredInputRef(ProtocolModel):
    kind: Literal["stored"] = "stored"
    pointer: ResolvedArtifactPointerRef


class ResolvedFutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    producer: ResolvedStageRef


ResolvedInternalInputRef = Annotated[
    ResolvedStoredInputRef | ResolvedFutureInputRef,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Resolved execution records
# ---------------------------------------------------------------------------


class ResolvedSingleFileArtifact(ProtocolModel):
    """Records the exact file representing one artifact."""

    kind: Literal["file"] = "file"
    file: SnapshotFileRef


class ResolvedBundleMember(ProtocolModel):
    """Records one exact file beneath a bundle artifact's directory root."""

    relative_path: RepoRelPath
    file: SnapshotFileRef


class ResolvedBundleArtifact(ProtocolModel):
    """Records every exact file representing one bundle artifact."""

    kind: Literal["bundle"] = "bundle"
    members: tuple[ResolvedBundleMember, ...] = Field(min_length=2)


ResolvedArtifact = Annotated[
    ResolvedSingleFileArtifact | ResolvedBundleArtifact,
    Field(discriminator="kind"),
]


class ResolvedBaseSpec(ProtocolModel):
    """
    Record written after an execution has produced and hashed its output.
    """

    schema_version: Literal[1] = 1
    kind: str

    spec: BaseSpec
    source: ResolvedGitFileRef

    environment: ResolvedGCEEnvironment
    execution_context: ExecutionContext

    command: tuple[str, ...] = Field(min_length=1)

    artifacts: dict[ArtifactName, ResolvedArtifact] = Field(min_length=1)
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_common_invariants(self) -> ResolvedBaseSpec:
        if not self.command[0]:
            raise ValueError("command executable must be nonempty")

        if self.source.stored_at.path != self.spec.script:
            raise ValueError(
                "resolved source entrypoint must match the stage spec script path"
            )

        if set(self.artifacts) != set(self.spec.artifacts):
            raise ValueError(
                "resolved artifact names must match declared artifact names"
            )

        for name, resolved_artifact in self.artifacts.items():
            declared_artifact = self.spec.artifacts[name]

            if resolved_artifact.kind != declared_artifact.kind:
                raise ValueError(
                    f"resolved artifact {name!r} kind must match its declaration"
                )

            if declared_artifact.kind == "file" and resolved_artifact.kind == "file":
                if resolved_artifact.file.path != declared_artifact.path:
                    raise ValueError(
                        f"resolved artifact {name!r} path must match its declaration"
                    )
                continue

            if (
                declared_artifact.kind == "bundle"
                and resolved_artifact.kind == "bundle"
            ):
                relative_paths = tuple(
                    member.relative_path for member in resolved_artifact.members
                )
                if len(set(relative_paths)) != len(relative_paths):
                    raise ValueError(
                        f"resolved artifact {name!r} member paths must be unique"
                    )
                if relative_paths != tuple(sorted(relative_paths)):
                    raise ValueError(
                        f"resolved artifact {name!r} members must use canonical order"
                    )

                for member in resolved_artifact.members:
                    expected_path = f"{declared_artifact.path}/{member.relative_path}"
                    if member.file.path != expected_path:
                        raise ValueError(
                            f"resolved artifact {name!r} member path must equal "
                            "its declared bundle root plus relative path"
                        )

        requested_environment = self.spec.environment
        if requested_environment is not None:
            resolved_image = self.environment.machine_image
            requested_image = requested_environment.machine_image

            if (
                resolved_image.project != requested_image.project
                or resolved_image.name != requested_image.name
            ):
                raise ValueError(
                    "resolved machine image must match the stage environment override"
                )

            if self.environment.machine_type != requested_environment.machine_type:
                raise ValueError(
                    "resolved machine type must match the stage environment override"
                )

            if self.environment.compute != requested_environment.compute:
                raise ValueError(
                    "resolved compute must match the stage environment override"
                )

            resolved_lockfile = self.environment.lockfile
            requested_lockfile = requested_environment.lockfile

            if (
                resolved_lockfile.stored_at.repository != requested_lockfile.repository
                or resolved_lockfile.stored_at.commit != requested_lockfile.commit
                or resolved_lockfile.stored_at.path != requested_lockfile.path
            ):
                raise ValueError(
                    "resolved lockfile must match the stage environment override"
                )

        if self.environment.machine_type != self.execution_context.host.machine_type:
            raise ValueError(
                "resolved machine type must match the observed host machine type"
            )

        compute = self.environment.compute
        backend = self.execution_context.backend

        if compute.kind != backend.kind:
            raise ValueError("resolved compute kind must match the observed backend")

        if compute.kind == "cuda" and backend.kind == "cuda":
            if len(backend.gpu_devices) != compute.count:
                raise ValueError(
                    "observed CUDA device count must match the resolved compute"
                )
            if any(device.model != compute.model for device in backend.gpu_devices):
                raise ValueError(
                    "observed CUDA device models must match the resolved compute"
                )

        return self


class ResolvedDownloadSpec(ResolvedBaseSpec):
    """
    Download receipt.

    The input remains the source URL because no artifact exists before the
    download. Its artifacts are the first verified values created from that URL.
    """

    kind: Literal["download"] = "download"  # pyright: ignore[reportIncompatibleVariableOverride]
    spec: DownloadSpec  # pyright: ignore[reportIncompatibleVariableOverride]

    inputs: dict[InputName, RemoteFileRef]
    retrieved_at: AwareDatetime

    @model_validator(mode="after")
    def validate_download_inputs(self) -> ResolvedDownloadSpec:
        if self.inputs != self.spec.inputs:
            raise ValueError(
                "resolved download inputs must match the stage spec remote inputs"
            )

        if self.retrieved_at > self.completed_at:
            raise ValueError("download retrieval cannot follow stage completion")

        return self


class ResolvedInternalSpec(ResolvedBaseSpec):
    """
    Receipt for an operation that consumes previously produced artifacts.
    """

    spec: InternalSpec  # pyright: ignore[reportIncompatibleVariableOverride]
    inputs: dict[InputName, ResolvedInternalInputRef]

    @model_validator(mode="after")
    def validate_internal_inputs(self) -> ResolvedInternalSpec:
        if set(self.inputs) != set(self.spec.inputs):
            raise ValueError(
                "resolved input names must match the stage spec input names"
            )

        for name, resolved_input in self.inputs.items():
            spec_input = self.spec.inputs[name]

            if resolved_input.kind != spec_input.kind:
                raise ValueError(
                    f"resolved input {name!r} kind must match the stage spec input"
                )

            if (
                resolved_input.kind == "stored"
                and spec_input.kind == "stored"
                and resolved_input.pointer.stored_at != spec_input.pointer
            ):
                raise ValueError(
                    f"resolved input {name!r} pointer location must match "
                    "the stage spec pointer location"
                )

        return self


class ResolvedBuildSpec(ResolvedInternalSpec):
    kind: Literal["build"] = "build"  # pyright: ignore[reportIncompatibleVariableOverride]
    spec: BuildSpec  # pyright: ignore[reportIncompatibleVariableOverride]


class ResolvedEmbedSpec(ResolvedInternalSpec):
    kind: Literal["embed"] = "embed"  # pyright: ignore[reportIncompatibleVariableOverride]
    spec: EmbedSpec  # pyright: ignore[reportIncompatibleVariableOverride]


class ResolvedTrainSpec(ResolvedInternalSpec):
    kind: Literal["train"] = "train"  # pyright: ignore[reportIncompatibleVariableOverride]
    spec: TrainSpec  # pyright: ignore[reportIncompatibleVariableOverride]


class ResolvedEvaluateSpec(ResolvedInternalSpec):
    kind: Literal["evaluate"] = "evaluate"  # pyright: ignore[reportIncompatibleVariableOverride]
    spec: EvaluateSpec  # pyright: ignore[reportIncompatibleVariableOverride]


ResolvedSpec = Annotated[
    ResolvedDownloadSpec
    | ResolvedBuildSpec
    | ResolvedEmbedSpec
    | ResolvedTrainSpec
    | ResolvedEvaluateSpec,
    Field(discriminator="kind"),
]
