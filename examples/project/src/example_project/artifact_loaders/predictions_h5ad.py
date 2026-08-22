"""Load and validate perturbation-expression predictions stored as H5AD."""

from pathlib import Path
from typing import Any, cast

import anndata as ad
import numpy as np
from scipy import sparse


def load(path: Path) -> ad.AnnData:
    """Return a validated prediction matrix with profile and gene identities."""
    if path.suffix != ".h5ad":
        raise ValueError("prediction artifact must use the .h5ad suffix")

    predictions = ad.read_h5ad(path)
    if predictions.n_obs < 1 or predictions.n_vars < 1:
        raise ValueError("prediction matrix must contain profiles and genes")
    if not predictions.obs_names.is_unique:
        raise ValueError("prediction profile IDs must be unique")
    if not predictions.var_names.is_unique:
        raise ValueError("prediction gene IDs must be unique")
    if "perturbation_id" not in predictions.obs:
        raise ValueError("prediction observations must include perturbation_id")
    if predictions.X is None:
        raise ValueError("prediction values must be stored in AnnData.X")

    values = predictions.X
    # Sparse matrices expose only stored nonzero values, avoiding a dense copy.
    finite_values = (
        cast(Any, values).data if sparse.issparse(values) else np.asarray(values)
    )
    if not np.isfinite(finite_values).all():
        raise ValueError("prediction values must be finite")

    return predictions
