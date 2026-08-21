"""Cross-file verification for MANTRA provenance records."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import yaml
from huggingface_hub import hf_hub_download
from pydantic import TypeAdapter, ValidationError

from .ids import InputName, StageId
from .models_v4 import (
    ArtifactPointer,
    ArtifactSpec,
    BaseSpec,
    BenchmarkResult,
    BenchmarkSpec,
    BuildSpec,
    EmbedSpec,
    EvaluateSpec,
    ExperimentSpec,
    FutureInputRef,
    GitFileRef,
    HuggingFaceFileRef,
    InternalSpec,
    Measurement,
    RepoRelPath,
    ResolvedArtifact,
    ResolvedBaseSpec,
    ResolvedBundleArtifact,
    ResolvedFileRef,
    ResolvedFutureInputRef,
    ResolvedInternalSpec,
    ResolvedRun,
    ResolvedRunSpecRef,
    ResolvedSingleFileArtifact,
    ResolvedSpec,
    ResolvedStageRef,
    ResolvedStoredInputRef,
    RunAttempt,
    RunSpec,
    SnapshotFileRef,
    Spec,
    StageResultSnapshotRef,
    StorageModel,
    StoredInputRef,
    TrainSpec,
    VariantSpec,
    repo_file_paths_overlap,
)

StorageFetcher = Callable[[StorageModel], bytes]
SPEC_ADAPTER = TypeAdapter(Spec)
RESOLVED_SPEC_ADAPTER = TypeAdapter(ResolvedSpec)


class VerificationError(ValueError):
    """A referenced file could not be retrieved or failed verification."""


@dataclass(frozen=True)
class VerifiedSnapshotFile:
    """One snapshot file whose bytes match its recorded identity."""

    reference: SnapshotFileRef
    content: bytes


@dataclass(frozen=True)
class VerifiedArtifact:
    """One resolved artifact and all of its verified files."""

    artifact: ResolvedArtifact
    files: tuple[VerifiedSnapshotFile, ...]


@dataclass(frozen=True)
class VerifiedInput:
    """A verified artifact and the local path where a stage consumes it."""

    path: RepoRelPath
    artifact: ResolvedArtifact
    files: tuple[VerifiedSnapshotFile, ...]


@dataclass(frozen=True)
class VerifiedRunPlan:
    """The connected records constituting one verified run plan."""

    run: RunSpec
    experiment: ExperimentSpec
    variant: VariantSpec
    benchmark: BenchmarkSpec | None
    stages: dict[StageId, BaseSpec]


@dataclass(frozen=True)
class VerifiedRunResult:
    """A verified terminal run and its connected records."""

    plan: VerifiedRunPlan
    resolved_stages: dict[StageId, ResolvedBaseSpec]
    measurements: tuple[Measurement, ...]


@dataclass(frozen=True)
class VerifiedBenchmarkResult:
    """A benchmark result and its verified run and confirmation execution."""

    result: BenchmarkResult
    run: VerifiedRunResult
    confirmation_stages: dict[StageId, ResolvedBaseSpec]
    confirmation_measurements: tuple[Measurement, ...]


def fetch_git_file_bytes(
    location: GitFileRef,
    *,
    timeout_seconds: float = 60,
) -> bytes:
    """Read one file from the exact commit recorded by a Git reference."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    git_environment = os.environ.copy()
    git_environment["GIT_TERMINAL_PROMPT"] = "0"

    def run_git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                ("git", *arguments),
                check=True,
                capture_output=True,
                env=git_environment,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise VerificationError("Git is required to retrieve Git files") from exc
        except subprocess.TimeoutExpired as exc:
            raise VerificationError("Git file retrieval timed out") from exc
        except subprocess.CalledProcessError as exc:
            raise VerificationError(
                "Git could not retrieve the referenced file"
            ) from exc

    with tempfile.TemporaryDirectory(prefix="mantra-provenance-git-") as checkout:
        run_git("init", "--quiet", checkout)
        run_git("-C", checkout, "remote", "add", "origin", str(location.repository))
        run_git(
            "-C",
            checkout,
            "fetch",
            "--quiet",
            "--depth=1",
            "origin",
            location.commit,
        )

        fetched_commit = (
            run_git("-C", checkout, "rev-parse", "FETCH_HEAD^{commit}")
            .stdout.decode("ascii")
            .strip()
        )
        if fetched_commit != location.commit:
            raise VerificationError("Git returned a different commit than requested")

        return run_git(
            "-C",
            checkout,
            "show",
            f"FETCH_HEAD:{location.path}",
        ).stdout


def fetch_huggingface_file_bytes(location: HuggingFaceFileRef) -> bytes:
    """Read one file from the exact Hugging Face commit in the reference."""
    repo_type = None if location.repo_type == "model" else location.repo_type

    try:
        downloaded_path = hf_hub_download(
            repo_id=location.repository,
            filename=location.path,
            repo_type=repo_type,
            revision=location.commit,
        )
        return Path(downloaded_path).read_bytes()
    except (OSError, ValueError) as exc:
        raise VerificationError(
            "Hugging Face could not retrieve the referenced file"
        ) from exc


