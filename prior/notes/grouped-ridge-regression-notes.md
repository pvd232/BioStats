# Grouped Ridge Regression Notes

These notes were pulled from the referenced ChatGPT conversation on July 16, 2026 and condensed into project form.

## Core idea

Ordinary linear regression fits a linear map from features to outcomes:

\[
\hat{y} = X\hat{\beta}
\]

with

\[
\hat{\beta}_{OLS} = (X^\top X)^{-1}X^\top y
\]

when `X^T X` is invertible.

Geometrically, `\hat{y}` is the orthogonal projection of `y` onto the column space of `X`.

Ridge regression adds a shared `L2` penalty:

\[
\hat{\beta}_{ridge} = (X^\top X + \lambda I)^{-1}X^\top y
\]

This stabilizes the inverse by lifting small eigenvalues of `X^T X`.

Grouped ridge replaces the single scalar penalty with group-specific penalties:

\[
\hat{\beta}_{grouped} = (X^\top X + \Lambda)^{-1}X^\top y
\]

where `\Lambda` is block diagonal, typically one block per feature family.

## Interpretation

Ordinary ridge is isotropic in coefficient space because the penalty is `\lambda I`. Every coefficient direction is treated equally.

Grouped ridge is not globally isotropic. It is block-isotropic and globally anisotropic: each feature group is treated uniformly within the group, but different groups can be shrunk by different amounts.

Bayesian view:

- Ridge: `\beta \sim N(0, \tau^2 I)`
- Grouped ridge: `\beta_k \sim N(0, \tau_k^2 I)`

So grouped ridge is equivalent to assigning each feature family its own prior variance.

## Useful matrix view

OLS fitted responses can be written as:

\[
\hat{y} = X(X^\top X)^{-1}X^\top y
\]

The projection matrix

\[
P_X = X(X^\top X)^{-1}X^\top
\]

has entries

\[
(P_X)_{ij} = x_i^\top (X^\top X)^{-1} x_j
\]

which can be read as a covariance-adjusted similarity between observations `i` and `j`.

Ridge changes this to:

\[
X(X^\top X + \lambda I)^{-1}X^\top
\]

and grouped ridge changes it to:

\[
X(X^\top X + \Lambda)^{-1}X^\top
\]

So grouped ridge can be viewed as defining a group-aware similarity geometry over observations.

## Marginal vs joint

`X^T y` is the vector of raw feature-response alignments. Its `j`th entry is:

\[
(X^\top y)_j = \sum_{i=1}^n x_{ij} y_i
\]

This is "marginal" because each feature is aligned with `y` on its own, before correcting for correlations with other features.

Multiplying by `(X^T X)^{-1}` converts those marginal alignments into joint regression coefficients by accounting for feature scale and feature correlation.

## MANTRA family64 flow

The MANTRA builder discussed in the conversation uses grouped ridge as a map from concatenated prior features into response-coefficient space, then applies PCA.

Let:

- `n` = number of perturbations
- `p` = concatenated prior feature width
- `d` = response coefficient dimension

The grouped-ridge stage is:

\[
X \in \mathbb{R}^{n \times p}
\]

\[
C \in \mathbb{R}^{n \times d}
\]

\[
B = (X^\top X + \Lambda)^{-1} X^\top C
\]

with

\[
B \in \mathbb{R}^{p \times d}
\]

Then predicted response coefficients are:

\[
\hat{C} = X B
\]

with

\[
\hat{C} \in \mathbb{R}^{n \times d}
\]

The important distinction is:

- `B` is the learned linear operator from prior-feature space to response-coefficient space
- `\hat{C}` is the per-perturbation representation after applying that operator

The downstream dimensionality reduction is applied to `\hat{C}`, not to `B`.

If the response coefficient dimension is `d = 210`, then the core shape flow is:

`n x p -> p x 210 -> n x 210 -> n x 64`

More explicitly:

1. Start with concatenated prior features: `X` is `n x p`
2. Learn grouped-ridge map: `B` is `p x 210`
3. Apply map to every perturbation: `\hat{C} = X B` is `n x 210`
4. Fit PCA on fit-split rows of `\hat{C}` and project to family64: output is `n x 64`

## Practical takeaway

If we want to use this conversation inside the project, the most reusable mental model is:

- Grouped ridge learns how prior feature families map into response space
- The actual perturbation embedding is the predicted response vector `\hat{C}_i`
- PCA then compresses those response vectors into a lower-dimensional family representation

## Suggested next artifacts

If helpful, this note can be split into:

- a short math primer
- a MANTRA-specific implementation note
- a one-page diagram of the `n x p -> n x 210 -> n x 64` pipeline
