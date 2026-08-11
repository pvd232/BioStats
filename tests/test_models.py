from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from mantra_provenance.models import (
    BuildSpec,
    DownloadSpec,
    ExternalResolvedInput,
    ProducedResolvedInput,
    RepoFileRef,
    ResolvedBuildSpec,
    ResolvedDownloadSpec,
)
from mantra_provenance.serialization import (
    canonical_json_bytes,
    resolved_spec_sha256,
)
from mantra_provenance.yaml_io import load_resolved_spec, load_spec


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "provenance"


class SpecFixtureTests(unittest.TestCase):
    def test_load_operation_specs(self) -> None:
        download = load_spec(FIXTURES / "download.spec.yaml")
        build = load_spec(FIXTURES / "build.spec.yaml")

        self.assertIsInstance(download, DownloadSpec)
        self.assertIsInstance(build, BuildSpec)

    def test_spec_source_hashes_match_raw_yaml(self) -> None:
        for stem in ("download", "build"):
            spec_path = FIXTURES / f"{stem}.spec.yaml"
            resolved_path = FIXTURES / f"{stem}.fixture.resolved.spec.yaml"
            resolved = load_resolved_spec(resolved_path)
            actual = hashlib.sha256(spec_path.read_bytes()).hexdigest()
            self.assertEqual(actual, resolved.spec_source.raw_sha256)

    def test_download_and_build_form_a_valid_provenance_chain(self) -> None:
        download = load_resolved_spec(
            FIXTURES / "download.fixture.resolved.spec.yaml"
        )
        build = load_resolved_spec(FIXTURES / "build.fixture.resolved.spec.yaml")

        self.assertIsInstance(download, ResolvedDownloadSpec)
        self.assertIsInstance(build, ResolvedBuildSpec)
        self.assertIsInstance(download.inputs["source"], ExternalResolvedInput)
        self.assertIsInstance(build.inputs["raw_data"], ProducedResolvedInput)

        produced = build.inputs["raw_data"]
        self.assertEqual(produced.artifact.sha256, download.output.sha256)
        self.assertEqual(produced.artifact.bytes, download.output.bytes)
        self.assertEqual(produced.producer.sha256, resolved_spec_sha256(download))

    def test_record_identity_is_deterministic(self) -> None:
        first = load_resolved_spec(
            FIXTURES / "download.fixture.resolved.spec.yaml"
        )
        second = load_resolved_spec(
            FIXTURES / "download.fixture.resolved.spec.yaml"
        )

        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        self.assertEqual(resolved_spec_sha256(first), resolved_spec_sha256(second))


class ValidationInvariantTests(unittest.TestCase):
    def test_repository_paths_reject_parent_traversal(self) -> None:
        with self.assertRaises(ValidationError):
            RepoFileRef(path="../outside.txt")

    def test_extra_fields_are_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            RepoFileRef.model_validate(
                {"kind": "repo", "path": "data/input.csv", "typo": True}
            )

    def test_resolved_output_must_match_requested_path(self) -> None:
        resolved = load_resolved_spec(
            FIXTURES / "build.fixture.resolved.spec.yaml"
        )
        payload = resolved.model_dump(mode="json")
        payload["output"]["locations"] = [
            {"kind": "repo", "path": "artifacts/wrong.pt"}
        ]

        with self.assertRaises(ValidationError):
            ResolvedBuildSpec.model_validate(payload)

    def test_duplicate_yaml_keys_are_rejected(self) -> None:
        duplicate = """\
schema_version: 1
kind: build
kind: train
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml") as stream:
            stream.write(duplicate)
            stream.flush()
            with self.assertRaises(ValueError):
                load_spec(stream.name)


if __name__ == "__main__":
    unittest.main()
