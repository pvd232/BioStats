"""Acceptance test for a complete two-stage trusted-local VIPER run."""

from __future__ import annotations

import hashlib
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tests.fixtures import (
    builtin_http_transport,
    http_policy,
    http_request,
    resume_state,
)
from viper import run as run_stage
from viper.application import CompareRunsRequest, RunSuccess
from viper.application import compare_runs as compare_runs_application
from viper.authoring import RunPlanDraft, StageDraft, freeze_run_plan
from viper.journal import DurableJournal
from viper.local_store import LocalArtifactStore
from viper.metric_execution import MetricWorkerResult
from viper.protocol import (
    PARAMETERS,
    RESUME_STATE,
    ArtifactLoaderRef,
    DownloadParams,
    DownloadSpec,
    DownloadVariantStageParams,
    ExperimentSpec,
    FloatComparator,
    FutureInputRef,
    GitFileRef,
    GitSource,
    HuggingFaceFileRef,
    LocalEnvironmentSpec,
    MetricDependency,
    MetricImplementationRef,
    MetricParams,
    MetricSpec,
    ParameterModelRef,
    ReplicateSpec,
    ReproducibilitySpec,
    SingleFileArtifactSpec,
    StageArtifactRef,
    StageImplementationRef,
    TrainParams,
    TrainSpec,
    TrainVariantStageParams,
    VariantSpec,
)
from viper.runner import RunFetcher
from viper.runner import run as execute_run
from viper.serialization import serialize_document
from viper.stages import load_stage_callable
from viper.verifier import VerificationError, VerificationPolicy, verify_run_result

REPOSITORY = "https://github.com/example/viper-local-project"
RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RUN_ROOT = f"experiments/example/runs/baseline/{RUN_ID}"


@pytest.fixture
def http_source() -> Iterator[tuple[str, int]]:
    """Serve one redirect followed by the exact body selected by the run."""

    class Handler(BaseHTTPRequestHandler):
        """Return the deterministic HTTP exchange used by the acceptance run."""

        def do_GET(self) -> None:
            """Redirect the initial request and serve the selected body."""
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/prior")
                self.end_headers()
                return
            if self.path == "/prior":
                body = b"prior"
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def log_message(self, format: str, *args: object) -> None:
            """Suppress HTTP server logs inside the acceptance output."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "127.0.0.1", server.server_port
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _git(root: Path, *arguments: str) -> str:
    """Run one successful Git command in the acceptance repository."""
    return subprocess.run(
        ("git", "-C", str(root), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _reproducibility() -> ReproducibilitySpec:
    """Build the strict CPU controls used by the local acceptance run."""
    return ReproducibilitySpec.model_validate(
        {
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
                "generators": {"training": "PCG64"},
                "capture_legacy_global": True,
            },
        }
    )


def test_local_fetcher_dispatches_hugging_face_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieve a Hugging Face input through its declared remote backend."""
    reference = HuggingFaceFileRef(
        repository="example/dataset",
        commit="a" * 40,
        path="data.bin",
        repo_type="dataset",
    )
    monkeypatch.setattr(
        "viper.runner.fetch_huggingface_file_bytes",
        lambda location: b"remote bytes",
    )
    fetcher = RunFetcher(
        tmp_path,
        LocalArtifactStore(tmp_path),
        REPOSITORY,
    )

    assert fetcher(reference) == b"remote bytes"


