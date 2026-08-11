# AdaPert Paper Overview - imported conversation

Imported from: [AdaPert Paper Overview](chatgpt-conversation://6a574d8e-d680-83ea-ba2f-47f29f47e45c)

Original conversation ID: `6a574d8e-d680-83ea-ba2f-47f29f47e45c`

This project note preserves the substance of the referenced ChatGPT conversation, with equations normalized for Markdown and source claims checked against the saved AdaPert paper. It is a curated local import rather than a byte-for-byte ChatGPT export.

## Local sources

- [AdaPert arXiv/ICML paper PDF](../output/pdf/adapert-arxiv-2602.18885.pdf) - arXiv:2602.18885v2, 34 pages; the first page identifies it as an ICML 2026 proceedings paper.
- [Official arXiv source archive](../sources/adapert/adapert-arxiv-source.tar.gz) - LaTeX, bibliography, tables, and figures supplied by the authors.
- [arXiv metadata](../sources/adapert/arxiv-metadata.xml)
- [arXiv record](https://arxiv.org/abs/2602.18885)
- [ICLR 2026 GEM workshop version](https://openreview.net/forum?id=Vnx6ZyV6cw)

## 1. Initial rundown of AdaPert

### User

Can you give me a rundown on the AdaPert paper?

### Assistant

AdaPert, *Learning Adaptive Perturbation-Conditioned Contexts for Robust Transcriptional Response Prediction*, argues that a central failure mode in perturbation prediction is **mean collapse**. Because only a small fraction of genes respond strongly to any one perturbation, an ordinary high-dimensional regression loss can be minimized by predicting something close to the average perturbation response. That can produce respectable global correlation while blurring perturbation identity, missing true differentially expressed genes (DEGs), and generating false positives.

The paper's main criticism of prior graph models is that biological knowledge graphs are commonly used as dense, static priors shared by every perturbation. AdaPert instead learns a perturbation-conditioned sparse node-induced subgraph. Conceptually:

```text
perturbed gene
    -> semantic embedding and global biological KG
    -> perturbation-conditioned node scoring
    -> sparse selected subgraph
    -> pooled context representation
    -> expression decoder
```

The adaptive objective has three pieces:

1. A global reconstruction loss over the perturbed expression profile.
2. A robust non-DEG loss that suppresses predicted changes for genes expected not to respond.
3. An alignment loss that makes the selected subgraph context reflect the observed DEG response pattern during training.

On K562.Replogle, the paper reports Pearson-delta values of 0.298 for GEARS, 0.442 for MorPH, 0.580 for TxPert, and 0.619 for AdaPert. AdaPert also improves DEG-aware metrics and perturbation discrimination.

The conceptual contrast with RICO is:

- AdaPert asks: which region of a biological graph is relevant to this perturbation?
- RICO asks: which measured response programs from fit perturbations are useful for predicting this one?

AdaPert retrieves or selects graph context; RICO retrieves empirical response programs.

## 2. How the knowledge graph, subgraph, and GNN differ

### User

How do the GNN, knowledge graph, and subgraph work?

### Assistant

They are distinct objects:

- The **knowledge graph** is the fixed biological prior: nodes are genes and edges encode relationships such as protein interactions, regulation, pathways, or complexes.
- The **subgraph** is the perturbation-specific subset of nodes and induced edges chosen from that prior.
- The **GNN** is the parameterized computation that exchanges information over the edges of whichever graph it receives.

At layer \(\ell\), a generic message-passing GNN updates node \(i\) as

\[
h_i^{(\ell+1)} = U_\ell\!\left(
h_i^{(\ell)},
\operatorname{AGG}_{j\in\mathcal N(i)}
M_\ell(h_i^{(\ell)},h_j^{(\ell)},e_{ij})
\right).
\]

One layer communicates across one-hop neighborhoods; two layers allow information to travel across two hops. In AdaPert, each candidate node is scored using both its structural graph embedding and a semantic embedding of the perturbed gene. Gumbel-Softmax sampling and thresholding select a sparse node set. The original KG remains fixed; the learned mask changes with the perturbation.

## 3. Could an induced-subgraph embedding query a Hopfield memory?

### User

Could you form an embedding from the induced subgraph - for example, a Laplacian embedding for each perturbation - and use that as the identity embedding for my Hopfield? Please do not just tell me what I want to hear.

### Assistant

Yes in principle, but independently eigendecomposing each induced subgraph is not the cleanest representation.

For perturbation \(p\), an induced subgraph Laplacian could be written

\[
L_p = I-D_p^{-1/2}A_pD_p^{-1/2}=U_p\Lambda_pU_p^\top.
\]

The problems with using \(U_p\) directly are:

- Different subgraphs have different sizes.
- Eigenvectors are sign-indeterminate.
- Repeated or near-repeated eigenvalues permit arbitrary rotations within eigenspaces.
- Isomorphic subgraphs with different gene identities can share the same spectrum.
- Small changes in the selected node mask can cause unstable eigenvectors.

A safer spectral construction uses one global KG Laplacian,

\[
L=U\Lambda U^\top,
\]

and represents every perturbation-specific soft mask \(m_p\in[0,1]^{|V|}\) in the same basis:

\[
z_p^{\mathrm{spectral}}=U_k^\top m_p.
\]

This gives every perturbation the same dimensionality and coordinate semantics. However, it primarily describes where the selected nodes lie in the global graph and incompletely captures internal edge structure.

A rooted diffusion representation may better match the perturbation problem:

\[
r_p(t)=e^{-tL}e_p,
\qquad
\widetilde r_p(t)=m_p\odot e^{-tL}e_p,
\]

where \(e_p\) identifies the perturbed gene. Multiple diffusion times capture local and pathway-scale context.

A robust query should preserve three kinds of information:

\[
z_p=\operatorname{MLP}\left(
z_p^{\mathrm{root}}\Vert
z_p^{\mathrm{selected\ genes}}\Vert
z_p^{\mathrm{topology}}
\right),
\]

with weighted gene-content pooling such as

\[
z_p^{\mathrm{selected\ genes}}=
\frac{\sum_v m_{p,v}h_v}{\sum_v m_{p,v}}.
\]

The supervision contract matters. AdaPert's selector is response-supervised on training perturbations through the DEG alignment target. This is still valid for held-out inference if the selector is trained only on fit perturbations, then frozen, and held-out subgraphs use only static gene/KG information. It should be described accurately as a response-supervised perturbation representation rather than a purely mechanistic prior.

For a Hopfield reader with fit-bank keys \(q_i\) and response-program values \(v_i\), a held-out graph query \(q_p\) could retrieve via

\[
a_{pi}=\operatorname{softmax}_i\left(\beta\,\operatorname{sim}(q_p,q_i)\right),
\qquad
\widehat y_p=\sum_i a_{pi}v_i.
\]

The key uncertainty is whether graph-context similarity predicts response-program similarity. The graph encoder should therefore be calibrated for retrieval rather than assumed to have the right geometry.

Suggested representation ablation:

\[
\begin{aligned}
q_p^{(1)} &= \text{root-gene prior only},\\
q_p^{(2)} &= \text{weighted selected-node pooling},\\
q_p^{(3)} &= U_k^\top m_p,\\
q_p^{(4)} &= \text{rooted diffusion + content pooling + spectral mask}.
\end{aligned}
\]

The prior expressed in the original conversation was that content pooling plus rooted diffusion would likely provide most of the value, while per-subgraph eigenvectors alone would probably be weak.

## 4. Does AdaPert predict in a lower-dimensional gene space?

### User

Does AdaPert predict in a lower-dimensional gene space? How do they do dimension reduction?

### Assistant

AdaPert predicts a full gene-expression profile; it does not use a PCA/cNMF-style low-rank response basis as its output space. It does, however, use low-dimensional internal representations.

The paper's encoder maps the control expression profile to a latent control-state representation. Separately, the selected graph nodes are sum-pooled into a fixed-dimensional perturbation context:

\[
z_{\mathrm{context}}=\sum_{v\in V(G_p)}h_v.
\]

Those representations condition a decoder that predicts the full perturbed expression profile. Thus:

- Output gene dimension: full benchmark gene space.
- Node/structural embedding dimension: learned and low-dimensional.
- Pooled perturbation context: learned and low-dimensional.
- Response target: not explicitly restricted to a fixed low-rank basis.

This differs from RICO, where response compression is itself a modeling assumption:

\[
c_p\in\mathbb R^r,
\qquad
\widehat y_p=Bc_p.
\]

AdaPert has more freedom in output space; RICO gains statistical sharing and denoising if the response basis is well chosen.

## 5. Mathematical case for complementarity with a Hopfield query

### User

Is there any mathematical reason to believe an AdaPert graph embedding would be useful as the learned Hopfield query or as complementary augmentation? Account strictly for the mathematics and inductive biases.

### Assistant

There is a coherent reason, but no general guarantee. Let \(X\) be the current perturbation representation, \(G\) the AdaPert-style graph representation, and \(Y\) the response program. The graph view adds population-level predictive information precisely when

\[
I(Y;G\mid X)>0,
\]

or equivalently when

\[
\mathbb E[Y\mid X,G]\neq\mathbb E[Y\mid X].
\]

For unrestricted Bayes predictors under squared loss, conditioning on more information cannot increase population risk:

\[
R_{X,G}\le R_X.
\]

That does not imply finite-sample improvement: a noisy or redundant graph branch can increase estimation variance and overfitting.

The graph branch changes the retrieval kernel. If the current and graph views define

\[
K_x(p,i)=\langle\phi_x(x_p),\phi_x(x_i)\rangle,
\qquad
K_g(p,i)=\langle\phi_g(g_p),\phi_g(g_i)\rangle,
\]

then a nonnegative mixture

\[
K=\alpha K_x+(1-\alpha)K_g
\]

is a valid positive-semidefinite kernel and is equivalent to retrieval in the direct-sum feature space

\[
\Phi(p)=
\begin{bmatrix}
\sqrt\alpha\,\phi_x(x_p)\\
\sqrt{1-\alpha}\,\phi_g(g_p)
\end{bmatrix}.
\]

This is the cleanest mathematical account of complementary augmentation: two views provide two notions of neighborhood.

The graph view can reduce variance by sharing parameters and imposing graph smoothness:

\[
\sum_{(i,j)\in E}\|q_i-q_j\|^2=\operatorname{tr}(Q^\top LQ).
\]

That helps only when graph adjacency is aligned with response similarity. It introduces bias when connected genes have opposite, asymmetric, or unrelated perturbation effects.

Redundancy occurs when the graph view is largely recoverable from the existing view,

\[
g_p\approx h(x_p),
\]

so that \(I(Y;G\mid X)\approx0\). In that case, graph features duplicate useful directions and add nuisance variation.

Hopfield retrieval is particularly sensitive because similarities are exponentiated:

\[
a_{pi}\propto e^{\beta s_{pi}}.
\]

If a graph branch changes similarities by \(\delta_{pi}\), relative retrieval odds change by

\[
\frac{a'_{pi}/a'_{pj}}{a_{pi}/a_{pj}}
=e^{\beta(\delta_{pi}-\delta_{pj})}.
\]

At high \(\beta\), modest graph noise can reorder the memory bank sharply.

A safer design keeps branches normalized and inspectable:

\[
s_{pi}=\alpha_p\langle q_p^x,k_i^x\rangle
+(1-\alpha_p)\langle q_p^g,k_i^g\rangle.
\]

An even safer alternative computes separate retrieval distributions and mixes their predictions, avoiding raw cross-branch scale competition before softmax.

Evidence of true complementarity should be conditional: test whether graph similarity explains residual response similarity after accounting for the current query, and then test whether the combined view improves held-out bank-neighbor quality and final prediction.

## 6. What exactly is a GNN?

### User

Can we work through the math of what exactly a GNN is first?

### Assistant

Let a graph be \(G=(V,E)\) with adjacency matrix \(A\in\mathbb R^{n\times n}\). Each node has an initial feature vector \(x_i\in\mathbb R^{d_0}\), stacked as

\[
X\in\mathbb R^{n\times d_0},
\qquad
H^{(0)}=X.
\]

A generic message-passing layer has a message function, permutation-invariant aggregation, and update:

\[
m_{j\to i}^{(\ell)}=
M_\ell(h_i^{(\ell)},h_j^{(\ell)},e_{ij}),
\]

\[
m_i^{(\ell)}=
\operatorname{AGG}\{m_{j\to i}^{(\ell)}:j\in\mathcal N(i)\},
\]

\[
h_i^{(\ell+1)}=
U_\ell(h_i^{(\ell)},m_i^{(\ell)}).
\]

Aggregation must be invariant to neighbor ordering; sums, means, and maxima are standard choices.

For a simple linear message and sum aggregation,

\[
h_i^{(\ell+1)}=
\sigma\left(
\sum_{j\in\mathcal N(i)}W^{(\ell)}h_j^{(\ell)}
\right).
\]

Adding self-loops gives \(\widetilde A=A+I\). To avoid confounding degree with magnitude, define

\[
\widetilde D_{ii}=\sum_j\widetilde A_{ij},
\qquad
\widehat A=widetilde D^{-1/2}\widetilde A\widetilde D^{-1/2}.
\]

The standard GCN layer is

\[
\boxed{
H^{(\ell+1)}=
\sigma\left(\widehat A H^{(\ell)}W^{(\ell)}\right)
}.
\]

Here \(\widehat A H\) mixes information across nodes according to the graph, while \(HW\) mixes feature coordinates using learned parameters. An \(L\)-layer GNN has an \(L\)-hop receptive field in the absence of skip or global operations.

The normalized Laplacian is

\[
L_{\mathrm{sym}}=I-D^{-1/2}AD^{-1/2},
\]

so normalized adjacency propagation is related to

\[
D^{-1/2}AD^{-1/2}=I-L_{\mathrm{sym}}.
\]

Repeated propagation is therefore a graph-smoothing or low-pass operation. This supplies the inductive bias that connected nodes should exchange and partially share information. Too many layers can cause **oversmoothing**, where node representations become difficult to distinguish.

A graph-attention layer replaces fixed degree-normalized neighbor weights with learned coefficients:

\[
h_i^{(\ell+1)}=
\sigma\left(
\sum_{j\in\mathcal N(i)\cup\{i\}}
\alpha_{ij}^{(\ell)}W^{(\ell)}h_j^{(\ell)}
\right).
\]

Finally, a node-level GNN produces \(H^{(L)}\in\mathbb R^{n\times d_L}\). A graph or subgraph embedding requires a permutation-invariant readout:

\[
z_G=\operatorname{READOUT}\{h_i^{(L)}:i\in V\},
\]

such as sum, mean, or attention-weighted pooling. This pooled vector is the object that could serve as one view of perturbation identity for a Hopfield memory.

## Source-checked notes

- The saved paper's first page states: *Proceedings of the 43rd International Conference on Machine Learning, Seoul, South Korea. PMLR 306, 2026.* The source archive also contains `main_camera_ready_icml.tex` and the ICML 2026 style files.
- The arXiv source is version 2, dated 5 July 2026. The earlier ICLR 2026 GEM workshop version remains available through OpenReview.
- Section 3.3 defines structural node embeddings by message passing, semantic perturbation embeddings from gene descriptions, perturbation-conditioned node scores, Gumbel-Softmax node selection, and sum pooling of selected node embeddings.
- Section 3.4 defines global reconstruction, non-DEG Huber, and DEG-alignment losses.
- Table 1 supports the K562.Replogle Pearson-delta values quoted above.
- The paper uses a low-dimensional internal control/context representation but decodes a full expression profile; it does not introduce a fixed low-rank output basis of the RICO/cNMF kind.

