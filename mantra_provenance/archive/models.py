"""Pydantic models for the MANTRA artifact provenance protocol."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import (
    AnyUrl,
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


class ProtocolModel(BaseModel):
    """Closed, immutable-by-convention protocol object."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RepoFileRef(ProtocolModel):
    """An unresolved repository-relative file location."""

    kind: Literal["repo"] = "repo"
    path: RepoRelPath


class RemoteFileRef(ProtocolModel):
    """An unresolved remote file location."""

    kind: Literal["remote"] = "remote"
    url: AnyUrl


FileRef = Annotated[RepoFileRef | RemoteFileRef, Field(discriminator="kind")]


class ResolvedFileRef(ProtocolModel):
    """The identity and known retrieval locations of exact artifact bytes."""

    sha256: SHA256
    bytes: ByteCount
    locations: tuple[FileRef, ...] = Field(min_length=1)


class ResolvedSpecRef(ProtocolModel):
    """A content-addressed reference to a serialized resolved spec."""

    sha256: SHA256
    locations: tuple[FileRef, ...] = Field(min_length=1)


class ExternalResolvedInput(ProtocolModel):
    """A verified input whose provenance begins outside MANTRA."""

    kind: Literal["external"] = "external"
    artifact: ResolvedFileRef


class ProducedResolvedInput(ProtocolModel):
    """A verified input produced by another MANTRA resolved spec."""

    kind: Literal["produced"] = "produced"
    artifact: ResolvedFileRef
    producer: ResolvedSpecRef


ResolvedInput = Annotated[
    ExternalResolvedInput | ProducedResolvedInput,
    Field(discriminator="kind"),
]


class PythonLockEnvironmentSpec(ProtocolModel):
    """A requested Python environment defined by a repository lockfile."""

    kind: Literal["python-lock"] = "python-lock"
    lockfile: RepoRelPath
    requires_python: Annotated[str, Field(min_length=1)]


class OCIEnvironmentSpec(ProtocolModel):
    """A requested OCI environment; the executor resolves the image digest."""

    kind: Literal["oci"] = "oci"
    image: Annotated[str, Field(min_length=1)]


EnvironmentSpec = Annotated[
    PythonLockEnvironmentSpec | OCIEnvironmentSpec,
    Field(discriminator="kind"),
]


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


ResolvedEnvironment = Annotated[
    ResolvedPythonEnvironment | ResolvedOCIEnvironment,
    Field(discriminator="kind"),
]


class ResolvedCodeRef(ProtocolModel):
    """The clean Git snapshot and entrypoint used by an execution."""

    repository: AnyUrl | None = None
    commit: GitObjectID
    tree: GitObjectID
    entrypoint: RepoRelPath
    entrypoint_sha256: SHA256


class ResolvedSpecSource(ProtocolModel):
    """The repository source of the human-authored spec."""

    path: RepoRelPath
    raw_sha256: SHA256
    repository: AnyUrl | None = None
    commit: GitObjectID


class ExecutionContext(ProtocolModel):
    """Observed runtime facts useful for diagnosing replay differences."""

    operating_system: Annotated[str, Field(min_length=1)]
    architecture: Annotated[str, Field(min_length=1)]
    accelerator: str | None = None
    device: str | None = None
    runtime_versions: dict[str, str] = Field(default_factory=dict)


class BaseSpec(ProtocolModel):
    """Human-authored intent for one artifact-producing invocation."""

    schema_version: Literal[1] = 1
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

    schema_version: Literal[1] = 1
    kind: str
    spec: BaseSpec
    spec_source: ResolvedSpecSource
    inputs: dict[InputName, ResolvedInput]
    code: ResolvedCodeRef
    environment: ResolvedEnvironment
    command: tuple[str, ...] = Field(min_length=1)
    output: ResolvedFileRef
    execution_context: ExecutionContext | None = None

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

        expected_output = RepoFileRef(path=self.spec.output)
        if expected_output not in self.output.locations:
            raise ValueError("resolved output must include the requested repository path")

        for name, requested in self.spec.inputs.items():
            if requested not in self.inputs[name].artifact.locations:
                raise ValueError(
                    f"resolved input {name!r} must include its requested location"
                )

        if isinstance(self.spec.environment, PythonLockEnvironmentSpec):
            assert isinstance(self.environment, ResolvedPythonEnvironment)
            requested_lockfile = RepoFileRef(path=self.spec.environment.lockfile)
            if requested_lockfile not in self.environment.lockfile.locations:
                raise ValueError(
                    "resolved environment must include the requested lockfile path"
                )
        return self


class ResolvedDownloadSpec(BaseResolvedSpec):
    kind: Literal["download"] = "download"
    spec: DownloadSpec

    @model_validator(mode="after")
    def require_external_inputs(self) -> ResolvedDownloadSpec:
        if any(
            not isinstance(item, ExternalResolvedInput)
            for item in self.inputs.values()
        ):
            raise ValueError("download inputs must be external provenance boundaries")
        return self


class ResolvedBuildSpec(BaseResolvedSpec):
    kind: Literal["build"] = "build"
    spec: BuildSpec


class ResolvedEmbedSpec(BaseResolvedSpec):
    kind: Literal["embed"] = "embed"
    spec: EmbedSpec


class ResolvedTrainSpec(BaseResolvedSpec):
    kind: Literal["train"] = "train"
    spec: TrainSpec


ResolvedSpec = Annotated[
    ResolvedDownloadSpec
    | ResolvedBuildSpec
    | ResolvedEmbedSpec
    | ResolvedTrainSpec,
    Field(discriminator="kind"),
]
