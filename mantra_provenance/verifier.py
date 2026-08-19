"""Cross-file verification for MANTRA provenance records."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping
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
    ResolvedArtifactManifestRef,
    ResolvedBaseSpec,
    ResolvedFileRef,
    ResolvedFutureInputRef,
    ResolvedInternalSpec,
    ResolvedRun,
    ResolvedSpec,
    ResolvedStoredInputRef,
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
class VerifiedArtifactManifest:
    """Files and records verified through one artifact manifest."""

    manifest: ArtifactManifest
    spec: BaseSpec
    resolved_spec: ResolvedBaseSpec
    artifact: ResolvedFileRef
    content: bytes


@dataclass(frozen=True)
class VerifiedInput:
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
        path=(f"experiments/{run.experiment_id}/{run.experiment_id}.experiment.yaml"),
    )
    variant_location = GitFileRef(
        repository=run.source.repository,
        commit=run.source.commit,
        path=(
            f"experiments/{run.experiment_id}/variants/{run.variant_id}.variant.yaml"
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


def verify_stage_plan(
    run: RunSpec,
    run_file: ResolvedFileRef,
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, BaseSpec]:
    """Load and verify stage specs from the run-plan snapshot."""
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
                f"stage {stage.stage_id!r} file is not a valid stage spec"
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
    stage_specs: Mapping[StageId, BaseSpec],
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, ResolvedBaseSpec]:
    """Verify the resolved stages retained by a successful run attempt."""
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

    expected_stage_ids = tuple(stage.stage_id for stage in resolved_run.run.stages)
    resolved_stage_ids = tuple(
        stage.stage_id for stage in successful_attempt.resolved_stages
    )
    if resolved_stage_ids != expected_stage_ids:
        raise VerificationError(
            "successful attempt resolved stages do not match the run stage order"
        )

    if set(stage_specs) != set(expected_stage_ids):
        raise VerificationError("loaded stage specs do not match the run stage plan")

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

        stage_spec = stage_specs[stage_reference.stage_id]
        if resolved_spec.spec != stage_spec:
            raise VerificationError(
                f"stage {stage_reference.stage_id!r} does not embed its stage spec"
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

            verified_manifest = verify_artifact_manifest(
                pointer.manifest,
                fetcher=fetcher,
            )

            stage_inputs[input_name] = VerifiedInput(
                path=spec_input.path,
                artifact=verified_manifest.artifact,
                content=verified_manifest.content,
            )

        if stage_inputs:
            verified_inputs[stage_id] = stage_inputs

    return verified_inputs


def verify_future_inputs(
    resolved_run: ResolvedRun,
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

    verified_manifests: list[
        tuple[ResolvedArtifactManifestRef, VerifiedArtifactManifest]
    ] = []
    for manifest_reference in successful_attempt.artifact_manifests:
        verified_manifest = verify_artifact_manifest(
            manifest_reference, fetcher=fetcher
        )
        verified_manifests.append((manifest_reference, verified_manifest))

    stage_positions: dict[StageId, int] = {}
    for position, stage_reference in enumerate(resolved_run.run.stages):
        stage_positions[stage_reference.stage_id] = position

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

            producer_stage_reference = None
            for stage_reference in successful_attempt.resolved_stages:
                if stage_reference.stage_id == producer_stage_id:
                    producer_stage_reference = stage_reference
                    break

            if producer_stage_reference is None:
                raise VerificationError(
                    f"successful attempt has no resolved stage for "
                    f"{producer_stage_id!r}"
                )

            producer_manifest_reference = None
            verified_producer_manifest = None

            for manifest_reference, verified_manifest in verified_manifests:
                if (
                    verified_manifest.manifest.resolved_spec
                    == producer_stage_reference.resolved_spec
                ):
                    if producer_manifest_reference is not None:
                        raise VerificationError(
                            f"producer stage {producer_stage_id!r} has multiple "
                            "artifact manifests"
                        )
                    producer_manifest_reference = manifest_reference
                    verified_producer_manifest = verified_manifest

            if (
                producer_manifest_reference is None
                or verified_producer_manifest is None
            ):
                raise VerificationError(
                    f"producer stage {producer_stage_id!r} has no artifact manifest"
                )

            if resolved_input.manifest != producer_manifest_reference:
                raise VerificationError(
                    f"future input {input_name!r} of stage "
                    f"{consumer_stage_id!r} does not reference the producer's "
                    "artifact manifest"
                )

            if verified_producer_manifest.resolved_spec != resolved_producer_spec:
                raise VerificationError(
                    f"artifact manifest for producer stage "
                    f"{producer_stage_id!r} does not reference its resolved spec"
                )

            if verified_producer_manifest.artifact != resolved_producer_spec.output:
                raise VerificationError(
                    f"artifact manifest for producer stage "
                    f"{producer_stage_id!r} does not identify its output"
                )

            stage_inputs[input_name] = VerifiedInput(
                path=resolved_producer_spec.spec.output,
                artifact=verified_producer_manifest.artifact,
                content=verified_producer_manifest.content,
            )

        if stage_inputs:
            verified_inputs[consumer_stage_id] = stage_inputs

    return verified_inputs


def verify_artifact_manifest(
    reference: ResolvedArtifactManifestRef,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifiedArtifactManifest:
    manifest_raw = read_resolved_file(
        reference,
        fetcher=fetcher,
    )
    try:
        manifest = ArtifactManifest.model_validate(yaml.safe_load(manifest_raw))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError(
            "file is not a valid ArtifactManifest document"
        ) from exc
    artifact_raw = read_resolved_file(
        manifest.artifact,
        fetcher=fetcher,
    )
    spec_raw = read_resolved_file(
        manifest.spec,
        fetcher=fetcher,
    )
    resolved_spec_raw = read_resolved_file(
        manifest.resolved_spec,
        fetcher=fetcher,
    )
    read_resolved_file(
        manifest.source,
        fetcher=fetcher,
    )

    try:
        spec = SPEC_ADAPTER.validate_python(yaml.safe_load(spec_raw))
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError("manifest spec is not a valid stage spec") from exc

    try:
        resolved_spec = RESOLVED_SPEC_ADAPTER.validate_python(
            yaml.safe_load(resolved_spec_raw)
        )
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise VerificationError(
            "manifest resolved_spec is not a valid resolved stage spec"
        ) from exc

    if resolved_spec.spec != spec:
        raise VerificationError(
            "resolved spec does not embed the manifest's stage spec"
        )

    if resolved_spec.output != manifest.artifact:
        raise VerificationError("resolved spec output does not match manifest artifact")

    if resolved_spec.source != manifest.source:
        raise VerificationError(
            "resolved spec source does not match manifest source"
        )

    return VerifiedArtifactManifest(
        manifest=manifest,
        spec=spec,
        resolved_spec=resolved_spec,
        artifact=manifest.artifact,
        content=artifact_raw,
    )
