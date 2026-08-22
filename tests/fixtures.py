"""Shared protocol objects used by independent test modules."""

import hashlib

from viper.protocol import (
    DataLoaderConfiguration,
    DataLoaderResumeState,
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
)
from viper.verifier import VerificationPolicy


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


def verification_policy(*repositories: object) -> VerificationPolicy:
    """Trust artifact-loader code from the named test repositories."""
    return VerificationPolicy(
        trusted_loader_repositories=frozenset(str(value) for value in repositories)
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
