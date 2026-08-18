from __future__ import annotations

import hashlib
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

import yaml

from mantra_provenance.models_v4 import (
    GitFileRef,
    GitSource,
    HuggingFaceFileRef,
    ResolvedFileRef,
    ResolvedRun,
    RunSpec,
)
from mantra_provenance.verifier import (
    VerificationError,
    fetch_storage_bytes,
    read_resolved_file,
    verify_authored_stage_plan,
    verify_experiment_and_variant,
    verify_resolved_run_file,
)

GIT_COMMIT = "a" * 40
REPOSITORY = "https://example.com/mantra.git"


def run_spec(*, seed: int = 42) -> RunSpec:
    return RunSpec(
        run_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        experiment_id="e001_low_rank",
        variant_id="low_rank_32",
        replicate_id="replicate_01",
        seed=seed,
        source=GitSource(repository=REPOSITORY, commit=GIT_COMMIT),
        stages=(
            {"stage_id": "embed", "spec": "stages/embed.spec.yaml"},
            {"stage_id": "train", "spec": "stages/train.spec.yaml"},
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

    def test_valid_stage_plan_is_returned_in_run_order(self) -> None:
        stages = verify_authored_stage_plan(
            run_spec(),
            fetcher=self.fetcher(self.stage_documents()),
        )

        self.assertEqual(tuple(stages), ("embed", "train"))
        self.assertEqual(stages["embed"].kind, "embed")
        self.assertEqual(stages["train"].kind, "train")

    def test_future_input_must_name_an_earlier_stage(self) -> None:
        documents = self.stage_documents(future_producer="future_stage")

        with self.assertRaisesRegex(VerificationError, "must name an earlier stage"):
            verify_authored_stage_plan(
                run_spec(),
                fetcher=self.fetcher(documents),
            )

    def test_stage_output_paths_must_not_collide(self) -> None:
        documents = self.stage_documents(train_output="artifacts/embedding.pt")

        with self.assertRaisesRegex(VerificationError, "stage output paths.*collide"):
            verify_authored_stage_plan(
                run_spec(),
                fetcher=self.fetcher(documents),
            )

    def test_future_output_must_not_collide_with_consumer_script(self) -> None:
        documents = self.stage_documents(embed_output="src/mantra/train.py")

        with self.assertRaisesRegex(VerificationError, "collides with the script"):
            verify_authored_stage_plan(
                run_spec(),
                fetcher=self.fetcher(documents),
            )

    def test_future_output_must_not_collide_with_stored_input(self) -> None:
        documents = self.stage_documents(
            embed_output="workspace/data.csv",
            stored_path="workspace/data.csv",
        )

        with self.assertRaisesRegex(VerificationError, "collides with a stored input"):
            verify_authored_stage_plan(
                run_spec(),
                fetcher=self.fetcher(documents),
            )
