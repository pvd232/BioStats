"""Tests for project-owned stage-parameter model loading and validation."""

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.fixtures import stage_implementation_ref
from viper.parameter_models import (
    ParameterModelError,
    load_parameter_model,
    validate_parameters,
    validate_stage_parameters,
    verify_parameter_model_bytes,
)
from viper.protocol import (
    PARAMETERS,
    RESUME_STATE,
    ArtifactPointerRef,
    ParameterModelRef,
    SingleFileArtifactSpec,
    StoredInputRef,
    TrainParams,
    TrainSpec,
)
from viper.serialization import serialize_document


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


def test_parameter_model_rejects_implicit_defaults(tmp_path: Path) -> None:
    """Require every effective project-model value in the frozen mapping."""
    raw = (
        b"from viper.protocol import TrainParams\n\n"
        b"class DefaultedTrainParams(TrainParams):\n"
        b"    epochs: int\n"
        b"    dropout: float = 0.1\n"
    )
    path = tmp_path / "defaulted.py"
    path.write_bytes(raw)
    reference = ParameterModelRef(
        path="project/parameters/defaulted.py",
        symbol="DefaultedTrainParams",
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
    )

    with pytest.raises(ParameterModelError, match="every effective"):
        validate_parameters(
            path,
            reference,
            TrainParams.model_validate({"epochs": 2}),
            TrainParams,
        )


def test_parameter_model_rejects_type_coercion(tmp_path: Path) -> None:
    """Keep project field types identical to the frozen JSON value types."""
    path, raw = _model_file(tmp_path)

    with pytest.raises(ValidationError):
        validate_parameters(
            path,
            _reference(raw),
            TrainParams.model_validate({"epochs": "2", "learning_rate": 0.1}),
            TrainParams,
        )


def test_parameter_model_requires_the_stage_specific_base(tmp_path: Path) -> None:
    """Reject a selected class that does not specialize TrainParams."""
    path = tmp_path / "wrong.py"
    path.write_text(
        'class WrongParams:\n    """Does not specialize TrainParams."""\n',
        encoding="utf-8",
    )

    with pytest.raises(ParameterModelError, match="subclass TrainParams"):
        load_parameter_model(path, "WrongParams", TrainParams)


def test_parameter_model_reports_import_failure(tmp_path: Path) -> None:
    """Report an exception raised while importing the selected project file."""
    path = tmp_path / "broken.py"
    path.write_text(
        'raise RuntimeError("broken import")\n',
        encoding="utf-8",
    )

    with pytest.raises(ParameterModelError, match="raised during import"):
        load_parameter_model(path, "BrokenParams", TrainParams)


def test_parameter_model_rejects_tampered_bytes(tmp_path: Path) -> None:
    """Reject implementation bytes that differ from the frozen reference."""
    _, raw = _model_file(tmp_path)
    reference = _reference(raw)

    with pytest.raises(ParameterModelError, match="byte count"):
        verify_parameter_model_bytes(reference, raw + b"# changed\n")


def test_stage_parameter_validation_runs_in_a_worker(tmp_path: Path) -> None:
    """Validate a stage while keeping project imports outside this process."""
    _, raw = _model_file(tmp_path)
    reference = _reference(raw)
    model_path = tmp_path / reference.path
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(raw)
    stage = TrainSpec(
        implementation=stage_implementation_ref("project/train.py"),
        parameter_model=reference,
        inputs={
            "dataset": StoredInputRef(
                pointer=ArtifactPointerRef.model_validate(
                    {
                        "repository": "https://github.com/example/project",
                        "commit": "a" * 40,
                        "path": "inputs/datasets/example/current.pointer.yaml",
                    }
                ),
                path="inputs/datasets/example/data.bin",
                data_role="training",
            )
        },
        params=TrainParams.model_validate({"epochs": 2, "learning_rate": 0.1}),
        artifacts={
            PARAMETERS: SingleFileArtifactSpec(
                path="experiments/example/runs/baseline/"
                "01JABCDEFGHJKMNPQRSTVWXYZ0/artifacts/models/main/parameters.bin",
                loader="project/loaders/parameters.py",
                data_role="training",
            ),
            RESUME_STATE: SingleFileArtifactSpec(
                path="experiments/example/runs/baseline/"
                "01JABCDEFGHJKMNPQRSTVWXYZ0/artifacts/models/main/resume.bin",
                loader="project/loaders/resume.py",
                data_role="training",
            ),
        },
    )
    stage_path = tmp_path / "drafts/train.yaml"
    stage_path.parent.mkdir(parents=True)
    stage_path.write_bytes(serialize_document(stage))

    validated = validate_stage_parameters(tmp_path, stage_path, stage)

    assert validated["epochs"] == 2
    assert validated["learning_rate"] == 0.1

    invalid_stage = stage.model_copy(
        update={
            "params": TrainParams.model_validate({"epochs": 0, "learning_rate": 0.1})
        }
    )
    stage_path.write_bytes(serialize_document(invalid_stage))
    with pytest.raises(ParameterModelError, match="worker failed"):
        validate_stage_parameters(tmp_path, stage_path, invalid_stage)
