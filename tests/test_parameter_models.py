"""Tests for project-owned stage-parameter model loading and validation."""

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from viper.parameter_models import (
    ParameterModelError,
    load_parameter_model,
    validate_parameters,
    verify_parameter_model_bytes,
)
from viper.protocol import ParameterModelRef, TrainParams


def _model_file(tmp_path: Path) -> tuple[Path, bytes]:
    """Write one constrained training-parameter class for focused tests."""
    raw = (
        b"from pydantic import Field\n"
        b"from viper.protocol import TrainParams\n\n"
        b"class TinyTrainParams(TrainParams):\n"
        b"    epochs: int = Field(gt=0)\n"
        b"    learning_rate: float = Field(gt=0)\n"
    )
    path = tmp_path / "tiny_train_params.py"
    path.write_bytes(raw)
    return path, raw


def _reference(raw: bytes) -> ParameterModelRef:
    """Identify the exact parameter-model bytes written by the test."""
    return ParameterModelRef(
        path="project/parameters/tiny_train.py",
        symbol="TinyTrainParams",
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
    )


def test_parameter_model_validates_project_fields(tmp_path: Path) -> None:
    """Validate supplied values through the selected TrainParams subclass."""
    path, raw = _model_file(tmp_path)

    validated = validate_parameters(
        path,
        _reference(raw),
        TrainParams.model_validate({"epochs": 2, "learning_rate": 0.1}),
        TrainParams,
    )

    assert validated["epochs"] == 2
    assert validated["learning_rate"] == 0.1


def test_parameter_model_rejects_invalid_project_values(tmp_path: Path) -> None:
    """Propagate project Pydantic constraints for an invalid parameter value."""
    path, raw = _model_file(tmp_path)

    with pytest.raises(ValidationError, match="greater than 0"):
        validate_parameters(
            path,
            _reference(raw),
            TrainParams.model_validate({"epochs": 0, "learning_rate": 0.1}),
            TrainParams,
        )


def test_parameter_model_requires_the_stage_specific_base(tmp_path: Path) -> None:
    """Reject a selected class that does not specialize TrainParams."""
    path = tmp_path / "wrong.py"
    path.write_text("class WrongParams:\n    pass\n", encoding="utf-8")

    with pytest.raises(ParameterModelError, match="subclass TrainParams"):
        load_parameter_model(path, "WrongParams", TrainParams)


def test_parameter_model_rejects_tampered_bytes(tmp_path: Path) -> None:
    """Reject implementation bytes that differ from the frozen reference."""
    _, raw = _model_file(tmp_path)
    reference = _reference(raw)

    with pytest.raises(ParameterModelError, match="byte count"):
        verify_parameter_model_bytes(reference, raw + b"# changed\n")
