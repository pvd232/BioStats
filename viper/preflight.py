"""Inspect a complete local run plan before stage execution begins."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .ids import StageId
from .protocol import (
    BaseSpec,
    FutureInputRef,
    GitFileRef,
    InternalSpec,
    LocalEnvironmentSpec,
    RunSpec,
    StorageModel,
)
from .serialization import load_stage_spec, parse_yaml_bytes
from .verifier import (
    VerificationError,
    fetch_storage_bytes,
    verify_benchmark_spec,
    verify_experiment_and_variant,
    verify_run_plan_relationships,
)

PreflightStatus = Literal["pass", "warning", "failure"]


class PreflightCheck(BaseModel):
    """Report one stable plan check and its exact target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    status: PreflightStatus
    target: str
    message: str


class PreflightReport(BaseModel):
    """Collect every applicable check for one local run plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str | None
    checks: tuple[PreflightCheck, ...]

    @property
    def ready(self) -> bool:
        """Return whether every blocking check passed."""
        return all(check.status != "failure" for check in self.checks)


def _check(
    code: str,
    target: str,
    passed: bool,
    failure_message: str,
) -> PreflightCheck:
    """Construct one pass or failure result from a boolean condition."""
    return PreflightCheck(
        code=code,
        status="pass" if passed else "failure",
        target=target,
        message="check passed" if passed else failure_message,
    )


def _git_bytes(repository_root: Path, commit: str, path: str) -> bytes:
    """Read one exact file from the selected local Git commit."""
    return subprocess.run(
        ("git", "-C", str(repository_root), "show", f"{commit}:{path}"),
        check=True,
        capture_output=True,
    ).stdout


def preflight_local_plan(repository_root: Path, run_spec_path: Path) -> PreflightReport:
    """Validate local plan bytes, source paths, and same-run dependencies."""
    root = repository_root.resolve()
    checks: list[PreflightCheck] = []
    try:
        run = RunSpec.model_validate(parse_yaml_bytes(run_spec_path.read_bytes()))
    except Exception:
        return PreflightReport(
            run_id=None,
            checks=(
                PreflightCheck(
                    code="plan.document",
                    status="failure",
                    target=run_spec_path.as_posix(),
                    message="run specification failed validation",
                ),
            ),
        )
    checks.append(_check("plan.document", run_spec_path.as_posix(), True, ""))

    def fetch(location: StorageModel) -> bytes:
        """Retrieve source-repository files locally and dispatch other backends."""
        if (
            isinstance(location, GitFileRef)
            and location.repository == run.source.repository
        ):
            return _git_bytes(root, location.commit, location.path)
        return fetch_storage_bytes(location)

    try:
        relative_run_path = run_spec_path.resolve().relative_to(root).as_posix()
        plan_raw = _git_bytes(root, "HEAD", relative_run_path)
        plan_is_frozen = plan_raw == run_spec_path.read_bytes()
    except (OSError, ValueError, subprocess.CalledProcessError):
        plan_is_frozen = False
    checks.append(
        _check(
            "plan.git_identity",
            run_spec_path.as_posix(),
            plan_is_frozen,
            "run specification bytes are absent from the current Git commit",
        )
    )

    try:
        origin = subprocess.run(
            ("git", "-C", str(root), "remote", "get-url", "origin"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        source_repository_matches = origin == str(run.source.repository)
    except (OSError, subprocess.CalledProcessError):
        source_repository_matches = False
    checks.append(
        _check(
            "source.repository",
            str(run.source.repository),
            source_repository_matches,
            "local Git origin differs from RunSpec.source.repository",
        )
    )

    checks.append(
        _check(
            "environment.local",
            "run.environment",
            isinstance(run.environment, LocalEnvironmentSpec),
            "trusted local execution requires a local shared environment",
        )
    )

    loaded: dict[StageId, BaseSpec] = {}
    prior: set[StageId] = set()
    for reference in run.stages:
        target = root / reference.spec
        raw = target.read_bytes() if target.is_file() else b""
        identity_matches = (
            target.is_file()
            and len(raw) == reference.bytes
            and hashlib.sha256(raw).hexdigest() == reference.sha256
        )
        checks.append(
            _check(
                "stage.identity",
                reference.stage_id,
                identity_matches,
                "stage specification bytes differ from RunStageRef",
            )
        )
        if not identity_matches:
            continue
        try:
            stage = load_stage_spec(target)
        except Exception:
            checks.append(
                PreflightCheck(
                    code="stage.document",
                    status="failure",
                    target=reference.stage_id,
                    message="stage specification failed validation",
                )
            )
            continue
        checks.append(_check("stage.document", reference.stage_id, True, ""))
        loaded[reference.stage_id] = stage

        script_path = root / stage.script
        try:
            script_exists = (
                script_path.is_file()
                and script_path.read_bytes()
                == _git_bytes(root, run.source.commit, stage.script)
            )
        except (OSError, subprocess.CalledProcessError):
            script_exists = False
        checks.append(
            _check(
                "stage.script",
                reference.stage_id,
                script_exists,
                "stage entrypoint differs from the frozen source commit",
            )
        )
        loaders_exist = True
        for artifact in stage.artifacts.values():
            loader_path = root / artifact.loader
            try:
                if not loader_path.is_file() or loader_path.read_bytes() != _git_bytes(
                    root, run.source.commit, artifact.loader
                ):
                    loaders_exist = False
            except (OSError, subprocess.CalledProcessError):
                loaders_exist = False
        checks.append(
            _check(
                "artifact.loader",
                reference.stage_id,
                loaders_exist,
                "one or more artifact loaders are absent from the source tree",
            )
        )

        valid_future_inputs = True
        if isinstance(stage, InternalSpec):
            for input_ref in stage.inputs.values():
                if not isinstance(input_ref, FutureInputRef):
                    continue
                producer = loaded.get(input_ref.producer_stage_id)
                if (
                    input_ref.producer_stage_id not in prior
                    or producer is None
                    or input_ref.producer_artifact not in producer.artifacts
                ):
                    valid_future_inputs = False
        checks.append(
            _check(
                "input.future",
                reference.stage_id,
                valid_future_inputs,
                "future input lacks an earlier declared producer artifact",
            )
        )
        prior.add(reference.stage_id)

    experiment = None
    variant = None
    benchmark = None
    try:
        experiment, variant = verify_experiment_and_variant(run, fetcher=fetch)
        benchmark = verify_benchmark_spec(run, fetcher=fetch)
        plan_records_valid = True
    except (VerificationError, OSError, subprocess.CalledProcessError):
        plan_records_valid = False
    checks.append(
        _check(
            "plan.records",
            str(run.run_id),
            plan_records_valid,
            "experiment, variant, or benchmark records failed verification",
        )
    )

    relationships_valid = False
    if (
        plan_records_valid
        and experiment is not None
        and variant is not None
        and len(loaded) == len(run.stages)
    ):
        try:
            verify_run_plan_relationships(
                run,
                experiment,
                variant,
                benchmark,
                loaded,
            )
            relationships_valid = True
        except VerificationError:
            pass
    checks.append(
        _check(
            "plan.relationships",
            str(run.run_id),
            relationships_valid,
            "run, experiment, variant, benchmark, and stage relationships conflict",
        )
    )

    implementations_valid = experiment is not None
    if experiment is not None:
        selected_metric_ids = {
            metric_id for stage in loaded.values() for metric_id in stage.metric_ids
        }
        metrics = {metric.metric_id: metric for metric in experiment.metrics}
        for metric_id in selected_metric_ids:
            metric = metrics.get(metric_id)
            if metric is None:
                implementations_valid = False
                continue
            implementation_path = root / metric.implementation
            try:
                if (
                    not implementation_path.is_file()
                    or implementation_path.read_bytes()
                    != _git_bytes(root, run.source.commit, metric.implementation)
                ):
                    implementations_valid = False
            except (OSError, subprocess.CalledProcessError):
                implementations_valid = False
    checks.append(
        _check(
            "metric.implementation",
            str(run.run_id),
            implementations_valid,
            "one or more selected metric implementations differ from frozen source",
        )
    )

    return PreflightReport(run_id=run.run_id, checks=tuple(checks))
