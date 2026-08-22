"""Acceptance test for a real stage command and its produced artifact files."""

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from viper.protocol import (
    DownloadParams,
    DownloadSpec,
    ParameterModelRef,
    RemoteFileRef,
    ResolvedSingleFileArtifact,
    RunSpec,
    RunStageRef,
    SingleFileArtifactSpec,
)
from viper.serialization import serialize_document
from viper.stage_execution import execute_stage_process

RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RUN_ROOT = f"experiments/e001_download/runs/baseline/{RUN_ID}"


class StageExecutionAcceptanceTests(unittest.TestCase):
    """Verify one actual entrypoint invocation through artifact identification."""

    def test_stage_command_writes_and_hashes_its_declared_artifact(self) -> None:
        """Run a download stage and record the exact bytes it produces."""
        artifact_path = f"{RUN_ROOT}/artifacts/datasets/tiny/dataset.bin"
        parameter_source = (
            b"from viper.protocol import DownloadParams\n\n"
            b"class TinyDownloadParameters(DownloadParams):\n"
            b'    """Validate parameters for the execution fixture."""\n'
        )
        spec = DownloadSpec(
            script="jobs/ingest_tiny.py",
            parameter_model=ParameterModelRef(
                path="project/parameters/download.py",
                symbol="TinyDownloadParameters",
                sha256=hashlib.sha256(parameter_source).hexdigest(),
                bytes=len(parameter_source),
            ),
            inputs={
                "source": RemoteFileRef.model_validate(
                    {
                        "url": "https://example.com/tiny-v1",
                        "version": "v1",
                    }
                )
            },
            artifacts={
                "dataset": SingleFileArtifactSpec(
                    path=artifact_path,
                    loader="project/loaders/bytes_file.py",
                    data_role="training",
                )
            },
            params=DownloadParams(),
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
            parameter_path = root / spec.parameter_model.path
            parameter_path.parent.mkdir(parents=True)
            parameter_path.write_bytes(parameter_source)
            stage_path = root / f"{RUN_ROOT}/stages/download/spec.yaml"
            stage_path.parent.mkdir(parents=True)
            stage_raw = serialize_document(spec)
            stage_path.write_bytes(stage_raw)
            reference = RunStageRef(
                stage_id="download",
                spec=stage_path.relative_to(root).as_posix(),
                sha256=hashlib.sha256(stage_raw).hexdigest(),
                bytes=len(stage_raw),
            )

            run = RunSpec.model_validate(
                {
                    "run_id": RUN_ID,
                    "experiment_id": "e001_download",
                    "variant_id": "baseline",
                    "replicate_id": "r1",
                    "seed": 7,
                    "source": {
                        "kind": "git",
                        "repository": "https://github.com/example/project",
                        "commit": "a" * 40,
                    },
                    "environment": {
                        "kind": "local",
                        "lockfile": {
                            "kind": "git",
                            "repository": "https://github.com/example/project",
                            "commit": "a" * 40,
                            "path": "environment.yml",
                        },
                    },
                    "reproducibility": {
                        "determinism": {
                            "deterministic_algorithms": True,
                            "deterministic_warn_only": False,
                            "cudnn_deterministic": True,
                            "cudnn_benchmark": False,
                            "cublas_workspace_config": ":4096:8",
                        },
                        "precision": {
                            "float32_matmul_precision": "highest",
                            "cudnn_allow_tf32": False,
                            "autocast_enabled": False,
                            "autocast_dtype": None,
                        },
                        "parallelism": {
                            "process_count": 1,
                            "torch_intraop_threads": 1,
                            "torch_interop_threads": 1,
                            "dataloader": {
                                "workers": 0,
                                "prefetch_factor": None,
                                "persistent_workers": False,
                                "in_order": True,
                            },
                        },
                        "numpy_randomness": {
                            "generators": {},
                            "capture_legacy_global": False,
                        },
                    },
                    "stages": [
                        reference.model_dump(mode="json"),
                        {
                            "stage_id": "train",
                            "spec": f"{RUN_ROOT}/stages/train/spec.yaml",
                            "sha256": "b" * 64,
                            "bytes": 1,
                        },
                    ],
                    "estimator": {
                        "stage_id": "train",
                        "artifact_name": "parameters",
                    },
                }
            )
            run_path = root / f"{RUN_ROOT}/spec.yaml"
            run_path.write_bytes(serialize_document(run))
            result = execute_stage_process(root, run, reference, spec)
            produced = result.artifacts["dataset"]
            assert isinstance(produced, ResolvedSingleFileArtifact)
            raw = (root / produced.file.path).read_bytes()

        self.assertEqual(
            result.command,
            (
                "python",
                "-m",
                "viper.stage_worker",
                str(reference.spec),
                f"{RUN_ROOT}/spec.yaml",
            ),
        )
        self.assertEqual(raw, b"tiny dataset")
        self.assertEqual(produced.file.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(produced.file.bytes, len(raw))
