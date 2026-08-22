"""Load and invoke project-owned Pydantic stage-parameter models."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from .protocol import ParameterModelRef, ParameterSet


class ParameterModelError(RuntimeError):
    """Report an invalid parameter-model identity, class, or parameter value."""


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
