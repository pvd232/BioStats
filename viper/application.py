"""Expose VIPER operations through one typed Python application boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .authoring import freeze_run_plan, load_run_plan_draft
from .ids import RunId, StageId
from .protocol import (
    ArtifactPointer,
    BenchmarkResult,
    ResolvedArtifact,
    ResolvedRun,
    RunSpec,
    Spec,
)
from .runner import LocalRunError
from .runner import run_local as execute_local_run
from .serialization import load_resolved_stage, load_stage_spec, parse_yaml_bytes
from .stage_execution import StageExecutionError, execute_stage_process
from .verifier import (
    StorageFetcher,
    VerificationError,
    VerificationPolicy,
    verify_benchmark_result,
    verify_promoted_artifact,
    verify_run_result,
)

OperationName = Literal[
    "validate_stage",
    "validate_resolved_stage",
    "validate_run_spec",
    "freeze_run",
    "execute_stage",
    "run_local",
    "verify_run",
    "verify_benchmark",
    "verify_pointer",
    "get_schema",
    "get_capabilities",
]
FailureOrigin = Literal["request", "application", "cli", "internal"]
ErrorCode = Literal[
    "invalid_request",
    "invalid_document",
    "not_found",
    "write_conflict",
    "io_failed",
    "execution_failed",
    "verification_failed",
    "internal_error",
]


class ApplicationModel(BaseModel):
    """Base model for stable application requests and results."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        ser_json_bytes="base64",
    )


class ViperFailure(ApplicationModel):
    """Describe one expected failure at an application boundary."""

    status: Literal["error"] = "error"
    operation: OperationName | None
    origin: FailureOrigin
    code: ErrorCode
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class ViperError(RuntimeError):
    """Carry one typed expected application failure to a Python caller."""

    def __init__(self, failure: ViperFailure) -> None:
        """Initialize the exception from one stable failure model."""
        super().__init__(failure.message)
        self.failure = failure


class SuccessModel(ApplicationModel):
    """Base model for successful application results."""

    status: Literal["ok"] = "ok"
    operation: OperationName


class PathRequest(ApplicationModel):
    """Select one local protocol document."""

    path: Path


class ValidateStageRequest(PathRequest):
    """Select one authored stage specification."""


class ValidateStageSuccess(SuccessModel):
    """Report the kind of one valid authored stage specification."""

    operation: Literal["validate_stage"] = "validate_stage"  # pyright: ignore[reportIncompatibleVariableOverride]
    path: Path
    stage_kind: str


class ValidateResolvedStageRequest(PathRequest):
    """Select one resolved stage specification."""


class ValidateResolvedStageSuccess(SuccessModel):
    """Report the kind of one valid resolved stage specification."""

    operation: Literal["validate_resolved_stage"] = "validate_resolved_stage"  # pyright: ignore[reportIncompatibleVariableOverride]
    path: Path
    stage_kind: str


class ValidateRunSpecRequest(PathRequest):
    """Select one frozen RunSpec document."""


class ValidateRunSpecSuccess(SuccessModel):
    """Report the identity and stage order of one valid RunSpec."""

    operation: Literal["validate_run_spec"] = "validate_run_spec"  # pyright: ignore[reportIncompatibleVariableOverride]
    path: Path
    run_id: RunId
    stage_ids: tuple[StageId, ...]


class FreezeRunRequest(ApplicationModel):
    """Select one run-plan draft and its repository root."""

    draft: Path
    repository_root: Path


class FreezeRunSuccess(SuccessModel):
    """Report the canonical documents written for one frozen plan."""

    operation: Literal["freeze_run"] = "freeze_run"  # pyright: ignore[reportIncompatibleVariableOverride]
    run_id: RunId
    files: tuple[Path, ...]


class ExecuteStageRequest(ApplicationModel):
    """Select one stage from a frozen local run plan."""

    run_spec: Path
    stage_id: StageId
    repository_root: Path
    timeout_seconds: float | None = Field(default=None, gt=0)


class ExecuteStageSuccess(SuccessModel):
    """Return the observed result of one completed stage process."""

    operation: Literal["execute_stage"] = "execute_stage"  # pyright: ignore[reportIncompatibleVariableOverride]
    stage_id: StageId
    command: tuple[str, ...]
    artifacts: dict[str, ResolvedArtifact]
    stdout: bytes
    stderr: bytes


class RunLocalRequest(ApplicationModel):
    """Select one frozen plan for complete trusted-local execution."""

    run_spec: Path
    repository_root: Path
    timeout_seconds: float | None = Field(default=None, gt=0)


class RunLocalSuccess(SuccessModel):
    """Report the terminal document written by one verified local run."""

    operation: Literal["run_local"] = "run_local"  # pyright: ignore[reportIncompatibleVariableOverride]
    run_id: RunId
    resolved_run: Path
    journal: Path