def fetch_storage_bytes(location: StorageModel) -> bytes:
    """Dispatch an immutable storage reference to its retrieval backend."""
    if isinstance(location, GitFileRef):
        return fetch_git_file_bytes(location)
    if isinstance(location, HuggingFaceFileRef):
        return fetch_huggingface_file_bytes(location)
    raise TypeError(f"unsupported storage reference: {type(location).__name__}")


def verify_resolved_file_bytes(
    reference: ResolvedFileRef,
    raw: bytes,
) -> bytes:
    """Verify retrieved bytes against a resolved file reference."""
    if not isinstance(raw, bytes):
        raise TypeError("retrieved file content must be bytes")

    if len(raw) != reference.bytes:
        raise VerificationError(
            f"byte-count mismatch: expected {reference.bytes}, received {len(raw)}"
        )

    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != reference.sha256:
        raise VerificationError(
            f"SHA-256 mismatch: expected {reference.sha256}, received {actual_sha256}"
        )

    return raw


def read_resolved_file(
    reference: ResolvedFileRef,
    *,
    fetcher: StorageFetcher | None = None,
) -> bytes:
    """Retrieve a resolved file and verify its byte count and SHA-256."""
    retrieve = fetch_storage_bytes if fetcher is None else fetcher
    raw = retrieve(reference.stored_at)
    return verify_resolved_file_bytes(reference, raw)


def read_snapshot_file(
    snapshot: StageResultSnapshotRef,
    reference: SnapshotFileRef,
    *,
    fetcher: StorageFetcher | None = None,
) -> bytes:
    """Retrieve and verify one file from a stage-result snapshot."""
    retrieve = fetch_storage_bytes if fetcher is None else fetcher
    location = HuggingFaceFileRef(
        repository=snapshot.repository,
        commit=snapshot.commit,
        path=reference.path,
        repo_type=snapshot.repo_type,
    )
    raw = retrieve(location)

    resolved_reference = ResolvedFileRef(
        sha256=reference.sha256,
        bytes=reference.bytes,
        stored_at=location,
    )
    return verify_resolved_file_bytes(resolved_reference, raw)


