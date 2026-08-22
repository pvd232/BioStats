"""Execute, publish, and verify one frozen run plan on a trusted local host."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from .ids import InputName, StageId
from .journal import DurableJournal
from .local_store import LocalArtifactStore, snapshot_file
from .metrics import MeasurementSink, MetricContext, load_metric
from .protocol import (
    ArtifactPointer,
    BaseSpec,
    DownloadSpec,
    ExperimentSpec,
    GitFileRef,
    InternalSpec,
    LocalEnvironmentSpec,
    RemoteFileRef,
    ResolvedArtifactPointerRef,
    ResolvedBuildSpec,
    ResolvedDownloadSpec,
    ResolvedEmbedSpec,
    ResolvedEvaluateSpec,
    ResolvedFutureInputRef,
    ResolvedGitFileRef,
    ResolvedInternalInputRef,
    ResolvedLocalEnvironment,
    ResolvedRun,
    ResolvedRunSpecRef,
    ResolvedSpec,
    ResolvedStageRef,
    ResolvedStoredInputRef,
    ResolvedTrainSpec,
    RunAttempt,
    RunSpec,
    SnapshotFileRef,
    StorageModel,
    StoredInputRef,
)
from .serialization import load_stage_spec, parse_yaml_bytes, serialize_document
from .stage_execution import StageProcessResult, execute_stage_process
from .verifier import (
    VerificationPolicy,
    VerifiedArtifact,
    verify_promoted_artifact,
    verify_run_result,
)
from .workspace import AttemptWorkspace


class LocalRunError(RuntimeError):
    """Report a local plan, source, materialization, or execution failure."""


class LocalRunResult(BaseModel):
    """Return one verified terminal run and its local output path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resolved_run: ResolvedRun
    resolved_run_path: Path
    journal_path: Path


def _git(repository_root: Path, *arguments: str) -> bytes:
    """Run one bounded Git query against the selected repository."""
    try:
        return subprocess.run(
            ("git", "-C", str(repository_root), *arguments),
            check=True,
            capture_output=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise LocalRunError("local Git evidence could not be read") from exc


class LocalRunFetcher:
    """Retrieve frozen Git source and repository-local immutable outputs."""

    def __init__(self, repository_root: Path, store: LocalArtifactStore) -> None:
        """Bind retrieval to one local Git checkout and output store."""
        self.repository_root = repository_root.resolve()
        self.store = store

    def __call__(self, location: StorageModel) -> bytes:
        """Retrieve one file from its declared immutable backend."""
        if isinstance(location, GitFileRef):
            return _git(
                self.repository_root,
                "show",
                f"{location.commit}:{location.path}",
            )
        return self.store.fetch(location)


def _resolved_git_file(
    fetcher: LocalRunFetcher,
    location: GitFileRef,
) -> ResolvedGitFileRef:
    """Retrieve and identify one exact file in the local Git checkout."""
    raw = fetcher(location)
    return ResolvedGitFileRef(
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
        stored_at=location,
    )


def _write_materialized_file(root: Path, relative_path: str, raw: bytes) -> None:
    """Write verified input bytes at one safe repository-relative path."""
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise LocalRunError("materialized input escapes the repository root")
    if target.exists() and (not target.is_file() or target.read_bytes() != raw):
        raise LocalRunError("materialized input path contains different bytes")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)


def _materialize_verified_artifact(
    root: Path,
    target_path: str,
    artifact: VerifiedArtifact,
) -> None:
    """Write every verified artifact file at its selected input path."""
    if artifact.artifact.kind == "file":
        _write_materialized_file(root, target_path, artifact.files[0].content)
        return
    for member, verified_file in zip(
        artifact.artifact.members,
        artifact.files,
        strict=True,
    ):
        _write_materialized_file(
            root,
            f"{target_path}/{member.relative_path}",
            verified_file.content,
        )


