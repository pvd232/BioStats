"""Invoke one frozen stage command and identify every produced artifact file."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .parameter_models import ParameterModelError, validate_stage_parameters
from .protocol import (
    ArtifactName,
    BaseSpec,
    BundleArtifactSpec,
    ExecutionContext,
    ParameterizedSpec,
    ResolvedArtifact,
    ResolvedBundleArtifact,
    ResolvedBundleMember,
    ResolvedSingleFileArtifact,
    RunSpec,
    RunStageRef,
    SingleFileArtifactSpec,
    SnapshotFileRef,
)
from .runtime import process_environment


class StageExecutionError(RuntimeError):
    """A frozen stage command failed or did not produce its declared files."""


@dataclass(frozen=True)
class StageProcessResult:
    """Record one local stage invocation and its exact output file identities."""

    command: tuple[str, ...]
    started_at: datetime
    completed_at: datetime
    artifacts: dict[ArtifactName, ResolvedArtifact]
    execution_context: ExecutionContext
    stdout: bytes
    stderr: bytes


def _workspace_path(repository_root: Path, relative_path: str) -> Path:
    """Resolve a protocol path without permitting workspace escape."""
    root = repository_root.resolve()
    path = root / relative_path
    if not path.resolve().is_relative_to(root):
        raise StageExecutionError("stage path escapes the repository root")
    return path


def _snapshot_file(repository_root: Path, relative_path: str) -> SnapshotFileRef:
    """Hash one regular output file at its repository-relative path."""
    path = _workspace_path(repository_root, relative_path)
    if path.is_symlink() or not path.is_file():
        raise StageExecutionError(f"declared artifact file is missing: {relative_path}")
    raw = path.read_bytes()
    return SnapshotFileRef(
        path=relative_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
    )


def _resolve_artifact(
    repository_root: Path,
    declaration: SingleFileArtifactSpec | BundleArtifactSpec,
) -> ResolvedArtifact:
    """Convert one materialized artifact into exact file records."""
    if isinstance(declaration, SingleFileArtifactSpec):
        return ResolvedSingleFileArtifact(
            file=_snapshot_file(repository_root, declaration.path)
        )

    root = _workspace_path(repository_root, declaration.path)
    if root.is_symlink() or not root.is_dir():
        raise StageExecutionError(
            f"declared artifact bundle is missing: {declaration.path}"
        )

    members: list[ResolvedBundleMember] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise StageExecutionError("artifact bundles must not contain symlinks")
        if not path.is_file():
            continue
        relative_member = path.relative_to(root).as_posix()
        members.append(
            ResolvedBundleMember(
                relative_path=relative_member,
                file=_snapshot_file(
                    repository_root,
                    f"{declaration.path}/{relative_member}",
                ),
            )
        )

    try:
        return ResolvedBundleArtifact(members=tuple(members))
    except ValueError as exc:
        raise StageExecutionError(
            "artifact bundle does not satisfy its declared file contract"
        ) from exc


def execute_stage_process(
    repository_root: Path,
    run: RunSpec,
    stage_reference: RunStageRef,
    stage_spec: BaseSpec,
    *,
    timeout_seconds: float | None = None,
) -> StageProcessResult:
    """Run the canonical stage command and hash every declared output file."""
    root = repository_root.resolve()
    spec_path = _workspace_path(root, stage_reference.spec)
    spec_raw = spec_path.read_bytes()
    if hashlib.sha256(spec_raw).hexdigest() != stage_reference.sha256:
        raise StageExecutionError("stage spec SHA-256 does not match RunStageRef")
    if len(spec_raw) != stage_reference.bytes:
        raise StageExecutionError("stage spec byte count does not match RunStageRef")

    script_path = _workspace_path(root, stage_spec.script)
    if not script_path.is_file():
        raise StageExecutionError(f"stage entrypoint is missing: {stage_spec.script}")

    if isinstance(stage_spec, ParameterizedSpec):
        try:
            validate_stage_parameters(
                root,
                spec_path,
                stage_spec,
                timeout_seconds=timeout_seconds,
            )
        except ParameterModelError as exc:
            raise StageExecutionError("stage parameter validation failed") from exc

    run_spec_path = (
        f"experiments/{run.experiment_id}/runs/{run.variant_id}/{run.run_id}/spec.yaml"
    )
    command = (
        "python",
        "-m",
        "viper.stage_worker",
        str(stage_reference.spec),
        run_spec_path,
    )
    environment = os.environ.copy()
    environment.update(process_environment(run.seed, run.reproducibility))
    package_root = str(Path(__file__).resolve().parents[1])
    existing_python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        package_root
        if existing_python_path is None
        else f"{package_root}{os.pathsep}{existing_python_path}"
    )
    runtime_context_path = (
        root / ".viper" / "runtime" / (f"{run.run_id}.{stage_reference.stage_id}.json")
    )
    runtime_context_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_context_path.unlink(missing_ok=True)
    environment["VIPER_RUNTIME_CONTEXT_PATH"] = str(runtime_context_path)
    started_at = datetime.now(UTC)
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )
    completed_at = datetime.now(UTC)
    if completed.returncode != 0:
        raise StageExecutionError(
            f"stage command exited with status {completed.returncode}: "
            f"{completed.stderr.decode(errors='replace').strip()}"
        )
    if not runtime_context_path.is_file():
        raise StageExecutionError("stage worker did not record its runtime context")
    execution_context = ExecutionContext.model_validate_json(
        runtime_context_path.read_text(encoding="utf-8")
    )

    artifacts = {
        name: _resolve_artifact(root, declaration)
        for name, declaration in stage_spec.artifacts.items()
    }
    return StageProcessResult(
        command=command,
        started_at=started_at,
        completed_at=completed_at,
        artifacts=artifacts,
        execution_context=execution_context,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
