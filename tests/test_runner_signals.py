"""Acceptance tests for signal-driven cancellation and preemption evidence."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tests.fixtures import (
    builtin_http_transport,
    http_policy,
    http_request,
    reproducibility,
    resume_state,
)
from viper.authoring import RunPlanDraft, StageDraft, freeze_run_plan
from viper.journal import DurableJournal
from viper.local_store import LocalArtifactStore
from viper.protocol import (
    PARAMETERS,
    RESUME_STATE,
    ArtifactLoaderRef,
    DownloadParams,
    DownloadSpec,
    DownloadVariantStageParams,
    ExperimentSpec,
    FutureInputRef,
    GitFileRef,
    GitSource,
    LocalEnvironmentSpec,
    ParameterModelRef,
    ReplicateSpec,
    ResolvedRun,
    RunSpec,
    SingleFileArtifactSpec,
    StageArtifactRef,
    StageImplementationRef,
    StageInvocationReceipt,
    TrainParams,
    TrainSpec,
    TrainVariantStageParams,
    VariantSpec,
)
from viper.runner import RunFetcher
from viper.serialization import parse_yaml_bytes, serialize_document
from viper.verifier import (
    VerificationPolicy,
    read_attempt_reference,
    verify_run_result,
)

REPOSITORY = "https://github.com/example/viper-signal-project"
RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RUN_ROOT = f"experiments/signals/runs/baseline/{RUN_ID}"


@pytest.fixture
def signal_http_source() -> Iterator[tuple[str, int]]:
    """Serve the immutable input consumed by the completed first stage."""

    class Handler(BaseHTTPRequestHandler):
        """Return one exact response body for the signal acceptance plan."""

        def do_GET(self) -> None:
            """Serve the selected body at its single declared path."""
            if self.path != "/prior":
                self.send_error(404)
                return
            body = b"prior"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            """Suppress request logs inside test output."""

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
    """Run one successful Git command in the isolated test repository."""
    return subprocess.run(
        ("git", "-C", str(root), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_source_files(root: Path) -> dict[str, bytes]:
    """Write the two stage callables and their supporting project code."""
    source_files = {
        "environment.yml": b"name: viper-signal-test\n",
        "project/loaders/bytes_file.py": (
            b"def load(path):\n    return path.read_bytes()\n"
        ),
        "project/loaders/resume_state.py": (
            "def load(path):\n"
            f"    return {resume_state().model_dump(mode='python')!r}\n"
        ).encode(),
        "project/parameters/download.py": (
            b"from viper.protocol import DownloadParams\n\n"
            b"class SignalDownloadParameters(DownloadParams):\n"
            b'    """Validate this fixture\'s download parameters."""\n'
        ),
        "project/parameters/train.py": (
            b"from viper.protocol import TrainParams\n\n"
            b"class SignalTrainParameters(TrainParams):\n"
            b'    """Validate this fixture\'s training parameters."""\n'
        ),
        "jobs/download.py": (
            b"from project.parameters.download import SignalDownloadParameters\n"
            b"from viper import download_stage\n\n"
            b"@download_stage(parameter_model=SignalDownloadParameters)\n"
            b"def download(context):\n"
            b"    target = context.artifacts['prior']\n"
            b"    target.parent.mkdir(parents=True, exist_ok=True)\n"
            b"    target.write_bytes(context.retrievals['source'].body.read_bytes())\n"
        ),
        "jobs/train.py": (
            b"import os\n"
            b"import subprocess\n"
            b"import sys\n"
            b"import time\n\n"
            b"from project.parameters.train import SignalTrainParameters\n"
            b"from viper import train_stage\n\n"
            b"@train_stage(parameter_model=SignalTrainParameters)\n"
            b"def train(context):\n"
            b"    output_root = context.artifacts['parameters'].parent\n"
            b"    output_root.mkdir(parents=True, exist_ok=True)\n"
            b"    child = subprocess.Popen(\n"
            b"        [sys.executable, '-c', 'import time; time.sleep(300)']\n"
            b"    )\n"
            b"    (output_root / 'worker-pids.txt').write_text(\n"
            b"        f'{os.getpid()}\\n{child.pid}\\n', encoding='utf-8'\n"
            b"    )\n"
            b"    print('blocking train started', flush=True)\n"
            b"    while True:\n"
            b"        time.sleep(1)\n"
        ),
    }
    for relative_path, raw in source_files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return source_files


