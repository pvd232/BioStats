"""YAML loading for human-authored specs and resolved-spec fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter

from .models import ResolvedSpec, Spec


class UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeySafeLoader,
    node: yaml.MappingNode,
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
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)

_SPEC_ADAPTER = TypeAdapter(Spec)
_RESOLVED_SPEC_ADAPTER = TypeAdapter(ResolvedSpec)


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.load(stream, Loader=UniqueKeySafeLoader)


def load_spec(path: str | Path):
    """Load and validate a human-authored MANTRA spec."""
    return _SPEC_ADAPTER.validate_python(_load_yaml(Path(path)))


def load_resolved_spec(path: str | Path):
    """Load and validate an immutable MANTRA resolved spec."""
    return _RESOLVED_SPEC_ADAPTER.validate_python(_load_yaml(Path(path)))
