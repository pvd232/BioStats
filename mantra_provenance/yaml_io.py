"""Duplicate-key-safe YAML loading for stage and resolved-stage specs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver

from .models_v4 import ResolvedSpec, Spec


class UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeySafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeySafeLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)

_SPEC_ADAPTER = TypeAdapter(Spec)
_RESOLVED_SPEC_ADAPTER = TypeAdapter(ResolvedSpec)


def load_yaml_bytes(raw: bytes) -> Any:
    """Parse YAML bytes while rejecting duplicate mapping keys."""
    if not isinstance(raw, bytes):
        raise TypeError("YAML content must be bytes")
    return yaml.load(raw, Loader=UniqueKeySafeLoader)


def _load_yaml(path: Path) -> Any:
    return load_yaml_bytes(path.read_bytes())


def load_spec(path: str | Path) -> Spec:
    """Load and validate a MANTRA stage spec."""
    return _SPEC_ADAPTER.validate_python(_load_yaml(Path(path)))


def load_resolved_spec(path: str | Path) -> ResolvedSpec:
    """Load and validate an immutable MANTRA resolved spec."""
    return _RESOLVED_SPEC_ADAPTER.validate_python(_load_yaml(Path(path)))
