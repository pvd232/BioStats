"""Fourth draft of the Pydantic models for the MANTRA provenance protocol.

This version separates authored execution requests, verified data artifacts,
the exact Git source tree, the GCE machine-image environment, observed
execution conditions, and the manifest connecting an artifact to its producer.
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

class GitSource(ProtocolModel):
    """A file stored at an exact Git revision."""

    kind: Literal["git"] = "git"
    repository: HttpUrl
    commit: GitCommit


class GitFileRef(GitSource):
    """A file stored at an exact Git revision."""
    path: RepoRelPath


class ArtifactPointerRef(GitFileRef):
    """A Git reference to the pointer selecting a promoted artifact manifest."""


class HuggingFaceFileRef(ProtocolModel):
    """A file stored at an exact Hugging Face repository revision."""

    kind: Literal["huggingface"] = "huggingface"
    repository: str = Field(min_length=1)
    commit: GitCommit
    path: RepoRelPath
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


class ResolvedGitFileRef(GitFileRef):
    """
    sha256 identifies the file contents.
    bytes records the file length.

    """

    sha256: SHA256
    bytes: int = Field(ge=0)


class ResolvedArtifactManifestRef(ResolvedFileRef):
    kind: Literal["artifact_manifest"] = "artifact_manifest"


class ResolvedArtifactPointerRef(ResolvedFileRef):
    kind: Literal["artifact_pointer"] = "artifact_pointer"
    stored_at: ArtifactPointerRef


# ---------------------------------------------------------------------------
# Artifact connectors
# ---------------------------------------------------------------------------


class ArtifactManifest(ProtocolModel):
    """
    Connects an artifact to the files that explain how it was produced.

    Each field points to an exact file and therefore carries its own SHA-256.
    """

    schema_version: Literal[1] = 1

    artifact: ResolvedFileRef
    resolved_spec: ResolvedFileRef
    spec: ResolvedFileRef
    source: ResolvedGitFileRef

    created_at: AwareDatetime


class ArtifactPointer(ProtocolModel):
    """
    Selects the manifest for an artifact chosen as a reusable input.

    The manifest identifies the artifact bytes and records the execution that
    created them. Updating the Git-tracked pointer selects a different manifest
    without moving or overwriting either artifact.
    """

    schema_version: Literal[1] = 1
    manifest: ResolvedArtifactManifestRef


# ---------------------------------------------------------------------------
# Authored and resolved GCE environment
# ---------------------------------------------------------------------------


class GCEMachineImageRef(ProtocolModel):
    project: str = Field(min_length=1)
    name: str = Field(min_length=1)


class ResolvedGCEMachineImageRef(GCEMachineImageRef):
    id: str = Field(min_length=1)


class GCEEnvironmentSpec(ProtocolModel):
    kind: Literal["gce"] = "gce"

    machine_image: GCEMachineImageRef
    lockfile: GitFileRef


class ResolvedGCEEnvironment(GCEEnvironmentSpec):
    machine_image: ResolvedGCEMachineImageRef
    lockfile: ResolvedGitFileRef


# ---------------------------------------------------------------------------
# Randomness, determinism, and precision
# ---------------------------------------------------------------------------


class RNGSeedSpec(ProtocolModel):
    """
    Seeds for the run-wide random-number generators controlled by MANTRA.

    Algorithm-specific generators remain parameters of the operation that
    creates them.
    """

    python_seed: int
    numpy_seed: int
    torch_seed: int
    dataloader_seed: int | None


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


class StrictReproducibilitySpec(ProtocolModel):
    """
    Requests an execution for which MANTRA expects a replay under the recorded
    conditions to reproduce the output bytes.
    """

    mode: Literal["strict"] = "strict"

    randomness: RNGSeedSpec
    determinism: TorchDeterminismSpec
    precision: TorchPrecisionSpec

    @model_validator(mode="after")
    def validate_strict_policy(self) -> StrictReproducibilitySpec:
        determinism = self.determinism

        if not determinism.deterministic_algorithms:
            raise ValueError("strict mode requires deterministic_algorithms=true")

        if determinism.deterministic_warn_only:
            raise ValueError("strict mode requires deterministic_warn_only=false")

        if not determinism.cudnn_deterministic:
            raise ValueError("strict mode requires cudnn_deterministic=true")

        if determinism.cudnn_benchmark:
            raise ValueError("strict mode requires cudnn_benchmark=false")

        return self


class RelaxedReproducibilitySpec(ProtocolModel):
    """
    Records the same controls as strict mode while allowing performance-oriented
    algorithms, defaults, and nondeterministic implementations.
    """

    mode: Literal["relaxed"] = "relaxed"

    randomness: RNGSeedSpec
    determinism: TorchDeterminismSpec
    precision: TorchPrecisionSpec


ReproducibilitySpec = Annotated[
    StrictReproducibilitySpec | RelaxedReproducibilitySpec,
    Field(discriminator="mode"),
]

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

The cartesian product would be 3 x 3 x 2 x 2 = 36 combinations. But we only specify four meaningful variants:

variants:
  - baseline
  - low_rank_32
  - low_rank_64
  - attention_adamw

"""


