"""Tests for the installed VIPER command surface."""

import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from viper.cli import main


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