class VerificationRequest(PathRequest):
    """Select a document and source repositories trusted to supply code."""

    trusted_loader_repositories: frozenset[str] = Field(min_length=1)


class VerifyRunRequest(VerificationRequest):
    """Select one terminal run for complete verification."""


class VerifyRunSuccess(SuccessModel):
    """Summarize one verified terminal run."""

    operation: Literal["verify_run"] = "verify_run"  # pyright: ignore[reportIncompatibleVariableOverride]
    run_id: RunId
    run_status: str
    successful_attempt_id: int | None
    stage_ids: tuple[StageId, ...]
    measurement_count: int


class VerifyBenchmarkRequest(VerificationRequest):
    """Select one benchmark result for verification."""


class VerifyBenchmarkSuccess(SuccessModel):
    """Summarize one verified benchmark result."""

    operation: Literal["verify_benchmark"] = "verify_benchmark"  # pyright: ignore[reportIncompatibleVariableOverride]
    benchmark_id: str
    run_id: RunId
    benchmark_status: str
    confirmation_attempt_id: int


class VerifyPointerRequest(VerificationRequest):
    """Select one promoted artifact pointer for verification."""


class VerifyPointerSuccess(SuccessModel):
    """Summarize one verified promoted artifact."""

    operation: Literal["verify_pointer"] = "verify_pointer"  # pyright: ignore[reportIncompatibleVariableOverride]
    file_count: int


class SchemaRequest(ApplicationModel):
    """Select one public schema by its registered name."""

    name: str = Field(min_length=1)


class SchemaSuccess(SuccessModel):
    """Return one registered JSON Schema."""

    operation: Literal["get_schema"] = "get_schema"  # pyright: ignore[reportIncompatibleVariableOverride]
    name: str
    json_schema: dict[str, Any]


class CapabilitiesRequest(ApplicationModel):
    """Request the installed operation and backend inventory."""


class CapabilitiesSuccess(SuccessModel):
    """Return installed application operations and execution backends."""

    operation: Literal["get_capabilities"] = "get_capabilities"  # pyright: ignore[reportIncompatibleVariableOverride]
    protocol_version: int
    operations: tuple[OperationName, ...]
    execution_backends: tuple[str, ...]


SCHEMA_REGISTRY: dict[str, Any] = {
    "ArtifactPointer": ArtifactPointer,
    "BenchmarkResult": BenchmarkResult,
    "ResolvedRun": ResolvedRun,
    "RunSpec": RunSpec,
    "Spec": Spec,
}

OPERATIONS: tuple[OperationName, ...] = (
    "validate_stage",
    "validate_resolved_stage",
    "validate_run_spec",
    "freeze_run",
    "execute_stage",
    "run_local",
    "verify_run",
    "verify_benchmark",
    "verify_pointer",
    "get_schema",
    "get_capabilities",
)


def _load_model(path: Path, model_type: type[BaseModel]) -> BaseModel:
    """Load one local YAML document through its concrete Pydantic model."""
    return model_type.model_validate(parse_yaml_bytes(path.read_bytes()))


def _document_error(
    operation: OperationName,
    path: Path,
    exc: Exception,
) -> ViperError:
    """Translate a local document failure into the stable application model."""
    if isinstance(exc, FileNotFoundError):
        code: ErrorCode = "not_found"
        message = "document path does not exist"
    elif isinstance(exc, OSError):
        code = "io_failed"
        message = "document could not be read"
    else:
        code = "invalid_document"
        message = "document failed schema validation"
    return ViperError(
        ViperFailure(
            operation=operation,
            origin="application",
            code=code,
            message=message,
            details={"path": path.as_posix()},
        )
    )


