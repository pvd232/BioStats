# Normalization in scRNA-seq

- Original conversation: [Normalization in scRNA-seq](chatgpt-conversation://6a0d2c3f-1150-83ea-88b6-e3733c69c0e6)
- Archive type: substantive reconstruction; not a verbatim transcript.

## Observational cell-type annotation

The conversation clarified that annotating blood cells from overexpression of marker genes is observational enrichment, not causal evidence. A cell is assigned a type because its expression pattern resembles known cell-type signatures. “Marker overexpression” means high expression relative to other cells or a reference, not proof that the marker caused the identity.

## Typical normalization

For count (x_{ig}) of gene (g) in cell (i), library-size normalization computes

\[
\tilde x_{ig}=s\frac{x_{ig}}{\sum_{g'}x_{ig'}},
\]

where (s) is a target total such as (10^4). Log transformation gives

\[
y_{ig}=\log(1+\tilde x_{ig}).
\]

This corrects gross sequencing-depth differences but does not make technical noise disappear, recover absolute molecule counts, or guarantee comparability under strong compositional shifts.

## PPCA

Probabilistic PCA represents an observation (x\in\mathbb R^D) as

\[
x=Wz+\mu+\varepsilon,
\]

with latent (z\sim\mathcal N(0,I)) and isotropic noise (\varepsilon\sim\mathcal N(0,\sigma^2I)). Marginally,

\[
x\sim\mathcal N(\mu,WW^\top+\sigma^2I).
\]

Unlike ordinary PCA's geometric formulation, PPCA is a probabilistic latent-variable model and supplies a likelihood and posterior over latent coordinates.

## VAE architecture discussed

The proposed VAE used input dimension 500, encoder (500\to128\to64), two heads projecting to a 20-dimensional latent mean and log-variance, and decoder (20\to64\to128\to500). It used reconstruction loss plus KL regularization, Adam with learning rate (10^{-3}), and 50 epochs.

The phrase “projecting into log-variance space” was clarified. A neural-network head outputs an unconstrained vector

\[
\ell(x)=W_\ell h(x)+b_\ell,
\]

interpreted as (\log \sigma^2(x)). The variance is

\[
\sigma^2(x)=\exp(\ell(x)),
\]

which is necessarily positive. Sampling uses the reparameterization trick,

\[
z=\mu(x)+\exp\!\left(\tfrac12\ell(x)\right)\odot\epsilon,
\qquad \epsilon\sim\mathcal N(0,I).
\]

The head is not literally mapping data into a pre-existing “log-variance space”; it learns parameters that are interpreted as log variances.

## Loss clarification

For a Gaussian latent posterior (q_\phi(z\mid x)), the VAE objective combines reconstruction and

\[
D_{\mathrm{KL}}(q_\phi(z\mid x)\|\mathcal N(0,I))
=-\frac12\sum_j\left(1+\ell_j-\mu_j^2-e^{\ell_j}\right).
\]

MSE reconstruction corresponds to an isotropic Gaussian observation model up to constants and a fixed variance assumption. For count-like scRNA-seq data, negative-binomial or zero-inflated likelihoods may be more biologically/statistically appropriate, depending on the data representation.

## Bottom line

Normalization defines the measurement scale the model sees; annotation remains an observational inference; PPCA supplies a linear Gaussian latent model; and a VAE generalizes this with nonlinear encoders/decoders and per-observation latent uncertainty.

