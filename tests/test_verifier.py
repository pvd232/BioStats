from __future__ import annotations

import hashlib
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import yaml
from pydantic import HttpUrl, TypeAdapter

from mantra_provenance.models_v4 import (
    ArtifactManifest,
    ArtifactPointer,
    ArtifactPointerRef,
    DownloadSpec,
    GitFileRef,
    GitSource,
    HuggingFaceFileRef,
    ResolvedArtifactManifestRef,
    ResolvedArtifactPointerRef,
    ResolvedBaseSpec,
    ResolvedBuildSpec,
    ResolvedDownloadSpec,
    ResolvedFileRef,
    ResolvedGitFileRef,
    ResolvedRun,
    ResolvedStageRef,
    ResolvedStoredInputRef,
    RunAttempt,
    RunSpec,
    RunStageRef,
)
from mantra_provenance.verifier import (
    VerificationError,
    fetch_storage_bytes,
    read_resolved_file,
    verify_artifact_manifest,
    verify_stage_plan,
    verify_experiment_and_variant,
    verify_future_inputs,
    verify_resolved_run_file,
    verify_resolved_stages,
    verify_stored_inputs,
)

GIT_COMMIT = "a" * 40
PLAN_COMMIT = "b" * 40
REPOSITORY = HttpUrl("https://example.com/mantra.git")
PLAN_REPOSITORY = HttpUrl("https://example.com/mantra-run-plans.git")
YAML_VALUE_ADAPTER = TypeAdapter(Any)


def yaml_bytes(value: object) -> bytes:
    serializable = YAML_VALUE_ADAPTER.dump_python(value, mode="json")
    dumped = yaml.safe_dump(serializable, sort_keys=True)

    if not isinstance(dumped, str):
        raise TypeError("expected yaml.safe_dump to return text")

    return dumped.encode("utf-8")


def run_spec(*, seed: int = 42) -> RunSpec:
    return RunSpec(
        run_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        experiment_id="e001_low_rank",
        variant_id="low_rank_32",
        replicate_id="replicate_01",
        seed=seed,
        source=GitSource(repository=REPOSITORY, commit=GIT_COMMIT),
        stages=(
            RunStageRef(
                stage_id="embed",
                spec="stages/embed.spec.yaml",
                sha256="c" * 64,
                bytes=100,
            ),
            RunStageRef(
                stage_id="train",
                spec="stages/train.spec.yaml",
                sha256="d" * 64,
                bytes=200,
            ),
        ),
    )


def resolved_reference(raw: bytes) -> ResolvedFileRef:
    return ResolvedFileRef(
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
        stored_at=GitFileRef(
            repository=REPOSITORY,
            commit=GIT_COMMIT,
            path="runs/01JABC.run.yaml",
        ),
    )


def resolved_run(run: RunSpec, run_file: ResolvedFileRef) -> ResolvedRun:
    # Isolate this external cross-file check from ResolvedRun's local
    # validation logic.
    return ResolvedRun.model_construct(
        schema_version=1,
        run=run,
        run_file=run_file,
        status="failed",
        attempts=(),
        successful_attempt_id=None,
        completed_at=datetime(2026, 8, 17, tzinfo=UTC),
    )


class ResolvedFileVerificationTests(unittest.TestCase):
    def test_read_resolved_file_accepts_matching_bytes(self) -> None:
        raw = b"exact file bytes"
        reference = resolved_reference(raw)

        self.assertEqual(
            read_resolved_file(reference, fetcher=lambda _: raw),
            raw,
        )

    def test_read_resolved_file_rejects_byte_count_mismatch(self) -> None:
        raw = b"exact file bytes"
        reference = resolved_reference(raw)
        mismatched = reference.model_copy(update={"bytes": len(raw) + 1})

        with self.assertRaisesRegex(VerificationError, "byte-count mismatch"):
            read_resolved_file(mismatched, fetcher=lambda _: raw)

    def test_read_resolved_file_rejects_sha256_mismatch(self) -> None:
        raw = b"exact file bytes"
        reference = resolved_reference(raw)
        mismatched = reference.model_copy(update={"sha256": "b" * 64})

        with self.assertRaisesRegex(VerificationError, "SHA-256 mismatch"):
            read_resolved_file(mismatched, fetcher=lambda _: raw)

    def test_storage_dispatches_git_and_huggingface_references(self) -> None:
        git = GitFileRef(
            repository=REPOSITORY,
            commit=GIT_COMMIT,
            path="run.yaml",
        )
        huggingface = HuggingFaceFileRef(
            repository="machina/mantra-artifacts",
            commit=GIT_COMMIT,
            path="run.yaml",
            repo_type="dataset",
        )

        with patch(
            "mantra_provenance.verifier.fetch_git_file_bytes",
            return_value=b"git",
        ) as git_fetch:
            self.assertEqual(fetch_storage_bytes(git), b"git")
            git_fetch.assert_called_once_with(git)

        with patch(
            "mantra_provenance.verifier.fetch_huggingface_file_bytes",
            return_value=b"huggingface",
        ) as huggingface_fetch:
            self.assertEqual(fetch_storage_bytes(huggingface), b"huggingface")
            huggingface_fetch.assert_called_once_with(huggingface)

    def test_resolved_git_file_uses_the_common_verified_file_loader(self) -> None:
        raw = b"exact Git-hosted file bytes"
        reference = ResolvedGitFileRef(
            sha256=hashlib.sha256(raw).hexdigest(),
            bytes=len(raw),
            stored_at=GitFileRef(
                repository=REPOSITORY,
                commit=GIT_COMMIT,
                path="src/mantra/train.py",
            ),
        )

        self.assertEqual(read_resolved_file(reference, fetcher=lambda _: raw), raw)


