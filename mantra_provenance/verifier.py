"""Cross-file verification for MANTRA provenance records."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import yaml
from huggingface_hub import hf_hub_download
from pydantic import TypeAdapter, ValidationError

from .ids import StageId
from .models_v4 import (
    BaseSpec,
    ExperimentSpec,
    FutureInputRef,
    GitFileRef,
    HuggingFaceFileRef,
    InternalSpec,
    ResolvedFileRef,
    ResolvedRun,
    RunSpec,
    Spec,
    StorageModel,
    StoredInputRef,
    VariantSpec,
    repo_file_paths_overlap,
)

StorageFetcher = Callable[[StorageModel], bytes]
SPEC_ADAPTER = TypeAdapter(Spec)


class VerificationError(ValueError):
    """A referenced file could not be retrieved or failed verification."""


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
    *,
    fetcher: StorageFetcher | None = None,
) -> dict[StageId, BaseSpec]:
    """Load the run's authored stage specs and verify their dependency plan."""
    retrieve = fetch_storage_bytes if fetcher is None else fetcher
    loaded_stages: dict[StageId, BaseSpec] = {}

    for stage in run.stages:
        location = GitFileRef(
            repository=run.source.repository,
            commit=run.source.commit,
            path=stage.spec,
        )

        try:
            spec = SPEC_ADAPTER.validate_python(yaml.safe_load(retrieve(location)))
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
