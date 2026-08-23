"""Shared protocol objects used by independent test modules."""

import hashlib

from viper.protocol import (
    ArtifactLoaderRef,
    BuiltinHttpTransportSpec,
    DataLoaderConfiguration,
    DataLoaderResumeState,
    HttpRequestSpec,
    HttpRetrievalPolicy,
    LegacyNumPyRNGState,
    MainProcessRNGState,
    MetricKind,
    MetricParams,
    MetricSpec,
    NumPyRNGState,
    ParameterModelRef,
    PCG64GeneratorState,
    PCG64InternalState,
    PythonRNGState,
    ResumeState,
    StageImplementationRef,
)
from viper.verifier import VerificationPolicy

DEFAULT_ARTIFACT_LOADER_SOURCE = b"def load(path):\n    return path.read_bytes()\n"


def parameter_model_ref(kind: str) -> ParameterModelRef:
    """Build one exact synthetic parameter-model identity for model tests."""
    raw = parameter_model_source(kind)
    class_name = f"{kind.title()}Parameters"
    return ParameterModelRef(
        path=f"project/parameters/{kind}.py",
        symbol=class_name,
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
    )


def parameter_model_source(kind: str) -> bytes:
    """Build the source bytes matched by ``parameter_model_ref``."""
    class_name = f"{kind.title()}Parameters"
    base_name = f"{kind.title()}Params"
    return (
        f"from viper.protocol import {base_name}\n\n"
        f"class {class_name}({base_name}):\n"
        f'    """Validate the {kind} parameters used by this fixture."""\n'
    ).encode()


def stage_implementation_ref(
    path: str,
    raw: bytes = b"# stage implementation\n",
    *,
    symbol: str = "run",
) -> StageImplementationRef:
    """Build one exact synthetic stage-callable identity for model tests."""
    return StageImplementationRef(
        path=path,
        symbol=symbol,
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
    )


def artifact_loader_ref(
    path: str,
    raw: bytes = DEFAULT_ARTIFACT_LOADER_SOURCE,
    *,
    symbol: str = "load",
) -> ArtifactLoaderRef:
    """Build one exact synthetic artifact-loader identity for tests."""
    return ArtifactLoaderRef(
        path=path,
        symbol=symbol,
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
    )


def http_request(
    *,
    url: str = "https://example.com/fixture.bin",
    body: bytes = b"fixture HTTP body",
    version: str = "v1",
) -> HttpRequestSpec:
    """Build one frozen request whose expected identity matches ``body``."""
    return HttpRequestSpec.model_validate(
        {
            "url": url,
            "version": version,
            "expected_body_sha256": hashlib.sha256(body).hexdigest(),
            "expected_body_bytes": len(body),
        }
    )


def http_policy(
    *,
    hosts: frozenset[str] = frozenset({"example.com"}),
    ports: frozenset[int] = frozenset({443}),
) -> HttpRetrievalPolicy:
    """Build the bounded retrieval policy used by synthetic download stages."""
    return HttpRetrievalPolicy(
        allowed_schemes=frozenset({"http", "https"}),
        allowed_hosts=hosts,
        allowed_ports=ports,
        max_redirects=2,
        max_body_bytes=1024 * 1024,
        timeout_seconds=30,
    )


def builtin_http_transport() -> BuiltinHttpTransportSpec:
    """Select the HTTPX transport for one synthetic download stage."""
    return BuiltinHttpTransportSpec()


def verification_policy(*repositories: object) -> VerificationPolicy:
    """Trust project code from the named test repositories."""
    return VerificationPolicy(
        trusted_source_repositories=frozenset(str(value) for value in repositories)
    )


def metric_spec(metric_id: str, kind: MetricKind) -> MetricSpec:
    """Build one metric bound to an exact user-repository implementation path."""
    return MetricSpec(
        metric_id=metric_id,
        kind=kind,
        implementation=f"project/metrics/{kind}/{metric_id}.py",
        params=MetricParams(),
        production="during_stage" if kind == "training" else "after_stage",
        verification="execution" if kind == "training" else "recompute",
    )


def resume_state(
    *,
    workers: int = 0,
    prefetch_factor: int | None = None,
    persistent_workers: bool = False,
) -> ResumeState:
    """Build a valid serialized resume state for verifier tests."""
    return ResumeState(
        optimizer_state={"state": {}, "param_groups": []},
        main_process_rng=MainProcessRNGState(
            python=PythonRNGState(
                version=3,
                internal_state=(1,),
                gaussian_cache=None,
            ),
            numpy=NumPyRNGState(
                generators={
                    "training": PCG64GeneratorState(
                        state=PCG64InternalState(state=1, inc=1),
                        has_uint32=0,
                        uinteger=0,
                    )
                },
                legacy_global=LegacyNumPyRNGState(
                    keys=(0,) * 624,
                    position=0,
                    has_gaussian=0,
                    cached_gaussian=0.0,
                ),
            ),
            torch_cpu=b"torch-cpu",
            torch_cuda=(),
        ),
        dataloader=DataLoaderResumeState(
            configuration=DataLoaderConfiguration(
                workers=workers,
                prefetch_factor=prefetch_factor,
                persistent_workers=persistent_workers,
                in_order=True,
            ),
            state_dict={"num_yielded": 10},
        ),
    )
