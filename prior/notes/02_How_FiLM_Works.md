# How FiLM Works

- Original conversation: [How FiLM Works](chatgpt-conversation://6a18de57-dc04-83ea-ab0e-bf52d63a8779)
- Archive type: substantive reconstruction; not a verbatim transcript.

## Definition

FiLM means **Feature-wise Linear Modulation**. It lets a conditioning input alter an intermediate representation through a learned, per-feature affine transformation.

For hidden representation (h\in\mathbb R^d) and condition (c), two learned functions produce

\[
\gamma(c),\beta(c)\in\mathbb R^d.
\]

FiLM applies

\[
h' = \gamma(c)\odot h + \beta(c),
\]

where (\odot) denotes elementwise multiplication. (\gamma) scales each feature and (\beta) shifts it. A common residual parameterization uses (1+\gamma(c)) so that zero-initialized modulation begins near the identity:

\[
h'=(1+\gamma(c))\odot h+\beta(c).
\]

## Interpretation

FiLM does not simply concatenate context with features. It makes the condition control how existing features are interpreted. Scaling can strengthen, weaken, or reverse a channel; shifting can activate or suppress it. Thus one shared backbone can behave differently for different perturbations, doses, cell types, or other contexts.

## Perturbation-model example

The conversation decomposed a conditional GRN model into:

1. `ConditionEncoder`: maps perturbation identity and dose ((r,d)) into condition vector (c).
2. `GeneGNNLayer`: propagates gene features through adjacency (A), then applies FiLM from (c).
3. `GRNGNN`: combines gene embeddings, stacked graph layers, conditioning, and a readout to predict gene-expression deltas.

One possible layer is

\[
\tilde H=A H W,
\qquad
H'=\sigma\!\left(\gamma(c)\odot \tilde H+\beta(c)\right),
\]

where (H\in\mathbb R^{G\times d}) contains (d)-dimensional features for (G) genes, (A\) is a gene graph, (W) is a learned weight matrix, and (\sigma) is a nonlinearity. The condition-specific (\gamma,\beta) may be broadcast across genes or made gene-specific.

## FiLM versus alternatives

- Concatenation gives the next layer access to context but leaves it to learn the interaction indirectly.
- Additive conditioning supplies only a shift.
- Gating supplies mostly multiplicative control.
- FiLM supplies both multiplicative and additive control with modest computational cost.
- Cross-attention is more expressive for token-to-token interaction but substantially heavier.

## Where to place FiLM and normalization

The discussion connected FiLM to LayerNorm in a GNN. A stable pattern is graph/message transformation, normalization, FiLM, nonlinearity, and optional residual connection. Exact order is empirical because normalization after FiLM can partially erase condition-dependent scale and shift. If preserving modulation magnitude is important, normalization usually precedes FiLM. Output heads generally remain unnormalized, while gradient clipping addresses optimization stability rather than feature normalization.

## Failure modes

- Unbounded (\gamma) can destabilize training.
- Strong conditioning may cause shortcut learning, with the backbone ignored.
- A low-quality condition vector cannot be repaired by FiLM.
- Broadcasting one modulation vector across all genes may be too coarse.
- Normalization placed after FiLM can remove part of the intended effect.

## Bottom line

FiLM is a parameter-efficient conditional control mechanism. In perturbation modeling, it is most defensible when the shared computation is broadly valid across conditions but feature relevance or magnitude changes systematically with perturbation identity, dose, or cell context.

