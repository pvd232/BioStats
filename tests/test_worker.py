"""Tests for bounded attempt workspaces, journals, and local workers."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from viper.journal import DurableJournal
from viper.worker import ExecutionPolicy, WorkerError, WorkerRequest, execute_worker
from viper.workspace import AttemptWorkspace, WorkspaceError


def test_workspace_enforces_exclusive_run_ownership(tmp_path: Path) -> None:
    """Reject a second owner while one run-workspace lock is active."""
    workspace = AttemptWorkspace.create(tmp_path, "01JABCDEFGHJKMNPQRSTVWXYZ", 1)
    workspace.acquire()

    with pytest.raises(WorkspaceError, match="active owner"):
        workspace.acquire()

    workspace.release()
    workspace.acquire()
    workspace.release()


def test_workspace_rejects_path_escape(tmp_path: Path) -> None:
    """Keep resolved attempt paths beneath the attempt root."""
    workspace = AttemptWorkspace.create(tmp_path, "01JABCDEFGHJKMNPQRSTVWXYZ", 1)

    with pytest.raises(WorkspaceError, match="escapes"):
        workspace.resolve("../../outside")


def test_journal_persists_ordered_attempt_transitions(tmp_path: Path) -> None:
    """Recover the latest attempt state from synchronized JSON Lines entries."""
    journal = DurableJournal(tmp_path / "control" / "journal.jsonl")
    now = datetime.now(UTC)

    journal.append("allocated", "attempt allocated", recorded_at=now)
    journal.append("preflighting", "preflight started", recorded_at=now)

    assert [entry.sequence for entry in journal.read()] == [1, 2]
    assert journal.latest().state == "preflighting"  # type: ignore[union-attr]


def test_trusted_local_worker_receives_context_path(tmp_path: Path) -> None:
    """Supply the versioned context path through the worker environment."""
    context = tmp_path / "control" / "context.json"
    context.parent.mkdir()
    context.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    request = WorkerRequest(
        workspace_root=tmp_path,
        working_directory=tmp_path,
        context_path=context,
        command=(
            sys.executable,
            "-c",
            "import os; print(os.environ['VIPER_CONTEXT_PATH'])",
        ),
    )

    result = execute_worker(request)

    assert result.stdout.decode().strip() == str(context)


def test_trusted_local_worker_enforces_timeout(tmp_path: Path) -> None:
    """Terminate a local worker after its declared process duration."""
    context = tmp_path / "context.json"
    context.write_text("{}", encoding="utf-8")
    request = WorkerRequest(
        workspace_root=tmp_path,
        working_directory=tmp_path,
        context_path=context,
        command=(sys.executable, "-c", "import time; time.sleep(1)"),
        policy=ExecutionPolicy(timeout_seconds=0.01),
    )

    with pytest.raises(WorkerError, match="timeout"):
        execute_worker(request)
