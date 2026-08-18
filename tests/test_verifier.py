from __future__ import annotations

import hashlib
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import yaml

from mantra_provenance.models_v4 import (
    DownloadSpec,
    GitFileRef,
    GitSource,
    HuggingFaceFileRef,
    ResolvedFileRef,
    ResolvedGitFileRef,
    ResolvedRun,
    ResolvedStageRef,
    RunAttempt,
    RunSpec,
)
from mantra_provenance.verifier import (
    VerificationError,
    fetch_storage_bytes,
    read_resolved_file,
    verify_authored_stage_plan,
    verify_experiment_and_variant,
    verify_resolved_run_file,
    verify_resolved_stages,
)

GIT_COMMIT = "a" * 40
PLAN_COMMIT = "b" * 40
REPOSITORY = "https://example.com/mantra.git"
PLAN_REPOSITORY = "https://example.com/mantra-run-plans.git"


def run_spec(*, seed: int = 42) -> RunSpec:
    return RunSpec(
        run_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        experiment_id="e001_low_rank",
        variant_id="low_rank_32",
        replicate_id="replicate_01",
        seed=seed,
        source=GitSource(repository=REPOSITORY, commit=GIT_COMMIT),
        stages=(
            {
                "stage_id": "embed",
                "spec": "stages/embed.spec.yaml",
                "sha256": "c" * 64,
                "bytes": 100,
            },
            {
                "stage_id": "train",
                "spec": "stages/train.spec.yaml",
                "sha256": "d" * 64,
                "bytes": 200,
            },
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
        raw = yaml.safe_dump(
            embedded.model_dump(mode="json"),
            sort_keys=True,
        ).encode("utf-8")
        record = resolved_run(embedded, resolved_reference(raw))

        self.assertEqual(
            verify_resolved_run_file(record, fetcher=lambda _: raw),
            embedded,
        )

    def test_run_file_rejects_different_valid_run(self) -> None:
        embedded = run_spec(seed=42)
        file_run = run_spec(seed=93)
        raw = yaml.safe_dump(
            file_run.model_dump(mode="json"),
            sort_keys=True,
        ).encode("utf-8")
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
            f"{root}/e001_low_rank.experiment.yaml": yaml.safe_dump(
                experiment,
                sort_keys=True,
            ).encode("utf-8"),
            f"{root}/variants/low_rank_32.variant.yaml": yaml.safe_dump(
                variant,
                sort_keys=True,
            ).encode("utf-8"),
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
        documents = self.documents(
            variant_updates={"levels": {"rank": "rank_32"}}
        )

        with self.assertRaisesRegex(VerificationError, "exactly one level"):
            verify_experiment_and_variant(
                run_spec(),
                fetcher=self.fetcher(documents),
            )

    def test_variant_levels_must_be_permitted(self) -> None:
        documents = self.documents(
            variant_updates={
                "levels": {"rank": "rank_128", "optimizer": "adamw"}
            }
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


class AuthoredStagePlanVerificationTests(unittest.TestCase):
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
            "stages/embed.spec.yaml": yaml.safe_dump(embed, sort_keys=True).encode(
                "utf-8"
            ),
            "stages/train.spec.yaml": yaml.safe_dump(train, sort_keys=True).encode(
                "utf-8"
            ),
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
        stages = verify_authored_stage_plan(
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
            verify_authored_stage_plan(
                run,
                run_file,
                fetcher=self.fetcher(documents),
            )

    def test_stage_output_paths_must_not_collide(self) -> None:
        documents = self.stage_documents(train_output="artifacts/embedding.pt")
        run, run_file = self.run_and_plan_file(documents)

        with self.assertRaisesRegex(VerificationError, "stage output paths.*collide"):
            verify_authored_stage_plan(
                run,
                run_file,
                fetcher=self.fetcher(documents),
            )

    def test_future_output_must_not_collide_with_consumer_script(self) -> None:
        documents = self.stage_documents(embed_output="src/mantra/train.py")
        run, run_file = self.run_and_plan_file(documents)

        with self.assertRaisesRegex(VerificationError, "collides with the script"):
            verify_authored_stage_plan(
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
            verify_authored_stage_plan(
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

        verify_authored_stage_plan(run, run_file, fetcher=fetcher)

        self.assertTrue(requested_locations)
        for location in requested_locations:
            self.assertEqual(str(location.repository), PLAN_REPOSITORY)
            self.assertEqual(location.commit, PLAN_COMMIT)

    def test_stage_spec_content_must_match_run_stage_hash_and_size(self) -> None:
        documents = self.stage_documents()
        run, run_file = self.run_and_plan_file(documents)
        tampered = documents | {
            "stages/embed.spec.yaml": documents["stages/embed.spec.yaml"] + b"\n"
        }

        with self.assertRaisesRegex(VerificationError, "byte-count mismatch"):
            verify_authored_stage_plan(
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
        authored_payload = {
            "schema_version": 1,
            "kind": "download",
            "inputs": {
                "dataset": {
                    "kind": "remote",
                    "url": "https://example.com/data.csv",
                }
            },
            "script": "src/mantra/download.py",
            "environment": AuthoredStagePlanVerificationTests.environment(),
            "reproducibility": (
                AuthoredStagePlanVerificationTests.reproducibility()
            ),
            "output": "artifacts/raw.pt",
        }
        authored = DownloadSpec.model_validate(authored_payload)
        authored_raw = yaml.safe_dump(authored_payload, sort_keys=True).encode("utf-8")

        source_raw = b"print('download')\n"
        lockfile_raw = b"version = 1\n"
        output_raw = b"dummy downloaded tensor"

        started_at = datetime(2026, 8, 17, 8, 30, tzinfo=UTC)
        completed_at = started_at + timedelta(seconds=2)
        stage_time = stage_completed_at or started_at + timedelta(seconds=1)

        resolved_payload = {
            "schema_version": 1,
            "kind": "download",
            "spec": authored_payload,
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
            "inputs": authored_payload["inputs"],
        }
        resolved_raw = yaml.safe_dump(resolved_payload, sort_keys=True).encode("utf-8")
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
                {
                    "stage_id": "download",
                    "spec": "stages/download.spec.yaml",
                    "sha256": hashlib.sha256(authored_raw).hexdigest(),
                    "bytes": len(authored_raw),
                },
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
        return record, {"download": authored}, documents

    @staticmethod
    def fetcher(documents: dict[str, bytes]):
        def retrieve(location):
            return documents[location.path]

        return retrieve

    def test_resolved_stage_and_its_exact_files_are_verified(self) -> None:
        record, authored_stages, documents = self.build_records()

        verified = verify_resolved_stages(
            record,
            authored_stages,
            fetcher=self.fetcher(documents),
        )

        self.assertEqual(tuple(verified), ("download",))
        self.assertEqual(
            verified["download"].output.bytes,
            len(documents["artifacts/raw.pt"]),
        )

    def test_resolved_stage_must_embed_the_loaded_authored_spec(self) -> None:
        record, authored_stages, documents = self.build_records()
        different = authored_stages["download"].model_copy(
            update={"output": "artifacts/other.pt"}
        )

        with self.assertRaisesRegex(VerificationError, "embed its authored spec"):
            verify_resolved_stages(
                record,
                {"download": different},
                fetcher=self.fetcher(documents),
            )

    def test_resolved_stage_source_must_match_run_source_snapshot(self) -> None:
        record, authored_stages, documents = self.build_records(
            source_commit="c" * 40
        )

        with self.assertRaisesRegex(VerificationError, "run source snapshot"):
            verify_resolved_stages(
                record,
                authored_stages,
                fetcher=self.fetcher(documents),
            )

    def test_resolved_stage_output_bytes_are_verified(self) -> None:
        record, authored_stages, documents = self.build_records()
        documents["artifacts/raw.pt"] += b"tampered"

        with self.assertRaisesRegex(VerificationError, "byte-count mismatch"):
            verify_resolved_stages(
                record,
                authored_stages,
                fetcher=self.fetcher(documents),
            )

    def test_resolved_stage_completion_must_fall_inside_attempt(self) -> None:
        record, authored_stages, documents = self.build_records(
            stage_completed_at=datetime(2026, 8, 17, 8, 29, tzinfo=UTC)
        )

        with self.assertRaisesRegex(
            VerificationError,
            "outside the successful attempt",
        ):
            verify_resolved_stages(
                record,
                authored_stages,
                fetcher=self.fetcher(documents),
            )
