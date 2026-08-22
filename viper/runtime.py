"""Apply run-wide reproducibility controls and observe the active Python runtime."""

from __future__ import annotations

import platform
import random
from collections.abc import Mapping
from typing import Any

import numpy as np
import torch

from .protocol import (
    CPUBackendContext,
    CPUContext,
    ExecutionContext,
    LocalHostContext,
    NativeLibraryContext,
    NativeThreadPoolContext,
    NumericalRuntimeContext,
    RandomnessContext,
    ReproducibilitySpec,
    RNGSeed,
)


def process_environment(
    seed: RNGSeed,
    reproducibility: ReproducibilitySpec,
) -> dict[str, str]:
    """Return environment variables that must exist when Python starts."""
    values = {
        "PYTHONHASHSEED": str(seed),
        "OMP_NUM_THREADS": str(reproducibility.parallelism.torch_intraop_threads),
        "MKL_NUM_THREADS": str(reproducibility.parallelism.torch_intraop_threads),
    }
    workspace = reproducibility.determinism.cublas_workspace_config
    if workspace is not None:
        values["CUBLAS_WORKSPACE_CONFIG"] = workspace
    return values


def apply_reproducibility(
    seed: RNGSeed,
    reproducibility: ReproducibilitySpec,
) -> None:
    """Apply supported random, numerical, and thread controls in one process."""
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    determinism = reproducibility.determinism
    torch.use_deterministic_algorithms(
        determinism.deterministic_algorithms,
        warn_only=determinism.deterministic_warn_only,
    )
    torch.backends.cudnn.deterministic = determinism.cudnn_deterministic
    torch.backends.cudnn.benchmark = determinism.cudnn_benchmark

    precision = reproducibility.precision
    torch.set_float32_matmul_precision(precision.float32_matmul_precision)
    torch.backends.cudnn.allow_tf32 = precision.cudnn_allow_tf32

    parallelism = reproducibility.parallelism
    torch.set_num_threads(parallelism.torch_intraop_threads)
    torch.set_num_interop_threads(parallelism.torch_interop_threads)


def _numpy_build_dependency(name: str) -> NativeLibraryContext:
    """Read one BLAS or LAPACK identity from NumPy's build configuration."""
    configuration = np.show_config(mode="dicts")
    assert isinstance(configuration, Mapping)
    dependencies = configuration.get("Build Dependencies", {})
    dependency: Mapping[str, Any] = {}
    if isinstance(dependencies, Mapping):
        candidate = dependencies.get(name, {})
        if isinstance(candidate, Mapping):
            dependency = candidate
    return NativeLibraryContext(
        implementation=str(dependency.get("name", "unreported")),
        version=str(dependency.get("version", "unreported")),
    )


def _instruction_features() -> tuple[str, ...]:
    """Read the enabled SIMD extensions reported by NumPy."""
    configuration = np.show_config(mode="dicts")
    assert isinstance(configuration, Mapping)
    simd = configuration.get("SIMD Extensions", {})
    features: list[str] = []
    if isinstance(simd, Mapping):
        for group in ("baseline", "found"):
            values = simd.get(group, ())
            if isinstance(values, list):
                features.extend(str(value) for value in values)
    return tuple(dict.fromkeys(features)) or ("unreported",)


def observe_local_execution(
    seed: RNGSeed,
    reproducibility: ReproducibilitySpec,
) -> ExecutionContext:
    """Capture the local CPU process facts required by a resolved stage."""
    architecture = platform.machine() or "unreported"
    processor = platform.processor() or architecture
    return ExecutionContext(
        host=LocalHostContext(
            operating_system=platform.system() or "unreported",
            release=platform.release() or "unreported",
            architecture=architecture,
        ),
        cpu=CPUContext(
            architecture=architecture,
            model=processor,
            instruction_features=_instruction_features(),
        ),
        backend=CPUBackendContext(),
        numerical_runtime=NumericalRuntimeContext(
            python_version=platform.python_version(),
            pytorch_version=torch.__version__,
            numpy_version=np.__version__,
            blas=_numpy_build_dependency("blas"),
            lapack=_numpy_build_dependency("lapack"),
            native_thread_pools=(
                NativeThreadPoolContext(
                    implementation="pytorch_intraop",
                    version=torch.__version__,
                    threads=torch.get_num_threads(),
                ),
                NativeThreadPoolContext(
                    implementation="pytorch_interop",
                    version=torch.__version__,
                    threads=torch.get_num_interop_threads(),
                ),
            ),
        ),
        randomness=RandomnessContext(
            python_seed=seed,
            numpy_seed=seed,
            torch_seed=seed,
            dataloader_seed=seed,
        ),
        determinism=reproducibility.determinism,
        precision=reproducibility.precision,
        parallelism=reproducibility.parallelism,
    )


def autocast_context(reproducibility: ReproducibilitySpec) -> Any:
    """Construct the run-wide autocast context for the active backend."""
    precision = reproducibility.precision
    if not precision.autocast_enabled:
        return torch.autocast(device_type="cpu", enabled=False)
    dtype = torch.float16 if precision.autocast_dtype == "float16" else torch.bfloat16
    device_type = "cuda" if torch.cuda.is_available() else "cpu"
    return torch.autocast(device_type=device_type, dtype=dtype, enabled=True)
