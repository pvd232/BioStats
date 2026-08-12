"""Fourth draft of the Pydantic models for the MANTRA provenance protocol.

This version separates authored execution requests, verified data artifacts,
the exact Git source tree, the container environment, observed execution
conditions, and the manifest connecting an artifact to its producer.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal
import datetime
from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
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


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

RepoRelPath = Annotated[str, AfterValidator(validate_repo_rel_path)]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GitCommit = Annotated[
    str,
    Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"),
]


class ProtocolModel(BaseModel):
    """Closed, immutable-by-convention protocol object."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# File locations
# ---------------------------------------------------------------------------

class RemoteFileRef(ProtocolModel):
    """A mutable or externally controlled source URL."""

    kind: Literal["remote"] = "remote"
    url: HttpUrl


class GitFileRef(ProtocolModel):
    """A file stored at an exact Git revision."""

    kind: Literal["git"] = "git"
    repository: HttpUrl
    commit: GitCommit
    path: RepoRelPath


class HuggingFaceFileRef(ProtocolModel):
    """A file stored at an exact Hugging Face repository revision."""

    kind: Literal["huggingface"] = "huggingface"
    repository: str = Field(min_length=1)
    revision: str = Field(min_length=1)
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


class ResolvedGitSourceRef(ProtocolModel):
    repository: HttpUrl
    commit: GitCommit

    entrypoint: RepoRelPath
    entrypoint_sha256: SHA256
    entrypoint_bytes: int = Field(ge=0)

# ---------------------------------------------------------------------------
# Artifact manifest
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
    source: ResolvedGitSourceRef

    created_at: AwareDatetime

# ---------------------------------------------------------------------------
# Authored container environment
# ---------------------------------------------------------------------------

class ContainerEnvironmentSpec(ProtocolModel):
    """
    Declares the container image and Python dependency lockfile requested
    for an execution.
    """

    image: str = Field(min_length=1)
    lockfile: GitFileRef


class ResolvedContainerEnvironment(ProtocolModel):
    """
    Records the exact container image and lockfile used by the executor.
    """

    image: str = Field(min_length=1)
    sha256: SHA256
    lockfile: ResolvedFileRef

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
    def validate_autocast(self) -> "TorchPrecisionSpec":
        if self.autocast_enabled and self.autocast_dtype is None:
            raise ValueError(
                "autocast_dtype is required when autocast_enabled is true"
            )

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
    def validate_strict_policy(self) -> "StrictReproducibilitySpec":
        determinism = self.determinism

        if not determinism.deterministic_algorithms:
            raise ValueError(
                "strict mode requires deterministic_algorithms=true"
            )

        if determinism.deterministic_warn_only:
            raise ValueError(
                "strict mode requires deterministic_warn_only=false"
            )

        if not determinism.cudnn_deterministic:
            raise ValueError(
                "strict mode requires cudnn_deterministic=true"
            )

        if determinism.cudnn_benchmark:
            raise ValueError(
                "strict mode requires cudnn_benchmark=false"
            )

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
# Observed execution context
# ---------------------------------------------------------------------------

class GCEHostContext(ProtocolModel):
    provider: Literal["gce"] = "gce"

    machine_type: str
    zone: str
    boot_image: str

    guest_os_name: str
    guest_os_version: str
    kernel_release: str


class CPUContext(ProtocolModel):
    """
    The CPU available to the container, including instruction sets that can
    change numerical-library implementation choices.
    """

    architecture: str
    model: str
    instruction_features: tuple[str, ...]


class CPUBackendContext(ProtocolModel):
    """Records that PyTorch executed without a GPU backend."""

    kind: Literal["cpu"] = "cpu"
    device: str = "cpu"


class CUDADeviceContext(ProtocolModel):
    ordinal: int = Field(ge=0)
    model: str

    compute_capability_major: int = Field(ge=0)
    compute_capability_minor: int = Field(ge=0)

    memory_bytes: int = Field(gt=0)


class CUDABackendContext(ProtocolModel):
    """The CUDA backend and devices observed during execution."""

    kind: Literal["cuda"] = "cuda"

    gpu_devices: tuple[CUDADeviceContext, ...] = Field(min_length=1)

    nvidia_driver_version: str
    pytorch_cuda_version: str
    cudnn_version: str


ComputeBackendContext = Annotated[
    CPUBackendContext | CUDABackendContext,
    Field(discriminator="kind"),
]


class NativeMathLibraryContext(ProtocolModel):
    implementation: str
    version: str


class NativeThreadPoolContext(ProtocolModel):
    implementation: str
    version: str
    threads: int = Field(ge=1)


class NumericalRuntimeContext(ProtocolModel):
    python_version: str
    pytorch_version: str
    numpy_version: str

    blas: NativeMathLibraryContext
    lapack: NativeMathLibraryContext

    native_thread_pools: tuple[NativeThreadPoolContext, ...]


class DistributedContext(ProtocolModel):
    """Distributed process layout, when distributed execution is used."""

    backend: Literal["nccl", "gloo", "mpi", "ucc"]
    world_size: int = Field(ge=2)
    rank_device_map: dict[int, str]

    @model_validator(mode="after")
    def validate_rank_map(self) -> "DistributedContext":
        expected_ranks = set(range(self.world_size))

        if set(self.rank_device_map) != expected_ranks:
            raise ValueError(
                "rank_device_map must contain every rank from zero through "
                "world_size - 1"
            )

        return self


class ParallelismContext(ProtocolModel):
    """Process, thread, worker, and distributed settings actually used."""

    process_count: int = Field(ge=1)

    torch_intraop_threads: int = Field(ge=1)
    torch_interop_threads: int = Field(ge=1)

    dataloader_workers: int = Field(ge=0)
    distributed: DistributedContext | None


