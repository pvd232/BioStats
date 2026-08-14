"""Version 3 Pydantic models for the MANTRA provenance protocol.

This version distinguishes an artifact's logical workspace binding from its
durable storage location. An input's provenance boundary is expressed by a
required nullable producer reference: ``None`` means external, while a
``ResolvedSpecRef`` means the input was produced inside MANTRA.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal
import datetime
from pydantic import (
    AnyHttpUrl,
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
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


RepoRelPath = Annotated[str, AfterValidator(validate_repo_rel_path)]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ByteCount = Annotated[int, Field(strict=True, ge=0)]
GitObjectID = Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]
InputName = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")]
HuggingFaceRepoID = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"),
]


class ProtocolModel(BaseModel):
    """Closed, immutable-by-convention protocol object."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# class RepoFileRef(ProtocolModel):
#     """A logical file location inside the MANTRA repository."""

#     kind: Literal["repo"] = "repo"
#     path: RepoRelPath


class RemoteFileRef(ProtocolModel):
    """An external HTTP(S) origin controlled outside MANTRA."""

    kind: Literal["remote"] = "remote"
    url: AnyHttpUrl


class HuggingFaceFileRef(ProtocolModel):
    """A file stored at an immutable Hugging Face repository revision."""

    kind: Literal["huggingface"] = "huggingface"
    repo_type: Literal["dataset", "model"]
    repo_id: HuggingFaceRepoID
    revision: GitObjectID
    path: RepoRelPath

class GitFileRef(ProtocolModel):
    kind: Literal["git"] = "git"
    repository: AnyHttpUrl
    commit: GitObjectID
    path: RepoRelPath 

StorageRef = Annotated[
    GitFileRef | HuggingFaceFileRef,
    Field(discriminator="kind"),
]

FileRef = Annotated[
    StorageRef | RemoteFileRef,
]



class ResolvedFileRef(ProtocolModel):
    """Exact bytes, local path and global storage path."""
    sha256: SHA256
    bytes: ByteCount
    stored_at: StorageRef 


class Manifest(ProtocolModel):
    """A verified input and its optional prior MANTRA producer."""
    artifact: ResolvedFileRef
    build_record: ResolvedFileRef
    spec: ResolvedFileRef
    producer: ResolvedFileRef
    created: datetime
    

class ResolvedInputRef(ProtocolModel):
    artifact: FileRef | ResolvedFileRef
    manifest: ResolvedFileRef | None
    @property
    def is_external(self) -> bool:
        return self.manifest is None

class PythonEnvironmentSpec(ProtocolModel):
    """A requested Python environment defined by a repository lockfile."""

    kind: Literal["python"] = "python"    
    lockfile: RepoRelPath    
    # requires_python: Annotated[str, Field(min_length=1)]


class OCIEnvironmentSpec(ProtocolModel):
    """A requested OCI environment; the executor resolves the image digest."""

    kind: Literal["oci"] = "oci"
    image: Annotated[str, Field(min_length=1)]


class BenchmarkDeterminismEnvironmentSpec(ProtocolModel):    
    torch_use_deterministic_algorithms: bool
    torch_backends_cudnn_benchmark: bool
    CUBLAS_WORKSPACE_CONFIG: str
    
class RNGSeedEnvironmentSpec(ProtocolModel):
    python_seed:int
    torch_seed: int
    numpy_seed: int



class ResolvedPythonEnvironment(ProtocolModel):
    """The verified lockfile and interpreter used by an execution."""

    kind: Literal["python-lock"] = "python-lock"
    lockfile: ResolvedFileRef
    python_implementation: Annotated[str, Field(min_length=1)]
    python_version: Annotated[str, Field(min_length=1)]


class ResolvedOCIEnvironment(ProtocolModel):
    """The immutable OCI image used by an execution."""

    kind: Literal["oci"] = "oci"
    image: Annotated[str, Field(min_length=1)]
    image_digest: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class ResolvedBenchmarkDeterminismEnvironment(ProtocolModel):
    torch_use_deterministic_algorithms: bool
    torch_backends_cudnn_benchmark: bool
    CUBLAS_WORKSPACE_CONFIG: str

class ResolvedRNGSeedEnvironment(ProtocolModel):
    python_seed:int
    torch_seed: int
    numpy_seed: int


class ResolvedCodeRef(ProtocolModel):
    """The clean Git snapshot and entrypoint used by an execution."""

    repository: AnyHttpUrl | None = None
    commit: GitObjectID
    tree: GitObjectID
    entrypoint: RepoRelPath
    entrypoint_sha256: SHA256