class ResolvedRunFileVerificationTests(unittest.TestCase):
    def test_run_file_must_equal_embedded_run(self) -> None:
        embedded = run_spec(seed=42)
        raw = yaml_bytes(
            embedded.model_dump(mode="json"),
        )
        record = resolved_run(embedded, resolved_reference(raw))

        self.assertEqual(
            verify_resolved_run_file(record, fetcher=lambda _: raw),
            embedded,
        )

    def test_run_file_rejects_different_valid_run(self) -> None:
        embedded = run_spec(seed=42)
        file_run = run_spec(seed=93)
        raw = yaml_bytes(file_run.model_dump(mode="json"))
        record = resolved_run(embedded, resolved_reference(raw))

        with self.assertRaisesRegex(
            VerificationError,
            "does not match the RunSpec embedded in ResolvedRun",
        ):
            verify_resolved_run_file(record, fetcher=lambda _: raw)

    def test_run_file_rejects_invalid_run_document(self) -> None:
        embedded = run_spec()
        raw = b"not: [valid"
        record = resolved_run(embedded, resolved_reference(raw))

        with self.assertRaisesRegex(VerificationError, "not a valid RunSpec"):
            verify_resolved_run_file(record, fetcher=lambda _: raw)


class ExperimentAndVariantVerificationTests(unittest.TestCase):
    @staticmethod
    def documents(
        *,
        experiment_updates: dict | None = None,
        variant_updates: dict | None = None,
    ) -> dict[str, bytes]:
        experiment = {
            "schema_version": 1,
            "experiment_id": "e001_low_rank",
            "factors": [
                {
                    "factor_id": "rank",
                    "levels": ["rank_32", "rank_64"],
                },
                {
                    "factor_id": "optimizer",
                    "levels": ["adam", "adamw"],
                },
            ],
            "variant_ids": ["low_rank_32"],
            "replicates": [
                {"replicate_id": "replicate_01", "seed": 42},
            ],
            "metric_ids": ["mean_squared_error"],
        }
        variant = {
            "schema_version": 1,
            "experiment_id": "e001_low_rank",
            "variant_id": "low_rank_32",
            "levels": {
                "rank": "rank_32",
                "optimizer": "adamw",
            },
        }

        if experiment_updates:
            experiment.update(experiment_updates)
        if variant_updates:
            variant.update(variant_updates)

        root = "experiments/e001_low_rank"
        return {
            f"{root}/e001_low_rank.experiment.yaml": yaml_bytes(experiment),
            f"{root}/variants/low_rank_32.variant.yaml": yaml_bytes(variant),
        }

    @staticmethod
    def fetcher(documents: dict[str, bytes]):
        def retrieve(location):
            return documents[location.path]

        return retrieve

    def test_valid_experiment_and_variant_are_returned(self) -> None:
        run = run_spec()
        documents = self.documents()

        experiment, variant = verify_experiment_and_variant(
            run,
            fetcher=self.fetcher(documents),
        )

        self.assertEqual(experiment.experiment_id, run.experiment_id)
        self.assertEqual(variant.variant_id, run.variant_id)

    def test_deterministic_experiment_and_variant_paths_are_used(self) -> None:
        requested_paths = []
        documents = self.documents()

        def fetcher(location):
            requested_paths.append(location.path)
            return documents[location.path]

        verify_experiment_and_variant(run_spec(), fetcher=fetcher)

        self.assertEqual(
            requested_paths,
            [
                "experiments/e001_low_rank/e001_low_rank.experiment.yaml",
                "experiments/e001_low_rank/variants/low_rank_32.variant.yaml",
            ],
        )

    def test_run_variant_must_be_declared_by_experiment(self) -> None:
        documents = self.documents(experiment_updates={"variant_ids": ["baseline"]})

        with self.assertRaisesRegex(VerificationError, "not declared"):
            verify_experiment_and_variant(
                run_spec(),
                fetcher=self.fetcher(documents),
            )

    def test_variant_must_assign_every_factor_once(self) -> None:
        documents = self.documents(variant_updates={"levels": {"rank": "rank_32"}})

        with self.assertRaisesRegex(VerificationError, "exactly one level"):
            verify_experiment_and_variant(
                run_spec(),
                fetcher=self.fetcher(documents),
            )

    def test_variant_levels_must_be_permitted(self) -> None:
        documents = self.documents(
            variant_updates={"levels": {"rank": "rank_128", "optimizer": "adamw"}}
        )

        with self.assertRaisesRegex(VerificationError, "is not permitted"):
            verify_experiment_and_variant(
                run_spec(),
                fetcher=self.fetcher(documents),
            )

    def test_run_replicate_and_seed_must_match_experiment(self) -> None:
        documents = self.documents()

        with self.assertRaisesRegex(VerificationError, "seed does not match"):
            verify_experiment_and_variant(
                run_spec(seed=93),
                fetcher=self.fetcher(documents),
            )


