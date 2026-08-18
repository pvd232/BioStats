from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

import yaml
from pydantic import TypeAdapter, ValidationError

from mantra_provenance.ids import HumanId, RunId
from mantra_provenance.models_v4 import (
    SHA256,
    ArtifactPointer,
    ArtifactPointerRef,
    BuildSpec,
    ExperimentSpec,
    FactorSpec,
    FutureInputRef,
    GitCommit,
    GitFileRef,
    GitSource,
    HuggingFaceFileRef,
    InternalInputRef,
    Measurement,
    ReplicateSpec,
    RemoteFileRef,
    RepoRelPath,
    ResolvedArtifactManifestRef,
    ResolvedArtifactPointerRef,
    ResolvedFileRef,
    ResolvedGitFileRef,
    ResolvedRun,
    ResolvedStageRef,
    RunAttempt,
    RunSpec,
    StorageRef,
    StoredInputRef,
    VariantSpec,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
GIT_A = "a" * 40
GIT_B = "b" * 40
REPOSITORY = "https://github.com/example/mantra"
HF_REPOSITORY = "example/mantra-artifacts"


def git_location(path: str = "inputs/models/current.pointer.yaml") -> dict:
    return {
        "kind": "git",
        "repository": REPOSITORY,
        "commit": GIT_A,
        "path": path,
    }


def hf_location(path: str = "artifacts/weights.pt") -> dict:
    return {
        "kind": "huggingface",
        "repository": HF_REPOSITORY,
        "commit": GIT_B,
        "path": path,
        "repo_type": "dataset",
    }


def manifest_reference() -> ResolvedArtifactManifestRef:
    return ResolvedArtifactManifestRef(
        kind="artifact_manifest",
        sha256=SHA_A,
        bytes=1024,
        stored_at=hf_location("artifacts/weights.pt.manifest.yaml"),
    )


def gce_environment() -> dict:
    return {
        "kind": "gce",
        "machine_image": {
            "project": "example-project",
            "name": "mantra-image",
        },
        "lockfile": git_location("uv.lock"),
    }


def relaxed_reproducibility() -> dict:
    return {
        "mode": "relaxed",
        "randomness": {
            "python_seed": 1,
            "numpy_seed": 1,
            "torch_seed": 1,
            "dataloader_seed": None,
        },
        "determinism": {
            "deterministic_algorithms": False,
            "deterministic_warn_only": False,
            "cudnn_deterministic": False,
            "cudnn_benchmark": True,
            "cublas_workspace_config": None,
        },
        "precision": {
            "float32_matmul_precision": "high",
            "cudnn_allow_tf32": True,
            "autocast_enabled": False,
            "autocast_dtype": None,
        },
    }


def stored_input(
    path: str,
    pointer_path: str = "inputs/data/current.pointer.yaml",
) -> dict:
    return {
        "kind": "stored",
        "pointer": git_location(pointer_path),
        "path": path,
    }


def build_spec(
    inputs: dict,
    *,
    script: str = "src/mantra/build.py",
    output: str = "artifacts/prior.pt",
) -> BuildSpec:
    return BuildSpec.model_validate(
        {
            "kind": "build",
            "inputs": inputs,
            "script": script,
            "environment": gce_environment(),
            "reproducibility": relaxed_reproducibility(),
            "output": output,
            "params": {},
        }
    )


class PrimitiveValidationTests(unittest.TestCase):
    def test_repository_relative_path_accepts_normalized_posix_path(self) -> None:
        adapter = TypeAdapter(RepoRelPath)
        self.assertEqual(
            adapter.validate_python("artifacts/models/weights.pt"),
            "artifacts/models/weights.pt",
        )

    def test_repository_relative_path_rejects_invalid_paths(self) -> None:
        adapter = TypeAdapter(RepoRelPath)
        invalid_paths = (
            "",
            "/absolute/path",
            "C:/windows/path",
            "artifacts\\weights.pt",
            "artifacts//weights.pt",
            "artifacts/./weights.pt",
            "artifacts/../weights.pt",
        )

        for path in invalid_paths:
            with self.subTest(path=path), self.assertRaises(ValidationError):
                adapter.validate_python(path)

    def test_sha256_rejects_wrong_length_case_and_alphabet(self) -> None:
        adapter = TypeAdapter(SHA256)
        invalid_hashes = (
            "a" * 63,
            "a" * 65,
            "A" * 64,
            "g" * 64,
        )

        for value in invalid_hashes:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                adapter.validate_python(value)

    def test_git_commit_accepts_full_sha1_and_sha256(self) -> None:
        adapter = TypeAdapter(GitCommit)
        self.assertEqual(adapter.validate_python("a" * 40), "a" * 40)
        self.assertEqual(adapter.validate_python("b" * 64), "b" * 64)

    def test_git_commit_rejects_mutable_or_malformed_values(self) -> None:
        adapter = TypeAdapter(GitCommit)
        invalid_commits = ("main", "a" * 39, "a" * 41, "G" * 40)

        for value in invalid_commits:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                adapter.validate_python(value)

    def test_human_id_accepts_lowercase_snake_case(self) -> None:
        adapter = TypeAdapter(HumanId)
        self.assertEqual(adapter.validate_python("low_rank_32"), "low_rank_32")

    def test_human_id_rejects_invalid_forms(self) -> None:
        adapter = TypeAdapter(HumanId)
        invalid_ids = (
            "",
            "Low_rank_32",
            "low rank 32",
            "low-rank-32",
            "low/rank/32",
            "32_low_rank",
        )

        for value in invalid_ids:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                adapter.validate_python(value)

    def test_run_id_accepts_ulid_and_rejects_invalid_forms(self) -> None:
        adapter = TypeAdapter(RunId)
        valid = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        self.assertEqual(adapter.validate_python(valid), valid)

        for value in (valid.lower(), valid[:-1], "0IARZ3NDEKTSV4RRFFQ69G5FAV"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                adapter.validate_python(value)


class FileReferenceTests(unittest.TestCase):
    def test_storage_union_discriminates_git_and_hugging_face(self) -> None:
        adapter = TypeAdapter(StorageRef)

        git = adapter.validate_python(git_location())
        huggingface = adapter.validate_python(hf_location())

        self.assertIsInstance(git, GitFileRef)
        self.assertIsInstance(huggingface, HuggingFaceFileRef)

    def test_storage_union_rejects_unknown_kind(self) -> None:
        payload = git_location()
        payload["kind"] = "s3"

        with self.assertRaises(ValidationError):
            TypeAdapter(StorageRef).validate_python(payload)

    def test_resolved_artifact_pointer_requires_git_storage(self) -> None:
        valid = ResolvedArtifactPointerRef(
            kind="artifact_pointer",
            sha256=SHA_A,
            bytes=512,
            stored_at=git_location(),
        )
        self.assertIsInstance(valid.stored_at, ArtifactPointerRef)

        with self.assertRaises(ValidationError):
            ResolvedArtifactPointerRef(
                kind="artifact_pointer",
                sha256=SHA_A,
                bytes=512,
                stored_at=hf_location("inputs/models/current.pointer.yaml"),
            )

    def test_artifact_pointer_requires_manifest_reference(self) -> None:
        pointer = ArtifactPointer(manifest=manifest_reference())
        self.assertIsInstance(pointer.manifest, ResolvedArtifactManifestRef)

        invalid_manifest = manifest_reference().model_dump(mode="json")
        invalid_manifest["kind"] = "artifact_pointer"

        with self.assertRaises(ValidationError):
            ArtifactPointer.model_validate({"manifest": invalid_manifest})

    def test_artifact_pointer_rejects_obsolete_artifact_field(self) -> None:
        payload = {
            "manifest": manifest_reference().model_dump(mode="json"),
            "artifact": {
                "sha256": SHA_B,
                "bytes": 2048,
                "stored_at": hf_location(),
            },
        }

        with self.assertRaises(ValidationError):
            ArtifactPointer.model_validate(payload)

    def test_reference_models_round_trip_through_json_and_yaml(self) -> None:
        models = (
            RemoteFileRef(url="https://example.com/raw/data.csv"),
            GitFileRef(**git_location("specs/train.spec.yaml")),
            ArtifactPointerRef(**git_location()),
            HuggingFaceFileRef(**hf_location()),
            ResolvedFileRef(
                sha256=SHA_A,
                bytes=2048,
                stored_at=hf_location(),
            ),
            ResolvedGitFileRef(
                sha256=SHA_A,
                bytes=4096,
                stored_at=git_location("src/mantra/train.py"),
            ),
            manifest_reference(),
            ResolvedArtifactPointerRef(
                kind="artifact_pointer",
                sha256=SHA_B,
                bytes=512,
                stored_at=git_location(),
            ),
            ArtifactPointer(manifest=manifest_reference()),
        )

        for model in models:
            with self.subTest(model=type(model).__name__):
                from_json = type(model).model_validate_json(model.model_dump_json())
                self.assertEqual(from_json, model)

                dumped = yaml.safe_dump(
                    model.model_dump(mode="json"),
                    sort_keys=False,
                )
                from_yaml = type(model).model_validate(yaml.safe_load(dumped))
                self.assertEqual(from_yaml, model)


class MetricAndMeasurementTests(unittest.TestCase):
    def test_measurement_accepts_finite_value_and_optional_position(self) -> None:
        measurement = Measurement(
            run_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            attempt_id=1,
            stage_id="train",
            metric_id="mean_squared_error",
            value=0.184,
            measured_at=datetime(2026, 8, 14, 8, 30, tzinfo=UTC),
            epoch=4,
            step=100,
        )

        self.assertEqual(measurement.value, 0.184)
        self.assertEqual(measurement.epoch, 4)
        self.assertEqual(measurement.step, 100)

    def test_measurement_rejects_nonfinite_values(self) -> None:
        common = {
            "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "attempt_id": 1,
            "stage_id": "train",
            "metric_id": "mean_squared_error",
            "measured_at": datetime(2026, 8, 14, 8, 30, tzinfo=UTC),
        }

        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                Measurement(value=value, **common)

    def test_measurement_rejects_invalid_attempt_epoch_and_step(self) -> None:
        common = {
            "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "attempt_id": 1,
            "stage_id": "train",
            "metric_id": "mean_squared_error",
            "value": 0.184,
            "measured_at": datetime(2026, 8, 14, 8, 30, tzinfo=UTC),
        }

        for field, value in (("attempt_id", 0), ("epoch", -1), ("step", -1)):
            payload = common | {field: value}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Measurement(**payload)

    def test_measurement_round_trips_through_json_and_yaml(self) -> None:
        measurement = Measurement(
            run_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            attempt_id=1,
            stage_id="train",
            metric_id="pearson_correlation",
            value=0.91,
            measured_at=datetime(2026, 8, 14, 8, 30, tzinfo=UTC),
        )

        from_json = Measurement.model_validate_json(measurement.model_dump_json())
        self.assertEqual(from_json, measurement)

        dumped = yaml.safe_dump(
            measurement.model_dump(mode="json"),
            sort_keys=False,
        )
        from_yaml = Measurement.model_validate(yaml.safe_load(dumped))
        self.assertEqual(from_yaml, measurement)


class ExperimentAndVariantTests(unittest.TestCase):
    def test_experiment_and_variant_accept_selected_factor_assembly(self) -> None:
        experiment = ExperimentSpec(
            experiment_id="e001_low_rank",
            factors=(
                FactorSpec(
                    factor_id="aggregation",
                    levels=("dense", "low_rank"),
                ),
                FactorSpec(
                    factor_id="rank",
                    levels=("not_applicable", "rank_32", "rank_64"),
                ),
            ),
            variant_ids=("baseline", "low_rank_32"),
            replicates=(
                ReplicateSpec(replicate_id="replicate_01", seed=42),
                ReplicateSpec(replicate_id="replicate_02", seed=93),
            ),
            metric_ids=("mean_squared_error", "pearson_correlation"),
        )
        variant = VariantSpec(
            experiment_id="e001_low_rank",
            variant_id="low_rank_32",
            levels={
                "aggregation": "low_rank",
                "rank": "rank_32",
            },
        )

        self.assertIn(variant.variant_id, experiment.variant_ids)
        self.assertEqual(variant.levels["rank"], "rank_32")

    def test_experiment_rejects_duplicate_factor_ids(self) -> None:
        with self.assertRaises(ValidationError):
            ExperimentSpec(
                experiment_id="e001_low_rank",
                factors=(
                    FactorSpec(factor_id="rank", levels=("rank_32", "rank_64")),
                    FactorSpec(factor_id="rank", levels=("small", "large")),
                ),
                variant_ids=("low_rank_32",),
                replicates=(ReplicateSpec(replicate_id="replicate_01", seed=42),),
                metric_ids=("mean_squared_error",),
            )

    def test_experiment_rejects_duplicate_variant_replicate_and_metric_ids(
        self,
    ) -> None:
        base = {
            "experiment_id": "e001_low_rank",
            "factors": (
                FactorSpec(factor_id="rank", levels=("rank_32", "rank_64")),
            ),
            "variant_ids": ("low_rank_32",),
            "replicates": (
                ReplicateSpec(replicate_id="replicate_01", seed=42),
            ),
            "metric_ids": ("mean_squared_error",),
        }
        duplicates = {
            "variant_ids": ("low_rank_32", "low_rank_32"),
            "replicates": (
                ReplicateSpec(replicate_id="replicate_01", seed=42),
                ReplicateSpec(replicate_id="replicate_01", seed=93),
            ),
            "metric_ids": ("mean_squared_error", "mean_squared_error"),
        }

        for field, value in duplicates.items():
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ExperimentSpec(**(base | {field: value}))

class RunAndAttemptTests(unittest.TestCase):
    RUN_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"

    @staticmethod
    def run_spec(**updates) -> RunSpec:
        payload = {
            "run_id": RunAndAttemptTests.RUN_ID,
            "experiment_id": "e001_low_rank",
            "variant_id": "low_rank_32",
            "replicate_id": "replicate_01",
            "seed": 42,
            "source": GitSource(
                repository=REPOSITORY,
                commit=GIT_A,
            ),
            "stages": (
                {
                    "stage_id": "embed",
                    "spec": "stages/embed.spec.yaml",
                    "sha256": SHA_A,
                    "bytes": 1024,
                },
                {
                    "stage_id": "train",
                    "spec": "stages/train.spec.yaml",
                    "sha256": SHA_B,
                    "bytes": 2048,
                },
            ),
        }
        return RunSpec.model_validate(payload | updates)

    @staticmethod
    def resolved_stage(
        stage_id: str,
        path: str | None = None,
    ) -> ResolvedStageRef:
        resolved_path = path or f"stages/{stage_id}.spec.resolved.yaml"
        return ResolvedStageRef(
            stage_id=stage_id,
            resolved_spec=ResolvedFileRef(
                sha256=SHA_A,
                bytes=1024,
                stored_at=hf_location(resolved_path),
            ),
        )

    @staticmethod
    def attempt(**updates) -> RunAttempt:
        started_at = datetime(2026, 8, 14, 8, 30, tzinfo=UTC)
        payload = {
            "attempt_id": 1,
            "status": "succeeded",
            "started_at": started_at,
            "completed_at": started_at + timedelta(seconds=1),
            "resolved_stages": (
                RunAndAttemptTests.resolved_stage("embed"),
                RunAndAttemptTests.resolved_stage("train"),
            ),
            "artifact_manifests": (),
            "measurement_files": (),
            "log_files": (),
            "failure_reason": None,
        }
        return RunAttempt.model_validate(payload | updates)

    def test_run_accepts_ordered_nonempty_stage_plan(self) -> None:
        run = self.run_spec()
        self.assertEqual(tuple(stage.stage_id for stage in run.stages), ("embed", "train"))

    def test_run_rejects_empty_stage_plan(self) -> None:
        with self.assertRaises(ValidationError):
            self.run_spec(stages=())

    def test_run_rejects_duplicate_stage_ids(self) -> None:
        with self.assertRaises(ValidationError):
            self.run_spec(
                stages=(
                    {
                        "stage_id": "train",
                        "spec": "stages/train_a.spec.yaml",
                        "sha256": SHA_A,
                        "bytes": 1024,
                    },
                    {
                        "stage_id": "train",
                        "spec": "stages/train_b.spec.yaml",
                        "sha256": SHA_B,
                        "bytes": 2048,
                    },
                )
            )

    def test_run_rejects_duplicate_stage_spec_paths(self) -> None:
        with self.assertRaises(ValidationError):
            self.run_spec(
                stages=(
                    {
                        "stage_id": "embed",
                        "spec": "stages/shared.spec.yaml",
                        "sha256": SHA_A,
                        "bytes": 1024,
                    },
                    {
                        "stage_id": "train",
                        "spec": "stages/shared.spec.yaml",
                        "sha256": SHA_B,
                        "bytes": 2048,
                    },
                )
            )

    def test_attempt_accepts_success_and_failure_terminal_states(self) -> None:
        succeeded = self.attempt()
        failed = self.attempt(status="failed", failure_reason="process exited")

        self.assertEqual(succeeded.status, "succeeded")
        self.assertEqual(failed.failure_reason, "process exited")

    def test_successful_attempt_rejects_failure_reason(self) -> None:
        with self.assertRaises(ValidationError):
            self.attempt(failure_reason="unexpected reason")

    def test_unsuccessful_attempt_requires_nonempty_failure_reason(self) -> None:
        for status in ("failed", "preempted", "cancelled"):
            for reason in (None, "", "   "):
                with (
                    self.subTest(status=status, reason=reason),
                    self.assertRaises(ValidationError),
                ):
                    self.attempt(status=status, failure_reason=reason)

    def test_attempt_rejects_completion_before_start(self) -> None:
        started_at = datetime(2026, 8, 14, 8, 30, tzinfo=UTC)
        with self.assertRaises(ValidationError):
            self.attempt(
                started_at=started_at,
                completed_at=started_at - timedelta(seconds=1),
            )

    def test_attempt_rejects_duplicate_resolved_stage_ids(self) -> None:
        with self.assertRaises(ValidationError):
            self.attempt(
                resolved_stages=(
                    self.resolved_stage("train", "stages/train_a.resolved.yaml"),
                    self.resolved_stage("train", "stages/train_b.resolved.yaml"),
                )
            )

    def test_run_and_attempt_round_trip_through_json(self) -> None:
        run = self.run_spec()
        attempt = self.attempt()

        self.assertEqual(RunSpec.model_validate_json(run.model_dump_json()), run)
        self.assertEqual(
            RunAttempt.model_validate_json(attempt.model_dump_json()),
            attempt,
        )

    def test_resolved_run_accepts_one_successful_attempt(self) -> None:
        run = self.run_spec()
        attempt = self.attempt()
        resolved = ResolvedRun(
            run=run,
            run_file=ResolvedFileRef(
                sha256=SHA_A,
                bytes=1024,
                stored_at=hf_location("runs/run.yaml"),
            ),
            status="succeeded",
            attempts=(attempt,),
            successful_attempt_id=attempt.attempt_id,
            completed_at=attempt.completed_at,
        )

        self.assertEqual(resolved.successful_attempt_id, 1)

    def test_successful_attempt_must_complete_run_stages_in_order(self) -> None:
        attempt = self.attempt(
            resolved_stages=(
                self.resolved_stage("train"),
                self.resolved_stage("embed"),
            )
        )

        with self.assertRaisesRegex(ValidationError, "declared stage order"):
            ResolvedRun(
                run=self.run_spec(),
                run_file=ResolvedFileRef(
                    sha256=SHA_A,
                    bytes=1024,
                    stored_at=hf_location("runs/run.yaml"),
                ),
                status="succeeded",
                attempts=(attempt,),
                successful_attempt_id=attempt.attempt_id,
                completed_at=attempt.completed_at,
            )

    def test_unsuccessful_attempt_may_retain_resolved_stage_references(self) -> None:
        attempt = self.attempt(
            status="failed",
            resolved_stages=(self.resolved_stage("embed"),),
            failure_reason="training failed",
        )
        resolved = ResolvedRun(
            run=self.run_spec(),
            run_file=ResolvedFileRef(
                sha256=SHA_A,
                bytes=1024,
                stored_at=hf_location("runs/run.yaml"),
            ),
            status="failed",
            attempts=(attempt,),
            successful_attempt_id=None,
            completed_at=attempt.completed_at,
        )

        self.assertEqual(resolved.attempts[0].resolved_stages[0].stage_id, "embed")

    def test_unsuccessful_attempt_stages_must_be_a_run_prefix(self) -> None:
        attempt = self.attempt(
            status="failed",
            resolved_stages=(self.resolved_stage("train"),),
            failure_reason="embedding failed",
        )

        with self.assertRaisesRegex(ValidationError, "declared stage order"):
            ResolvedRun(
                run=self.run_spec(),
                run_file=ResolvedFileRef(
                    sha256=SHA_A,
                    bytes=1024,
                    stored_at=hf_location("runs/run.yaml"),
                ),
                status="failed",
                attempts=(attempt,),
                successful_attempt_id=None,
                completed_at=attempt.completed_at,
            )

    def test_no_attempt_may_follow_a_successful_attempt(self) -> None:
        succeeded = self.attempt()
        failed = self.attempt(
            attempt_id=2,
            status="failed",
            started_at=succeeded.completed_at,
            completed_at=succeeded.completed_at + timedelta(seconds=1),
            failure_reason="unexpected retry",
        )

        with self.assertRaisesRegex(ValidationError, "after a successful attempt"):
            ResolvedRun(
                run=self.run_spec(),
                run_file=ResolvedFileRef(
                    sha256=SHA_A,
                    bytes=1024,
                    stored_at=hf_location("runs/run.yaml"),
                ),
                status="succeeded",
                attempts=(succeeded, failed),
                successful_attempt_id=succeeded.attempt_id,
                completed_at=failed.completed_at,
            )

    def test_attempt_ids_must_increase_in_execution_order(self) -> None:
        first = self.attempt(
            attempt_id=2,
            status="failed",
            resolved_stages=(),
            failure_reason="preparation failed",
        )
        second = self.attempt(
            attempt_id=1,
            started_at=first.completed_at,
            completed_at=first.completed_at + timedelta(seconds=1),
        )

        with self.assertRaisesRegex(ValidationError, "must increase"):
            ResolvedRun(
                run=self.run_spec(),
                run_file=ResolvedFileRef(
                    sha256=SHA_A,
                    bytes=1024,
                    stored_at=hf_location("runs/run.yaml"),
                ),
                status="succeeded",
                attempts=(first, second),
                successful_attempt_id=second.attempt_id,
                completed_at=second.completed_at,
            )

    def test_attempts_must_not_overlap(self) -> None:
        first = self.attempt(
            status="failed",
            resolved_stages=(),
            failure_reason="preparation failed",
        )
        second = self.attempt(
            attempt_id=2,
            started_at=first.completed_at - timedelta(milliseconds=1),
            completed_at=first.completed_at + timedelta(seconds=1),
        )

        with self.assertRaisesRegex(ValidationError, "previous attempt finishes"):
            ResolvedRun(
                run=self.run_spec(),
                run_file=ResolvedFileRef(
                    sha256=SHA_A,
                    bytes=1024,
                    stored_at=hf_location("runs/run.yaml"),
                ),
                status="succeeded",
                attempts=(first, second),
                successful_attempt_id=second.attempt_id,
                completed_at=second.completed_at,
            )

    def test_resolved_run_cannot_complete_before_an_attempt(self) -> None:
        attempt = self.attempt()

        with self.assertRaisesRegex(ValidationError, "cannot complete before"):
            ResolvedRun(
                run=self.run_spec(),
                run_file=ResolvedFileRef(
                    sha256=SHA_A,
                    bytes=1024,
                    stored_at=hf_location("runs/run.yaml"),
                ),
                status="succeeded",
                attempts=(attempt,),
                successful_attempt_id=attempt.attempt_id,
                completed_at=attempt.completed_at - timedelta(milliseconds=1),
            )


class InternalInputValidationTests(unittest.TestCase):
    def test_internal_input_union_discriminates_stored_and_future(self) -> None:
        adapter = TypeAdapter(InternalInputRef)

        stored = adapter.validate_python(stored_input("workspace/data.csv"))
        future = adapter.validate_python(
            {
                "kind": "future",
                "producer_stage_id": "embed",
            }
        )

        self.assertIsInstance(stored, StoredInputRef)
        self.assertIsInstance(future, FutureInputRef)

    def test_future_input_rejects_redundant_path(self) -> None:
        with self.assertRaises(ValidationError):
            TypeAdapter(InternalInputRef).validate_python(
                {
                    "kind": "future",
                    "producer_stage_id": "embed",
                    "path": "artifacts/embedding.pt",
                }
            )

    def test_build_spec_accepts_distinct_stored_and_future_inputs(self) -> None:
        spec = build_spec(
            {
                "dataset": stored_input("workspace/data.csv"),
                "embedding": {
                    "kind": "future",
                    "producer_stage_id": "embed",
                },
            }
        )

        self.assertEqual(spec.inputs["dataset"].path, "workspace/data.csv")
        self.assertEqual(spec.inputs["embedding"].producer_stage_id, "embed")

    def test_duplicate_stored_materialization_paths_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "materialization paths.*collide",
        ):
            build_spec(
                {
                    "dataset": stored_input(
                        "workspace/shared.bin",
                        "inputs/data/dataset.pointer.yaml",
                    ),
                    "weights": stored_input(
                        "workspace/shared.bin",
                        "inputs/models/weights.pointer.yaml",
                    ),
                }
            )

    def test_stored_input_cannot_overwrite_stage_script(self) -> None:
        with self.assertRaisesRegex(ValidationError, "collides with the stage script"):
            build_spec(
                {"dataset": stored_input("src/mantra/build.py")},
            )

    def test_stage_output_cannot_overwrite_stored_input(self) -> None:
        with self.assertRaisesRegex(ValidationError, "collides with input"):
            build_spec(
                {"dataset": stored_input("artifacts/prior.pt")},
            )

    def test_stage_output_cannot_overwrite_stage_script(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "collides with the stage script",
        ):
            build_spec(
                {"dataset": stored_input("workspace/data.csv")},
                output="src/mantra/build.py",
            )

    def test_remote_pointer_path_is_not_a_local_path_collision(self) -> None:
        shared_spelling = "inputs/data/current.pointer.yaml"
        spec = build_spec(
            {
                "dataset": stored_input(
                    shared_spelling,
                    pointer_path=shared_spelling,
                )
            }
        )

        self.assertEqual(spec.inputs["dataset"].path, shared_spelling)
        self.assertEqual(spec.inputs["dataset"].pointer.path, shared_spelling)

    def test_nested_file_paths_are_rejected_as_collisions(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "materialization paths.*collide",
        ):
            build_spec(
                {
                    "dataset": stored_input(
                        "workspace/data.bin",
                        "inputs/data/dataset.pointer.yaml",
                    ),
                    "weights": stored_input(
                        "workspace/data.bin/weights.pt",
                        "inputs/models/weights.pointer.yaml",
                    ),
                }
            )


if __name__ == "__main__":
    unittest.main()
