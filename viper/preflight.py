"""Inspect a complete local run plan before stage execution begins."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .ids import StageId
from .protocol import BaseSpec, FutureInputRef, InternalSpec, RunSpec
from .serialization import load_stage_spec, parse_yaml_bytes

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

        script_exists = (root / stage.script).is_file()
        checks.append(
            _check(
                "stage.script",
                reference.stage_id,
                script_exists,
                "stage entrypoint is absent from the local source tree",
            )
        )
        loaders_exist = all(
            (root / artifact.loader).is_file() for artifact in stage.artifacts.values()
        )
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

    return PreflightReport(run_id=run.run_id, checks=tuple(checks))
