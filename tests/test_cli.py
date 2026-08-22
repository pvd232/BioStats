"""Tests for the installed VIPER command surface."""

import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from viper.cli import main
from viper.journal import DurableJournal


class CommandLineTests(unittest.TestCase):
    """Verify command dispatch through public authoring and validation paths."""

    def test_validate_stage_command_loads_active_example(self) -> None:
        """Validate one canonical stage file and report its stage kind."""
        path = Path("examples/provenance/stages/download/spec.yaml")
        output = StringIO()

        with redirect_stdout(output):
            status = main(["validate-stage", str(path)])

        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue(), "valid download stage\n")

    def test_cli_json_success_contract(self) -> None:
        """Emit one JSON success document on standard output."""
        process = subprocess.run(
            [sys.executable, "-m", "viper.cli", "--json", "capabilities"],
            check=False,
            capture_output=True,
        )

        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stderr, b"")
        self.assertEqual(json.loads(process.stdout)["status"], "ok")

    def test_cli_json_failure_contract(self) -> None:
        """Emit one JSON parsing failure with a nonzero exit status."""
        process = subprocess.run(
            [sys.executable, "-m", "viper.cli", "--json", "unknown"],
            check=False,
            capture_output=True,
        )

        self.assertEqual(process.returncode, 1)
        self.assertEqual(process.stderr, b"")
        failure = json.loads(process.stdout)
        self.assertEqual(failure["origin"], "cli")
        self.assertEqual(failure["operation"], None)

    def test_preflight_failure_uses_nonzero_exit_status(self) -> None:
        """Return a failing exit status when plan checks find an invalid path."""
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "viper.cli",
                "--json",
                "preflight",
                "missing/spec.yaml",
            ],
            check=False,
            capture_output=True,
        )

        self.assertEqual(process.returncode, 1)
        self.assertEqual(process.stderr, b"")
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["ready"], False)

    def test_status_command_reads_attempt_journal(self) -> None:
        """Return one attempt's latest durable state through the JSON command."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            DurableJournal(path).append(
                "allocated",
                "attempt allocated",
                recorded_at=datetime(2026, 8, 22, tzinfo=UTC),
            )
            process = subprocess.run(
                [sys.executable, "-m", "viper.cli", "--json", "status", str(path)],
                check=False,
                capture_output=True,
            )

        self.assertEqual(process.returncode, 0)
        result = json.loads(process.stdout)
        self.assertEqual(result["state"], "allocated")
        self.assertEqual(result["next_states"], ["preflighting", "terminal"])
