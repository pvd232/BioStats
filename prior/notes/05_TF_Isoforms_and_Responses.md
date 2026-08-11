# TF Isoforms and Responses

- Original conversation: [TF Isoforms and Responses](chatgpt-conversation://6a0a5c11-622c-83ea-88e1-5e1a8d76b661)
- Archive type: substantive reconstruction; not a verbatim transcript.

## Biochemical hierarchy

A gene is a DNA locus. It can produce multiple transcript isoforms through alternative promoters, transcription start sites, splicing, and polyadenylation. Those transcripts can encode distinct protein isoforms. Thus the hierarchy is:

`TF gene -> transcript isoforms -> protein isoforms`.

Isoforms from the same gene are not unrelated proteins, but neither are they identical copies. They generally share some exons and amino-acid sequence while differing in others.

## Modular TF structure

Transcription factors often contain separable functional modules:

- DNA-binding domain (DBD)
- dimerization domain
- activation or repression domains
- nuclear localization/export signals
- intrinsically disordered regions and regulatory motifs

An isoform may preserve the DBD while changing an activation domain, giving similar binding specificity but different transcriptional consequences. Conversely, an isoform can alter the DBD or dimerization region, changing its targets or interaction partners. Truncation can also produce dominant-negative behavior.

## Shared latent response

The conversation concluded that a shared-but-not-identical latent response is biologically plausible. A useful model is

\[
z_{g,i}=z_g^{\text{shared}}+r_{g,i},
\]

where (z_g^{\text{shared}}) represents response structure shared by isoforms of gene (g), and (r_{g,i}) is an isoform-specific residual.

The shared component may arise from common DNA-binding specificity, common interaction partners, overlapping regulatory programs, or shared dosage effects. The residual captures altered domains, localization, stability, expression, partner choice, and unique targets.

## Correction to an overly weak interpretation

The isoforms do not merely “have one bound gene in common.” Their relationship comes from common genomic origin and shared sequence/domain architecture. They may bind overlapping gene sets, distinct gene sets, or the same loci with different regulatory outcomes. Sequence overlap and domain preservation determine how strong a shared prior should be.

## Modeling implications

A hierarchical model is preferable to forcing all isoforms to share one embedding or treating them as completely independent:

\[
e_{g,i}=e_g+\delta_{g,i},
\qquad
\delta_{g,i}\sim \mathcal N(0,\Sigma_g).
\]

The amount of shrinkage toward (e_g) should depend on biochemical similarity: retained domains, protein-sequence identity, shared DNA motif preference, interaction partners, and observed response concordance.

Evaluation should compare:

- gene-only pooling;
- fully independent isoforms;
- hierarchical shared-plus-residual models;
- domain-aware or sequence-aware sharing.

## Literature mentioned

The conversation referenced the Joung et al. transcription-factor atlas, which tested thousands of annotated human TF splice isoforms with single-cell readouts in human embryonic stem cells, and work by Lambourne and colleagues comparing hundreds of TF isoforms across functional assays. These studies support widespread functional divergence among isoforms while also showing structured relationships within TF genes.

## Bottom line

Same-gene TF isoforms are related by shared origin and often shared domains, but the relationship is graded rather than absolute. A shared latent response is defensible as a hierarchical prior, not as an assumption that the isoforms have identical target sets or effects.