def _resolve_inputs(
    root: Path,
    stage: InternalSpec,
    completed: Mapping[StageId, ResolvedStageRef],
    stage_specs: Mapping[StageId, BaseSpec],
    fetcher: LocalRunFetcher,
    policy: VerificationPolicy,
) -> tuple[dict[InputName, ResolvedInternalInputRef], dict[str, Path]]:
    """Materialize stage inputs and bind each one to its verified producer."""
    resolved: dict[InputName, ResolvedInternalInputRef] = {}
    paths: dict[str, Path] = {}
    for name, input_ref in stage.inputs.items():
        if input_ref.kind == "future":
            producer = completed.get(input_ref.producer_stage_id)
            if producer is None:
                raise LocalRunError("future input producer has not completed")
            resolved[name] = ResolvedFutureInputRef(producer=producer)
            producer_spec = stage_specs[input_ref.producer_stage_id]
            artifact = producer_spec.artifacts[input_ref.producer_artifact]
            paths[name] = root / artifact.path
            continue

        assert isinstance(input_ref, StoredInputRef)
        pointer_raw = fetcher(input_ref.pointer)
        pointer = ArtifactPointer.model_validate(parse_yaml_bytes(pointer_raw))
        verified = verify_promoted_artifact(
            pointer,
            policy=policy,
            expected_data_role=input_ref.data_role,
            fetcher=fetcher,
        )
        _materialize_verified_artifact(root, input_ref.path, verified)
        resolved[name] = ResolvedStoredInputRef(
            pointer=ResolvedArtifactPointerRef(
                sha256=hashlib.sha256(pointer_raw).hexdigest(),
                bytes=len(pointer_raw),
                stored_at=input_ref.pointer,
            )
        )
        paths[name] = root / input_ref.path
    return resolved, paths


def _artifact_paths(root: Path, stage: BaseSpec) -> dict[str, Path]:
    """Return the materialized path of each artifact declared by one stage."""
    return {name: root / artifact.path for name, artifact in stage.artifacts.items()}


def _run_after_stage_metrics(
    root: Path,
    run: RunSpec,
    stage_id: StageId,
    stage: BaseSpec,
    experiment: ExperimentSpec,
    input_paths: Mapping[str, Path],
    measurement_paths: list[Path],
) -> None:
    """Invoke each selected after-stage metric and append its Measurement row."""
    metrics = {metric.metric_id: metric for metric in experiment.metrics}
    for metric_id in stage.metric_ids:
        metric = metrics[metric_id]
        if metric.production != "after_stage":
            continue
        implementation = root / metric.implementation
        callable_metric = load_metric(implementation, metric.symbol)
        value = callable_metric(
            MetricContext(
                inputs=input_paths,
                artifacts=_artifact_paths(root, stage),
                params=metric.params,
            )
        )
        path = (
            root
            / f"experiments/{run.experiment_id}/runs/{run.variant_id}/{run.run_id}"
            / "measurements"
            / f"{stage_id}.{metric_id}.jsonl"
        )
        MeasurementSink(
            path,
            run_id=run.run_id,
            attempt_id=1,
            stage_id=stage_id,
            metric_id=metric_id,
        ).append(value)
        measurement_paths.append(path)


def _resolved_environment(
    fetcher: LocalRunFetcher,
    environment: LocalEnvironmentSpec,
) -> ResolvedLocalEnvironment:
    """Resolve one local environment's exact lockfile identity."""
    return ResolvedLocalEnvironment(
        compute=environment.compute,
        lockfile=_resolved_git_file(fetcher, environment.lockfile),
    )


def _resolved_stage(
    stage: BaseSpec,
    *,
    source: ResolvedGitFileRef,
    environment: ResolvedLocalEnvironment,
    process: StageProcessResult,
    inputs: dict[InputName, ResolvedInternalInputRef] | None,
    completed_at: datetime,
) -> ResolvedSpec:
    """Construct the concrete resolved-spec subtype for one completed stage."""
    result = process
    common = {
        "spec": stage,
        "source": source,
        "environment": environment,
        "execution_context": result.execution_context,
        "command": result.command,
        "artifacts": result.artifacts,
        "completed_at": completed_at,
    }
    if isinstance(stage, DownloadSpec):
        return ResolvedDownloadSpec(
            **common,
            inputs=cast(dict[InputName, RemoteFileRef], stage.inputs),
            retrieved_at=result.started_at,
        )
    assert inputs is not None
    if stage.kind == "build":
        return ResolvedBuildSpec(**common, inputs=inputs)
    if stage.kind == "embed":
        return ResolvedEmbedSpec(**common, inputs=inputs)
    if stage.kind == "train":
        return ResolvedTrainSpec(**common, inputs=inputs)
    return ResolvedEvaluateSpec(**common, inputs=inputs)


