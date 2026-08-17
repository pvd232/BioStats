from __future__ import annotations

import unittest

import yaml
from pydantic import TypeAdapter, ValidationError

from mantra_provenance.ids import HumanId, RunId
from mantra_provenance.models_v4 import (
    ArtifactPointer,
    ArtifactPointerRef,
    BuildSpec,
    FutureInputRef,
    GitCommit,
    GitFileRef,
    HuggingFaceFileRef,
    InternalInputRef,
    RemoteFileRef,
    RepoRelPath,
    ResolvedArtifactManifestRef,
    ResolvedArtifactPointerRef,
    ResolvedFileRef,
    ResolvedGitFileRef,
    SHA256,
    StoredInputRef,
    StorageRef,
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
                **git_location("src/mantra/train.py"),
                sha256=SHA_A,
                bytes=4096,
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