def validate_stage(request: ValidateStageRequest) -> ValidateStageSuccess:
    """Validate one authored stage document."""
    try:
        stage = load_stage_spec(request.path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("validate_stage", request.path, exc) from exc
    return ValidateStageSuccess(path=request.path, stage_kind=stage.kind)


def validate_resolved_stage(
    request: ValidateResolvedStageRequest,
) -> ValidateResolvedStageSuccess:
    """Validate one resolved stage document."""
    try:
        stage = load_resolved_stage(request.path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("validate_resolved_stage", request.path, exc) from exc
    return ValidateResolvedStageSuccess(path=request.path, stage_kind=stage.kind)


def validate_run_spec(request: ValidateRunSpecRequest) -> ValidateRunSpecSuccess:
    """Validate one RunSpec document and return its ordered stage identities."""
    try:
        run = _load_model(request.path, RunSpec)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("validate_run_spec", request.path, exc) from exc
    assert isinstance(run, RunSpec)
    return ValidateRunSpecSuccess(
        path=request.path,
        run_id=run.run_id,
        stage_ids=tuple(stage.stage_id for stage in run.stages),
    )


def freeze_run(request: FreezeRunRequest) -> FreezeRunSuccess:
    """Freeze one draft into canonical stage and run documents."""
    try:
        draft = load_run_plan_draft(request.draft)
        frozen = freeze_run_plan(request.repository_root, draft)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("freeze_run", request.draft, exc) from exc
    return FreezeRunSuccess(run_id=frozen.run.run_id, files=frozen.files)


def execute_stage(request: ExecuteStageRequest) -> ExecuteStageSuccess:
    """Execute one selected stage and identify its declared outputs."""
    try:
        run = _load_model(request.run_spec, RunSpec)
        assert isinstance(run, RunSpec)
        reference = next(
            (stage for stage in run.stages if stage.stage_id == request.stage_id),
            None,
        )
        if reference is None:
            raise ValueError("selected stage is absent from the run plan")
        stage = load_stage_spec(request.repository_root / reference.spec)
        result = execute_stage_process(
            request.repository_root,
            run,
            reference,
            stage,
            timeout_seconds=request.timeout_seconds,
        )
    except StageExecutionError as exc:
        raise ViperError(
            ViperFailure(
                operation="execute_stage",
                origin="application",
                code="execution_failed",
                message="stage process failed",
                details={"stage_id": request.stage_id},
            )
        ) from exc
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("execute_stage", request.run_spec, exc) from exc
    return ExecuteStageSuccess(
        stage_id=request.stage_id,
        command=result.command,
        artifacts=result.artifacts,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def run_local(request: RunLocalRequest) -> RunLocalSuccess:
    """Execute, publish, and verify one complete run on the local host."""
    try:
        result = execute_local_run(
            request.repository_root,
            request.run_spec,
            timeout_seconds=request.timeout_seconds,
        )
    except LocalRunError as exc:
        raise ViperError(
            ViperFailure(
                operation="run_local",
                origin="application",
                code="execution_failed",
                message="local run failed",
            )
        ) from exc
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("run_local", request.run_spec, exc) from exc
    run = RunSpec.model_validate(parse_yaml_bytes(request.run_spec.read_bytes()))
    return RunLocalSuccess(
        run_id=run.run_id,
        resolved_run=result.resolved_run_path,
        journal=result.journal_path,
    )


def _policy(repositories: frozenset[str]) -> VerificationPolicy:
    """Construct the verifier policy carried by one application request."""
    return VerificationPolicy(trusted_loader_repositories=repositories)


def verify_run(
    request: VerifyRunRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyRunSuccess:
    """Verify one terminal run and summarize the connected evidence."""
    try:
        resolved = _load_model(request.path, ResolvedRun)
        assert isinstance(resolved, ResolvedRun)
        verified = verify_run_result(
            resolved,
            policy=_policy(request.trusted_loader_repositories),
            fetcher=fetcher,
        )
    except VerificationError as exc:
        raise ViperError(
            ViperFailure(
                operation="verify_run",
                origin="application",
                code="verification_failed",
                message="run verification failed",
            )
        ) from exc
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("verify_run", request.path, exc) from exc
    return VerifyRunSuccess(
        run_id=verified.plan.run.run_id,
        run_status=resolved.status,
        successful_attempt_id=resolved.successful_attempt_id,
        stage_ids=tuple(verified.resolved_stages),
        measurement_count=len(verified.measurements),
    )


def verify_benchmark(
    request: VerifyBenchmarkRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyBenchmarkSuccess:
    """Verify one benchmark result and summarize its confirmation."""
    try:
        result = _load_model(request.path, BenchmarkResult)
        assert isinstance(result, BenchmarkResult)
        verified = verify_benchmark_result(
            result,
            policy=_policy(request.trusted_loader_repositories),
            fetcher=fetcher,
        )
    except VerificationError as exc:
        raise ViperError(
            ViperFailure(
                operation="verify_benchmark",
                origin="application",
                code="verification_failed",
                message="benchmark verification failed",
            )
        ) from exc
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("verify_benchmark", request.path, exc) from exc
    benchmark = verified.run.plan.benchmark
    assert benchmark is not None
    return VerifyBenchmarkSuccess(
        benchmark_id=benchmark.benchmark_id,
        run_id=verified.run.plan.run.run_id,
        benchmark_status=result.status,
        confirmation_attempt_id=result.confirmation.attempt_id,
    )


def verify_pointer(
    request: VerifyPointerRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyPointerSuccess:
    """Verify one promoted artifact and report its physical file count."""
    try:
        pointer = _load_model(request.path, ArtifactPointer)
        assert isinstance(pointer, ArtifactPointer)
        artifact = verify_promoted_artifact(
            pointer,
            policy=_policy(request.trusted_loader_repositories),
            fetcher=fetcher,
        )
    except VerificationError as exc:
        raise ViperError(
            ViperFailure(
                operation="verify_pointer",
                origin="application",
                code="verification_failed",
                message="artifact verification failed",
            )
        ) from exc
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise _document_error("verify_pointer", request.path, exc) from exc
    return VerifyPointerSuccess(file_count=len(artifact.files))


def get_schema(request: SchemaRequest) -> SchemaSuccess:
    """Return JSON Schema for one explicitly registered public type."""
    model = SCHEMA_REGISTRY.get(request.name)
    if model is None:
        raise ViperError(
            ViperFailure(
                operation="get_schema",
                origin="application",
                code="invalid_request",
                message="schema name is not registered",
                details={"name": request.name},
            )
        )
    return SchemaSuccess(
        name=request.name,
        json_schema=TypeAdapter(model).json_schema(),
    )


def get_capabilities(request: CapabilitiesRequest) -> CapabilitiesSuccess:
    """Return installed operations and available execution backends."""
    del request
    return CapabilitiesSuccess(
        protocol_version=1,
        operations=OPERATIONS,
        execution_backends=("trusted_local",),
    )


RequestType = type[ApplicationModel]
Handler = Callable[[Any], SuccessModel]

REQUEST_REGISTRY: dict[OperationName, RequestType] = {
    "validate_stage": ValidateStageRequest,
    "validate_resolved_stage": ValidateResolvedStageRequest,
    "validate_run_spec": ValidateRunSpecRequest,
    "freeze_run": FreezeRunRequest,
    "execute_stage": ExecuteStageRequest,
    "run_local": RunLocalRequest,
    "verify_run": VerifyRunRequest,
    "verify_benchmark": VerifyBenchmarkRequest,
    "verify_pointer": VerifyPointerRequest,
    "get_schema": SchemaRequest,
    "get_capabilities": CapabilitiesRequest,
}

HANDLER_REGISTRY: dict[OperationName, Handler] = {
    "validate_stage": validate_stage,
    "validate_resolved_stage": validate_resolved_stage,
    "validate_run_spec": validate_run_spec,
    "freeze_run": freeze_run,
    "execute_stage": execute_stage,
    "run_local": run_local,
    "verify_run": verify_run,
    "verify_benchmark": verify_benchmark,
    "verify_pointer": verify_pointer,
    "get_schema": get_schema,
    "get_capabilities": get_capabilities,
}


def dispatch(
    operation: OperationName,
    payload: Mapping[str, Any],
) -> SuccessModel | ViperFailure:
    """Validate one raw request and return a typed success or failure."""
    request_type = REQUEST_REGISTRY[operation]
    try:
        request = request_type.model_validate(payload)
    except ValidationError as exc:
        return ViperFailure(
            operation=operation,
            origin="request",
            code="invalid_request",
            message="request failed schema validation",
            details={
                "errors": exc.errors(
                    include_url=False,
                    include_context=False,
                    include_input=False,
                )
            },
        )
    try:
        return HANDLER_REGISTRY[operation](request)
    except ViperError as exc:
        return exc.failure
    except Exception:
        return ViperFailure(
            operation=operation,
            origin="internal",
            code="internal_error",
            message="unexpected application failure",
        )


def result_json_bytes(result: ApplicationModel) -> bytes:
    """Encode one application result as deterministic UTF-8 JSON."""
    value = result.model_dump(mode="json")
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return f"{rendered}\n".encode()


__all__ = [
    "CapabilitiesRequest",
    "CapabilitiesSuccess",
    "ExecuteStageRequest",
    "ExecuteStageSuccess",
    "FreezeRunRequest",
    "FreezeRunSuccess",
    "SchemaRequest",
    "SchemaSuccess",
    "ValidateResolvedStageRequest",
    "ValidateResolvedStageSuccess",
    "ValidateRunSpecRequest",
    "ValidateRunSpecSuccess",
    "ValidateStageRequest",
    "ValidateStageSuccess",
    "VerifyBenchmarkRequest",
    "VerifyBenchmarkSuccess",
    "VerifyPointerRequest",
    "VerifyPointerSuccess",
    "VerifyRunRequest",
    "VerifyRunSuccess",
    "ViperError",
    "ViperFailure",
    "dispatch",
    "execute_stage",
    "freeze_run",
    "get_capabilities",
    "get_schema",
    "result_json_bytes",
    "validate_resolved_stage",
    "validate_run_spec",
    "validate_stage",
    "verify_benchmark",
    "verify_pointer",
    "verify_run",
]
