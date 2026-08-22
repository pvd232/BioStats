"""Tests for the documented source and installed-package import inventory."""

from __future__ import annotations

import importlib

import viper
from viper import application

ROOT_MODULES = (
    "application",
    "authoring",
    "ids",
    "inspection",
    "journal",
    "local_store",
    "materialization",
    "metrics",
    "preflight",
    "protocol",
    "runner",
    "resume",
    "stage_execution",
    "worker",
    "workspace",
)

PUBLIC_MODULES = (
    *ROOT_MODULES,
    "runtime",
    "serialization",
    "stage_worker",
    "verifier",
)


def test_root_package_exports_documented_modules() -> None:
    """Keep the root module inventory equal to the documented public surface."""
    assert tuple(viper.__all__) == ROOT_MODULES
    for name in ROOT_MODULES:
        assert getattr(viper, name).__name__ == f"viper.{name}"


def test_every_public_module_imports() -> None:
    """Import every module promised by the public API inventory."""
    for name in PUBLIC_MODULES:
        assert importlib.import_module(f"viper.{name}") is not None


def test_application_exports_and_registries_are_complete() -> None:
    """Resolve every exported name and every declared application operation."""
    for name in application.__all__:
        assert getattr(application, name) is not None
    assert tuple(application.REQUEST_REGISTRY) == application.OPERATIONS
    assert tuple(application.HANDLER_REGISTRY) == application.OPERATIONS
