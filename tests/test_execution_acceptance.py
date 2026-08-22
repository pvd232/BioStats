"""Acceptance test for a real stage command and its produced artifact files."""

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from viper.records import (
    DownloadSpec,
    ResolvedSingleFileArtifact,
    RunStageRef,
)
from viper.serialization import serialize_record
from viper.stage_execution import execute_stage_process

RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RUN_ROOT = f"experiments/e001_download/runs/baseline/{RUN_ID}"


class StageExecutionAcceptanceTests(unittest.TestCase):
    """Verify one actual entrypoint invocation through artifact identification."""

    def test_stage_command_writes_and_hashes_its_declared_artifact(self) -> None:
        """Run a download stage and record the exact bytes it produces."""
        artifact_path = f"{RUN_ROOT}/artifacts/datasets/tiny/dataset.bin"
        spec = DownloadSpec.model_validate(
            {
                "kind": "download",
                "script": "jobs/ingest_tiny.py",
                "inputs": {
                    "source": {
                        "kind": "remote",
                        "url": "https://example.com/tiny-v1",
                        "version": "v1",
                    }
                },
                "artifacts": {
                    "dataset": {
                        "kind": "file",
                        "path": artifact_path,
                        "loader": "project/loaders/bytes_file.py",
                    }
                },
            }
        )

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            script_path = root / spec.script
            script_path.parent.mkdir(parents=True)
            script_path.write_text(
                "from pathlib import Path\n"
                f"target = Path({artifact_path!r})\n"
                "target.parent.mkdir(parents=True, exist_ok=True)\n"
                "target.write_bytes(b'tiny dataset')\n"
            )
            stage_path = root / f"{RUN_ROOT}/stages/download/spec.yaml"
            stage_path.parent.mkdir(parents=True)
            stage_raw = serialize_record(spec)
            stage_path.write_bytes(stage_raw)
            reference = RunStageRef(
                stage_id="download",
                spec=stage_path.relative_to(root).as_posix(),
                sha256=hashlib.sha256(stage_raw).hexdigest(),
                bytes=len(stage_raw),
            )

            result = execute_stage_process(root, reference, spec)
            produced = result.artifacts["dataset"]
            assert isinstance(produced, ResolvedSingleFileArtifact)
            raw = (root / produced.file.path).read_bytes()

        self.assertEqual(
            result.command,
            ("python", str(spec.script), str(reference.spec)),
        )
        self.assertEqual(raw, b"tiny dataset")
        self.assertEqual(produced.file.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(produced.file.bytes, len(raw))
