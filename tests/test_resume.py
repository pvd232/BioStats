"""Runtime tests for exact training-continuation state."""

from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
from torch.optim import Adam
from torch.utils.data import TensorDataset
from torchdata.stateful_dataloader import StatefulDataLoader

from viper.resume import (
    capture_main_process_rng,
    capture_resume_state,
    load_resume_state,
    restore_main_process_rng,
    restore_resume_state,
    save_resume_state,
)


def dataloader(workers: int) -> StatefulDataLoader:
    """Create the deterministic loader used before and after continuation."""
    if workers > 0:
        return StatefulDataLoader(
            TensorDataset(torch.arange(24)),
            batch_size=3,
            shuffle=True,
            generator=torch.Generator().manual_seed(17),
            num_workers=workers,
            in_order=True,
            prefetch_factor=2,
            persistent_workers=False,
        )

    return StatefulDataLoader(
        TensorDataset(torch.arange(24)),
        batch_size=3,
        shuffle=True,
        generator=torch.Generator().manual_seed(17),
        num_workers=0,
        in_order=True,
    )


class ContinuationTests(unittest.TestCase):
    """Verify exact process and DataLoader continuation state."""

    def test_main_process_rng_round_trip(self) -> None:
        """Restore the next Python, NumPy, and PyTorch random values exactly."""
        random.seed(17)
        np.random.seed(17)
        torch.manual_seed(17)
        generators = {"training": np.random.default_rng(17)}

        saved = capture_main_process_rng(
            generators,
            capture_legacy_global=True,
        )
        expected = (
            random.random(),
            float(np.random.random()),
            float(generators["training"].random()),
            float(torch.rand(())),
        )

        random.random()
        np.random.random()
        generators["training"].random()
        torch.rand(())

        restore_main_process_rng(saved, generators)
        actual = (
            random.random(),
            float(np.random.random()),
            float(generators["training"].random()),
            float(torch.rand(())),
        )

        self.assertEqual(actual, expected)

    def test_training_continuation_restores_next_batch(self) -> None:
        """Restore the next shuffled batch with zero or multiple workers."""
        for workers in (0, 2):
            with self.subTest(workers=workers):
                loader = dataloader(workers)
                optimizer = Adam([torch.nn.Parameter(torch.tensor(1.0))], lr=0.01)
                generators = {"training": np.random.default_rng(17)}
                iterator = iter(loader)
                next(iterator)

                continuation = capture_resume_state(
                    optimizer,
                    loader,
                    generators,
                    capture_legacy_global=True,
                )
                expected_batch = next(iterator)[0]

                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "resume_state.pt"
                    save_resume_state(path, continuation)
                    loaded = load_resume_state(path)

                restored_loader = dataloader(workers)
                restored_optimizer = Adam(
                    [torch.nn.Parameter(torch.tensor(1.0))],
                    lr=0.5,
                )
                restored_generators = {
                    "training": np.random.default_rng(999),
                }
                restore_resume_state(
                    loaded,
                    restored_optimizer,
                    restored_loader,
                    restored_generators,
                )

                actual_batch = next(iter(restored_loader))[0]
                self.assertTrue(torch.equal(actual_batch, expected_batch))
                self.assertEqual(
                    restored_optimizer.param_groups[0]["lr"],
                    0.01,
                )


if __name__ == "__main__":
    unittest.main()