def verify_snapshot_artifact(
    stage: ResolvedStageRef,
    artifact: ResolvedArtifact,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifiedArtifact:
    """Verify every file representing one artifact in a stage snapshot."""
    if isinstance(artifact, ResolvedSingleFileArtifact):
        references = (artifact.file,)
    elif isinstance(artifact, ResolvedBundleArtifact):
        references = tuple(member.file for member in artifact.members)
    else:
        raise TypeError(f"unsupported resolved artifact: {type(artifact).__name__}")

    files = tuple(
        VerifiedSnapshotFile(
            reference=reference,
            content=read_snapshot_file(
                stage.snapshot,
                reference,
                fetcher=fetcher,
            ),
        )
        for reference in references
    )
    return VerifiedArtifact(artifact=artifact, files=files)


def load_verified_artifact(
    run: RunSpec,
    declaration: ArtifactSpec,
    artifact: VerifiedArtifact,
    *,
    fetcher: StorageFetcher | None = None,
) -> object:
    """Materialize verified files and reconstruct one artifact with its loader."""
    retrieve = fetch_storage_bytes if fetcher is None else fetcher
    loader_location = GitFileRef(
        repository=run.source.repository,
        commit=run.source.commit,
        path=f"src/mantra/artifact_loaders/{declaration.loader}.py",
    )
    loader_raw = retrieve(loader_location)

    module = ModuleType(f"mantra_artifact_loader_{declaration.loader}")
    module.__file__ = str(loader_location.path)
    try:
        exec(compile(loader_raw, module.__file__, "exec"), module.__dict__)
    except Exception as exc:
        raise VerificationError(
            f"artifact loader {declaration.loader!r} could not be loaded"
        ) from exc

    load = getattr(module, "load", None)
    if not callable(load):
        raise VerificationError(
            f"artifact loader {declaration.loader!r} does not define load(path)"
        )

    with tempfile.TemporaryDirectory(prefix="mantra-artifact-") as directory:
        root = Path(directory)
        for verified_file in artifact.files:
            materialized = root / verified_file.reference.path
            materialized.parent.mkdir(parents=True, exist_ok=True)
            materialized.write_bytes(verified_file.content)

        artifact_path = root / declaration.path
        try:
            return load(artifact_path)
        except Exception as exc:
            raise VerificationError(
                f"artifact loader {declaration.loader!r} could not reconstruct "
                "the verified artifact"
            ) from exc


def verify_resolved_run_file(
    resolved_run: ResolvedRun,
    *,
    fetcher: StorageFetcher | None = None,
) -> RunSpec:
    """Retrieve and verify the RunSpec governing a resolved run."""
    raw = read_resolved_file(resolved_run.spec, fetcher=fetcher)

    try:
        file_run = RunSpec.model_validate(yaml.safe_load(raw))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError("resolved run spec is not a valid RunSpec") from exc

    return file_run


def verify_experiment_and_variant(
    run: RunSpec,
    *,
    fetcher: StorageFetcher | None = None,
) -> tuple[ExperimentSpec, VariantSpec]:
    """Load and verify the experiment and variant selected by a run."""
    retrieve = fetch_storage_bytes if fetcher is None else fetcher

    experiment_location = GitFileRef(
        repository=run.source.repository,
        commit=run.source.commit,
        path=f"experiments/{run.experiment_id}/spec.yaml",
    )
    variant_location = GitFileRef(
        repository=run.source.repository,
        commit=run.source.commit,
        path=f"experiments/{run.experiment_id}/variants/{run.variant_id}.spec.yaml",
    )

    try:
        experiment = ExperimentSpec.model_validate(
            yaml.safe_load(retrieve(experiment_location))
        )
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError(
            "experiment file is not a valid ExperimentSpec document"
        ) from exc

    try:
        variant = VariantSpec.model_validate(yaml.safe_load(retrieve(variant_location)))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError(
            "variant file is not a valid VariantSpec document"
        ) from exc

    if experiment.experiment_id != run.experiment_id:
        raise VerificationError("run and experiment IDs do not match")

    if variant.experiment_id != run.experiment_id:
        raise VerificationError("run and variant experiment IDs do not match")

    if variant.variant_id != run.variant_id:
        raise VerificationError("run and variant IDs do not match")

    if run.variant_id not in experiment.variant_ids:
        raise VerificationError("run variant is not declared by the experiment")

    factors = {factor.factor_id: factor for factor in experiment.factors}
    if set(variant.levels) != set(factors):
        raise VerificationError(
            "variant must assign exactly one level to every experiment factor"
        )

    for factor_id, level_id in variant.levels.items():
        if level_id not in factors[factor_id].levels:
            raise VerificationError(
                f"variant level {level_id!r} is not permitted for factor {factor_id!r}"
            )

    replicates = {
        replicate.replicate_id: replicate for replicate in experiment.replicates
    }
    if run.replicate_id not in replicates:
        raise VerificationError("run replicate is not declared by the experiment")

    if run.seed != replicates[run.replicate_id].seed:
        raise VerificationError("run seed does not match the experiment replicate")

    return experiment, variant


def verify_benchmark_spec(
    run: RunSpec,
    *,
    fetcher: StorageFetcher | None = None,
) -> BenchmarkSpec | None:
    """Load the benchmark selected by a run, when one is selected."""
    if run.benchmark_id is None:
        return None

    retrieve = fetch_storage_bytes if fetcher is None else fetcher
    location = GitFileRef(
        repository=run.source.repository,
        commit=run.source.commit,
        path=f"benchmarks/{run.benchmark_id}.spec.yaml",
    )
    try:
        benchmark = BenchmarkSpec.model_validate(yaml.safe_load(retrieve(location)))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError(
            "benchmark file is not a valid BenchmarkSpec document"
        ) from exc

    if benchmark.benchmark_id != run.benchmark_id:
        raise VerificationError("run and benchmark IDs do not match")
    return benchmark


def verify_run_plan_relationships(
    run: RunSpec,
    experiment: ExperimentSpec,
    variant: VariantSpec,
    benchmark: BenchmarkSpec | None,
    stages: Mapping[StageId, BaseSpec],
) -> None:
    """Verify plan relationships spanning experiment, variant, and stages."""
    parameterized_stages = {
        stage_id: stage
        for stage_id, stage in stages.items()
        if isinstance(stage, (BuildSpec, EmbedSpec, TrainSpec, EvaluateSpec))
    }
    variant_params = {stage.stage_id: stage for stage in variant.stage_params}

    if set(variant_params) != set(parameterized_stages):
        raise VerificationError(
            "variant stage parameters must match all parameterized run stages"
        )

    for stage_id, stage in parameterized_stages.items():
        selected = variant_params[stage_id]
        if selected.kind != stage.kind or selected.params != stage.params:
            raise VerificationError(
                f"variant parameters do not match stage {stage_id!r}"
            )

    estimator_stage = stages.get(run.estimator.stage_id)
    if not isinstance(estimator_stage, TrainSpec):
        raise VerificationError("run estimator must select a training stage")

    experiment_metrics = set(experiment.metric_ids)
    for stage_id, stage in stages.items():
        if not isinstance(stage, EvaluateSpec):
            continue
        if not set(stage.params.metric_ids) <= experiment_metrics:
            raise VerificationError(
                f"evaluation stage {stage_id!r} selects undeclared metrics"
            )

    if benchmark is None:
        return

    evaluation_stages = [
        stage for stage in stages.values() if isinstance(stage, EvaluateSpec)
    ]
    if len(evaluation_stages) != 1:
        raise VerificationError(
            "benchmark runs require exactly one evaluation stage"
        )

    evaluation = evaluation_stages[0]
    dataset_input = evaluation.inputs["evaluation_dataset"]
    if not isinstance(dataset_input, StoredInputRef):
        raise VerificationError("benchmark evaluation dataset must be stored")
    if dataset_input.pointer != benchmark.evaluation_dataset:
        raise VerificationError(
            "evaluation dataset does not match the benchmark specification"
        )

    if set(evaluation.params.split_inputs) != set(benchmark.splits):
        raise VerificationError(
            "evaluation split names do not match the benchmark specification"
        )
    for split_name, pointer in benchmark.splits.items():
        split_input = evaluation.inputs[split_name]
        if not isinstance(split_input, StoredInputRef):
            raise VerificationError(f"benchmark split {split_name!r} must be stored")
        if split_input.pointer != pointer:
            raise VerificationError(
                f"evaluation split {split_name!r} does not match the benchmark"
            )

    benchmark_metric_ids = {criterion.metric_id for criterion in benchmark.metrics}
    if set(evaluation.params.metric_ids) != benchmark_metric_ids:
        raise VerificationError(
            "evaluation metrics do not match the benchmark specification"
        )


def verify_stage_plan(
    run: RunSpec,
    run_file: ResolvedRunSpecRef,
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, BaseSpec]:
    """Load and verify stage specs from the run-plan snapshot."""
    retrieve = fetch_storage_bytes if fetcher is None else fetcher
    loaded_stages: dict[StageId, BaseSpec] = {}

    for stage in run.stages:
        plan_location = run_file.stored_at
        location = GitFileRef(
            repository=plan_location.repository,
            commit=plan_location.commit,
            path=stage.spec,
        )

        stage_reference = ResolvedFileRef(
            sha256=stage.sha256,
            bytes=stage.bytes,
            stored_at=location,
        )
        raw = verify_resolved_file_bytes(stage_reference, retrieve(location))

        try:
            spec = SPEC_ADAPTER.validate_python(yaml.safe_load(raw))
        except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
            raise VerificationError(
                f"stage {stage.stage_id!r} file is not a valid stage spec"
            ) from exc

        for previous_stage_id, previous_spec in loaded_stages.items():
            for artifact_name, artifact in spec.artifacts.items():
                for previous_name, previous_artifact in previous_spec.artifacts.items():
                    if repo_file_paths_overlap(
                        artifact.path,
                        previous_artifact.path,
                    ):
                        raise VerificationError(
                            f"artifact paths for {previous_stage_id!r}/"
                            f"{previous_name!r} and {stage.stage_id!r}/"
                            f"{artifact_name!r} collide"
                        )

        if isinstance(spec, InternalSpec):
            stored_inputs = tuple(
                input_ref
                for input_ref in spec.inputs.values()
                if isinstance(input_ref, StoredInputRef)
            )

            for input_name, input_ref in spec.inputs.items():
                if not isinstance(input_ref, FutureInputRef):
                    continue

                producer_stage_id = input_ref.producer_stage_id
                if producer_stage_id not in loaded_stages:
                    raise VerificationError(
                        f"future input {input_name!r} of stage {stage.stage_id!r} "
                        "must name an earlier stage"
                    )

                producer_spec = loaded_stages[producer_stage_id]
                producer_artifact = producer_spec.artifacts.get(
                    input_ref.producer_artifact
                )
                if producer_artifact is None:
                    raise VerificationError(
                        f"future input {input_name!r} of stage {stage.stage_id!r} "
                        f"selects undeclared artifact "
                        f"{input_ref.producer_artifact!r}"
                    )

                producer_path = producer_artifact.path

                if repo_file_paths_overlap(producer_path, spec.script):
                    raise VerificationError(
                        f"future input {input_name!r} path collides with the "
                        f"script of stage {stage.stage_id!r}"
                    )

                for artifact_name, artifact in spec.artifacts.items():
                    if repo_file_paths_overlap(producer_path, artifact.path):
                        raise VerificationError(
                            f"future input {input_name!r} path collides with "
                            f"artifact {artifact_name!r} of stage "
                            f"{stage.stage_id!r}"
                        )

                for stored_input in stored_inputs:
                    if repo_file_paths_overlap(producer_path, stored_input.path):
                        raise VerificationError(
                            f"future input {input_name!r} path collides with a "
                            f"stored input of stage {stage.stage_id!r}"
                        )

        loaded_stages[stage.stage_id] = spec

    return loaded_stages


def verify_run_plan(
    resolved_run: ResolvedRun,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifiedRunPlan:
    """Retrieve and verify every record constituting a frozen run plan."""
    run = verify_resolved_run_file(resolved_run, fetcher=fetcher)
    experiment, variant = verify_experiment_and_variant(run, fetcher=fetcher)
    benchmark = verify_benchmark_spec(run, fetcher=fetcher)
    stages = verify_stage_plan(run, resolved_run.spec, fetcher=fetcher)
    verify_run_plan_relationships(
        run,
        experiment,
        variant,
        benchmark,
        stages,
    )
    return VerifiedRunPlan(
        run=run,
        experiment=experiment,
        variant=variant,
        benchmark=benchmark,
        stages=stages,
    )


def verify_attempt_stages(
    attempt: RunAttempt,
    run: RunSpec,
    stage_specs: Mapping[StageId, BaseSpec],
    *,
    require_complete: bool,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, ResolvedBaseSpec]:
    """Verify the ordered resolved-stage prefix retained by one attempt."""
    expected_stage_ids = tuple(stage.stage_id for stage in run.stages)
    resolved_stage_ids = tuple(stage.stage_id for stage in attempt.resolved_stages)
    if resolved_stage_ids != expected_stage_ids[: len(resolved_stage_ids)]:
        raise VerificationError(
            "attempt resolved stages must form an ordered run-stage prefix"
        )
    if require_complete and resolved_stage_ids != expected_stage_ids:
        raise VerificationError("successful attempt must contain every run stage")

    if set(stage_specs) != set(expected_stage_ids):
        raise VerificationError("loaded stage specs do not match the run stage plan")

    verified_stages: dict[StageId, ResolvedBaseSpec] = {}
    run_stage_refs = {stage.stage_id: stage for stage in run.stages}

    for stage_reference in attempt.resolved_stages:
        raw = read_snapshot_file(
            stage_reference.snapshot,
            stage_reference.resolved_spec,
            fetcher=fetcher,
        )
        try:
            resolved_spec = RESOLVED_SPEC_ADAPTER.validate_python(yaml.safe_load(raw))
        except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} file is not a valid "
                "resolved stage spec"
            ) from exc

        stage_spec = stage_specs[stage_reference.stage_id]
        if resolved_spec.spec != stage_spec:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} does not embed its stage spec"
            )

        source_location = resolved_spec.source.stored_at
        if (
            source_location.repository != run.source.repository
            or source_location.commit != run.source.commit
        ):
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} source does not match the "
                "run source snapshot"
            )

        if not (
            attempt.started_at
            < resolved_spec.completed_at
            <= attempt.completed_at
        ):
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} completion time falls outside "
                "the successful attempt"
            )

        read_resolved_file(resolved_spec.source, fetcher=fetcher)
        read_resolved_file(resolved_spec.environment.lockfile, fetcher=fetcher)

        requested_environment = stage_spec.environment or run.environment
        resolved_environment = resolved_spec.environment
        if (
            resolved_environment.machine_image.project
            != requested_environment.machine_image.project
            or resolved_environment.machine_image.name
            != requested_environment.machine_image.name
            or resolved_environment.machine_type != requested_environment.machine_type
            or resolved_environment.compute != requested_environment.compute
            or resolved_environment.lockfile.stored_at
            != requested_environment.lockfile
        ):
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} realized a different "
                "environment than requested"
            )

        context = resolved_spec.execution_context
        if context.determinism != run.reproducibility.determinism:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} determinism controls do "
                "not match the run plan"
            )
        if context.precision != run.reproducibility.precision:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} precision controls do not "
                "match the run plan"
            )
        if context.parallelism != run.reproducibility.parallelism:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} parallelism controls do "
                "not match the run plan"
            )

        recorded_seeds = {
            context.randomness.python_seed,
            context.randomness.numpy_seed,
            context.randomness.torch_seed,
            context.randomness.dataloader_seed,
        }
        if recorded_seeds != {run.seed}:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} did not apply the run seed"
            )

        run_stage_ref = run_stage_refs[stage_reference.stage_id]
        expected_command = (
            "python",
            str(stage_spec.script),
            str(run_stage_ref.spec),
        )
        if resolved_spec.command != expected_command:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} command does not match "
                "the run plan"
            )

        for artifact_name, artifact in resolved_spec.artifacts.items():
            verified_artifact = verify_snapshot_artifact(
                stage_reference,
                artifact,
                fetcher=fetcher,
            )
            load_verified_artifact(
                run,
                stage_spec.artifacts[artifact_name],
                verified_artifact,
                fetcher=fetcher,
            )

        verified_stages[stage_reference.stage_id] = resolved_spec

    return verified_stages


