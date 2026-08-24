"""Generate a small project that demonstrates every VIPER stage kind."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

PACKAGE_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


class ProjectInitializationError(RuntimeError):
    """Report an invalid target or a failed scaffold write."""


def validate_package_name(package: str) -> None:
    """Require one importable lowercase Python package name."""
    if PACKAGE_PATTERN.fullmatch(package) is None:
        raise ProjectInitializationError("package must match ^[a-z][a-z0-9_]*$")


def _project_files(package: str) -> dict[str, str]:
    """Return the complete starter-project file mapping."""
    stage_definitions = {
        "download": ("DownloadParams", "download_stage", "dataset"),
        "build": ("BuildParams", "build_stage", "prior"),
        "embed": ("EmbedParams", "embed_stage", "embedding"),
        "train": ("TrainParams", "train_stage", "parameters"),
        "evaluate": ("EvaluateParams", "evaluate_stage", "predictions"),
    }
    files: dict[str, str] = {
        ".gitignore": ".viper/\n__pycache__/\n*.egg-info/\n",
        "README.md": f"""# {package}

This project contains one decorated callable for each VIPER stage kind.

Run the focused project tests:

```bash
python -m pytest -q
```

The files under `experiments/` and `benchmarks/` hold authored protocol
documents. Their implementation references use repository-relative paths, so
the package can be renamed or moved beneath another source directory before a
run is frozen.
""",
        "pyproject.toml": f'''[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "{package.replace("_", "-")}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["viper-provenance>=0.1.0a1"]

[project.optional-dependencies]
test = ["pytest>=9,<10"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
''',
        f"src/{package}/__init__.py": (
            f'"""Project-owned stages and provenance extensions for {package}."""\n'
        ),
        f"src/{package}/parameters.py": (
            '''"""Define project-owned stage parameter models."""

from pydantic import Field

from viper.protocol import (
    BuildParams,
    DownloadParams,
    EmbedParams,
    EvaluateParams,
    TrainParams,
)


class ProjectDownloadParams(DownloadParams):
    """Select the expected media type for the retrieved dataset."""

    media_type: str = "text/plain"


class ProjectBuildParams(BuildParams):
    """Select the delimiter consumed by the prior builder."""

    delimiter: str = ","


class ProjectEmbedParams(EmbedParams):
    """Select the dimension of the example embedding."""

    dimensions: int = Field(default=2, gt=0)


class ProjectTrainParams(TrainParams):
    """Select the number of example training passes."""

    epochs: int = Field(default=1, gt=0)


class ProjectEvaluateParams(EvaluateParams):
    """Select the label written beside the example predictions."""

    label: str = "baseline"
'''
        ),
        f"src/{package}/artifact_loaders/__init__.py": (
            '"""Project-owned artifact reconstruction functions."""\n'
        ),
        f"src/{package}/artifact_loaders/bytes_file.py": (
            '''"""Load one file artifact as exact bytes."""

from pathlib import Path


def load(path: Path) -> bytes:
    """Return the complete file contents."""
    return path.read_bytes()
'''
        ),
        f"src/{package}/metrics/__init__.py": (
            '"""Project-owned metric implementations."""\n'
        ),
        f"src/{package}/metrics/evaluation.py": (
            '''"""Define one recomputed evaluation metric."""

from viper.metrics import metric


@metric(metric_id="prediction_bytes", kind="evaluation", mode="recompute")
def prediction_bytes(context) -> float:
    """Return the byte count of the verified prediction artifact."""
    return float(len(context.artifacts["predictions"].read_bytes()))
'''
        ),
        "experiments/README.md": """# Experiments

Freeze authored experiment, variant, stage, and run documents here. VIPER
binds every implementation through its repository-relative path and exact
source identity.
""",
        "benchmarks/README.md": """# Benchmarks

A benchmark governs one evaluation contract across candidate run plans and
requires an independently executed confirmation.
""",
        "tests/test_stage_definitions.py": (
            f'''"""Verify generated stages expose their VIPER definitions."""

from {package}.stages.build import build
from {package}.stages.download import download
from {package}.stages.embed import embed
from {package}.stages.evaluate import evaluate
from {package}.stages.train import train

from viper.stages import stage_definition


def test_stage_kinds() -> None:
    """Match each callable with the stage kind fixed by its decorator."""
    stages = (download, build, embed, train, evaluate)

    assert tuple(stage_definition(stage).kind for stage in stages) == (
        "download",
        "build",
        "embed",
        "train",
        "evaluate",
    )
'''
        ),
    }
    for stage, (params, decorator, artifact) in stage_definitions.items():
        input_read = ""
        if stage != "download":
            input_read = (
                "    source = next(iter(context.inputs.values()))\n"
                "    payload = source.read_bytes()\n"
            )
        else:
            input_read = (
                "    retrieval = next(iter(context.retrievals.values()))\n"
                "    payload = retrieval.body.read_bytes()\n"
            )
        extra_artifact = ""
        if stage == "train":
            extra_artifact = (
                "    context.artifacts['resume_state'].write_bytes(b'resume')\n"
            )
        files[
            f"src/{package}/stages/{stage}.py"
        ] = f'''"""Execute the example {stage} stage."""

from {package}.parameters import Project{params}
from viper import {decorator}


@{decorator}(parameter_model=Project{params})
def {stage}(context) -> None:
    """Write the declared {artifact} artifact from verified inputs."""
{input_read}    destination = context.artifacts["{artifact}"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
{extra_artifact}'''
    files[f"src/{package}/stages/__init__.py"] = (
        '"""Project-owned decorated stage callables."""\n'
    )
    return files


def initialize_project(path: Path, package: str) -> tuple[Path, ...]:
    """Write the starter project into one absent or empty directory."""
    validate_package_name(package)
    target = path.resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ProjectInitializationError("target directory must be absent or empty")

    files = _project_files(package)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        for relative_path, content in files.items():
            destination = staging / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        if target.exists():
            target.rmdir()
        staging.replace(target)
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise ProjectInitializationError(
            "project scaffold could not be written"
        ) from exc
    return tuple(target / relative_path for relative_path in sorted(files))
