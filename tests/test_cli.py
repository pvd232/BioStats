"""Tests for the installed VIPER command surface."""

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