class FactorSpec(ProtocolModel):
    factor_id: FactorId
    levels: tuple[LevelId, ...] = Field(min_length=2)


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

        if len(set(self.metric_ids)) != len(self.metric_ids):
            raise ValueError("metric IDs must be unique")

        return self


class VariantSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    experiment_id: ExperimentId
    variant_id: VariantId

    levels: dict[FactorId, LevelId]


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
    """Binds a completed run stage to its resolved execution record."""

    stage_id: StageId
    resolved_spec: ResolvedFileRef


class RunAttempt(ProtocolModel):
    attempt_id: int = Field(ge=1)
    status: AttemptStatus

    started_at: AwareDatetime
    completed_at: AwareDatetime

    completed_stages: tuple[ResolvedStageRef, ...]
    artifact_manifests: tuple[ResolvedArtifactManifestRef, ...]
    measurement_files: tuple[ResolvedFileRef, ...]
    log_files: tuple[ResolvedFileRef, ...]

    failure_reason: str | None

    @model_validator(mode="after")
    def validate_common_invariants(self) -> RunAttempt:
        if self.status == "succeeded" and self.failure_reason is not None:
            raise ValueError("Successful runs should not have a failure reason")

        if (
            self.status != "succeeded"
            and self.failure_reason is None
            or self.failure_reason == ""
        ):
            raise ValueError("Must give a valid reason for legitimate failure")

        if self.completed_at <= self.started_at:
            raise ValueError("Invalid chronological order of timestamps")

        unique = set()
        for stage in self.completed_stages:
            if stage.stage_id in unique:
                raise ValueError("No duplicate stages")
            unique.add(stage.stage_id)
        return self


class StageSpec(ProtocolModel):
    stage_id: StageId
    spec: RepoRelPath


class RunSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    run_id: RunId
    experiment_id: ExperimentId
    variant_id: VariantId
    replicate_id: ReplicateId

    seed: int
    source: GitSource

    stages: tuple[StageSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_common_invariants(self) -> RunSpec:
        stage_ids = tuple(stage.stage_id for stage in self.stages)
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("stage IDs must be unique")

        stage_spec_paths = tuple(stage.spec for stage in self.stages)
        if len(set(stage_spec_paths)) != len(stage_spec_paths):
            raise ValueError("stage spec paths must be unique")

        return self


class ResolvedRun(ProtocolModel):
    schema_version: Literal[1] = 1

    run: RunSpec
    run_file: ResolvedFileRef

    status: Literal["succeeded", "failed", "cancelled"]

    attempts: tuple[RunAttempt, ...] = Field(min_length=1)
    successful_attempt_id: int | None

    completed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_common_invariants(self) -> ResolvedRun:
        unique_attempt_ids = set()
        successful_attempts = []
        expected_stage_ids = tuple(stage.stage_id for stage in self.run.stages)

        for index, attempt in enumerate(self.attempts):
            if attempt.attempt_id in unique_attempt_ids:
                raise ValueError("No duplicative attempts")
            unique_attempt_ids.add(attempt.attempt_id)

            completed_stage_ids = tuple(
                stage.stage_id for stage in attempt.completed_stages
            )
            if completed_stage_ids != expected_stage_ids[: len(completed_stage_ids)]:
                raise ValueError(
                    "Completed stages must follow the run's declared stage order"
                )

            if attempt.status == "succeeded":
                successful_attempts.append(attempt)
                if index != len(self.attempts) - 1:
                    raise ValueError("No attempt may occur after a successful attempt")

        if self.status == "succeeded":
            if len(successful_attempts) != 1:
                raise ValueError("A succeeded run requires one successful attempt")

            successful_attempt = successful_attempts[0]
            if self.successful_attempt_id != successful_attempt.attempt_id:
                raise ValueError(
                    "successful_attempt_id must identify the successful attempt"
                )

            completed_stage_ids = tuple(
                stage.stage_id for stage in successful_attempt.completed_stages
            )
            if completed_stage_ids != expected_stage_ids:
                raise ValueError(
                    "The successful attempt must complete every run stage in order"
                )
        else:
            if successful_attempts:
                raise ValueError("A failed or cancelled run cannot have a success")
            if self.successful_attempt_id is not None:
                raise ValueError(
                    "successful_attempt_id must be null without a successful attempt"
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

    gpu_devices: tuple[CUDADeviceContext, ...] = Field(
        min_length=1,
        max_length=1,
    )

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
    threads: Literal[1] = 1


class NumericalRuntimeContext(ProtocolModel):
    python_version: NonEmptyStr
    pytorch_version: NonEmptyStr
    numpy_version: NonEmptyStr

    blas: NativeLibraryContext
    lapack: NativeLibraryContext
    native_thread_pools: tuple[NativeThreadPoolContext, ...]


class ParallelismContext(ProtocolModel):
    """Process, thread, worker, and distributed settings actually used."""

    process_count: Literal[1] = 1
    torch_intraop_threads: Literal[1] = 1
    torch_interop_threads: Literal[1] = 1
    dataloader_workers: Literal[0] = 0


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
    parallelism: ParallelismContext


# ---------------------------------------------------------------------------
# Authored input references
# ---------------------------------------------------------------------------

"""

Git pointer file
inputs/models/current_weights.pt.pointer.yaml
        ↓
remote artifact manifest
        ↓
remote weights.pt bytes
        ↓
local execution binding
inputs/models/current_weights.pt

"""


class StoredInputRef(ProtocolModel):
    """A promoted artifact selected before the run begins."""

    kind: Literal["stored"] = "stored"
    pointer: ArtifactPointerRef
    path: RepoRelPath


class FutureInputRef(ProtocolModel):
    """The declared output of an earlier stage in the same run."""

    kind: Literal["future"] = "future"
    producer_stage_id: StageId


InternalInputRef = Annotated[
    StoredInputRef | FutureInputRef,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Authored specifications
# ---------------------------------------------------------------------------


class BaseSpec(ProtocolModel):
    """
    Human-authored execution request.

    Inputs describe where required files should come from. The output is the
    repository-relative path where the command must write its one artifact.
    """

    schema_version: Literal[1] = 1
    kind: str

    inputs: dict[InputName, FileRef]
    script: RepoRelPath

    environment: GCEEnvironmentSpec
    reproducibility: ReproducibilitySpec

    output: RepoRelPath


class DownloadSpec(BaseSpec):
    kind: Literal["download"] = "download"
    inputs: dict[InputName, RemoteFileRef] = Field(min_length=1)


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

            if repo_file_paths_overlap(self.output, ref.path):
                raise ValueError(f"stage output path collides with input {name!r}")

        if repo_file_paths_overlap(self.output, self.script):
            raise ValueError("stage output path collides with the stage script")

        return self


class BuildParams(ProtocolModel):
    pass


class EmbedParams(ProtocolModel):
    pass


class TrainParams(ProtocolModel):
    epochs: int = Field(ge=1)
    batch_size: int = Field(ge=1)
    learning_rate: float = Field(gt=0)


class BuildSpec(InternalSpec):
    kind: Literal["build"] = "build"
    params: BuildParams


class EmbedSpec(InternalSpec):
    kind: Literal["embed"] = "embed"
    params: EmbedParams


class TrainSpec(InternalSpec):
    kind: Literal["train"] = "train"
    params: TrainParams


Spec = Annotated[
    DownloadSpec | BuildSpec | EmbedSpec | TrainSpec,
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
    manifest: ResolvedArtifactManifestRef


ResolvedInternalInputRef = Annotated[
    ResolvedStoredInputRef | ResolvedFutureInputRef,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Resolved execution records
# ---------------------------------------------------------------------------

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


    output: ResolvedFileRef
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_common_invariants(self) -> ResolvedBaseSpec:
        if self.kind != self.spec.kind:
            raise ValueError(
                "resolved spec kind must match the embedded authored spec kind"
            )

        if not self.command[0]:
            raise ValueError("command executable must be nonempty")

        if self.source.path != self.spec.script:
            raise ValueError(
                "resolved source entrypoint must match the authored script path"
            )

        if self.output.stored_at.path != self.spec.output:
            raise ValueError(
                "resolved output path must match intended spec output path"
            )

        resolved_image = self.environment.machine_image
        requested_image = self.spec.environment.machine_image

        if (
            resolved_image.project != requested_image.project
            or resolved_image.name != requested_image.name
        ):
            raise ValueError(
                "resolved machine image must match the requested machine image"
            )

        resolved_lockfile = self.environment.lockfile
        requested_lockfile = self.spec.environment.lockfile

        if (
            resolved_lockfile.repository != requested_lockfile.repository
            or resolved_lockfile.commit != requested_lockfile.commit
            or resolved_lockfile.path != requested_lockfile.path
        ):
            raise ValueError("resolved lockfile must match the requested Git file")

        reproducibility = self.spec.reproducibility
        backend = self.execution_context.backend

        if (
            reproducibility.mode == "strict"
            and backend.kind == "cuda"
            and reproducibility.determinism.cublas_workspace_config is None
        ):
            raise ValueError("strict CUDA execution requires cublas_workspace_config")

        return self


class ResolvedDownloadSpec(ResolvedBaseSpec):
    """
    Download receipt.

    The input remains the source URL because no artifact exists before the
    download. The output is the first verified artifact created from that URL.
    """

    kind: Literal["download"] = "download"
    spec: DownloadSpec

    inputs: dict[InputName, RemoteFileRef]

    @model_validator(mode="after")
    def validate_download_inputs(self) -> ResolvedDownloadSpec:
        if self.inputs != self.spec.inputs:
            raise ValueError(
                "resolved download inputs must match the authored remote inputs"
            )

        return self


class ResolvedInternalSpec(ResolvedBaseSpec):
    """
    Receipt for an operation that consumes previously produced artifacts.
    """

    spec: InternalSpec
    inputs: dict[InputName, ResolvedInternalInputRef]

    @model_validator(mode="after")
    def validate_internal_inputs(self) -> ResolvedInternalSpec:
        if set(self.inputs) != set(self.spec.inputs):
            raise ValueError(
                "resolved input names must match the authored input names"
            )

        for name, resolved_input in self.inputs.items():
            authored_input = self.spec.inputs[name]

            if resolved_input.kind != authored_input.kind:
                raise ValueError(
                    f"resolved input {name!r} kind must match the authored input"
                )

            if (
                resolved_input.kind == "stored"
                and authored_input.kind == "stored"
                and resolved_input.pointer.stored_at != authored_input.pointer
            ):
                raise ValueError(
                    f"resolved input {name!r} pointer location must match "
                    "the authored pointer location"
                )

        return self


class ResolvedBuildSpec(ResolvedInternalSpec):
    kind: Literal["build"] = "build"
    spec: BuildSpec


class ResolvedEmbedSpec(ResolvedInternalSpec):
    kind: Literal["embed"] = "embed"
    spec: EmbedSpec


class ResolvedTrainSpec(ResolvedInternalSpec):
    kind: Literal["train"] = "train"
    spec: TrainSpec


ResolvedSpec = Annotated[
    ResolvedDownloadSpec
    | ResolvedBuildSpec
    | ResolvedEmbedSpec
    | ResolvedTrainSpec,
    Field(discriminator="kind"),
]
