# Optimal Transport Explained

- Original conversation: [Optimal Transport Explained](chatgpt-conversation://6a05796b-3264-83ea-bae5-9da7f62edd1a)
- Archive type: substantive reconstruction; not a verbatim transcript.
- Relevant supplied sources: `03-STRAND.pdf`, `02-Ota_Causal_Networks.pdf`.

## Discrete optimal transport

Let source points (x_1,\dots,x_n) carry masses (a\in\mathbb R_+^n), and target points (y_1,\dots,y_m) carry masses (b\in\mathbb R_+^m), usually with equal total mass. A transport plan (\Pi\in\mathbb R_+^{n\times m}) specifies how much source mass (i) is sent to target (j).

The constraints

\[
\Pi\mathbf 1_m=a,
\qquad
\Pi^\top\mathbf 1_n=b
\]

mean that each row sums to the available source mass and each column sums to the required target mass. If (C_{ij}=c(x_i,y_j)) is the cost, balanced Kantorovich OT solves

\[
\min_{\Pi\ge0}\langle \Pi,C\rangle
\quad\text{subject to}\quad
\Pi\mathbf 1=a,\;\Pi^\top\mathbf 1=b.
\]

For a metric ground cost, the optimized value defines a Wasserstein distance (or its (p\)-th power, depending on convention). Thus “minimizing the OT objective” and “computing Wasserstein distance” are not different operations; the distance is the optimal value under a particular cost and constraints.

## Entropic regularization

Entropic OT adds a strictly convex entropy/KL term:

\[
\min_{\Pi\in U(a,b)}
\sum_{ij}\Pi_{ij}C_{ij}
+\varepsilon\sum_{ij}\Pi_{ij}(\log\Pi_{ij}-1).
\]

The objective can be written as one double sum because both cost and entropy are elementwise. Regularization makes the solution smoother and usually unique, enables fast Sinkhorn scaling, and improves differentiability of the optimized value with respect to costs and inputs. It does not make every numerical implementation automatically stable.

Defining the Gibbs kernel

\[
K_{ij}=e^{-C_{ij}/\varepsilon},
\]

the solution has form

\[
\Pi^*=\operatorname{diag}(u)K\operatorname{diag}(v),
\]

with (u,v) iteratively scaled to satisfy the marginals. The kernel is a soft affinity induced by transport cost and temperature (\varepsilon), not a kernel method in the generic machine-learning sense.

## Unbalanced OT

Balanced OT forces all mass to match. Unbalanced OT relaxes the marginal constraints with penalties such as

\[
\min_{\Pi\ge0}
\langle\Pi,C\rangle+\varepsilon H(\Pi)
+\tau_a\operatorname{KL}(\Pi\mathbf1\|a)
+\tau_b\operatorname{KL}(\Pi^\top\mathbf1\|b).
\]

This allows mass creation/destruction and can be more appropriate when cell populations differ in abundance, survival, sampling, or support. It is not automatically superior: relaxed marginals can also hide misspecification.

## Sinkhorn divergence

Entropic OT is biased because even a distribution compared with itself can have nonzero regularized cost. The Sinkhorn divergence corrects this:

\[
S_\varepsilon(\mu,\nu)=
OT_\varepsilon(\mu,\nu)
-\tfrac12OT_\varepsilon(\mu,\mu)
-\tfrac12OT_\varepsilon(\nu,\nu).
\]

The self-terms debias the scalar discrepancy. They do **not** create the cross-distribution correspondence used for a barycentric map.

## Coupling versus divergence versus barycentric map

These objects serve different purposes:

- (\Pi_{\mu\nu}): cross coupling between source and target.
- (S_\varepsilon(\mu,\nu)): debiased scalar loss/distance-like quantity.
- Barycentric projection: point prediction derived from the cross coupling,

\[
\hat y_i=rac{\sum_j\Pi_{ij}y_j}{\sum_j\Pi_{ij}}.
\]

The self-couplings (\Pi_{\mu\mu}) and (\Pi_{\nu\nu}) contribute to the Sinkhorn-divergence loss but are not mixed into this cross barycentric map. Therefore one can train or compare with Sinkhorn divergence while still using the cross OT plan for matching or mapping.

## Single-cell interpretation

Cells are empirical samples from source and target distributions. OT can align control and treated populations, create matched baselines, or define training supervision. Whether to use balanced or unbalanced OT depends on whether population mass differences are biological/technical and whether full matching is defensible. Whether to use raw entropic OT or Sinkhorn divergence depends on whether the goal is a coupling, a debiased distributional loss, or both.

## Main conclusion

There is no universal rule to “always use Sinkhorn divergence” in single-cell work. Use the cross transport plan when correspondence or barycentric mapping is needed; use Sinkhorn divergence when a debiased differentiable distribution discrepancy is needed; and keep those roles conceptually separate.

