# Mechanistic Priors in Modeling

- Original conversation: [Mechanistic Priors in Modeling](chatgpt-conversation://6a09c21f-3028-83ea-a0b7-301645d9a010)
- Archive type: substantive reconstruction; not a verbatim transcript.
- Relevant supplied sources: `02-Ota_Causal_Networks.pdf`, `04-ReplogleK562.pdf`.

## Problem context

The project sought an inference-legal replacement for the old `family59` branch. `family59` encoded Replogle-style perturbation-family structure derived from observed perturbation responses and Table S3 clustering. It was useful as a teacher or evaluation target but illegal as a direct feature for held-out perturbations.

The target files were described as `Table_S3_mmc3__perturbation_clusters.csv` and its description table. Evaluation clustered one row per perturbation, commonly with HDBSCAN, and measured ARI together with labeled fraction and coverage-adjusted ARI.

## Central distinction

The conversation separated:

- **Teacher/oracle information:** may use fit/tune response-derived geometry to define what should be mimicked.
- **Student inputs at inference:** must not use held-out perturbation responses, held-out OT-derived treated/control summaries, or any feature computed using the held-out response.
- **Legal static/control-only information:** GO, PPI, complexes, pathways, sequence/protein embeddings, subcellular localization, gene-regulatory annotations, and genuinely control-only state information.

## Candidate prior families

The proposed mechanistic blocks included:

1. GO biological process, molecular function, and cellular component.
2. PPI topology and graph embeddings.
3. CORUM protein complexes.
4. Pathway databases and Hallmark gene sets.
5. Subcellular localization.
6. TF identity and TF-target networks such as DoRothEA/OmniPath.
7. Protein domains, sequence embeddings, and structural information.
8. Genetic-essentiality and dependency context where legally available.
9. Disease/phenotype ontology annotations, treated cautiously because their relevance may be indirect.

The conversation emphasized that a “functional family” is not one canonical ontology. It is a designed composite representation, and its provenance and semantics need to be explicit.

## Teacher-student formulation

Let (y_p\) represent teacher family structure for perturbation (p), and (x_p\) a legal prior vector. A student (s_\theta(x_p)) can be trained to recover teacher labels, pairwise affinities, or an embedding whose clustering agrees with the teacher.

Possible objectives include classification,

\[
\mathcal L_{\text{CE}}=-\sum_p \log P_\theta(y_p\mid x_p),
\]

pairwise metric learning,

\[
\mathcal L_{\text{pair}}=\sum_{p,q}\ell\big(\operatorname{sim}(s_\theta(x_p),s_\theta(x_q)),\mathbf 1[y_p=y_q]\big),
\]

or distillation of teacher distances/affinities. The held-out perturbations receive embeddings from (x_p) alone.

## Why exact ARI recovery may fail

Even if Replogle published the clustering procedure, exact reproduction can fail because the paper-level description may omit low-level preprocessing choices: cell/gene filters, normalization, perturbation aggregation, distance metric, dimensionality, random seeds, graph construction, and cluster post-processing. In addition, response-derived clusters can encode dataset-specific effects that static mechanistic annotations genuinely cannot recover.

Therefore, ARI below 0.95 is not automatically an implementation failure. The key diagnostic is to decompose disagreement into:

- missing reconstruction details in the teacher;
- unstable or weakly labeled teacher points;
- biological information absent from legal priors;
- student optimization/capacity limits;
- mismatch between cluster-level ARI and downstream predictive utility.

## Recommended experiment structure

- First reproduce or hash-verify the teacher surface.
- Audit cluster stability under preprocessing and clustering perturbations.
- Measure prior-block coverage by cluster.
- Run single-block and leave-one-block-out ablations.
- Distill pairwise geometry as well as hard labels.
- Evaluate both teacher agreement and downstream held-out response prediction.
- Treat any response-derived feature as teacher-only and fail closed if split provenance is ambiguous.

## Broader conclusion

The replacement should imitate the useful inductive behavior of `family59`, not blindly reproduce its representation. A slightly lower-ARI legal surrogate may be scientifically preferable if it generalizes and improves downstream inference, while a near-perfect surrogate may simply reconstruct dataset-specific response information unavailable at deployment.

