# Jurkat Perturbation Dataset

- Original conversation: [Jurkat Perturbation Dataset](chatgpt-conversation://6a06eb61-9990-83ea-9719-e34b33171f5e)
- Archive type: substantive reconstruction; not a verbatim transcript.
- Primary supplied source: `01-jurkat.pdf` (*Transcriptome-wide characterization of genetic perturbations*).

## Question

The conversation asked whether the Jurkat Perturb-seq study provided a supplementary perturbation-family dataset analogous to Replogle K562 Table S3.

## Main conclusion

The answer distinguished between a study containing perturbation groupings, pathway annotations, or clusters and a study releasing a directly analogous, perturbation-level family table with the same semantics as Replogle K562 S3. The Jurkat materials may support constructing family-like labels, but they should not automatically be treated as a drop-in equivalent of Replogle's response-derived perturbation clusters.

## Why the distinction matters

Replogle Table S3 family labels are derived from perturbational response structure. They are not merely GO categories or static gene families. A Jurkat supplement containing gene sets, modules, enriched pathways, guide annotations, or cell-state clusters answers a different question.

To establish equivalence, the Jurkat material would need:

- one record or clearly resolvable label per perturbation;
- an explicit derivation from perturbation-level response profiles;
- documented preprocessing and clustering;
- interpretable cluster/family descriptions;
- enough coverage for the desired evaluation axis.

## Recommended audit

1. Inventory supplementary tables and deposited data files.
2. Identify the unit of every table: cells, guides, perturbations, genes, modules, or pathways.
3. Determine whether any cluster label is assigned to perturbations themselves.
4. Trace whether labels are response-derived or annotation-derived.
5. Check whether controls, multiple guides, and low-quality perturbations were excluded or merged.
6. Compare the resulting semantics with Replogle S3 before calling it an analogue.

## If no direct table exists

A Jurkat family surface could be reconstructed from perturbation pseudobulk responses using a documented pipeline: quality filtering, perturbation aggregation, response-space normalization, dimensionality reduction or distance construction, clustering, stability analysis, and biological annotation. But that reconstructed surface would be a new derived artifact and should be named and versioned as such.

For held-out inference, it would remain teacher/evaluation information. A legal student would need to predict it from static or control-only priors.

## Bottom line

The relevant Jurkat paper is a valuable perturbation-response resource, but a pathway or module supplement is not automatically the Jurkat equivalent of Replogle Table S3. Equivalence depends on the unit of analysis and derivation of the labels.