def verify_resolved_stages(
    resolved_run: ResolvedRun,
    run: RunSpec,
    stage_specs: Mapping[StageId, BaseSpec],
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, ResolvedBaseSpec]:
    """Verify the complete stage sequence retained by a successful run."""
    if resolved_run.status != "succeeded":
        raise VerificationError("resolved-stage verification requires a succeeded run")

    successful_attempt = next(
        (
            attempt
            for attempt in resolved_run.attempts
            if attempt.attempt_id == resolved_run.successful_attempt_id
        ),
        None,
    )
    if successful_attempt is None or successful_attempt.status != "succeeded":
        raise VerificationError("successful attempt could not be identified")

    return verify_attempt_stages(
        successful_attempt,
        run,
        stage_specs,
        require_complete=True,
        fetcher=fetcher,
    )


def verify_attempt_files(
    attempt: RunAttempt,
    run: RunSpec,
    experiment: ExperimentSpec,
    *,
    fetcher: StorageFetcher | None = None,
) -> tuple[Measurement, ...]:
    """Verify an attempt's measurements and logs against their file identities."""
    completed_stage_ids = {stage.stage_id for stage in attempt.resolved_stages}
    permitted_metrics = set(experiment.metric_ids)
    measurements: list[Measurement] = []

    for reference in attempt.measurement_files:
        raw = read_resolved_file(reference, fetcher=fetcher)
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise VerificationError("measurement file is not valid UTF-8") from exc

        for line in lines:
            if not line.strip():
                continue
            try:
                measurement = Measurement.model_validate(json.loads(line))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise VerificationError(
                    "measurement file contains an invalid Measurement row"
                ) from exc

            if measurement.run_id != run.run_id:
                raise VerificationError("measurement run ID does not match the run")
            if measurement.attempt_id != attempt.attempt_id:
                raise VerificationError(
                    "measurement attempt ID does not match its containing attempt"
                )
            if measurement.stage_id not in completed_stage_ids:
                raise VerificationError(
                    "measurement stage is absent from its containing attempt"
                )
            if measurement.metric_id not in permitted_metrics:
                raise VerificationError(
                    "measurement metric is absent from the experiment"
                )
            if not (
                attempt.started_at
                <= measurement.measured_at
                <= attempt.completed_at
            ):
                raise VerificationError(
                    "measurement timestamp falls outside its containing attempt"
                )
            measurements.append(measurement)

    for reference in attempt.log_files:
        read_resolved_file(reference, fetcher=fetcher)

    return tuple(measurements)


