"""Tests for canonical artifact reconstruction and schema validation."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import anndata as ad
import numpy as np
import pandas as pd

from mantra.artifact_loaders.predictions_h5ad import load


def prediction_data(*, include_perturbation_id: bool = True) -> ad.AnnData:
    """Build a small perturbation-by-gene prediction matrix."""
    observations = pd.DataFrame(index=["prediction_1", "prediction_2"])
    if include_perturbation_id:
        observations["perturbation_id"] = ["TP53", "KRAS"]
    variables = pd.DataFrame(index=["GENE1", "GENE2", "GENE3"])
    return ad.AnnData(
        X=np.asarray([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]),
        obs=observations,
        var=variables,
    )


class PredictionH5ADLoaderTests(unittest.TestCase):
    """Verify the canonical prediction loader's structural contract."""

    def test_loader_returns_identified_prediction_matrix(self) -> None:
        """Accept finite predictions with profile, perturbation, and gene IDs."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.h5ad"
            prediction_data().write_h5ad(path)

            loaded = load(path)

        self.assertEqual(loaded.shape, (2, 3))
        self.assertEqual(tuple(loaded.obs["perturbation_id"]), ("TP53", "KRAS"))

    def test_loader_requires_perturbation_identity(self) -> None:
        """Reject a prediction matrix whose observations omit perturbation IDs."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.h5ad"
            prediction_data(include_perturbation_id=False).write_h5ad(path)

            with self.assertRaisesRegex(ValueError, "perturbation_id"):
                load(path)
