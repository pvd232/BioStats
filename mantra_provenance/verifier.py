"""Cross-file verification for MANTRA provenance records."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml
from huggingface_hub import hf_hub_download
from pydantic import TypeAdapter, ValidationError

from .ids import InputName, StageId
from .models_v4 import (
    ArtifactManifest,
    ArtifactPointer,
    BaseSpec,
    ExperimentSpec,
    FutureInputRef,
    GitFileRef,
    HuggingFaceFileRef,
    InternalSpec,
    RepoRelPath,
    ResolvedBaseSpec,
    ResolvedFileRef,
    ResolvedInternalSpec,
    ResolvedRun,
    ResolvedStoredInputRef,
    ResolvedSpec,
    RunSpec,
    Spec,
    StorageModel,
    StoredInputRef,
    VariantSpec,
    repo_file_paths_overlap,
)

StorageFetcher = Callable[[StorageModel], bytes]
SPEC_ADAPTER = TypeAdapter(Spec)
RESOLVED_SPEC_ADAPTER = TypeAdapter(ResolvedSpec)


class VerificationError(ValueError):
    """A referenced file could not be retrieved or failed verification."""


@dataclass(frozen=True)
class VerifiedStoredInput:
    """Verified artifact bytes and the local path where a stage consumes them."""

    path: RepoRelPath
    artifact: ResolvedFileRef
    content: bytes


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
            raise VerificationError("Git could not retrieve the referenced file") from exc

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


def verify_resolved_run_file(
    resolved_run: ResolvedRun,
    *,
    fetcher: StorageFetcher | None = None,
) -> RunSpec:
    """Verify that ``run_file`` parses to the RunSpec embedded in a resolved run."""
    raw = read_resolved_file(resolved_run.run_file, fetcher=fetcher)

    try:
        file_run = RunSpec.model_validate(yaml.safe_load(raw))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError("run_file is not a valid RunSpec document") from exc

    if file_run != resolved_run.run:
        raise VerificationError(
            "run_file does not match the RunSpec embedded in ResolvedRun"
        )

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
        path=(
            f"experiments/{run.experiment_id}/"
            f"{run.experiment_id}.experiment.yaml"
        ),
    )
    variant_location = GitFileRef(
        repository=run.source.repository,
        commit=run.source.commit,
        path=(
            f"experiments/{run.experiment_id}/variants/"
            f"{run.variant_id}.variant.yaml"
        ),
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
        variant = VariantSpec.model_validate(
            yaml.safe_load(retrieve(variant_location))
        )
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
                f"variant level {level_id!r} is not permitted for factor "
                f"{factor_id!r}"
            )

    replicates = {
        replicate.replicate_id: replicate for replicate in experiment.replicates
    }
    if run.replicate_id not in replicates:
        raise VerificationError("run replicate is not declared by the experiment")

    if run.seed != replicates[run.replicate_id].seed:
        raise VerificationError("run seed does not match the experiment replicate")

    return experiment, variant


def verify_authored_stage_plan(
    run: RunSpec,
    run_file: ResolvedFileRef,
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, BaseSpec]:
    """Load and verify authored stage specs from the run-plan snapshot."""
    retrieve = fetch_storage_bytes if fetcher is None else fetcher
    loaded_stages: dict[StageId, BaseSpec] = {}

    for stage in run.stages:
        plan_location = run_file.stored_at
        if isinstance(plan_location, GitFileRef):
            location: StorageModel = GitFileRef(
                repository=plan_location.repository,
                commit=plan_location.commit,
                path=stage.spec,
            )
        else:
            location = HuggingFaceFileRef(
                repository=plan_location.repository,
                commit=plan_location.commit,
                path=stage.spec,
                repo_type=plan_location.repo_type,
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
                f"stage {stage.stage_id!r} file is not a valid authored stage spec"
            ) from exc

        for previous_stage_id, previous_spec in loaded_stages.items():
            if repo_file_paths_overlap(spec.output, previous_spec.output):
                raise VerificationError(
                    f"stage output paths for {previous_stage_id!r} and "
                    f"{stage.stage_id!r} collide"
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

                producer_output = loaded_stages[producer_stage_id].output

                if repo_file_paths_overlap(producer_output, spec.script):
                    raise VerificationError(
                        f"future input {input_name!r} path collides with the "
                        f"script of stage {stage.stage_id!r}"
                    )

                if repo_file_paths_overlap(producer_output, spec.output):
                    raise VerificationError(
                        f"future input {input_name!r} path collides with the "
                        f"output of stage {stage.stage_id!r}"
                    )

                for stored_input in stored_inputs:
                    if repo_file_paths_overlap(producer_output, stored_input.path):
                        raise VerificationError(
                            f"future input {input_name!r} path collides with a "
                            f"stored input of stage {stage.stage_id!r}"
                        )

        loaded_stages[stage.stage_id] = spec

    return loaded_stages


def verify_resolved_stages(
    resolved_run: ResolvedRun,
    authored_stages: dict[StageId, BaseSpec],
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, ResolvedBaseSpec]:
    """Verify the resolved stages retained by a successful run attempt."""
    if resolved_run.status != "succeeded":
        raise VerificationError(
            "resolved-stage verification requires a succeeded run"
        )

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

    expected_stage_ids = tuple(stage.stage_id for stage in resolved_run.run.stages)
    resolved_stage_ids = tuple(
        stage.stage_id for stage in successful_attempt.resolved_stages
    )
    if resolved_stage_ids != expected_stage_ids:
        raise VerificationError(
            "successful attempt resolved stages do not match the run stage order"
        )

    if set(authored_stages) != set(expected_stage_ids):
        raise VerificationError(
            "loaded authored stages do not match the run stage plan"
        )

    verified_stages: dict[StageId, ResolvedBaseSpec] = {}

    for stage_reference in successful_attempt.resolved_stages:
        raw = read_resolved_file(stage_reference.resolved_spec, fetcher=fetcher)
        try:
            resolved_spec = RESOLVED_SPEC_ADAPTER.validate_python(yaml.safe_load(raw))
        except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} file is not a valid "
                "resolved stage spec"
            ) from exc

        authored_spec = authored_stages[stage_reference.stage_id]
        if resolved_spec.spec != authored_spec:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} does not embed its authored spec"
            )

        source_location = resolved_spec.source.stored_at
        if (
            source_location.repository != resolved_run.run.source.repository
            or source_location.commit != resolved_run.run.source.commit
        ):
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} source does not match the "
                "run source snapshot"
            )

        if not (
            successful_attempt.started_at
            < resolved_spec.completed_at
            <= successful_attempt.completed_at
        ):
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} completion time falls outside "
                "the successful attempt"
            )

        read_resolved_file(resolved_spec.source, fetcher=fetcher)
        read_resolved_file(resolved_spec.environment.lockfile, fetcher=fetcher)
        read_resolved_file(resolved_spec.output, fetcher=fetcher)

        verified_stages[stage_reference.stage_id] = resolved_spec

    return verified_stages


def verify_stored_inputs(
    resolved_stages: dict[StageId, ResolvedBaseSpec],
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, dict[InputName, VerifiedStoredInput]]:
    """Verify every promoted artifact consumed by the resolved stages."""
    verified_inputs: dict[StageId, dict[InputName, VerifiedStoredInput]] = {}

    for stage_id, resolved_stage in resolved_stages.items():
        if not isinstance(resolved_stage, ResolvedInternalSpec):
            continue

        stage_inputs: dict[InputName, VerifiedStoredInput] = {}

        for input_name, authored_input in resolved_stage.spec.inputs.items():
            if not isinstance(authored_input, StoredInputRef):
                continue

            resolved_input = resolved_stage.inputs.get(input_name)
            if not isinstance(resolved_input, ResolvedStoredInputRef):
                raise VerificationError(
                    f"stored input {input_name!r} of stage {stage_id!r} has no "
                    "resolved stored-input reference"
                )

            if resolved_input.pointer.stored_at != authored_input.pointer:
                raise VerificationError(
                    f"stored input {input_name!r} of stage {stage_id!r} resolved "
                    "a different pointer location than the authored spec"
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

            manifest_raw = read_resolved_file(pointer.manifest, fetcher=fetcher)
            try:
                manifest = ArtifactManifest.model_validate(
                    yaml.safe_load(manifest_raw)
                )
            except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
                raise VerificationError(
                    f"stored input {input_name!r} of stage {stage_id!r} manifest "
                    "is not a valid ArtifactManifest document"
                ) from exc

            artifact_raw = read_resolved_file(manifest.artifact, fetcher=fetcher)
            stage_inputs[input_name] = VerifiedStoredInput(
                path=authored_input.path,
                artifact=manifest.artifact,
                content=artifact_raw,
            )

        if stage_inputs:
            verified_inputs[stage_id] = stage_inputs

    return verified_inputs
