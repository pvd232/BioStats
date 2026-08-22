"""Acceptance test for a complete two-stage trusted-local VIPER run."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.fixtures import resume_state
from viper.authoring import RunPlanDraft, StageDraft, freeze_run_plan
from viper.protocol import (
    PARAMETERS,
    RESUME_STATE,
    DownloadSpec,
    ExperimentSpec,
    FutureInputRef,
    GitFileRef,
    GitSource,
    LocalEnvironmentSpec,
    RemoteFileRef,
    ReplicateSpec,
    ReproducibilitySpec,
    SingleFileArtifactSpec,
    StageArtifactRef,
    TrainParams,
    TrainSpec,
    TrainVariantStageParams,
    VariantSpec,
)
from viper.runner import run_local
from viper.serialization import serialize_document

REPOSITORY = "https://github.com/example/viper-local-project"
RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RUN_ROOT = f"experiments/example/runs/baseline/{RUN_ID}"


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


def test_two_stage_local_run_writes_and_verifies_terminal_result(
    tmp_path: Path,
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
    experiment = ExperimentSpec(
        experiment_id="example",
        factors=(),
        variant_ids=("baseline",),
        replicates=(ReplicateSpec(replicate_id="r1", seed=7),),
        metrics=(),
    )
    variant = VariantSpec(
        experiment_id="example",
        variant_id="baseline",
        levels={},
        stage_params=(TrainVariantStageParams(stage_id="train", params=train_params),),
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
        "jobs/download.py": (
            "from pathlib import Path\n"
            f"path = Path({f'{RUN_ROOT}/artifacts/datasets/tiny/prior.bin'!r})\n"
            "path.parent.mkdir(parents=True, exist_ok=True)\n"
            "path.write_bytes(b'prior')\n"
        ).encode(),
        "jobs/train.py": (
            "from pathlib import Path\n"
            f"root = Path({f'{RUN_ROOT}/artifacts/models/tiny'!r})\n"
            "root.mkdir(parents=True, exist_ok=True)\n"
            "assert Path("
            f"{f'{RUN_ROOT}/artifacts/datasets/tiny/prior.bin'!r}"
            ").read_bytes() == b'prior'\n"
            "(root / 'parameters.bin').write_bytes(b'parameters')\n"
            "(root / 'resume_state.bin').write_bytes(b'resume')\n"
        ).encode(),
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
    download = DownloadSpec(
        script="jobs/download.py",
        inputs={
            "source": RemoteFileRef.model_validate(
                {"url": "https://example.com/prior", "version": "v1"}
            )
        },
        artifacts={
            "prior": SingleFileArtifactSpec(
                path=f"{RUN_ROOT}/artifacts/datasets/tiny/prior.bin",
                loader="project/loaders/bytes_file.py",
                data_role="training",
            )
        },
    )
    train = TrainSpec(
        script="jobs/train.py",
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
                loader="project/loaders/bytes_file.py",
                data_role="training",
            ),
            RESUME_STATE: SingleFileArtifactSpec(
                path=f"{RUN_ROOT}/artifacts/models/tiny/resume_state.bin",
                loader="project/loaders/resume_state.py",
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

    result = run_local(root, frozen.files[-1])

    assert result.resolved_run.status == "succeeded"
    assert result.resolved_run_path.is_file()
    assert len(result.resolved_run.attempts[0].resolved_stages) == 2
    assert result.journal_path.is_file()
