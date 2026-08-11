# PPI and GO Fusion

- Original conversation: [PPI and GO Fusion](chatgpt-conversation://69f0e2ef-ab9c-83ea-add5-a288a15f3fbc)
- Archive type: substantive reconstruction; not a verbatim transcript.
- Relevant supplied sources: `02-Ota_Causal_Networks.pdf`, `04-ReplogleK562.pdf`.

## Question addressed

The conversation examined how a biological graph was constructed by combining a protein-protein interaction (PPI) network with Gene Ontology (GO) information, what “maximum additional interactors = 0” means, and how these choices change when the graph is used as a prior embedding for a perturbation-response model.

## Conceptual construction

PPI and GO provide different evidence:

- PPI supplies physical or functional edges between proteins.
- GO supplies annotations describing biological process, molecular function, and cellular component.

A fused graph typically begins with a seed set of genes/proteins. PPI edges are collected among those seeds, optionally expanding the node set with neighboring interactors. GO can then be used to add semantic similarity, filter or weight PPI edges, create gene-GO bipartite structure, or derive gene features that are fused with PPI-derived features.

A generic weighted fusion can be written

\[
A_{\text{fused}}=\alpha A_{\text{PPI}}+(1-\alpha)S_{\text{GO}},
\]

where (A_{\text{PPI}}) is a PPI adjacency matrix, (S_{\text{GO}}) is a gene-gene GO similarity matrix, and (\alpha\) controls the balance. Another common construction retains PPI topology and attaches GO vectors (X_{\text{GO}}) as node features instead of converting GO into edges.

## Meaning of zero additional interactors

“Maximum additional interactors = 0” normally means that the database may connect the submitted proteins to one another but may not add new neighboring proteins outside the submitted list. This keeps the graph node universe fixed.

Advantages:

- Exact alignment to the perturbation/gene axis.
- No high-degree hubs introduced merely to connect the network.
- Easier provenance and leakage control.
- Comparable graph size across experiments.

Costs:

- Sparse or disconnected graphs.
- Loss of biologically meaningful mediator proteins.
- Greater dependence on incomplete PPI coverage.
- Potentially poor representation for lightly studied genes.

Allowing extra interactors can improve connectivity but changes the object: the graph becomes an expanded mechanistic neighborhood, not simply a graph over modeled perturbations.

## Considerations for a perturbation prior

For held-out perturbation prediction, the graph must be inference-legal. Static PPI and ontology annotations are generally legal, whereas response-derived clusters, treated-cell summaries, or labels computed using held-out responses are not.

Important design choices include:

- Fix the gene axis before graph construction.
- Record database version, evidence channels, confidence threshold, and identifier mapping.
- Avoid silently treating “no edge” as biological noninteraction; it may be missing evidence.
- Separate topology from node attributes so ablations can identify what helps.
- Normalize high-degree hubs or use degree-aware propagation.
- Preserve disconnected nodes with self-features rather than dropping them.
- Compare PPI-only, GO-only, early fusion, and late fusion.

## Embedding options

1. Spectral or diffusion embedding of the PPI graph.
2. Node2Vec/random-walk embedding.
3. GNN trained on a legitimate auxiliary objective.
4. GO sparse vectors reduced by SVD/PCA.
5. Separate PPI and GO encoders followed by concatenation or learned gated fusion.

For a mechanistic prior, separate encoders followed by controlled fusion are often easier to audit than collapsing all evidence into one adjacency matrix.

## Main conclusion

PPI and GO should not be treated as interchangeable evidence. PPI is relational topology; GO is curated semantic annotation. The safest perturbation-model design preserves that distinction, evaluates each block independently, and only then learns or specifies how to fuse them.

