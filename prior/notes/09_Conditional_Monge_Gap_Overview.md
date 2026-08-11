# Conditional Monge Gap Overview

- Original conversation: [Conditional Monge Gap Overview](chatgpt-conversation://6a0932a3-4600-83ea-a60d-e932d92a6748)
- Archive type: substantive reconstruction; not a verbatim transcript.
- Relevant supplied source: `03-STRAND.pdf` for the broader sequence-conditioned transport context.

## Paper and motivation

The conversation discussed Driessen et al., *Towards Generalizable Single-Cell Perturbation Modeling via the Conditional Monge Gap* (2025). The motivation was that fitting an independent transport map for each perturbation cannot naturally generalize to an unseen treatment. A shared conditional map can aggregate information across conditions.

For condition (i), let (\mu_i) be the control/source distribution, (\nu_i) the treated/target distribution, and (c_i) a covariate describing the condition. Rather than fit maps (T_i) separately, learn

\[
T_\theta(x,c_i).
\]

## Distribution matching and the Monge gap

The map should push the source distribution toward the target:

\[
T_{\theta\#}\mu_i\approx\nu_i,
\]

where (T_{\#}\mu) denotes the pushforward distribution. Distribution matching alone is underdetermined: many maps can produce the same output distribution while pairing cells implausibly.

The Monge-gap regularizer measures how far the learned map is from an optimal Monge transport map under the chosen cost. A schematic objective is

\[
\sum_i
\operatorname{Sinkhorn}\big(T_{\theta\#}\mu_i,\nu_i\big)
+\lambda\,\operatorname{MongeGap}(T_\theta;\mu_i,c_i).
\]

The first term matches predicted and observed treated distributions; the second constrains the geometry of the map.

## Why conditioning helps

Parameters are shared across treatments, so the model can learn regularities across conditions and interpolate or extrapolate to a new covariate (c_*\). Generalization is only credible when (c\) contains meaningful structure: drug descriptors, dose, target-gene embeddings, pathway annotations, or other inference-available features. A categorical ID alone cannot describe a never-seen treatment.

## Relationship to entropic OT

Sinkhorn-based losses make distribution comparison computationally tractable and differentiable. The learned neural map is not simply the Sinkhorn coupling itself. Sinkhorn supplies a training discrepancy; the network supplies an amortized map that can be evaluated on new cells and conditions.

## Relevance to perturbation modeling

The paper was considered closer to the project's objective because it combines cell-state transport with arbitrary treatment covariates. However, it does not remove the core inference constraint: the held-out condition descriptor must be available without observing held-out treated cells.

Open risks include confounding between condition and batch, lack of overlap in control-state support, weak descriptors, multimodal outcomes that a deterministic map cannot express, and good distributional matching with poor cell-level correspondence.

## Bottom line

Conditional Monge Gap turns a collection of condition-specific OT problems into one shared conditional transport learner. Its key contribution is not “OT plus another covariate” in isolation; it is amortized transport with a regularizer that favors geometrically coherent maps and can therefore be evaluated on unseen conditions.