class ExecutionContext(ProtocolModel):
    """
    Facts observed from the host and running process.

    The container environment records what was supplied to the execution.
    This class records the host and runtime conditions under which it ran.
    """

    host: GCEHostContext
    cpu: CPUContext
    backend: ComputeBackendContext
    numerical_runtime: NumericalRuntimeContext
    parallelism: ParallelismContext

# ---------------------------------------------------------------------------
# Authored specifications
# ---------------------------------------------------------------------------

InputName = Annotated[str, Field(min_length=1)]

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

    environment: ContainerEnvironmentSpec
    reproducibility: ReproducibilitySpec

    output: RepoRelPath


class DownloadSpec(BaseSpec):
    kind: Literal["download"] = "download"

    @model_validator(mode="after")
    def require_remote_inputs(self) -> "DownloadSpec":
        for name, input_ref in self.inputs.items():
            if not isinstance(input_ref, RemoteFileRef):
                raise ValueError(
                    f"download input {name!r} must be a RemoteFileRef"
                )

        return self


class InternalSpec(BaseSpec):
    """Base class for stages that consume previously produced artifacts."""

    @model_validator(mode="after")
    def prohibit_remote_inputs(self) -> "InternalSpec":
        for name, input_ref in self.inputs.items():
            if isinstance(input_ref, RemoteFileRef):
                raise ValueError(
                    f"internal input {name!r} cannot be a RemoteFileRef"
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

class BuildSpec(InternalSpec):
    kind: Literal["build"] = "build"
    params: BuildParams


class EmbedSpec(InternalSpec):
    kind: Literal["embed"] = "embed"
    params:EmbedParams


class TrainSpec(InternalSpec):
    kind: Literal["train"] = "train"
    params: TrainParams


Spec = Annotated[
    DownloadSpec | BuildSpec | EmbedSpec | TrainSpec,
    Field(discriminator="kind"),
]

# ---------------------------------------------------------------------------
# Resolved internal inputs
# ---------------------------------------------------------------------------

class ResolvedInternalInputRef(ProtocolModel):
    """
    A previously produced artifact bound into the current execution.

    artifact:
        The exact input file.

    manifest:
        The ArtifactManifest file that links the artifact to its producing
        spec, resolved spec, and script.

    path:
        The repository-relative path at which the executor made the artifact
        available to the command. This is not its durable storage path.
    """

    artifact: ResolvedFileRef
    manifest: ResolvedFileRef
    path: RepoRelPath


# ---------------------------------------------------------------------------
# Resolved execution records
# ---------------------------------------------------------------------------

class BaseResolvedSpec(ProtocolModel):
    """
    Record written after an execution has produced and hashed its output.
    """

    schema_version: Literal[1] = 1
    kind: str

    spec: BaseSpec
    code: ResolvedGitSourceRef

    environment: ResolvedContainerEnvironment
    execution_context: ExecutionContext

    command: tuple[str, ...] = Field(min_length=1)


    output: ResolvedFileRef
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_common_invariants(self) -> "BaseResolvedSpec":
        if self.kind != self.spec.kind:
            raise ValueError(
                "resolved spec kind must match the embedded authored spec kind"
            )

        if self.source.entrypoint != self.spec.script:
            raise ValueError(
                "resolved source entrypoint must match the authored script path"
            )

        if self.environment.image != self.spec.environment.image:
            raise ValueError(
                "resolved container image must match the requested image"
            )

        if (
            self.environment.lockfile.stored_at
            != self.spec.environment.lockfile
        ):
            raise ValueError(
                "resolved lockfile location must match the requested lockfile"
            )
    
        if self.spec.reproducibility.mode == "strict":
            if isinstance(self.execution_context.backend, CUDABackendContext):
                workspace_config = (
                    self.spec.reproducibility
                    .determinism
                    .cublas_workspace_config
                )

                if workspace_config not in {":16:8", ":4096:8"}:
                    raise ValueError(
                        "strict CUDA execution requires an explicit "
                        "CUBLAS_WORKSPACE_CONFIG"
                    )

            workers = self.execution_context.parallelism.dataloader_workers
            dataloader_seed = (
                self.spec.reproducibility.randomness.dataloader_seed
            )

            if workers > 0 and dataloader_seed is None:
                raise ValueError(
                    "strict execution with DataLoader workers requires "
                    "dataloader_seed"
                )

        return self


class ResolvedDownloadSpec(BaseResolvedSpec):
    """
    Download receipt.

    The input remains the source URL because no artifact exists before the
    download. The output is the first verified artifact created from that URL.
    """

    kind: Literal["download"] = "download"
    spec: DownloadSpec

    inputs: dict[InputName, RemoteFileRef]

    @model_validator(mode="after")
    def validate_download_inputs(self) -> "ResolvedDownloadSpec":
        if self.inputs != self.spec.inputs:
            raise ValueError(
                "resolved download inputs must match the authored remote inputs"
            )

        return self


class ResolvedInternalSpec(BaseResolvedSpec):
    """
    Receipt for an operation that consumes previously produced artifacts.
    """

    inputs: dict[InputName, ResolvedInternalInputRef]

    @model_validator(mode="after")
    def validate_internal_inputs(self) -> "ResolvedInternalSpec":
        if set(self.inputs) != set(self.spec.inputs):
            raise ValueError(
                "resolved input names must match the authored input names"
            )

        for name, resolved_input in self.inputs.items():
            requested_location = self.spec.inputs[name]

            if resolved_input.artifact.stored_at != requested_location:
                raise ValueError(
                    f"resolved input {name!r} does not match the authored "
                    "storage location"
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
