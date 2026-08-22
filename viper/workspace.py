"""Create bounded local workspaces for VIPER run attempts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .ids import RunId


class WorkspaceError(RuntimeError):
    """Report an unsafe path or conflicting attempt workspace."""


@dataclass(frozen=True)
class AttemptWorkspace:
    """Identify every writable directory owned by one local run attempt."""

    root: Path
    control: Path
    source: Path
    inputs: Path
    stages: Path
    measurements: Path
    logs: Path
    terminal: Path
    lock: Path

    @classmethod
    def create(
        cls,
        workspace_root: Path,
        run_id: RunId,
        attempt_id: int,
    ) -> AttemptWorkspace:
        """Create the canonical directory set for one attempt."""
        if attempt_id < 1:
            raise WorkspaceError("attempt_id must be positive")
        root = workspace_root.resolve() / str(run_id) / f"attempt-{attempt_id}"
        root.mkdir(parents=True, exist_ok=True)
        workspace = cls(
            root=root,
            control=root / "control",
            source=root / "source",
            inputs=root / "inputs",
            stages=root / "stages",
            measurements=root / "measurements",
            logs=root / "logs",
            terminal=root / "resolved.yaml",
            lock=root.parent / ".active.lock",
        )
        for directory in (
            workspace.control,
            workspace.source,
            workspace.inputs,
            workspace.stages,
            workspace.measurements,
            workspace.logs,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return workspace

    def resolve(self, relative_path: str) -> Path:
        """Resolve one relative path beneath this attempt root."""
        if Path(relative_path).is_absolute():
            raise WorkspaceError("workspace path must be relative")
        candidate = (self.root / relative_path).resolve()
        if not candidate.is_relative_to(self.root):
            raise WorkspaceError("workspace path escapes the attempt root")
        return candidate

    def acquire(self) -> None:
        """Acquire exclusive ownership of the run workspace."""
        try:
            descriptor = os.open(
                self.lock,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise WorkspaceError("run workspace already has an active owner") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())

    def release(self) -> None:
        """Release this attempt's exclusive run-workspace lock."""
        self.lock.unlink(missing_ok=True)