def verify_run_result(
    resolved_run: ResolvedRun,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifiedRunResult:
    """Verify a terminal run from its RunSpec through every completed attempt."""
    plan = verify_run_plan(resolved_run, fetcher=fetcher)
    all_measurements: list[Measurement] = []
    successful_stages: dict[StageId, ResolvedBaseSpec] = {}

    for attempt in resolved_run.attempts:
        complete = attempt.status == "succeeded"
        verified_stages = verify_attempt_stages(
            attempt,
            plan.run,
            plan.stages,
            require_complete=complete,
            fetcher=fetcher,
        )
        all_measurements.extend(
            verify_attempt_files(
                attempt,
                plan.run,
                plan.experiment,
                fetcher=fetcher,
            )
        )
        if attempt.attempt_id == resolved_run.successful_attempt_id:
            successful_stages = verified_stages

    if resolved_run.status == "succeeded":
        estimator_stage = successful_stages.get(plan.run.estimator.stage_id)
        if estimator_stage is None:
            raise VerificationError("successful run has no estimator-producing stage")
        if plan.run.estimator.artifact_name not in estimator_stage.artifacts:
            raise VerificationError("successful run has no selected estimator artifact")

        verify_stored_inputs(successful_stages, fetcher=fetcher)
        verify_future_inputs(
            resolved_run,
            plan.run,
            successful_stages,
            fetcher=fetcher,
        )

    return VerifiedRunResult(
        plan=plan,
        resolved_stages=successful_stages,
        measurements=tuple(all_measurements),
    )


def verify_promoted_artifact(
    pointer: ArtifactPointer,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifiedArtifact:
    """Follow a promoted artifact pointer through its completed producer run."""
    resolved_run_raw = read_resolved_file(pointer.run, fetcher=fetcher)
    try:
        resolved_run = ResolvedRun.model_validate(yaml.safe_load(resolved_run_raw))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError(
            "artifact pointer run is not a valid ResolvedRun document"
        ) from exc

    verified_plan = verify_run_plan(resolved_run, fetcher=fetcher)
    resolved_stages = verify_resolved_stages(
        resolved_run,
        verified_plan.run,
        verified_plan.stages,
        fetcher=fetcher,
    )

    producer_spec = resolved_stages.get(pointer.artifact.stage_id)
    if producer_spec is None:
        raise VerificationError("artifact pointer selects an absent producer stage")

    artifact = producer_spec.artifacts.get(pointer.artifact.artifact_name)
    if artifact is None:
        raise VerificationError("artifact pointer selects an undeclared artifact")

    if pointer.benchmark_result is not None:
        benchmark_result_raw = read_resolved_file(
            pointer.benchmark_result,
            fetcher=fetcher,
        )
        try:
            benchmark_result = BenchmarkResult.model_validate(
                yaml.safe_load(benchmark_result_raw)
            )
        except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
            raise VerificationError(
                "artifact pointer benchmark result is invalid"
            ) from exc

        verify_benchmark_result(benchmark_result, fetcher=fetcher)
        if benchmark_result.status != "passed":
            raise VerificationError(
                "artifact pointer benchmark result must have passed"
            )
        if benchmark_result.run != pointer.run:
            raise VerificationError(
                "artifact pointer and benchmark result select different runs"
            )
        if pointer.artifact != verified_plan.run.estimator:
            raise VerificationError(
                "benchmark promotion must select the run estimator"
            )

    successful_attempt = next(
        attempt
        for attempt in resolved_run.attempts
        if attempt.attempt_id == resolved_run.successful_attempt_id
    )
    producer_stage = next(
        stage
        for stage in successful_attempt.resolved_stages
        if stage.stage_id == pointer.artifact.stage_id
    )
    return verify_snapshot_artifact(producer_stage, artifact, fetcher=fetcher)


def verify_stored_inputs(
    resolved_stages: Mapping[StageId, ResolvedBaseSpec],
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, dict[InputName, VerifiedInput]]:
    """Verify every promoted artifact consumed by the resolved stages."""
    verified_inputs: dict[StageId, dict[InputName, VerifiedInput]] = {}

    for stage_id, resolved_stage in resolved_stages.items():
        if not isinstance(resolved_stage, ResolvedInternalSpec):
            continue

        stage_inputs: dict[InputName, VerifiedInput] = {}

        for input_name, spec_input in resolved_stage.spec.inputs.items():
            if not isinstance(spec_input, StoredInputRef):
                continue

            resolved_input = resolved_stage.inputs.get(input_name)
            if not isinstance(resolved_input, ResolvedStoredInputRef):
                raise VerificationError(
                    f"stored input {input_name!r} of stage {stage_id!r} has no "
                    "resolved stored-input reference"
                )

            if resolved_input.pointer.stored_at != spec_input.pointer:
                raise VerificationError(
                    f"stored input {input_name!r} of stage {stage_id!r} resolved "
                    "a different pointer location than the stage spec"
                )

            pointer_raw = read_resolved_file(
                resolved_input.pointer,
                fetcher=fetcher,
            )
            try:
                pointer = ArtifactPointer.model_validate(yaml.safe_load(pointer_raw))
            except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
                raise VerificationError(
                    f"stored input {input_name!r} of stage {stage_id!r} pointer "
                    "is not a valid ArtifactPointer document"
                ) from exc

            verified_artifact = verify_promoted_artifact(pointer, fetcher=fetcher)
            stage_inputs[input_name] = VerifiedInput(
                path=spec_input.path,
                artifact=verified_artifact.artifact,
                files=verified_artifact.files,
            )

        if stage_inputs:
            verified_inputs[stage_id] = stage_inputs

    return verified_inputs


def verify_future_inputs(
    resolved_run: ResolvedRun,
    run: RunSpec,
    resolved_stages: Mapping[StageId, ResolvedBaseSpec],
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, dict[InputName, VerifiedInput]]:
    if resolved_run.status != "succeeded":
        raise VerificationError("future-input verification requires a succeeded run")

    successful_attempt = next(
        (
            attempt
            for attempt in resolved_run.attempts
            if attempt.attempt_id == resolved_run.successful_attempt_id
        ),
        None,
    )
    if successful_attempt is None or successful_attempt.status != "succeeded":
        raise VerificationError("successful attempt could not be identified")

    stage_positions: dict[StageId, int] = {}
    for position, stage_reference in enumerate(run.stages):
        stage_positions[stage_reference.stage_id] = position

    completed_stages = {
        stage.stage_id: stage for stage in successful_attempt.resolved_stages
    }

    verified_inputs: dict[StageId, dict[InputName, VerifiedInput]] = {}
    for consumer_stage_id, resolved_consumer_spec in resolved_stages.items():
        # Not checking download specs because they don't have any inputs to verify
        if not isinstance(resolved_consumer_spec, ResolvedInternalSpec):
            continue

        stage_inputs: dict[InputName, VerifiedInput] = {}

        for input_name, spec_input in resolved_consumer_spec.spec.inputs.items():
            if not isinstance(spec_input, FutureInputRef):
                continue

            resolved_input = resolved_consumer_spec.inputs[input_name]

            if not isinstance(resolved_input, ResolvedFutureInputRef):
                raise VerificationError(
                    f"future input {input_name!r} of stage "
                    f"{consumer_stage_id!r} has no resolved future-input "
                    "reference"
                )

            producer_stage_id = spec_input.producer_stage_id

            if consumer_stage_id not in stage_positions:
                raise VerificationError(
                    f"consumer stage {consumer_stage_id!r} is not in the run plan"
                )

            if producer_stage_id not in stage_positions:
                raise VerificationError(
                    f"producer stage {producer_stage_id!r} is not in the run plan"
                )

            if stage_positions[producer_stage_id] >= stage_positions[consumer_stage_id]:
                raise VerificationError(
                    f"future input {input_name!r} must name an earlier stage"
                )

            resolved_producer_spec = resolved_stages.get(producer_stage_id)

            if resolved_producer_spec is None:
                raise VerificationError(
                    f"resolved producer stage {producer_stage_id!r} is missing"
                )

            producer_stage_reference = completed_stages.get(producer_stage_id)
            if producer_stage_reference is None:
                raise VerificationError(
                    f"successful attempt has no resolved stage for "
                    f"{producer_stage_id!r}"
                )

            if resolved_input.producer != producer_stage_reference:
                raise VerificationError(
                    f"future input {input_name!r} of stage "
                    f"{consumer_stage_id!r} does not identify the completed "
                    "producer stage"
                )

            artifact_name = spec_input.producer_artifact
            artifact = resolved_producer_spec.artifacts.get(artifact_name)
            if artifact is None:
                raise VerificationError(
                    f"producer stage {producer_stage_id!r} has no artifact "
                    f"named {artifact_name!r}"
                )

            declared_artifact = resolved_producer_spec.spec.artifacts.get(artifact_name)
            if declared_artifact is None:
                raise VerificationError(
                    f"producer stage {producer_stage_id!r} did not declare "
                    f"artifact {artifact_name!r}"
                )

            verified_artifact = verify_snapshot_artifact(
                producer_stage_reference,
                artifact,
                fetcher=fetcher,
            )
            stage_inputs[input_name] = VerifiedInput(
                path=declared_artifact.path,
                artifact=verified_artifact.artifact,
                files=verified_artifact.files,
            )

        if stage_inputs:
            verified_inputs[consumer_stage_id] = stage_inputs

    return verified_inputs


def verify_benchmark_result(
    result: BenchmarkResult,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifiedBenchmarkResult:
    """Verify benchmark parity and metric criteria across two executions."""
    benchmark_raw = read_resolved_file(result.benchmark, fetcher=fetcher)
    try:
        benchmark = BenchmarkSpec.model_validate(yaml.safe_load(benchmark_raw))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError(
            "benchmark result does not reference a valid BenchmarkSpec"
        ) from exc

    run_raw = read_resolved_file(result.run, fetcher=fetcher)
    try:
        resolved_run = ResolvedRun.model_validate(yaml.safe_load(run_raw))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError(
            "benchmark result does not reference a valid ResolvedRun"
        ) from exc

    verified_run = verify_run_result(resolved_run, fetcher=fetcher)
    if verified_run.plan.benchmark != benchmark:
        raise VerificationError(
            "benchmark result and run plan select different benchmark specs"
        )

    selected_attempt = next(
        attempt
        for attempt in resolved_run.attempts
        if attempt.attempt_id == resolved_run.successful_attempt_id
    )
    if result.confirmation.attempt_id == selected_attempt.attempt_id:
        raise VerificationError(
            "benchmark confirmation must use a distinct attempt ID"
        )

    confirmation_stages = verify_attempt_stages(
        result.confirmation,
        verified_run.plan.run,
        verified_run.plan.stages,
        require_complete=True,
        fetcher=fetcher,
    )
    confirmation_measurements = verify_attempt_files(
        result.confirmation,
        verified_run.plan.run,
        verified_run.plan.experiment,
        fetcher=fetcher,
    )

    estimator_ref = verified_run.plan.run.estimator
    selected_estimator = verified_run.resolved_stages[
        estimator_ref.stage_id
    ].artifacts[estimator_ref.artifact_name]
    confirmation_estimator = confirmation_stages[
        estimator_ref.stage_id
    ].artifacts[estimator_ref.artifact_name]
    estimator_parity = selected_estimator == confirmation_estimator

    evaluation_stage_ids = [
        stage_id
        for stage_id, stage in verified_run.plan.stages.items()
        if isinstance(stage, EvaluateSpec)
    ]
    if len(evaluation_stage_ids) != 1:
        raise VerificationError(
            "benchmark verification requires one evaluation stage"
        )
    evaluation_stage_id = evaluation_stage_ids[0]
    selected_predictions = verified_run.resolved_stages[
        evaluation_stage_id
    ].artifacts["predictions"]
    confirmation_predictions = confirmation_stages[evaluation_stage_id].artifacts[
        "predictions"
    ]
    prediction_parity = selected_predictions == confirmation_predictions

    selected_measurements = tuple(
        measurement
        for measurement in verified_run.measurements
        if measurement.attempt_id == selected_attempt.attempt_id
        and measurement.stage_id == evaluation_stage_id
    )
    confirmation_evaluation_measurements = tuple(
        measurement
        for measurement in confirmation_measurements
        if measurement.stage_id == evaluation_stage_id
    )

    criteria_pass = True
    for criterion in benchmark.metrics:
        selected_values = [
            measurement.value
            for measurement in selected_measurements
            if measurement.metric_id == criterion.metric_id
        ]
        confirmation_values = [
            measurement.value
            for measurement in confirmation_evaluation_measurements
            if measurement.metric_id == criterion.metric_id
        ]
        if len(selected_values) != 1 or len(confirmation_values) != 1:
            raise VerificationError(
                f"benchmark metric {criterion.metric_id!r} must occur once per "
                "evaluation execution"
            )

        values = (selected_values[0], confirmation_values[0])
        if criterion.comparison == "ge":
            criteria_pass &= all(value >= criterion.threshold for value in values)
        else:
            criteria_pass &= all(value <= criterion.threshold for value in values)

    passed = estimator_parity and prediction_parity and criteria_pass
    expected_status = "passed" if passed else "failed"
    if result.status != expected_status:
        raise VerificationError(
            "benchmark result status does not match parity and metric checks"
        )

    return VerifiedBenchmarkResult(
        result=result,
        run=verified_run,
        confirmation_stages=confirmation_stages,
        confirmation_measurements=confirmation_measurements,
    )
