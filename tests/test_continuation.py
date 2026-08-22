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

from mantra_provenance.continuation import (
    capture_main_process_rng,
    capture_training_continuation,
    load_training_continuation,
    restore_main_process_rng,
    restore_training_continuation,
    save_training_continuation,
)


def dataloader(workers: int) -> StatefulDataLoader:
    """Create the deterministic loader used before and after continuation."""

    options: dict[str, object] = {
        "dataset": TensorDataset(torch.arange(24)),
        "batch_size": 3,
        "shuffle": True,
        "generator": torch.Generator().manual_seed(17),
        "num_workers": workers,
        "in_order": True,
    }
    if workers > 0:
        options["prefetch_factor"] = 2
        options["persistent_workers"] = False

    return StatefulDataLoader(**options)


class ContinuationTests(unittest.TestCase):
    def test_main_process_rng_round_trip(self) -> None:
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
        for workers in (0, 2):
            with self.subTest(workers=workers):
                loader = dataloader(workers)
                optimizer = Adam([torch.nn.Parameter(torch.tensor(1.0))], lr=0.01)
                generators = {"training": np.random.default_rng(17)}
                iterator = iter(loader)
                next(iterator)

                continuation = capture_training_continuation(
                    optimizer,
                    loader,
                    generators,
                    capture_legacy_global=True,
                )
                expected_batch = next(iterator)[0]

                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "continuation_state.pt"
                    save_training_continuation(path, continuation)
                    loaded = load_training_continuation(path)

                restored_loader = dataloader(workers)
                restored_optimizer = Adam(
                    [torch.nn.Parameter(torch.tensor(1.0))],
                    lr=0.5,
                )
                restored_generators = {
                    "training": np.random.default_rng(999),
                }
                restore_training_continuation(
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