def run_local(
    repository_root: Path,
    run_spec_path: Path,
    *,
    timeout_seconds: float | None = None,
) -> LocalRunResult:
    """Execute one frozen plan locally and verify its terminal resolved run."""
    root = repository_root.resolve()
    run_path = run_spec_path.resolve()
    run_raw = run_path.read_bytes()
    run = RunSpec.model_validate(parse_yaml_bytes(run_raw))
    if not isinstance(run.environment, LocalEnvironmentSpec):
        raise LocalRunError("trusted local execution requires a local environment")

    plan_commit = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    relative_run_path = run_path.relative_to(root).as_posix()
    if _git(root, "show", f"{plan_commit}:{relative_run_path}") != run_raw:
        raise LocalRunError("RunSpec bytes are absent from the current Git commit")

    store = LocalArtifactStore(root)
    fetcher = LocalRunFetcher(root, store)
    policy = VerificationPolicy(
        trusted_loader_repositories=frozenset({str(run.source.repository)})
    )
    experiment = ExperimentSpec.model_validate(
        parse_yaml_bytes(
            fetcher(
                GitFileRef(
                    repository=run.source.repository,
                    commit=run.source.commit,
                    path=f"experiments/{run.experiment_id}/spec.yaml",
                )
            )
        )
    )

    workspace = AttemptWorkspace.create(root / ".viper" / "workspaces", run.run_id, 1)
    journal = DurableJournal(workspace.control / "journal.jsonl")
    workspace.acquire()
    attempt_started = datetime.now(UTC)
    resolved_stage_refs: list[ResolvedStageRef] = []
    completed: dict[StageId, ResolvedStageRef] = {}
    loaded_stages: dict[StageId, BaseSpec] = {}
    measurement_paths: list[Path] = []
    log_files: dict[str, bytes] = {}
    try:
        journal.append("allocated", "attempt allocated", recorded_at=attempt_started)
        journal.append(
            "preflighting",
            "frozen plan located in Git",
            recorded_at=datetime.now(UTC),
            details={"plan_commit": plan_commit},
        )
        for stage_reference in run.stages:
            stage = load_stage_spec(root / stage_reference.spec)
            loaded_stages[stage_reference.stage_id] = stage
            effective_environment = stage.environment or run.environment
            if not isinstance(effective_environment, LocalEnvironmentSpec):
                raise LocalRunError("local runner cannot apply a remote environment")
            source_location = GitFileRef(
                repository=run.source.repository,
                commit=run.source.commit,
                path=stage.script,
            )
            source = _resolved_git_file(fetcher, source_location)
            if (root / stage.script).read_bytes() != fetcher(source_location):
                raise LocalRunError("local stage source differs from the frozen source")

            resolved_inputs: dict[InputName, ResolvedInternalInputRef] | None = None
            input_paths: dict[str, Path] = {}
            if isinstance(stage, InternalSpec):
                resolved_inputs, input_paths = _resolve_inputs(
                    root,
                    stage,
                    completed,
                    loaded_stages,
                    fetcher,
                    policy,
                )

            journal.append(
                "running_stage",
                "stage process started",
                recorded_at=datetime.now(UTC),
                details={"stage_id": stage_reference.stage_id},
            )
            process = execute_stage_process(
                root,
                run,
                stage_reference,
                stage,
                timeout_seconds=timeout_seconds,
            )
            _run_after_stage_metrics(
                root,
                run,
                stage_reference.stage_id,
                stage,
                experiment,
                input_paths,
                measurement_paths,
            )
            stage_completed = datetime.now(UTC)
            resolved = _resolved_stage(
                stage,
                source=source,
                environment=_resolved_environment(fetcher, effective_environment),
                process=process,
                inputs=resolved_inputs,
                completed_at=stage_completed,
            )
            resolved_path = (
                f"experiments/{run.experiment_id}/runs/{run.variant_id}/{run.run_id}"
                f"/stages/{stage_reference.stage_id}/resolved.yaml"
            )
            resolved_raw = serialize_document(resolved)
            snapshot_files: dict[str, bytes] = {resolved_path: resolved_raw}
            for artifact in process.artifacts.values():
                artifact_references: tuple[SnapshotFileRef, ...]
                if artifact.kind == "file":
                    artifact_references = (artifact.file,)
                else:
                    artifact_references = tuple(
                        member.file for member in artifact.members
                    )
                for reference in artifact_references:
                    snapshot_files[reference.path] = (
                        root / reference.path
                    ).read_bytes()
            snapshot = store.snapshot(snapshot_files)
            resolved_stage_ref = ResolvedStageRef(
                stage_id=stage_reference.stage_id,
                snapshot=snapshot,
                resolved_spec=snapshot_file(resolved_path, resolved_raw),
            )
            resolved_stage_refs.append(resolved_stage_ref)
            completed[stage_reference.stage_id] = resolved_stage_ref
            run_root = (
                f"experiments/{run.experiment_id}/runs/{run.variant_id}/{run.run_id}"
            )
            log_files[f"{run_root}/logs/1.{stage_reference.stage_id}.stdout.log"] = (
                process.stdout
            )
            log_files[f"{run_root}/logs/1.{stage_reference.stage_id}.stderr.log"] = (
                process.stderr
            )
            journal.append(
                "publishing_stage",
                "stage snapshot published",
                recorded_at=datetime.now(UTC),
                details={
                    "stage_id": stage_reference.stage_id,
                    "commit": snapshot.commit,
                },
            )

        journal.append(
            "closing_attempt",
            "all planned stages completed",
            recorded_at=datetime.now(UTC),
        )
        attempt_files = dict(log_files)
        for path in measurement_paths:
            attempt_files[path.relative_to(root).as_posix()] = path.read_bytes()
        attempt_references = store.resolved_files(attempt_files)
        measurement_references = tuple(
            reference
            for reference in attempt_references
            if "/measurements/" in str(reference.stored_at.path)
        )
        log_references = tuple(
            reference
            for reference in attempt_references
            if "/logs/" in str(reference.stored_at.path)
        )
        attempt_completed = datetime.now(UTC)
        attempt = RunAttempt(
            attempt_id=1,
            status="succeeded",
            started_at=attempt_started,
            completed_at=attempt_completed,
            resolved_stages=tuple(resolved_stage_refs),
            measurement_files=measurement_references,
            log_files=log_references,
            failure_reason=None,
        )
        run_reference = GitFileRef(
            repository=run.source.repository,
            commit=plan_commit,
            path=relative_run_path,
        )
        resolved_run = ResolvedRun(
            spec=ResolvedRunSpecRef(
                sha256=hashlib.sha256(run_raw).hexdigest(),
                bytes=len(run_raw),
                stored_at=run_reference,
            ),
            status="succeeded",
            attempts=(attempt,),
            successful_attempt_id=1,
            completed_at=datetime.now(UTC),
        )
        terminal_raw = serialize_document(resolved_run)
        terminal_path = run_path.parent / "resolved.yaml"
        terminal_path.write_bytes(terminal_raw)
        workspace.terminal.write_bytes(terminal_raw)
        verify_run_result(resolved_run, policy=policy, fetcher=fetcher)
        journal.append(
            "terminal",
            "terminal run verified",
            recorded_at=datetime.now(UTC),
            details={"resolved_run": terminal_path.relative_to(root).as_posix()},
        )
        return LocalRunResult(
            resolved_run=resolved_run,
            resolved_run_path=terminal_path,
            journal_path=journal.path,
        )
    finally:
        workspace.release()
