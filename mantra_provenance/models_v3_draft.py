"""Version 3 Pydantic models for the MANTRA provenance protocol.

The protocol separates four roles:

* specs record what an invocation requests;
* resolved specs record what a completed invocation used and produced;
* artifact manifests connect stored artifacts to their production records; and
* execution context records the host and runtime used for one invocation.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)


# ---------------------------------------------------------------------------
# Validated scalar types
# ---------------------------------------------------------------------------


def validate_repo_rel_path(value: str) -> str:
    """Validate a normalized POSIX repository-relative path."""
    if not value:
        raise ValueError("expected nonempty repository-relative path")
    if "\\" in value:
        raise ValueError("expected POSIX repository-relative path")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError("expected repository-relative path")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("repository-relative path contains an invalid component")
    return value


RepoRelPath = Annotated[str, AfterValidator(validate_repo_rel_path)]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
OCIImageDigest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
ByteCount = Annotated[int, Field(strict=True, ge=0)]
GitObjectID = Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]
InputName = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")]
HuggingFaceRepoID = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"),
]
NonEmptyStr = Annotated[str, Field(min_length=1)]
PythonSeed = int
NumPySeed = Annotated[int, Field(ge=0, le=2**32 - 1)]
TorchSeed = Annotated[int, Field(ge=-(2**63), le=2**64 - 1)]


class ProtocolModel(BaseModel):
    """Closed protocol object whose fields cannot be reassigned after validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# File locations and exact stored files
# ---------------------------------------------------------------------------


class RemoteFileRef(ProtocolModel):
    """An external HTTP(S) location not controlled by MANTRA."""

    kind: Literal["remote"] = "remote"
    url: AnyHttpUrl


class HuggingFaceFileRef(ProtocolModel):
    """A file at an immutable Hugging Face repository revision."""

    kind: Literal["huggingface"] = "huggingface"
    repo_type: Literal["dataset", "model"]
    repo_id: HuggingFaceRepoID
    revision: GitObjectID
    path: RepoRelPath


class GitFileRef(ProtocolModel):
    """A file at an immutable Git commit."""

    kind: Literal["git"] = "git"
    repository: AnyHttpUrl
    commit: GitObjectID
    path: RepoRelPath


StorageRef = Annotated[
    GitFileRef | HuggingFaceFileRef,
    Field(discriminator="kind"),
]

FileRef = Annotated[
    GitFileRef | HuggingFaceFileRef | RemoteFileRef,
    Field(discriminator="kind"),
]


class ResolvedFileRef(ProtocolModel):
    """Exact stored file bytes and their immutable retrieval location."""

    sha256: SHA256
    bytes: ByteCount
    stored_at: StorageRef


# ---------------------------------------------------------------------------
# Code and artifact manifests
# ---------------------------------------------------------------------------


class ResolvedCodeRef(ProtocolModel):
    """The Git snapshot and entrypoint used by an invocation."""

    repository: AnyHttpUrl
    commit: GitObjectID
    tree: GitObjectID
    entrypoint: RepoRelPath
    entrypoint_sha256: SHA256


class ArtifactManifest(ProtocolModel):
    """Files and code associated with one stored artifact."""

    schema_version: Literal[3] = 3
    artifact: ResolvedFileRef
    resolved_spec: ResolvedFileRef
    spec: ResolvedFileRef
    producer: ResolvedCodeRef
    created_at: AwareDatetime


class ResolvedInternalInputRef(ProtocolModel):
    """An internal artifact, its manifest, and its path inside the invocation."""

    artifact: ResolvedFileRef
    manifest: ResolvedFileRef
    path: RepoRelPath


# ---------------------------------------------------------------------------
# Container environment
# ---------------------------------------------------------------------------


class ContainerEnvironmentSpec(ProtocolModel):
    """The container image and Python lockfile requested by an invocation."""

    image: NonEmptyStr
    lockfile: RepoRelPath


