"""Persist ordered run-attempt transitions in an append-only journal."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AttemptState = Literal[
    "allocated",
    "preflighting",
    "running_stage",
    "publishing_stage",
    "closing_attempt",
    "publishing_attempt_files",
    "publishing_terminal_run",
    "terminal",
]


class JournalEntry(BaseModel):
    """Record one durable attempt transition or external-effect result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    state: AttemptState
    recorded_at: datetime
    event: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class DurableJournal:
    """Append synchronized entries and reconstruct one attempt's latest state."""

    def __init__(self, path: Path) -> None:
        """Bind the journal to one canonical control-file path."""
        self.path = path

    def read(self) -> tuple[JournalEntry, ...]:
        """Load and validate every complete journal entry in order."""
        if not self.path.exists():
            return ()
        entries = tuple(
            JournalEntry.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line
        )
        expected = tuple(range(1, len(entries) + 1))
        if tuple(entry.sequence for entry in entries) != expected:
            raise ValueError("journal sequence is discontinuous")
        return entries

    def append(
        self,
        state: AttemptState,
        event: str,
        *,
        recorded_at: datetime,
        details: dict[str, Any] | None = None,
    ) -> JournalEntry:
        """Append and synchronize one validated journal entry."""
        entries = self.read()
        entry = JournalEntry(
            sequence=len(entries) + 1,
            state=state,
            recorded_at=recorded_at,
            event=event,
            details={} if details is None else details,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(entry.model_dump_json().encode("utf-8") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        return entry

    def latest(self) -> JournalEntry | None:
        """Return the latest durable entry for recovery decisions."""
        entries = self.read()
        return entries[-1] if entries else None