class ExecutionContext(ProtocolModel):
    """Observed runtime facts useful for diagnosing replay differences."""

    operating_system: Annotated[str, Field(min_length=1)]
    architecture: Annotated[str, Field(min_length=1)]
    device: Annotated[str, Field(min_length=1)]
    accelerator: str | None = None
    runtime_versions: dict[str, str] = Field(default_factory=dict)


class BaseSpec(ProtocolModel):
    """Human-authored intent for one artifact-producing invocation."""

    schema_version: Literal[2] = 2
    kind: str
    inputs: dict[InputName, FileRef] = Field(min_length=1)
    script: RepoRelPath
    environment: EnvironmentSpec
    params: dict[str, JsonValue] = Field(default_factory=dict)
    output: RepoRelPath


class DownloadSpec(BaseSpec):
    """A canonical external-ingestion operation."""

    kind: Literal["download"] = "download"

    @model_validator(mode="after")
    def require_remote_inputs(self) -> DownloadSpec:
        if any(not isinstance(item, RemoteFileRef) for item in self.inputs.values()):
            raise ValueError("download inputs must be remote file references")
        return self


class BuildSpec(BaseSpec):
    kind: Literal["build"] = "build"


class EmbedSpec(BaseSpec):
    kind: Literal["embed"] = "embed"


class TrainSpec(BaseSpec):
    kind: Literal["train"] = "train"


Spec = Annotated[
    DownloadSpec | BuildSpec | EmbedSpec | TrainSpec,
    Field(discriminator="kind"),
]


class BaseResolvedSpec(ProtocolModel):
    """Immutable execution receipt produced after a successful spec run."""
    schema_version: int
    spec: Spec
    inputs: dict[InputName, ResolvedInputRef]
    code: ResolvedCodeRef
    python_environment: ResolvedPythonEnvironment
    oci_environment: ResolvedOCIEnvironment
    rng_seed_environment: ResolvedRNGSeedEnvironment
    benchmark_determinism_environment: ResolvedBenchmarkDeterminismEnvironment
    command: tuple[str, ...] = Field(min_length=1)
    output: ResolvedFileRef
    execution_context: ExecutionContext

    @model_validator(mode="after")
    def validate_resolution_correspondence(self) -> BaseResolvedSpec:
        if self.kind != self.spec.kind:
            raise ValueError("resolved spec kind must match embedded spec kind")
        if set(self.inputs) != set(self.spec.inputs):
            raise ValueError("resolved input names must exactly match spec input names")
        if self.code.entrypoint != self.spec.script:
            raise ValueError("resolved code entrypoint must match spec script")
        if self.environment.kind != self.spec.environment.kind:
            raise ValueError("resolved environment kind must match spec environment kind")
        if self.output.path != self.spec.output:
            raise ValueError("resolved output workspace path must match spec output")
        if self.output.stored_at is None:
            raise ValueError("resolved output must have a durable storage location")

        for name, requested in self.spec.inputs.items():
            if isinstance(requested, RepoFileRef):
                if self.inputs[name].artifact.path != requested.path:
                    raise ValueError(
                        f"resolved input {name!r} workspace path must match its spec"
                    )
        
            if (
                self.python_environment.lockfile.path
                != self.spec.python_environment.lockfile
            ):
                raise ValueError(
                    "resolved environment workspace path must match its lockfile spec"
                )
        return self
    
    @model_validator(mode="after")
    def validate_resolved_input(self) -> BaseResolvedSpec:
        if isinstance(self.spec, DownloadSpec):
            assert(len(self.values ==1) and isinstance(self.values[0], RemoteFileRef))
        else:
            for item in self.values():
                assert(isinstance(item, ResolvedInput))
        return self


class ResolvedDownloadSpec(BaseResolvedSpec):
    kind: Literal["download"] = "download"
    spec: DownloadSpec

    @model_validator(mode="after")
    def require_external_inputs(self) -> ResolvedDownloadSpec:
        if any(not item.is_external for item in self.inputs.values()):
            raise ValueError("download inputs must be external provenance boundaries")
        return self


class ResolvedInternalSpec(BaseResolvedSpec):
    """Base receipt for operations whose inputs must have MANTRA producers."""

    @model_validator(mode="after")
    def require_internal_inputs(self) -> ResolvedInternalSpec:
        if any(item.is_external for item in self.inputs.values()):
            raise ValueError("internal operation inputs must reference producers")
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
