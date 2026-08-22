"""Load and invoke project-owned Pydantic stage-parameter models."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, JsonValue

from .protocol import InternalSpec, ParameterModelRef, ParameterSet
from .serialization import load_stage_spec
from .worker import ExecutionPolicy, WorkerRequest, execute_worker


class ParameterModelError(RuntimeError):
    """Report an invalid parameter-model identity, class, or parameter value."""


class ParameterValidationContext(BaseModel):
    """Tell one worker which frozen stage and parameter class to validate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_spec_path: Path
    result_path: Path


def verify_parameter_model_bytes(
    reference: ParameterModelRef,
    raw: bytes,
) -> None:
    """Compare retrieved parameter-model bytes with their frozen identity."""
    if len(raw) != reference.bytes:
        raise ParameterModelError(
            "parameter model byte count differs from its reference"
        )
    if hashlib.sha256(raw).hexdigest() != reference.sha256:
        raise ParameterModelError("parameter model SHA-256 differs from its reference")


def load_parameter_model(
    path: Path,
    symbol: str,
    expected_base: type[ParameterSet],
) -> type[ParameterSet]:
    """Load one top-level Pydantic class and enforce its stage-specific base."""
    module_name = f"_viper_parameter_model_{path.stem}_{abs(hash(path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ParameterModelError("parameter model module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ParameterModelError(
            "parameter model module raised during import"
        ) from exc
    value = getattr(module, symbol, None)
    if not isinstance(value, type) or not issubclass(value, expected_base):
        raise ParameterModelError(
            f"parameter model must subclass {expected_base.__name__}"
        )
    return cast(type[ParameterSet], value)


def validate_parameters(
    path: Path,
    reference: ParameterModelRef,
    params: ParameterSet,
    expected_base: type[ParameterSet],
) -> dict[str, JsonValue]:
    """Validate one frozen parameter mapping with its selected project class."""
    raw = path.read_bytes()
    verify_parameter_model_bytes(reference, raw)
    model = load_parameter_model(path, reference.symbol, expected_base)
    validated = model.model_validate(params.model_dump(mode="python"))
    return cast(dict[str, JsonValue], validated.model_dump(mode="json"))


def validate_stage_parameters(
    repository_root: Path,
    stage_spec_path: Path,
    stage: InternalSpec,
    *,
    timeout_seconds: float | None = None,
) -> dict[str, JsonValue]:
    """Validate one stage in a separate trusted-local worker process."""
    root = repository_root.resolve()
    package_root = str(Path(__file__).resolve().parents[1])
    existing_python_path = os.environ.get("PYTHONPATH")
    python_path = (
        package_root
        if existing_python_path is None
        else f"{package_root}{os.pathsep}{existing_python_path}"
    )
    state_root = root / ".viper" / "parameter-validation"
    state_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=state_root) as directory:
        workspace = Path(directory)
        context_path = workspace / "context.json"
        result_path = workspace / "result.json"
        context_path.write_text(
            ParameterValidationContext(
                stage_spec_path=stage_spec_path.resolve(),
                result_path=result_path,
            ).model_dump_json(),
            encoding="utf-8",
        )
        try:
            execute_worker(
                WorkerRequest(
                    workspace_root=root,
                    working_directory=root,
                    context_path=context_path,
                    command=(sys.executable, "-m", "viper.parameter_worker"),
                    environment={"PYTHONPATH": python_path},
                    policy=ExecutionPolicy(timeout_seconds=timeout_seconds),
                )
            )
        except Exception as exc:
            raise ParameterModelError("parameter validation worker failed") from exc
        if not result_path.is_file():
            raise ParameterModelError("parameter validation worker wrote no result")
        value = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ParameterModelError("parameter validation worker returned no mapping")
        return cast(dict[str, JsonValue], value)


def validate_loaded_stage_parameters(
    repository_root: Path,
    stage_spec_path: Path,
    *,
    timeout_seconds: float | None = None,
) -> dict[str, JsonValue]:
    """Load one stage specification and validate its selected parameter class."""
    stage = load_stage_spec(stage_spec_path)
    if not isinstance(stage, InternalSpec):
        raise ParameterModelError("parameter validation requires an internal stage")
    return validate_stage_parameters(
        repository_root,
        stage_spec_path,
        stage,
        timeout_seconds=timeout_seconds,
    )