class ResolvedContainerEnvironment(ProtocolModel):
    """The exact container image and lockfile used by an invocation."""

    image: NonEmptyStr
    image_digest: OCIImageDigest
    lockfile: ResolvedFileRef

    @model_validator(mode="after")
    def require_git_lockfile(self) -> ResolvedContainerEnvironment:
        if not isinstance(self.lockfile.stored_at, GitFileRef):
            raise ValueError("the Python lockfile must be stored at an immutable Git commit")
        return self


# ---------------------------------------------------------------------------
# Reproducibility controls
# ---------------------------------------------------------------------------


class RNGSeedSpec(ProtocolModel):
    """Seeds applied to the default Python, NumPy, PyTorch and DataLoader RNGs."""

    python_seed: PythonSeed
    numpy_seed: NumPySeed
    torch_seed: TorchSeed
    dataloader_seed: TorchSeed | None = None


class TorchDeterminismSpec(ProtocolModel):
    """PyTorch and CUDA controls that affect deterministic algorithm selection."""

    deterministic_algorithms: bool
    deterministic_warn_only: bool
    cudnn_deterministic: bool
    cudnn_benchmark: bool
    cublas_workspace_config: str | None


class TorchPrecisionSpec(ProtocolModel):
    """PyTorch controls that affect arithmetic precision."""

    float32_matmul_precision: Literal["highest", "high", "medium"]
    cudnn_allow_tf32: bool
    autocast_enabled: bool
    autocast_dtype: Literal["float16", "bfloat16"] | None

    @model_validator(mode="after")
    def validate_autocast_dtype(self) -> TorchPrecisionSpec:
        if self.autocast_enabled and self.autocast_dtype is None:
            raise ValueError("autocast_dtype is required when autocast is enabled")
        if not self.autocast_enabled and self.autocast_dtype is not None:
            raise ValueError("autocast_dtype must be null when autocast is disabled")
        return self


class BaseReproducibilitySpec(ProtocolModel):
    """Controls recorded for every strict or relaxed invocation."""

    randomness: RNGSeedSpec
    determinism: TorchDeterminismSpec
    precision: TorchPrecisionSpec


class StrictReproducibilitySpec(BaseReproducibilitySpec):
    """Settings for a run that enforces MANTRA's deterministic execution rules."""

    mode: Literal["strict"] = "strict"

    @model_validator(mode="after")
    def require_strict_determinism(self) -> StrictReproducibilitySpec:
        settings = self.determinism
        if not settings.deterministic_algorithms:
            raise ValueError("strict mode requires deterministic_algorithms=true")
        if settings.deterministic_warn_only:
            raise ValueError("strict mode requires deterministic_warn_only=false")
        if not settings.cudnn_deterministic:
            raise ValueError("strict mode requires cudnn_deterministic=true")
        if settings.cudnn_benchmark:
            raise ValueError("strict mode requires cudnn_benchmark=false")
        return self


class RelaxedReproducibilitySpec(BaseReproducibilitySpec):
    """Recorded settings for a run that permits performance-oriented choices."""

    mode: Literal["relaxed"] = "relaxed"


ReproducibilitySpec = Annotated[
    StrictReproducibilitySpec | RelaxedReproducibilitySpec,
    Field(discriminator="mode"),
]


# ---------------------------------------------------------------------------
# Observed execution context
# ---------------------------------------------------------------------------


class HostContext(ProtocolModel):
    """Host kernel used to run the container."""

    operating_system: NonEmptyStr
    kernel_version: NonEmptyStr


class CPUContext(ProtocolModel):
    """CPU made available to the invocation."""

    architecture: NonEmptyStr
    model: NonEmptyStr
    instruction_features: tuple[str, ...]


class CUDADeviceContext(ProtocolModel):
    """One CUDA device made visible to the container."""

    index: Annotated[int, Field(ge=0)]
    name: NonEmptyStr
    architecture: NonEmptyStr
    compute_capability: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$")]


class CPUBackendContext(ProtocolModel):
    """CPU-only numerical execution."""

    kind: Literal["cpu"] = "cpu"
    device: Literal["cpu"] = "cpu"


class CUDABackendContext(ProtocolModel):
    """CUDA execution using host-provided devices and driver."""

    kind: Literal["cuda"] = "cuda"
    devices: Annotated[tuple[CUDADeviceContext, ...], Field(min_length=1)]
    driver_version: NonEmptyStr
    runtime_version: NonEmptyStr


