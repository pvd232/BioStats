"""Tests for process-start controls and initialized generator evidence."""

import hashlib
import json

import pytest

from viper.protocol import (
    CPUComputeSpec,
    CUDAComputeSpec,
    DataLoaderConfiguration,
    NumPyRandomnessSpec,
    ParallelismSpec,
    ReproducibilitySpec,
    TorchDeterminismSpec,
    TorchPrecisionSpec,
)
from viper.runtime import apply_reproducibility, process_environment


def _controls() -> ReproducibilitySpec:
    """Build the run controls used by startup tests."""
    return ReproducibilitySpec(
        determinism=TorchDeterminismSpec(
            deterministic_algorithms=True,
            deterministic_warn_only=False,
            cudnn_deterministic=True,
            cudnn_benchmark=False,
            cublas_workspace_config=":4096:8",
        ),
        precision=TorchPrecisionSpec(
            float32_matmul_precision="highest",
            cudnn_allow_tf32=False,
            autocast_enabled=False,
            autocast_dtype=None,
        ),
        parallelism=ParallelismSpec(
            process_count=1,
            torch_intraop_threads=1,
            torch_interop_threads=1,
            dataloader=DataLoaderConfiguration(workers=0),
        ),
        numpy_randomness=NumPyRandomnessSpec(
            generators={"augmentation": "PCG64"},
            capture_legacy_global=True,
        ),
    )


def test_process_environment_hides_cuda_from_a_cpu_stage() -> None:
    """Derive the complete allowlisted startup mapping for CPU execution."""
    values = process_environment(7, _controls(), CPUComputeSpec())

    assert values == {
        "PYTHONHASHSEED": "7",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
        "CUDA_VISIBLE_DEVICES": "",
    }


def test_process_environment_rejects_multi_gpu_startup() -> None:
    """Route a multi-device request to the deferred distributed contract."""
    with pytest.raises(ValueError, match="startup.distributed"):
        process_environment(
            7,
            _controls(),
            CUDAComputeSpec(model="NVIDIA L4", count=2),
            cuda_ordinal=0,
        )


def test_named_numpy_receipt_identifies_the_delivered_generator() -> None:
    """Hash the same initialized generator object delivered to StageContext."""
    initialized = apply_reproducibility(7, _controls())
    generator = initialized.numpy_generators["augmentation"]
    receipt = next(
        value
        for value in initialized.receipt.generators
        if value.family == "numpy_generator"
    )
    initial_raw = json.dumps(
        generator.bit_generator.state,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert receipt.name == "augmentation"
    assert receipt.state_sha256 == hashlib.sha256(initial_raw).hexdigest()
    generator.random()
    advanced_raw = json.dumps(
        generator.bit_generator.state,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(advanced_raw).hexdigest() != receipt.state_sha256
