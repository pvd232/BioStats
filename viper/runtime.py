"""Apply run-wide reproducibility controls and observe the active Python runtime."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import platform
import random
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch

from .protocol import (
    ComputeSpec,
    CPUBackendContext,
    CPUContext,
    CUDABackendContext,
    CUDAComputeSpec,
    CUDADeviceContext,
    ExecutionContext,
    GeneratorInitializationReceipt,
    LocalHostContext,
    NativeLibraryContext,
    NativeThreadPoolContext,
    NumericalRuntimeContext,
    ProcessStartupReceipt,
    ReproducibilitySpec,
    RNGSeed,
    StartupVariable,
)


@dataclass(frozen=True)
class RuntimeInitialization:
    """Return the live named generators and the startup evidence for one child."""

    numpy_generators: dict[str, np.random.Generator]
    receipt: ProcessStartupReceipt


def process_environment(
    seed: RNGSeed,
    reproducibility: ReproducibilitySpec,
    compute: ComputeSpec,
    *,
    cuda_ordinal: int | None = None,
) -> dict[StartupVariable, str]:
    """Return environment variables that must exist when Python starts."""
    values: dict[StartupVariable, str] = {
        "PYTHONHASHSEED": str(seed),
        "OMP_NUM_THREADS": str(reproducibility.parallelism.torch_intraop_threads),
        "MKL_NUM_THREADS": str(reproducibility.parallelism.torch_intraop_threads),
    }
    workspace = reproducibility.determinism.cublas_workspace_config
    if workspace is not None:
        values["CUBLAS_WORKSPACE_CONFIG"] = workspace
    if isinstance(compute, CUDAComputeSpec):
        if compute.count != 1:
            raise ValueError("startup.distributed: CUDA count must equal one")
        if cuda_ordinal is None:
            raise ValueError("a CUDA stage requires one selected device ordinal")
        values["CUDA_VISIBLE_DEVICES"] = str(cuda_ordinal)
    else:
        values["CUDA_VISIBLE_DEVICES"] = ""
    return values


def _sha256(value: bytes) -> str:
    """Return the lowercase SHA-256 digest of one runtime-state encoding."""
    return hashlib.sha256(value).hexdigest()


def _numpy_state_bytes(generator: np.random.Generator) -> bytes:
    """Encode one NumPy bit-generator state in canonical JSON form."""
    return json.dumps(
        generator.bit_generator.state,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _startup_environment() -> dict[StartupVariable, str]:
    """Read the allowlisted startup variables from the active child process."""
    names: tuple[StartupVariable, ...] = (
        "CUBLAS_WORKSPACE_CONFIG",
        "CUDA_VISIBLE_DEVICES",
        "MKL_NUM_THREADS",
        "OMP_NUM_THREADS",
        "PYTHONHASHSEED",
    )
    return {
        name: os_value
        for name in names
        if (os_value := os.environ.get(name)) is not None
    }


def apply_reproducibility(
    seed: RNGSeed,
    reproducibility: ReproducibilitySpec,
) -> RuntimeInitialization:
    """Apply run controls and return the exact initialized generator objects."""
    random.seed(seed)
    receipts = [
        GeneratorInitializationReceipt(
            family="python",
            seed=seed,
            state_sha256=_sha256(pickle.dumps(random.getstate(), protocol=5)),
        )
    ]

    named_generators = {
        name: np.random.Generator(np.random.PCG64(seed))
        for name in sorted(reproducibility.numpy_randomness.generators)
    }
    receipts.extend(
        GeneratorInitializationReceipt(
            family="numpy_generator",
            name=name,
            seed=seed,
            state_sha256=_sha256(_numpy_state_bytes(generator)),
        )
        for name, generator in named_generators.items()
    )
    if reproducibility.numpy_randomness.capture_legacy_global:
        np.random.seed(seed)
        receipts.append(
            GeneratorInitializationReceipt(
                family="numpy_legacy",
                seed=seed,
                state_sha256=_sha256(pickle.dumps(np.random.get_state(), protocol=5)),
            )
        )

    torch.manual_seed(seed)
    receipts.append(
        GeneratorInitializationReceipt(
            family="torch_cpu",
            seed=seed,
            state_sha256=_sha256(torch.get_rng_state().numpy().tobytes()),
        )
    )
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        receipts.extend(
            GeneratorInitializationReceipt(
                family="torch_cuda",
                seed=seed,
                device_index=index,
                state_sha256=_sha256(state.cpu().numpy().tobytes()),
            )
            for index, state in enumerate(torch.cuda.get_rng_state_all())
        )

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

    return RuntimeInitialization(
        numpy_generators=named_generators,
        receipt=ProcessStartupReceipt(
            environment=_startup_environment(),
            reproducibility=reproducibility,
            generators=tuple(receipts),
        ),
    )


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


def _nvidia_driver_version() -> str:
    """Read the NVIDIA driver version visible to the active child."""
    try:
        output = subprocess.run(
            (
                "nvidia-smi",
                "--query-gpu=driver_version",
                "--format=csv,noheader",
            ),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("CUDA backend driver identity is unavailable") from exc
    version = output.splitlines()[0].strip() if output.splitlines() else ""
    if not version:
        raise RuntimeError("CUDA backend driver identity is empty")
    return version


def _cuda_backend() -> CUDABackendContext:
    """Observe the single CUDA device exposed to the active child."""
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("the CUDA child must expose exactly one device")
    properties = torch.cuda.get_device_properties(0)
    cudnn_version = torch.backends.cudnn.version()
    return CUDABackendContext(
        gpu_devices=(
            CUDADeviceContext(
                ordinal=0,
                model=properties.name,
                compute_capability_major=properties.major,
                compute_capability_minor=properties.minor,
                memory_bytes=properties.total_memory,
            ),
        ),
        nvidia_driver_version=_nvidia_driver_version(),
        pytorch_cuda_version=torch.version.cuda or "unreported",
        cudnn_version=str(cudnn_version or "unreported"),
    )


def select_cuda_device(model: str) -> int:
    """Return the first host CUDA ordinal whose model matches the request."""
    if not torch.cuda.is_available():
        raise RuntimeError("requested CUDA is unavailable")
    for ordinal in range(torch.cuda.device_count()):
        if torch.cuda.get_device_properties(ordinal).name == model:
            return ordinal
    raise RuntimeError(f"requested CUDA device model is unavailable: {model}")


def observe_local_execution(compute: ComputeSpec) -> ExecutionContext:
    """Capture local host, CPU, backend, and numerical runtime facts."""
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
        backend=(
            _cuda_backend()
            if isinstance(compute, CUDAComputeSpec)
            else CPUBackendContext()
        ),
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
    )


def autocast_context(reproducibility: ReproducibilitySpec) -> Any:
    """Construct the run-wide autocast context for the active backend."""
    precision = reproducibility.precision
    if not precision.autocast_enabled:
        return torch.autocast(device_type="cpu", enabled=False)
    dtype = torch.float16 if precision.autocast_dtype == "float16" else torch.bfloat16
    device_type = "cuda" if torch.cuda.is_available() else "cpu"
    return torch.autocast(device_type=device_type, dtype=dtype, enabled=True)