def _freeze_signal_plan(
    root: Path,
    source_files: dict[str, bytes],
    host: str,
    port: int,
) -> Path:
    """Freeze one download-then-blocking-train plan for a real coordinator."""
    experiment = ExperimentSpec(
        experiment_id="signals",
        factors=(),
        variant_ids=("baseline",),
        replicates=(ReplicateSpec(replicate_id="r1", seed=7),),
        metrics=(),
    )
    variant = VariantSpec(
        experiment_id="signals",
        variant_id="baseline",
        levels={},
        stage_params=(
            DownloadVariantStageParams(
                stage_id="download",
                params=DownloadParams(),
            ),
            TrainVariantStageParams(stage_id="train", params=TrainParams()),
        ),
    )
    experiment_path = root / "experiments/signals/spec.yaml"
    variant_path = root / "experiments/signals/variants/baseline.spec.yaml"
    experiment_path.parent.mkdir(parents=True, exist_ok=True)
    variant_path.parent.mkdir(parents=True, exist_ok=True)
    experiment_path.write_bytes(serialize_document(experiment))
    variant_path.write_bytes(serialize_document(variant))
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
    bytes_loader = ArtifactLoaderRef(
        path="project/loaders/bytes_file.py",
        symbol="load",
        sha256=hashlib.sha256(
            source_files["project/loaders/bytes_file.py"]
        ).hexdigest(),
        bytes=len(source_files["project/loaders/bytes_file.py"]),
    )
    resume_loader = ArtifactLoaderRef(
        path="project/loaders/resume_state.py",
        symbol="load",
        sha256=hashlib.sha256(
            source_files["project/loaders/resume_state.py"]
        ).hexdigest(),
        bytes=len(source_files["project/loaders/resume_state.py"]),
    )
    download = DownloadSpec(
        implementation=StageImplementationRef(
            path="jobs/download.py",
            symbol="download",
            sha256=hashlib.sha256(source_files["jobs/download.py"]).hexdigest(),
            bytes=len(source_files["jobs/download.py"]),
        ),
        parameter_model=ParameterModelRef(
            path="project/parameters/download.py",
            symbol="SignalDownloadParameters",
            sha256=hashlib.sha256(
                source_files["project/parameters/download.py"]
            ).hexdigest(),
            bytes=len(source_files["project/parameters/download.py"]),
        ),
        inputs={
            "source": http_request(
                url=f"http://{host}:{port}/prior",
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
                loader=bytes_loader,
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
            symbol="SignalTrainParameters",
            sha256=hashlib.sha256(
                source_files["project/parameters/train.py"]
            ).hexdigest(),
            bytes=len(source_files["project/parameters/train.py"]),
        ),
        inputs={
            "prior": FutureInputRef(
                producer_stage_id="download",
                producer_artifact="prior",
            )
        },
        params=TrainParams(),
        artifacts={
            PARAMETERS: SingleFileArtifactSpec(
                path=f"{RUN_ROOT}/artifacts/models/tiny/parameters.bin",
                loader=bytes_loader,
                data_role="training",
            ),
            RESUME_STATE: SingleFileArtifactSpec(
                path=f"{RUN_ROOT}/artifacts/models/tiny/resume_state.bin",
                loader=resume_loader,
                data_role="training",
            ),
        },
    )
    draft_root = root.parent / "drafts"
    draft_root.mkdir()
    download_draft = draft_root / "download.yaml"
    train_draft = draft_root / "train.yaml"
    download_draft.write_bytes(serialize_document(download))
    train_draft.write_bytes(serialize_document(train))
    frozen = freeze_run_plan(
        root,
        RunPlanDraft(
            run_id=RUN_ID,
            experiment_id="signals",
            variant_id="baseline",
            replicate_id="r1",
            seed=7,
            source=source,
            environment=environment,
            reproducibility=reproducibility(),
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
    _git(root, "add", f"experiments/signals/runs/baseline/{RUN_ID}")
    _git(root, "commit", "--quiet", "-m", "plan")
    return frozen.files[-1]


def _wait_for_file(path: Path, timeout_seconds: float = 30) -> None:
    """Wait until the blocking stage records its process identities."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {path}")


def _wait_for_process_exit(pid: int, timeout_seconds: float = 10) -> None:
    """Wait until one interrupted worker or descendant no longer exists."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise AssertionError(f"process {pid} survived coordinator interruption")


@pytest.mark.parametrize(
    ("signal_number", "expected_status", "expected_code"),
    (
        (signal.SIGINT, "cancelled", "cancelled"),
        (signal.SIGTERM, "preempted", "preempted"),
    ),
    ids=("sigint-cancelled", "sigterm-preempted"),
)
def test_signal_closes_attempt_with_active_stage_evidence(
    tmp_path: Path,
    signal_http_source: tuple[str, int],
    signal_number: signal.Signals,
    expected_status: str,
    expected_code: str,
) -> None:
    """Stop a real coordinator and preserve its completed prefix and active child."""
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "viper@example.com")
    _git(root, "config", "user.name", "VIPER Test")
    _git(root, "remote", "add", "origin", REPOSITORY)
    source_files = _write_source_files(root)
    run_path = _freeze_signal_plan(
        root,
        source_files,
        *signal_http_source,
    )
    pid_path = root / RUN_ROOT / "artifacts/models/tiny/worker-pids.txt"
    process = subprocess.Popen(
        (
            sys.executable,
            "-m",
            "viper.cli",
            "--json",
            "run",
            str(run_path),
            "--repository-root",
            str(root),
        ),
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        _wait_for_file(pid_path)
        worker_pids = tuple(
            int(value) for value in pid_path.read_text(encoding="utf-8").splitlines()
        )
        os.kill(process.pid, signal_number)
        stdout, stderr = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()

    assert process.returncode == 1
    assert stderr == b""
    assert json.loads(stdout)["code"] == "execution_failed"
    for worker_pid in worker_pids:
        _wait_for_process_exit(worker_pid)

    run = ResolvedRun.model_validate(
        parse_yaml_bytes((root / RUN_ROOT / "resolved.yaml").read_bytes())
    )
    run_spec = RunSpec.model_validate(parse_yaml_bytes(run_path.read_bytes()))
    store = LocalArtifactStore(root)
    fetcher = RunFetcher(root, store, REPOSITORY)
    attempt = read_attempt_reference(
        run.attempts[-1],
        run_spec,
        fetcher=fetcher,
    )
    assert attempt.status == expected_status
    assert attempt.failure is not None
    assert attempt.failure.code == expected_code
    assert tuple(stage.stage_id for stage in attempt.resolved_stages) == ("download",)
    assert len(attempt.invocations) == 2
    interrupted_receipt = StageInvocationReceipt.model_validate(
        parse_yaml_bytes(store.fetch(attempt.invocations[-1].stored_at))
    )
    assert interrupted_receipt.context.stage_id == "train"
    assert interrupted_receipt.outcome == expected_status
    log_paths = {reference.stored_at.path for reference in attempt.log_files}
    assert f"{RUN_ROOT}/attempts/1/logs/train.stdout.log" in log_paths
    assert f"{RUN_ROOT}/attempts/1/logs/train.stderr.log" in log_paths
    stdout_ref = next(
        reference
        for reference in attempt.log_files
        if reference.stored_at.path.endswith("train.stdout.log")
    )
    assert store.fetch(stdout_ref.stored_at) == b"blocking train started\n"
    assert DurableJournal(
        root / ".viper/workspaces" / RUN_ID / "attempt-1/control/journal.jsonl"
    ).latest().state == "terminal"  # type: ignore[union-attr]
    verified = verify_run_result(
        run,
        policy=VerificationPolicy(
            trusted_source_repositories=frozenset({REPOSITORY})
        ),
        fetcher=fetcher,
    )
    assert verified.attempts[-1] == attempt
