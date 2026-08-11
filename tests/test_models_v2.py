from __future__ import annotations

import unittest

from pydantic import ValidationError

from mantra_provenance.models_v2 import (
    BuildSpec,
    HuggingFaceFileRef,
    PythonLockEnvironmentSpec,
    RepoFileRef,
    ResolvedBuildSpec,
    ResolvedCodeRef,
    ResolvedFileRef,
    ResolvedInput,
    ResolvedPythonEnvironment,
    ResolvedSpecRef,
    ResolvedSpecSource,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
GIT_A = "a" * 40
GIT_B = "b" * 40


def hf_ref(path: str) -> HuggingFaceFileRef:
    return HuggingFaceFileRef(
        repo_type="dataset",
        repo_id="example/mantra-artifacts",
        revision=GIT_A,
        path=path,
    )


def resolved_file(path: str, sha256: str = SHA_A) -> ResolvedFileRef:
    return ResolvedFileRef(
        sha256=sha256,
        bytes=1024,
        workspace_path=path,
        stored_at=hf_ref(path),
    )


class ResolvedReferenceTests(unittest.TestCase):
    def test_workspace_binding_and_hugging_face_storage_are_distinct(self) -> None:
        reference = resolved_file("artifacts/raw/expression.csv")

        self.assertEqual(reference.workspace_path, "artifacts/raw/expression.csv")
        self.assertIsInstance(reference.stored_at, HuggingFaceFileRef)
        self.assertEqual(reference.stored_at.path, "artifacts/raw/expression.csv")

    def test_producer_is_required_but_nullable(self) -> None:
        artifact = ResolvedFileRef(
            sha256=SHA_A,
            bytes=1024,
            workspace_path=None,
            stored_at=None,
        )

        external = ResolvedInput(artifact=artifact, producer=None)
        self.assertTrue(external.is_external)

        with self.assertRaises(ValidationError):
            ResolvedInput.model_validate({"artifact": artifact.model_dump()})

    def test_resolved_spec_reference_uses_record_identity(self) -> None:
        producer = ResolvedSpecRef(
            record_id=SHA_B,
            location=RepoFileRef(path="provenance/download.resolved.spec.yaml"),
        )

        self.assertEqual(producer.record_id, SHA_B)
        self.assertFalse(hasattr(producer, "bytes"))
        self.assertFalse(hasattr(producer, "workspace_path"))

    def test_hugging_face_revision_must_be_immutable_git_id(self) -> None:
        with self.assertRaises(ValidationError):
            HuggingFaceFileRef(
                repo_type="dataset",
                repo_id="example/mantra-artifacts",
                revision="main",
                path="raw/expression.csv",
            )


class ResolvedSpecInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = BuildSpec(
            inputs={
                "raw_data": RepoFileRef(path="artifacts/raw/expression.csv")
            },
            script="scripts/build.py",
            environment=PythonLockEnvironmentSpec(
                lockfile="pylock.toml",
                requires_python=">=3.12,<3.13",
            ),
            params={"normalize": True},
            output="artifacts/processed/expression.pt",
        )
        self.producer = ResolvedSpecRef(
            record_id=SHA_B,
            location=RepoFileRef(path="provenance/download.resolved.spec.yaml"),
        )

    def make_resolved_build(
        self,
        *,
        producer: ResolvedSpecRef | None,
        output_path: str = "artifacts/processed/expression.pt",
    ) -> ResolvedBuildSpec:
        return ResolvedBuildSpec(
            spec=self.spec,
            spec_source=ResolvedSpecSource(
                path="specs/build.spec.yaml",
                raw_sha256=SHA_C,
                repository="https://github.com/example/mantra",
                commit=GIT_A,
            ),
            inputs={
                "raw_data": ResolvedInput(
                    artifact=resolved_file("artifacts/raw/expression.csv"),
                    producer=producer,
                )
            },
            code=ResolvedCodeRef(
                repository="https://github.com/example/mantra",
                commit=GIT_A,
                tree=GIT_B,
                entrypoint="scripts/build.py",
                entrypoint_sha256=SHA_C,
            ),
            environment=ResolvedPythonEnvironment(
                lockfile=ResolvedFileRef(
                    sha256=SHA_C,
                    bytes=2048,
                    workspace_path="pylock.toml",
                    stored_at=RepoFileRef(path="pylock.toml"),
                ),
                python_implementation="CPython",
                python_version="3.12.4",
            ),
            command=("python", "scripts/build.py"),
            output=resolved_file(output_path, sha256=SHA_C),
        )

    def test_internal_spec_requires_a_producer(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_resolved_build(producer=None)

        resolved = self.make_resolved_build(producer=self.producer)
        self.assertFalse(resolved.inputs["raw_data"].is_external)

    def test_output_workspace_path_must_match_spec(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_resolved_build(
                producer=self.producer,
                output_path="artifacts/processed/wrong.pt",
            )


if __name__ == "__main__":
    unittest.main()
