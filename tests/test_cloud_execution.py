"""Tests for immutable Python and GCE execution-environment evidence."""

from __future__ import annotations

import platform

import pytest
from pydantic import ValidationError

from viper.protocol import (
    CPUBackendContext,
    CPUComputeSpec,
    GCEHostContext,
    PythonDistributionSpec,
    PythonEnvironmentSpec,
)
from viper.runtime import (
    observe_gce_execution,
    observe_gce_provisioning,
    observe_python_environment,
)


def _metadata(path: str) -> str:
    """Return deterministic metadata for one synthetic GCE instance."""
    values = {
        "project/project-id": "mantra-477901",
        "instance/image": "projects/ubuntu-os-cloud/global/images/ubuntu-2404-v1",
        "instance/machine-type": "projects/123/machineTypes/g2-standard-12",
        "instance/zone": "projects/123/zones/us-central1-a",
    }
    return values[path]


def _provisioning_id(kind: str, project: str, name: str) -> str:
    """Return the immutable ID matched by the synthetic image selection."""
    assert kind == "boot_image"
    assert project == "ubuntu-os-cloud"
    assert name == "ubuntu-2404-v1"
    return "987654321"


def test_python_environment_is_normalized_sorted_and_exact() -> None:
    """Capture one canonical mapping of the active installed distributions."""
    environment = observe_python_environment()
    names = tuple(distribution.name for distribution in environment.distributions)

    assert environment.python_version == platform.python_version()
    assert names == tuple(sorted(names))
    assert len(names) == len(set(names))
    assert "viper-provenance" in names


def test_python_environment_rejects_noncanonical_distribution_order() -> None:
    """Reject authored distribution mappings whose order is ambiguous."""
    with pytest.raises(ValidationError, match="sorted by name"):
        PythonEnvironmentSpec(
            python_version="3.14.0",
            distributions=(
                PythonDistributionSpec(name="zeta", version="1"),
                PythonDistributionSpec(name="alpha", version="1"),
            ),
        )


def test_gce_boot_image_binds_metadata_name_to_server_id() -> None:
    """Combine the active image path with its server-defined immutable ID."""
    image = observe_gce_provisioning(_metadata, _provisioning_id)

    assert image.project == "ubuntu-os-cloud"
    assert image.name == "ubuntu-2404-v1"
    assert image.id == "987654321"


def test_gce_execution_records_host_and_cpu_backend() -> None:
    """Construct complete GCE host evidence for one CPU stage."""
    context = observe_gce_execution(
        CPUComputeSpec(),
        metadata_get=_metadata,
        provisioning_id_get=_provisioning_id,
    )

    assert isinstance(context.host, GCEHostContext)
    assert context.host.project_id == "mantra-477901"
    assert context.host.machine_type == "g2-standard-12"
    assert context.host.zone == "us-central1-a"
    assert context.host.provisioning.id == "987654321"
    assert isinstance(context.backend, CPUBackendContext)


def test_gce_boot_image_rejects_malformed_metadata_path() -> None:
    """Reject a metadata value that cannot identify an immutable boot image."""
    with pytest.raises(RuntimeError, match="invalid GCE image metadata path"):
        observe_gce_provisioning(lambda _: "ubuntu-2404-v1", _provisioning_id)


def test_gce_machine_image_requires_matching_provisioning_attestation() -> None:
    """Resolve an API-validated machine image from provisioning metadata."""
    values = {
        "instance/image": "",
        "instance/attributes/viper-provisioning-kind": "machine_image",
        "instance/attributes/viper-provisioning-project": "mantra-477901",
        "instance/attributes/viper-provisioning-name": "mantra-backup-blueprint",
        "instance/attributes/viper-provisioning-id": "4030260845309136958",
    }

    def resolve(kind: str, project: str, name: str) -> str:
        assert (kind, project, name) == (
            "machine_image",
            "mantra-477901",
            "mantra-backup-blueprint",
        )
        return "4030260845309136958"

    source = observe_gce_provisioning(values.__getitem__, resolve)

    assert source.kind == "machine_image"
    assert source.id == "4030260845309136958"