def test_two_stage_local_run_writes_and_verifies_terminal_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_source: tuple[str, int],
) -> None:
    """Execute source-frozen stages through immutable local publication."""
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "viper@example.com")
    _git(root, "config", "user.name", "VIPER Test")
    _git(root, "remote", "add", "origin", REPOSITORY)

    train_params = TrainParams.model_validate(
        {"epochs": 1, "batch_size": 1, "learning_rate": 0.1}
    )
    metric_source = (
        b"from viper.metrics import metric\n\n"
        b'@metric(metric_id="parameter_bytes", kind="diagnostic", '
        b'mode="recompute")\n'
        b"def compute(context):\n"
        b"    return float(len(context.artifacts['parameters'].read_bytes()))\n"
    )
    parameter_bytes = MetricSpec(
        metric_id="parameter_bytes",
        kind="diagnostic",
        implementation=MetricImplementationRef(
            path="project/metrics/parameter_bytes.py",
            symbol="compute",
            sha256=hashlib.sha256(metric_source).hexdigest(),
            bytes=len(metric_source),
        ),
        params=MetricParams(),
        mode="recompute",
        dependencies=(
            MetricDependency(
                source="artifact",
                name=PARAMETERS,
                required_data_role="training",
            ),
        ),
        comparator=FloatComparator(),
    )
    experiment = ExperimentSpec(
        experiment_id="example",
        factors=(),
        variant_ids=("baseline",),
        replicates=(ReplicateSpec(replicate_id="r1", seed=7),),
        metrics=(parameter_bytes,),
    )
    variant = VariantSpec(
        experiment_id="example",
        variant_id="baseline",
        levels={},
        stage_params=(
            DownloadVariantStageParams(
                stage_id="download",
                params=DownloadParams(),
            ),
            TrainVariantStageParams(stage_id="train", params=train_params),
        ),
    )
    source_files = {
        "environment.yml": b"name: viper-test\n",
        "project/loaders/bytes_file.py": (
            b"def load(path):\n    return path.read_bytes()\n"
        ),
        "project/loaders/resume_state.py": (
            "def load(path):\n"
            f"    return {resume_state().model_dump(mode='python')!r}\n"
        ).encode(),
        "project/metrics/parameter_bytes.py": metric_source,
        "project/parameters/train.py": (
            b"from pydantic import Field\n"
            b"from viper.protocol import TrainParams\n\n"
            b"class TinyTrainParameters(TrainParams):\n"
            b"    epochs: int = Field(gt=0)\n"
            b"    batch_size: int = Field(gt=0)\n"
            b"    learning_rate: float = Field(gt=0)\n"
        ),
        "project/parameters/download.py": (
            b"from viper.protocol import DownloadParams\n\n"
            b"class TinyDownloadParameters(DownloadParams):\n"
            b'    """Validate the download parameters used by this project."""\n'
        ),
        "jobs/download.py": (
            b"from project.parameters.download import TinyDownloadParameters\n"
            b"from viper import download_stage\n\n"
            b"@download_stage(parameter_model=TinyDownloadParameters)\n"
            b"def download(context):\n"
            b"    path = context.artifacts['prior']\n"
            b"    path.parent.mkdir(parents=True, exist_ok=True)\n"
            b"    body = context.retrievals['source'].body\n"
            b"    path.write_bytes(body.read_bytes())\n"
        ),
        "jobs/train.py": (
            b"from project.parameters.train import TinyTrainParameters\n"
            b"from viper import train_stage\n\n"
            b"@train_stage(parameter_model=TinyTrainParameters)\n"
            b"def train(context):\n"
            b"    assert context.params.epochs == 1\n"
            b"    assert context.params.batch_size == 1\n"
            b"    assert context.params.learning_rate == 0.1\n"
            b"    assert context.inputs['prior'].read_bytes() == b'prior'\n"
            b"    context.artifacts['parameters'].parent.mkdir(\n"
            b"        parents=True, exist_ok=True\n"
            b"    )\n"
            b"    context.artifacts['parameters'].write_bytes(b'parameters')\n"
            b"    context.artifacts['resume_state'].write_bytes(b'resume')\n"
        ),
        "experiments/example/spec.yaml": serialize_document(experiment),
        "experiments/example/variants/baseline.spec.yaml": serialize_document(variant),
    }
    for relative_path, raw in source_files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    _git(root, "add", ".")
    _git(root, "commit", "--quiet", "-m", "source")
    source_commit = _git(root, "rev-parse", "HEAD")

    source = GitSource.model_validate(
        {"repository": REPOSITORY, "commit": source_commit}
    )
    environment = LocalEnvironmentSpec(
        lockfile=GitFileRef.model_validate(
            {
                "repository": REPOSITORY,
                "commit": source_commit,
                "path": "environment.yml",
            }
        )
    )
    host, port = http_source
    download = DownloadSpec(
        implementation=StageImplementationRef(
            path="jobs/download.py",
            symbol="download",
            sha256=hashlib.sha256(source_files["jobs/download.py"]).hexdigest(),
            bytes=len(source_files["jobs/download.py"]),
        ),
        parameter_model=ParameterModelRef(
            path="project/parameters/download.py",
            symbol="TinyDownloadParameters",
            sha256=hashlib.sha256(
                source_files["project/parameters/download.py"]
            ).hexdigest(),
            bytes=len(source_files["project/parameters/download.py"]),
        ),
        inputs={
            "source": http_request(
                url=f"http://{host}:{port}/redirect",
                body=b"prior",
            )
        },
        transport=builtin_http_transport(),
        policy=http_policy(
            hosts=frozenset({host}),
            ports=frozenset({port}),
        ),
        artifacts={
            "prior": SingleFileArtifactSpec(
                path=f"{RUN_ROOT}/artifacts/datasets/tiny/prior.bin",
                loader=ArtifactLoaderRef(
                    path="project/loaders/bytes_file.py",
                    symbol="load",
                    sha256=hashlib.sha256(
                        source_files["project/loaders/bytes_file.py"]
                    ).hexdigest(),
                    bytes=len(source_files["project/loaders/bytes_file.py"]),
                ),
                data_role="training",
            )
        },
        params=DownloadParams(),
    )
    train = TrainSpec(
        implementation=StageImplementationRef(
            path="jobs/train.py",
            symbol="train",
            sha256=hashlib.sha256(source_files["jobs/train.py"]).hexdigest(),
            bytes=len(source_files["jobs/train.py"]),
        ),
        parameter_model=ParameterModelRef(
            path="project/parameters/train.py",
            symbol="TinyTrainParameters",
            sha256=hashlib.sha256(
                source_files["project/parameters/train.py"]
            ).hexdigest(),
            bytes=len(source_files["project/parameters/train.py"]),
        ),
        metric_ids=("parameter_bytes",),
        inputs={
            "prior": FutureInputRef(
                producer_stage_id="download",
                producer_artifact="prior",
            )
        },
        params=train_params,
        artifacts={
            PARAMETERS: SingleFileArtifactSpec(
                path=f"{RUN_ROOT}/artifacts/models/tiny/parameters.bin",
                loader=ArtifactLoaderRef(
                    path="project/loaders/bytes_file.py",
                    symbol="load",
                    sha256=hashlib.sha256(
                        source_files["project/loaders/bytes_file.py"]
                    ).hexdigest(),
                    bytes=len(source_files["project/loaders/bytes_file.py"]),
                ),
                data_role="training",
            ),
            RESUME_STATE: SingleFileArtifactSpec(
                path=f"{RUN_ROOT}/artifacts/models/tiny/resume_state.bin",
                loader=ArtifactLoaderRef(
                    path="project/loaders/resume_state.py",
                    symbol="load",
                    sha256=hashlib.sha256(
                        source_files["project/loaders/resume_state.py"]
                    ).hexdigest(),
                    bytes=len(source_files["project/loaders/resume_state.py"]),
                ),
                data_role="training",
            ),
        },
    )
    draft_root = tmp_path / "drafts"
    draft_root.mkdir()
    download_draft = draft_root / "download.yaml"
    train_draft = draft_root / "train.yaml"
    download_draft.write_bytes(serialize_document(download))
    train_draft.write_bytes(serialize_document(train))
    frozen = freeze_run_plan(
        root,
        RunPlanDraft(
            run_id=RUN_ID,
            experiment_id="example",
            variant_id="baseline",
            replicate_id="r1",
            seed=7,
            source=source,
            environment=environment,
            reproducibility=_reproducibility(),
            stages=(
                StageDraft(stage_id="download", spec_source=download_draft),
                StageDraft(stage_id="train", spec_source=train_draft),
            ),
            estimator=StageArtifactRef(
                stage_id="train",
                artifact_name=PARAMETERS,
            ),
        ),
    )
    _git(root, "add", "experiments/example/runs")
    _git(root, "commit", "--quiet", "-m", "plan")

    requests = []
    monkeypatch.setattr(
        "viper.api.application_run",
        lambda request: (
            requests.append(request)
            or RunSuccess(
                run_id=RUN_ID,
                resolved_run=root / RUN_ROOT / "resolved.yaml",
                journal=root / ".viper" / "attempt.jsonl",
            )
        ),
    )
    train_callable = load_stage_callable(
        root / train.implementation.path,
        train.implementation,
        import_root=root,
    )
    run_stage(
        train_callable,
        argv=(
            "--run",
            str(frozen.files[-1]),
            "--stage",
            "train",
            "--repository-root",
            str(root),
        ),
    )
    assert len(requests) == 1
    assert requests[0].run_spec == frozen.files[-1].resolve()

    result = execute_run(root, frozen.files[-1])

    assert result.resolved_run.status == "succeeded"
    assert result.resolved_run_path.is_file()
    assert len(result.resolved_run.attempts[0].resolved_stages) == 2
    assert len(result.resolved_run.attempts[0].measurement_files) == 1
    assert result.journal_path.is_file()
    assert (result.journal_path.parent / "preflight.json").is_file()
    metric_runtime = root / ".viper" / "runtime"
    production_result = MetricWorkerResult.model_validate_json(
        next(metric_runtime.glob("*.parameter_bytes.measurement.result.json")).read_text(
            encoding="utf-8"
        )
    )
    assert production_result.receipt is not None
    assert production_result.receipt.purpose == "measurement"
    assert tuple(
        entry.state for entry in DurableJournal(result.journal_path).read()
    ) == (
        "allocated",
        "preflighting",
        "running_stage",
        "publishing_stage",
        "running_stage",
        "publishing_stage",
        "closing_attempt",
        "publishing_attempt_files",
        "publishing_terminal_run",
        "terminal",
    )

    store = LocalArtifactStore(root)
    fetcher = RunFetcher(root, store, REPOSITORY)
    comparison = compare_runs_application(
        CompareRunsRequest(
            left_path=result.resolved_run_path,
            right_path=result.resolved_run_path,
            trusted_source_repositories=frozenset({REPOSITORY}),
        ),
        left_fetcher=fetcher,
        right_fetcher=fetcher,
    )
    assert comparison.identical is True
    assert comparison.changes == ()

    first_snapshot = result.resolved_run.attempts[0].resolved_stages[0].snapshot
    assert first_snapshot.kind == "local"
    stored_artifact = (
        root
        / first_snapshot.store
        / first_snapshot.commit
        / f"{RUN_ROOT}/artifacts/datasets/tiny/prior.bin"
    )
    stored_artifact.write_bytes(b"tampered")
    with pytest.raises(VerificationError, match="byte-count mismatch"):
        verify_run_result(
            result.resolved_run,
            policy=VerificationPolicy(
                trusted_source_repositories=frozenset({REPOSITORY})
            ),
            fetcher=RunFetcher(root, store, REPOSITORY),
        )
    stored_artifact.write_bytes(b"prior")
    stored_retrieval = (
        root
        / first_snapshot.store
        / first_snapshot.commit
        / f"{RUN_ROOT}/stages/download/retrievals/source/body"
    )
    stored_retrieval.write_bytes(b"PRIOR")
    with pytest.raises(VerificationError, match="SHA-256 mismatch"):
        verify_run_result(
            result.resolved_run,
            policy=VerificationPolicy(
                trusted_source_repositories=frozenset({REPOSITORY})
            ),
            fetcher=RunFetcher(root, store, REPOSITORY),
        )
