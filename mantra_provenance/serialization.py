"""Deterministic JSON serialization for protocol models."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel


def canonical_json_bytes(model: BaseModel) -> bytes:
    """Return the protocol's deterministic JSON representation of a model."""
    payload = model.model_dump(mode="json", exclude_none=False)
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def resolved_spec_sha256(model: BaseModel) -> str:
    """Hash a resolved spec's deterministic JSON representation."""
    return hashlib.sha256(canonical_json_bytes(model)).hexdigest()
