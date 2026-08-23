"""Tests for frozen HTTP requests, transports, and retrieval evidence."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from viper.protocol import (
    BuiltinHttpTransportSpec,
    EnvironmentSecretRef,
    HttpRequestSpec,
    HttpRetrievalPolicy,
    LocalFileRef,
    ObservedHttpResponse,
    ResolvedFileRef,
    ResolvedHttpRetrieval,
    ResolvedHttpTransport,
)


def _request(**updates: object) -> HttpRequestSpec:
    """Build one immutable request with fixed response-body identity."""
    values = {
        "url": "https://data.example.test/archive.bin",
        "version": "2026-08-23",
        "expected_body_sha256": "a" * 64,
        "expected_body_bytes": 128,
    }
    values.update(updates)
    return HttpRequestSpec.model_validate(values)


def test_request_rejects_literal_and_unauthorized_credentials() -> None:
    """Keep secret values out and require origin-scoped secret delivery."""
    with pytest.raises(ValidationError, match="literal credential"):
        _request(headers={"authorization": "Bearer secret"})

    secret = EnvironmentSecretRef.model_validate(
        {
            "variable": "DATA_TOKEN",
            "header": "authorization",
            "prefix": "Bearer ",
            "authorized_origins": [
                {"scheme": "https", "host": "other.example.test", "port": 443}
            ],
        }
    )
    with pytest.raises(ValidationError, match="not authorized"):
        _request(credentials=secret)


def test_policy_requires_normalized_exact_hosts() -> None:
    """Represent the request allowlist with exact normalized host values."""
    with pytest.raises(ValidationError, match="normalized"):
        HttpRetrievalPolicy(
            allowed_schemes=frozenset({"https"}),
            allowed_hosts=frozenset({"DATA.EXAMPLE.TEST"}),
            allowed_ports=frozenset({443}),
            max_redirects=2,
            max_body_bytes=1024,
            timeout_seconds=30,
        )


def test_resolved_retrieval_requires_the_expected_body_identity() -> None:
    """Reject a same-length response body with another SHA-256 identity."""
    request = _request()
    body = ResolvedFileRef(
        sha256="b" * 64,
        bytes=128,
        stored_at=LocalFileRef(
            store=".viper/store",
            commit="c" * 64,
            path="retrievals/archive/body",
        ),
    )
    with pytest.raises(ValidationError, match="SHA-256"):
        ResolvedHttpRetrieval(
            input_name="archive",
            request=request,
            transport=ResolvedHttpTransport(spec=BuiltinHttpTransportSpec()),
            response=ObservedHttpResponse(
                response_url=request.url,
                status=200,
                response_headers={"content-length": "128"},
            ),
            body=body,
            started_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
            completed_at=datetime(2026, 8, 23, 12, 1, tzinfo=UTC),
        )