ComputeBackendContext = Annotated[
    CPUBackendContext | CUDABackendContext,
    Field(discriminator="kind"),
]


class NativeLibrary(ProtocolModel):
    """One loaded native numerical library."""

    name: NonEmptyStr
    version: NonEmptyStr


class NumericalRuntimeContext(ProtocolModel):
    """Loaded language and numerical runtimes used by the process."""

    python_version: NonEmptyStr
    pytorch_version: NonEmptyStr
    numpy_version: NonEmptyStr
    blas: NativeLibrary
    lapack: NativeLibrary
    threading_layer: NonEmptyStr
    thread_count: Annotated[int, Field(ge=1)]


class DistributedContext(ProtocolModel):
    """Distributed process group used by an invocation."""

    backend: Literal["nccl", "gloo", "mpi", "ucc", "other"]
    world_size: Annotated[int, Field(ge=2)]
    rank_device_map: Annotated[tuple[str, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def validate_rank_device_map(self) -> DistributedContext:
        if len(self.rank_device_map) != self.world_size:
            raise ValueError("rank_device_map must contain one entry per rank")
        return self


class ParallelismContext(ProtocolModel):
    """Process, thread, worker and distributed settings used by an invocation."""

    process_count: Annotated[int, Field(ge=1)]
    torch_intraop_threads: Annotated[int, Field(ge=1)]
    torch_interop_threads: Annotated[int, Field(ge=1)]
    dataloader_workers: Annotated[int, Field(ge=0)]
    distributed: DistributedContext | None

    @model_validator(mode="after")
    def validate_distributed_context(self) -> ParallelismContext:
        if self.process_count == 1 and self.distributed is not None:
            raise ValueError("distributed must be null for a single-process run")
        if self.process_count > 1 and self.distributed is None:
            raise ValueError("distributed is required for a multi-process run")
        if self.distributed is not None:
            if self.distributed.world_size != self.process_count:
                raise ValueError("distributed world_size must equal process_count")
        return self


class ExecutionContext(ProtocolModel):
    """Host resources and loaded runtimes observed for one invocation."""

    host: HostContext
    cpu: CPUContext
    backend: ComputeBackendContext
    numerical_runtime: NumericalRuntimeContext
    parallelism: ParallelismContext


# ---------------------------------------------------------------------------
# Operation parameters
# ---------------------------------------------------------------------------


class PCALowRankParams(ProtocolModel):
    """Explicit parameters for ``torch.pca_lowrank``."""

    q: Annotated[int, Field(ge=1)]
    center: bool
    niter: Annotated[int, Field(ge=0)]


def _contains_auto(value: JsonValue) -> bool:
    """Return whether a JSON parameter tree contains the deferred value 'auto'."""
    if value == "auto":
        return True
    if isinstance(value, list):
        return any(_contains_auto(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_auto(item) for item in value.values())
    return False


# ---------------------------------------------------------------------------
# Human-authored specs
# ---------------------------------------------------------------------------


class BaseSpec(ProtocolModel):
    """Human-authored request for one artifact-producing invocation."""

    schema_version: Literal[3] = 3
    kind: str
    inputs: dict[InputName, FileRef] = Field(min_length=1)
    script: RepoRelPath
    environment: ContainerEnvironmentSpec
    reproducibility: ReproducibilitySpec
    params: dict[str, JsonValue] = Field(default_factory=dict)
    output: RepoRelPath


class DownloadSpec(BaseSpec):
    """Capture remote bytes as the first MANTRA-controlled artifact."""

    kind: Literal["download"] = "download"

    @model_validator(mode="after")
    def require_remote_inputs(self) -> DownloadSpec:
        if any(not isinstance(item, RemoteFileRef) for item in self.inputs.values()):
            raise ValueError("download inputs must be remote file references")
        return self


class InternalSpec(BaseSpec):
    """Base request for an operation consuming prior MANTRA artifacts."""

    @model_validator(mode="after")
    def require_stored_inputs(self) -> InternalSpec:
        if any(isinstance(item, RemoteFileRef) for item in self.inputs.values()):
            raise ValueError("internal operation inputs must use immutable storage references")
        return self


class BuildSpec(InternalSpec):
    kind: Literal["build"] = "build"


class EmbedSpec(InternalSpec):
    kind: Literal["embed"] = "embed"


class TrainSpec(InternalSpec):
    kind: Literal["train"] = "train"


Spec = Annotated[
    DownloadSpec | BuildSpec | EmbedSpec | TrainSpec,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Resolved execution records
# ---------------------------------------------------------------------------


class BaseResolvedSpec(ProtocolModel):
    """Record written after one artifact-producing invocation succeeds."""

    schema_version: Literal[3] = 3
    kind: str
    spec: BaseSpec
    code: ResolvedCodeRef
    environment: ResolvedContainerEnvironment
    effective_params: dict[str, JsonValue] | None = None
    command: Annotated[tuple[str, ...], Field(min_length=1)]
    output: ResolvedFileRef
    execution_context: ExecutionContext

    @model_validator(mode="after")
    def validate_common_correspondence(self) -> BaseResolvedSpec:
        if self.kind != self.spec.kind:
            raise ValueError("resolved spec kind must match embedded spec kind")
        if self.code.entrypoint != self.spec.script:
            raise ValueError("resolved code entrypoint must match the requested script")
        if self.environment.image != self.spec.environment.image:
            raise ValueError("resolved image name must match the requested image")

        lockfile_location = self.environment.lockfile.stored_at
        if not isinstance(lockfile_location, GitFileRef):
            raise ValueError("resolved lockfile must use an immutable Git location")
        if lockfile_location.path != self.spec.environment.lockfile:
            raise ValueError("resolved lockfile path must match the requested lockfile")

        if self.effective_params is not None and _contains_auto(self.effective_params):
            raise ValueError("effective_params must not contain 'auto'")

        requested_contains_auto = _contains_auto(self.spec.params)
        if isinstance(self.spec.reproducibility, StrictReproducibilitySpec):
            if requested_contains_auto and self.effective_params is None:
                raise ValueError(
                    "strict mode requires effective_params when requested params contain 'auto'"
                )

            if isinstance(self.execution_context.backend, CUDABackendContext):
                workspace = self.spec.reproducibility.determinism.cublas_workspace_config
                if workspace not in {":16:8", ":4096:8"}:
                    raise ValueError(
                        "strict CUDA mode requires CUBLAS_WORKSPACE_CONFIG "
                        "to be ':16:8' or ':4096:8'"
                    )

            workers = self.execution_context.parallelism.dataloader_workers
            if workers > 0:
                seed = self.spec.reproducibility.randomness.dataloader_seed
                if seed is None:
                    raise ValueError(
                        "strict mode requires dataloader_seed when DataLoader workers are used"
                    )
        return self


class ResolvedDownloadSpec(BaseResolvedSpec):
    """Completed capture of bytes from one or more external URLs."""

    kind: Literal["download"] = "download"
    spec: DownloadSpec
    inputs: dict[InputName, RemoteFileRef]

    @model_validator(mode="after")
    def validate_download_inputs(self) -> ResolvedDownloadSpec:
        if set(self.inputs) != set(self.spec.inputs):
            raise ValueError("resolved input names must exactly match spec input names")
        for name, source in self.inputs.items():
            if source != self.spec.inputs[name]:
                raise ValueError(f"resolved remote input {name!r} must match its spec")
        return self


class ResolvedInternalSpec(BaseResolvedSpec):
    """Base record for an operation consuming prior MANTRA artifacts."""

    inputs: dict[InputName, ResolvedInternalInputRef]

    @model_validator(mode="after")
    def validate_internal_inputs(self) -> ResolvedInternalSpec:
        if set(self.inputs) != set(self.spec.inputs):
            raise ValueError("resolved input names must exactly match spec input names")
        for name, requested in self.spec.inputs.items():
            if isinstance(requested, RemoteFileRef):
                raise ValueError("internal resolved specs cannot consume remote references")
            if self.inputs[name].artifact.stored_at != requested:
                raise ValueError(
                    f"resolved input {name!r} storage location must match its spec"
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
