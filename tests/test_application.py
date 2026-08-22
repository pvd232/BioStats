"""Tests for the typed VIPER application boundary."""

import json
from pathlib import Path

from viper.application import (
    CapabilitiesRequest,
    SchemaRequest,
    ValidateStageRequest,
    ViperFailure,
    dispatch,
    get_capabilities,
    get_schema,
    result_json_bytes,
    validate_stage,
)


def test_application_schema_and_capability_discovery() -> None:
    """Return registered schemas and the installed operation inventory."""
    schema = get_schema(SchemaRequest(name="RunSpec"))
    capabilities = get_capabilities(CapabilitiesRequest())

    assert schema.name == "RunSpec"
    assert schema.json_schema["title"] == "RunSpec"
    assert "validate_run_spec" in capabilities.operations
    assert capabilities.execution_backends == ("trusted_local",)


def test_validate_stage_returns_typed_success() -> None:
    """Validate a local stage through the public Python operation."""
    path = Path("examples/provenance/stages/download/spec.yaml")

    result = validate_stage(ValidateStageRequest(path=path))

    assert result.status == "ok"
    assert result.operation == "validate_stage"
    assert result.stage_kind == "download"


def test_dispatch_returns_typed_request_failure() -> None:
    """Return stable request errors before an operation is invoked."""
    result = dispatch("validate_stage", {})

    assert isinstance(result, ViperFailure)
    assert result.origin == "request"
    assert result.code == "invalid_request"


def test_result_json_is_deterministic_and_newline_terminated() -> None:
    """Encode the same result into identical compact JSON bytes."""
    result = get_capabilities(CapabilitiesRequest())

    first = result_json_bytes(result)
    second = result_json_bytes(result)

    assert first == second
    assert first.endswith(b"\n")
    assert json.loads(first)["operation"] == "get_capabilities"