class StagePlanVerificationTests(unittest.TestCase):
    @staticmethod
    def environment() -> dict:
        return {
            "kind": "gce",
            "machine_image": {
                "project": "example-project",
                "name": "mantra-image",
            },
            "lockfile": {
                "kind": "git",
                "repository": REPOSITORY,
                "commit": GIT_COMMIT,
                "path": "uv.lock",
            },
        }

    @staticmethod
    def reproducibility() -> dict:
        return {
            "mode": "relaxed",
            "randomness": {
                "python_seed": 42,
                "numpy_seed": 42,
                "torch_seed": 42,
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

    @classmethod
    def stage_documents(
        cls,
        *,
        embed_output: str = "artifacts/embedding.pt",
        train_output: str = "artifacts/weights.pt",
        train_script: str = "src/mantra/train.py",
        future_producer: str = "embed",
        stored_path: str = "workspace/data.csv",
    ) -> dict[str, bytes]:
        common = {
            "schema_version": 1,
            "environment": cls.environment(),
            "reproducibility": cls.reproducibility(),
        }
        embed = common | {
            "kind": "embed",
            "inputs": {
                "dataset": {
                    "kind": "stored",
                    "pointer": {
                        "kind": "git",
                        "repository": REPOSITORY,
                        "commit": GIT_COMMIT,
                        "path": "inputs/data/current.pointer.yaml",
                    },
                    "path": "workspace/embed-data.csv",
                }
            },
            "script": "src/mantra/embed.py",
            "output": embed_output,
            "params": {},
        }
        train = common | {
            "kind": "train",
            "inputs": {
                "embedding": {
                    "kind": "future",
                    "producer_stage_id": future_producer,
                },
                "dataset": {
                    "kind": "stored",
                    "pointer": {
                        "kind": "git",
                        "repository": REPOSITORY,
                        "commit": GIT_COMMIT,
                        "path": "inputs/data/current.pointer.yaml",
                    },
                    "path": stored_path,
                },
            },
            "script": train_script,
            "output": train_output,
            "params": {
                "epochs": 1,
                "batch_size": 2,
                "learning_rate": 0.001,
            },
        }

        return {
            "stages/embed.spec.yaml": yaml_bytes(embed),
            "stages/train.spec.yaml": yaml_bytes(train),
        }

    @staticmethod
    def fetcher(documents: dict[str, bytes]):
        def retrieve(location):
            return documents[location.path]

        return retrieve

    @staticmethod
    def run_and_plan_file(
        documents: dict[str, bytes],
    ) -> tuple[RunSpec, ResolvedFileRef]:
        base = run_spec().model_dump(mode="json")
        base["stages"] = [
            {
                "stage_id": "embed",
                "spec": "stages/embed.spec.yaml",
                "sha256": hashlib.sha256(
                    documents["stages/embed.spec.yaml"]
                ).hexdigest(),
                "bytes": len(documents["stages/embed.spec.yaml"]),
            },
            {
                "stage_id": "train",
                "spec": "stages/train.spec.yaml",
                "sha256": hashlib.sha256(
                    documents["stages/train.spec.yaml"]
                ).hexdigest(),
                "bytes": len(documents["stages/train.spec.yaml"]),
            },
        ]
        run = RunSpec.model_validate(base)
        plan_bytes = b"run-plan snapshot anchor"
        run_file = ResolvedFileRef(
            sha256=hashlib.sha256(plan_bytes).hexdigest(),
            bytes=len(plan_bytes),
            stored_at=GitFileRef(
                repository=PLAN_REPOSITORY,
                commit=PLAN_COMMIT,
                path="runs/01JABC.run.yaml",
            ),
        )
        return run, run_file

    def test_valid_stage_plan_is_returned_in_run_order(self) -> None:
        documents = self.stage_documents()
        run, run_file = self.run_and_plan_file(documents)
        stages = verify_stage_plan(
            run,
            run_file,
            fetcher=self.fetcher(documents),
        )

        self.assertEqual(tuple(stages), ("embed", "train"))
        self.assertEqual(stages["embed"].kind, "embed")
        self.assertEqual(stages["train"].kind, "train")

    def test_future_input_must_name_an_earlier_stage(self) -> None:
        documents = self.stage_documents(future_producer="future_stage")
        run, run_file = self.run_and_plan_file(documents)

        with self.assertRaisesRegex(VerificationError, "must name an earlier stage"):
            verify_stage_plan(
                run,
                run_file,
                fetcher=self.fetcher(documents),
            )

    def test_stage_output_paths_must_not_collide(self) -> None:
        documents = self.stage_documents(train_output="artifacts/embedding.pt")
        run, run_file = self.run_and_plan_file(documents)

        with self.assertRaisesRegex(VerificationError, "stage output paths.*collide"):
            verify_stage_plan(
                run,
                run_file,
                fetcher=self.fetcher(documents),
            )

    def test_future_output_must_not_collide_with_consumer_script(self) -> None:
        documents = self.stage_documents(embed_output="src/mantra/train.py")
        run, run_file = self.run_and_plan_file(documents)

        with self.assertRaisesRegex(VerificationError, "collides with the script"):
            verify_stage_plan(
                run,
                run_file,
                fetcher=self.fetcher(documents),
            )

    def test_future_output_must_not_collide_with_stored_input(self) -> None:
        documents = self.stage_documents(
            embed_output="workspace/data.csv",
            stored_path="workspace/data.csv",
        )
        run, run_file = self.run_and_plan_file(documents)

        with self.assertRaisesRegex(VerificationError, "collides with a stored input"):
            verify_stage_plan(
                run,
                run_file,
                fetcher=self.fetcher(documents),
            )

    def test_stage_specs_are_loaded_from_the_run_plan_snapshot(self) -> None:
        documents = self.stage_documents()
        run, run_file = self.run_and_plan_file(documents)
        requested_locations = []

        def fetcher(location):
            requested_locations.append(location)
            return documents[location.path]

        verify_stage_plan(run, run_file, fetcher=fetcher)

        self.assertTrue(requested_locations)
        for location in requested_locations:
            self.assertEqual(location.repository, PLAN_REPOSITORY)
            self.assertEqual(location.commit, PLAN_COMMIT)

    def test_stage_spec_content_must_match_run_stage_hash_and_size(self) -> None:
        documents = self.stage_documents()
        run, run_file = self.run_and_plan_file(documents)
        tampered = documents | {
            "stages/embed.spec.yaml": documents["stages/embed.spec.yaml"] + b"\n"
        }

        with self.assertRaisesRegex(VerificationError, "byte-count mismatch"):
            verify_stage_plan(
                run,
                run_file,
                fetcher=self.fetcher(tampered),
            )


class ResolvedStageVerificationTests(unittest.TestCase):
    @staticmethod
    def build_records(
        *,
        source_commit: str = GIT_COMMIT,
        stage_completed_at: datetime | None = None,
    ) -> tuple[ResolvedRun, dict[str, DownloadSpec], dict[str, bytes]]:
        spec_payload = {
            "schema_version": 1,
            "kind": "download",
            "inputs": {
                "dataset": {
                    "kind": "remote",
                    "url": "https://example.com/data.csv",
                }
            },
            "script": "src/mantra/download.py",
            "environment": StagePlanVerificationTests.environment(),
            "reproducibility": (StagePlanVerificationTests.reproducibility()),
            "output": "artifacts/raw.pt",
        }
        spec = DownloadSpec.model_validate(spec_payload)
        spec_raw = yaml_bytes(spec_payload)

        source_raw = b"print('download')\n"
        lockfile_raw = b"version = 1\n"
        output_raw = b"dummy downloaded tensor"

        started_at = datetime(2026, 8, 17, 8, 30, tzinfo=UTC)
        completed_at = started_at + timedelta(seconds=2)
        stage_time = stage_completed_at or started_at + timedelta(seconds=1)

        resolved_payload = {
            "schema_version": 1,
            "kind": "download",
            "spec": spec_payload,
            "source": {
                "sha256": hashlib.sha256(source_raw).hexdigest(),
                "bytes": len(source_raw),
                "stored_at": {
                    "kind": "git",
                    "repository": REPOSITORY,
                    "commit": source_commit,
                    "path": "src/mantra/download.py",
                },
            },
            "environment": {
                "kind": "gce",
                "machine_image": {
                    "project": "example-project",
                    "name": "mantra-image",
                    "id": "123456789",
                },
                "lockfile": {
                    "sha256": hashlib.sha256(lockfile_raw).hexdigest(),
                    "bytes": len(lockfile_raw),
                    "stored_at": {
                        "kind": "git",
                        "repository": REPOSITORY,
                        "commit": GIT_COMMIT,
                        "path": "uv.lock",
                    },
                },
            },
            "execution_context": {
                "host": {
                    "provider": "gce",
                    "machine_type": "g2-standard-4",
                    "zone": "us-central1-a",
                    "guest_os_name": "Ubuntu",
                    "guest_os_version": "24.04",
                    "kernel_release": "6.8.0",
                },
                "cpu": {
                    "architecture": "x86_64",
                    "model": "Intel Xeon",
                    "instruction_features": ["avx2"],
                },
                "backend": {"kind": "cpu", "device": "cpu"},
                "numerical_runtime": {
                    "python_version": "3.12.4",
                    "pytorch_version": "2.8.0",
                    "numpy_version": "2.1.0",
                    "blas": {"implementation": "OpenBLAS", "version": "0.3.27"},
                    "lapack": {
                        "implementation": "OpenBLAS",
                        "version": "0.3.27",
                    },
                    "native_thread_pools": [],
                },
                "parallelism": {
                    "process_count": 1,
                    "torch_intraop_threads": 1,
                    "torch_interop_threads": 1,
                    "dataloader_workers": 0,
                },
            },
            "command": ["python", "src/mantra/download.py"],
            "output": {
                "sha256": hashlib.sha256(output_raw).hexdigest(),
                "bytes": len(output_raw),
                "stored_at": {
                    "kind": "huggingface",
                    "repository": "machina/mantra-artifacts",
                    "commit": PLAN_COMMIT,
                    "path": "artifacts/raw.pt",
                    "repo_type": "dataset",
                },
            },
            "completed_at": stage_time.isoformat(),
            "inputs": spec_payload["inputs"],
        }
        resolved_raw = yaml_bytes(resolved_payload)
        resolved_reference = ResolvedFileRef(
            sha256=hashlib.sha256(resolved_raw).hexdigest(),
            bytes=len(resolved_raw),
            stored_at=HuggingFaceFileRef(
                repository="machina/mantra-artifacts",
                commit=PLAN_COMMIT,
                path="stages/download.spec.resolved.yaml",
                repo_type="dataset",
            ),
        )

        run = RunSpec(
            run_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            experiment_id="e001_download",
            variant_id="baseline",
            replicate_id="replicate_01",
            seed=42,
            source=GitSource(repository=REPOSITORY, commit=GIT_COMMIT),
            stages=(
                RunStageRef(
                    stage_id="download",
                    spec="stages/download.spec.yaml",
                    sha256=hashlib.sha256(spec_raw).hexdigest(),
                    bytes=len(spec_raw),
                ),
            ),
        )
        attempt = RunAttempt(
            attempt_id=1,
            status="succeeded",
            started_at=started_at,
            completed_at=completed_at,
            resolved_stages=(
                ResolvedStageRef(
                    stage_id="download",
                    resolved_spec=resolved_reference,
                ),
            ),
            artifact_manifests=(),
            measurement_files=(),
            log_files=(),
            failure_reason=None,
        )
        run_file_raw = b"run plan"
        record = ResolvedRun(
            run=run,
            run_file=ResolvedFileRef(
                sha256=hashlib.sha256(run_file_raw).hexdigest(),
                bytes=len(run_file_raw),
                stored_at=GitFileRef(
                    repository=PLAN_REPOSITORY,
                    commit=PLAN_COMMIT,
                    path="runs/01JABC.run.yaml",
                ),
            ),
            status="succeeded",
            attempts=(attempt,),
            successful_attempt_id=1,
            completed_at=completed_at,
        )
        documents = {
            "stages/download.spec.resolved.yaml": resolved_raw,
            "src/mantra/download.py": source_raw,
            "uv.lock": lockfile_raw,
            "artifacts/raw.pt": output_raw,
        }
        return record, {"download": spec}, documents

    @staticmethod
    def fetcher(documents: dict[str, bytes]):
        def retrieve(location):
            return documents[location.path]

        return retrieve

    def test_resolved_stage_and_its_exact_files_are_verified(self) -> None:
        record, stage_specs, documents = self.build_records()

        verified = verify_resolved_stages(
            record,
            stage_specs,
            fetcher=self.fetcher(documents),
        )

        self.assertEqual(tuple(verified), ("download",))
        self.assertEqual(
            verified["download"].output.bytes,
            len(documents["artifacts/raw.pt"]),
        )

    def test_resolved_stage_must_embed_the_loaded_stage_spec(self) -> None:
        record, stage_specs, documents = self.build_records()
        different = stage_specs["download"].model_copy(
            update={"output": "artifacts/other.pt"}
        )

        with self.assertRaisesRegex(VerificationError, "embed its stage spec"):
            verify_resolved_stages(
                record,
                {"download": different},
                fetcher=self.fetcher(documents),
            )

    def test_resolved_stage_source_must_match_run_source_snapshot(self) -> None:
        record, stage_specs, documents = self.build_records(source_commit="c" * 40)

        with self.assertRaisesRegex(VerificationError, "run source snapshot"):
            verify_resolved_stages(
                record,
                stage_specs,
                fetcher=self.fetcher(documents),
            )

    def test_resolved_stage_output_bytes_are_verified(self) -> None:
        record, stage_specs, documents = self.build_records()
        documents["artifacts/raw.pt"] += b"tampered"

        with self.assertRaisesRegex(VerificationError, "byte-count mismatch"):
            verify_resolved_stages(
                record,
                stage_specs,
                fetcher=self.fetcher(documents),
            )

    def test_resolved_stage_completion_must_fall_inside_attempt(self) -> None:
        record, stage_specs, documents = self.build_records(
            stage_completed_at=datetime(2026, 8, 17, 8, 29, tzinfo=UTC)
        )

        with self.assertRaisesRegex(
            VerificationError,
            "outside the successful attempt",
        ):
            verify_resolved_stages(
                record,
                stage_specs,
                fetcher=self.fetcher(documents),
            )


def build_artifact_manifest_records(
    *,
    manifest_raw_override: bytes | None = None,
) -> tuple[
    ResolvedArtifactManifestRef,
    ArtifactManifest,
    dict[str, bytes],
]:
    record, stage_specs, documents = ResolvedStageVerificationTests.build_records()

    spec = stage_specs["download"]
    spec_raw = yaml_bytes(spec.model_dump(mode="json"))

    resolved_raw = documents["stages/download.spec.resolved.yaml"]
    resolved = ResolvedDownloadSpec.model_validate(yaml.safe_load(resolved_raw))

    spec_reference = ResolvedFileRef(
        sha256=hashlib.sha256(spec_raw).hexdigest(),
        bytes=len(spec_raw),
        stored_at=HuggingFaceFileRef(
            repository="machina/mantra-artifacts",
            commit=PLAN_COMMIT,
            path="stages/download.spec.yaml",
            repo_type="dataset",
        ),
    )

    resolved_reference = record.attempts[0].resolved_stages[0].resolved_spec

    manifest = ArtifactManifest(
        artifact=resolved.output,
        spec=spec_reference,
        resolved_spec=resolved_reference,
        source=resolved.source,
        created_at=resolved.completed_at,
    )

    manifest_raw = (
        manifest_raw_override
        if manifest_raw_override is not None
        else yaml_bytes(manifest.model_dump(mode="json"))
    )

    manifest_reference = ResolvedArtifactManifestRef(
        sha256=hashlib.sha256(manifest_raw).hexdigest(),
        bytes=len(manifest_raw),
        stored_at=HuggingFaceFileRef(
            repository="machina/mantra-artifacts",
            commit=PLAN_COMMIT,
            path="artifacts/raw.pt.manifest.yaml",
            repo_type="dataset",
        ),
    )

    documents = {
        **documents,
        spec_reference.stored_at.path: spec_raw,
        manifest_reference.stored_at.path: manifest_raw,
    }

    return manifest_reference, manifest, documents


class ArtifactManifestVerificationTests(unittest.TestCase):
    def test_manifest_and_referenced_files_are_verified(self) -> None:
        reference, manifest, documents = build_artifact_manifest_records()

        verified = verify_artifact_manifest(
            reference, fetcher=lambda location: documents[location.path]
        )

        self.assertEqual(verified.manifest, manifest)
        self.assertEqual(verified.artifact, manifest.artifact)
        self.assertEqual(verified.content, documents[manifest.artifact.stored_at.path])


class StoredInputVerificationTests(unittest.TestCase):
    @staticmethod
    def fetcher(documents: dict[str, bytes]):
        # Replace remote storage with an in-memory path-to-bytes mapping.
        def retrieve(location):
            return documents[location.path]

        return retrieve

    @staticmethod
    def build_records(
        *,
        pointer_raw_override: bytes | None = None,
        manifest_raw_override: bytes | None = None,
    ) -> tuple[
        ResolvedBuildSpec,
        ArtifactManifest,
        dict[str, bytes],
    ]:
        # Git location of the promotion pointer selected by the stage spec.
        pointer_location = ArtifactPointerRef(
            repository=REPOSITORY,
            commit=GIT_COMMIT,
            path="inputs/priors/current.pointer.yaml",
        )

        # Current build request: retrieve the promoted prior, then expose its verified bytes to build.py at the independent local input path.
        spec = {
            "schema_version": 1,
            "kind": "build",
            # InternalSpec.inputs -> dict[InputName, InternalInputRef]
            "inputs": {
                "prior": {
                    "kind": "stored",
                    "pointer": pointer_location.model_dump(mode="json"),
                    "path": "workspace/priors/current.pt",
                }
            },
            "script": "src/mantra/build.py",
            "environment": StagePlanVerificationTests.environment(),
            "reproducibility": (StagePlanVerificationTests.reproducibility()),
            "output": "artifacts/built.pt",
            "params": {},
        }
        # Preexisting promoted artifact consumed by the current build stage.
        manifest_reference, manifest, manifest_documents = (
            build_artifact_manifest_records(
                manifest_raw_override=manifest_raw_override,
            )
        )
        # Contents of the Git-tracked promotion pointer: one exact manifest.
        pointer = ArtifactPointer(manifest=manifest_reference)
        pointer_raw = (
            pointer_raw_override
            if pointer_raw_override is not None
            else yaml_bytes(pointer.model_dump(mode="json"))
        )
        resolved_pointer = ResolvedArtifactPointerRef(
            sha256=hashlib.sha256(pointer_raw).hexdigest(),
            bytes=len(pointer_raw),
            stored_at=pointer_location,
        )

        lockfile_raw = b"version = 1\n"
        output_raw = b"current stage output"
        # Current-stage receipt recording the exact pointer that was resolved.
        resolved = ResolvedBuildSpec.model_validate(
            {
                "schema_version": 1,
                "kind": "build",
                "spec": spec,
                "source": {
                    "sha256": hashlib.sha256(b"print('build')\n").hexdigest(),
                    "bytes": len(b"print('build')\n"),
                    "stored_at": {
                        "kind": "git",
                        "repository": REPOSITORY,
                        "commit": GIT_COMMIT,
                        "path": "src/mantra/build.py",
                    },
                },
                "environment": {
                    "kind": "gce",
                    "machine_image": {
                        "project": "example-project",
                        "name": "mantra-image",
                        "id": "123456789",
                    },
                    "lockfile": {
                        "sha256": hashlib.sha256(lockfile_raw).hexdigest(),
                        "bytes": len(lockfile_raw),
                        "stored_at": {
                            "kind": "git",
                            "repository": REPOSITORY,
                            "commit": GIT_COMMIT,
                            "path": "uv.lock",
                        },
                    },
                },
                "execution_context": {
                    "host": {
                        "provider": "gce",
                        "machine_type": "g2-standard-4",
                        "zone": "us-central1-a",
                        "guest_os_name": "Ubuntu",
                        "guest_os_version": "24.04",
                        "kernel_release": "6.8.0",
                    },
                    "cpu": {
                        "architecture": "x86_64",
                        "model": "Intel Xeon",
                        "instruction_features": ["avx2"],
                    },
                    "backend": {"kind": "cpu", "device": "cpu"},
                    "numerical_runtime": {
                        "python_version": "3.12.4",
                        "pytorch_version": "2.8.0",
                        "numpy_version": "2.1.0",
                        "blas": {
                            "implementation": "OpenBLAS",
                            "version": "0.3.27",
                        },
                        "lapack": {
                            "implementation": "OpenBLAS",
                            "version": "0.3.27",
                        },
                        "native_thread_pools": [],
                    },
                    "parallelism": {
                        "process_count": 1,
                        "torch_intraop_threads": 1,
                        "torch_interop_threads": 1,
                        "dataloader_workers": 0,
                    },
                },
                "command": ["python", "src/mantra/build.py"],
                "inputs": {
                    "prior": {
                        "kind": "stored",
                        "pointer": resolved_pointer.model_dump(mode="json"),
                    }
                },
                "output": {
                    "sha256": hashlib.sha256(output_raw).hexdigest(),
                    "bytes": len(output_raw),
                    "stored_at": {
                        "kind": "huggingface",
                        "repository": "machina/mantra-artifacts",
                        "commit": PLAN_COMMIT,
                        "path": "artifacts/built.pt",
                        "repo_type": "dataset",
                    },
                },
                "completed_at": "2026-08-17T08:31:00Z",
            }
        )
        # Fake remote files traversed as pointer -> manifest -> artifact.
        documents = {
            **manifest_documents,
            pointer_location.path: pointer_raw,
        }
        return resolved, manifest, documents

    def test_pointer_manifest_and_artifact_are_verified(self) -> None:
        resolved, manifest, documents = self.build_records()

        verified = verify_stored_inputs(
            {"build": resolved},
            fetcher=self.fetcher(documents),
        )

        # Verification results are indexed by stage ID, then input name.
        stored = verified["build"]["prior"]
        self.assertEqual(stored.path, "workspace/priors/current.pt")
        self.assertEqual(stored.artifact, manifest.artifact)
        self.assertEqual(
            stored.content,
            documents[manifest.artifact.stored_at.path],
        )

    def test_pointer_bytes_must_match_resolved_reference(self) -> None:
        resolved, _, documents = self.build_records()
        # Mutate retrieved bytes without updating the resolved pointer metadata.
        documents["inputs/priors/current.pointer.yaml"] += b"\n"

        with self.assertRaisesRegex(VerificationError, "byte-count mismatch"):
            verify_stored_inputs(
                {"build": resolved},
                fetcher=self.fetcher(documents),
            )

    def test_pointer_document_must_validate_as_artifact_pointer(self) -> None:
        # These invalid bytes are hashed correctly to isolate schema validation.
        invalid_pointer = b"schema_version: 1\nunexpected: true\n"
        resolved, _, documents = self.build_records(
            pointer_raw_override=invalid_pointer
        )

        with self.assertRaisesRegex(VerificationError, "valid ArtifactPointer"):
            verify_stored_inputs(
                {"build": resolved},
                fetcher=self.fetcher(documents),
            )

    def test_manifest_bytes_must_match_pointer_reference(self) -> None:
        resolved, _, documents = self.build_records()
        # Mutate retrieved bytes without changing the reference in the pointer.
        documents["artifacts/raw.pt.manifest.yaml"] += b"\n"

        with self.assertRaisesRegex(VerificationError, "byte-count mismatch"):
            verify_stored_inputs(
                {"build": resolved},
                fetcher=self.fetcher(documents),
            )

    def test_manifest_document_must_validate_as_artifact_manifest(self) -> None:
        # Correctly hash invalid bytes so failure occurs during model validation.
        invalid_manifest = b"schema_version: 1\nunexpected: true\n"
        resolved, _, documents = self.build_records(
            manifest_raw_override=invalid_manifest
        )

        with self.assertRaisesRegex(VerificationError, "valid ArtifactManifest"):
            verify_stored_inputs(
                {"build": resolved},
                fetcher=self.fetcher(documents),
            )

    def test_artifact_bytes_must_match_manifest_reference(self) -> None:
        resolved, _, documents = self.build_records()
        artifact = documents["artifacts/raw.pt"]
        # Preserve byte count so the SHA-256 check must detect the mutation.
        documents["artifacts/raw.pt"] = b"x" * len(artifact)

        with self.assertRaisesRegex(VerificationError, "SHA-256 mismatch"):
            verify_stored_inputs(
                {"build": resolved},
                fetcher=self.fetcher(documents),
            )
class FutureInputVerificationTests(unittest.TestCase):
    @staticmethod
    def build_records() -> tuple[
        ResolvedRun,
        dict[str, ResolvedBaseSpec],
        dict[str, bytes],
    ]:
        producer_run, _, producer_documents = (
            ResolvedStageVerificationTests.build_records()
        )
        manifest_reference, manifest, manifest_documents = (
            build_artifact_manifest_records()
        )

        resolved_producer = ResolvedDownloadSpec.model_validate(
            yaml.safe_load(producer_documents["stages/download.spec.resolved.yaml"])
        )

        stored_consumer, _, _ = StoredInputVerificationTests.build_records()

        consumer_payload = stored_consumer.model_dump(mode="json")

        consumer_payload["spec"]["inputs"] = {
            "dataset": {
                "kind": "future",
                "producer_stage_id": "download",
            }
        }
        consumer_payload["inputs"] = {
            "dataset": {
                "kind": "future",
                "manifest": manifest_reference.model_dump(mode="json"),
            }
        }

        resolved_consumer = ResolvedBuildSpec.model_validate(consumer_payload)
