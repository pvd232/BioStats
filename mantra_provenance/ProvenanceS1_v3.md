# Foundational reproducibility formalism

## 1. Model family and estimator

A family specification $\alpha$ determines:

$$
\alpha
\longmapsto
\left(
\Theta_\alpha,
I_\alpha,
\mathcal{G}_\alpha
\right),
$$

where:

- $\Theta_\alpha$ is the parameter space.
- $I_\alpha$ maps a parameter value to its prediction function.
- $\mathcal{G}_\alpha$ is the resulting family of prediction functions.

Thus:

$$
I_\alpha
:
\Theta_\alpha
\longrightarrow
\mathcal{G}_\alpha.
$$

An estimator specification $\beta$ determines the procedure used to select a parameter value from data.

The run plan $q$ fixes:

- The family specification $\alpha$.
- The estimator specification $\beta$.
- The dataset selection $D_q$.

The final parameter value produced by the run is denoted:

$$
\widehat{\theta}_q
\in
\Theta_\alpha.
$$

Its fitted prediction function is:

$$
\widehat{g}_q
=
I_\alpha
\left(
\widehat{\theta}_q
\right).
$$

## 2. Construction of the run plan

The experiment records and experiment decisions determine $q$:

```text
ExperimentSpec
├── factors and permitted levels
├── replicates and seeds
└── metric identities

VariantSpec
├── selected level for every factor
└── typed stage parameters

ReplicateSpec
└── selected seed
        │
        ▼
experiment decisions
├── run metadata
├── reproducibility controls
├── shared environment
└── ordered stage specifications
        │
        ▼
run plan q
```

Define:

- $\mathcal{M}$ as the set of possible run-metadata records.
- $\mathcal{C}$ as the set of possible reproducibility specifications.
- $\mathcal{H}$ as the set of possible shared-environment specifications.
- $\Omega$ as the set of valid stage specifications.
- $\Omega^+$ as the set of nonempty ordered sequences with members in $\Omega$.

The run-plan space is:

$$
\mathcal{Q}
=
\mathcal{M}
\times
\mathcal{C}
\times
\mathcal{H}
\times
\Omega^+.
$$

A run plan is:

$$
q
=
\left(
m_q,
c_q,
h_q,
\boldsymbol{\omega}_q
\right)
\in
\mathcal{Q}.
$$

### Run metadata

The metadata $m_q$ identifies the run, experiment, variant, replicate, source,
and estimator output. Each experiment replicate has one seed. The run uses the
selected replicate's seed, denoted $\zeta_q$, as its global seed.

### Reproducibility controls

The executor applies $\zeta_q$ to every stage's random-number generators. The
run-wide specification $c_q$ fixes the deterministic-algorithm, precision, and
parallelism controls applied to every stage.

### Shared environment

The shared environment is:

$$
h_q\in\mathcal{H}.
$$

It supplies the requested environment for each stage that uses the shared environment.

### Ordered stage specifications

The stage sequence is:

$$
\boldsymbol{\omega}_q
=
\left\langle
\omega_1,\ldots,\omega_m
\right\rangle
\in
\Omega^+,
\qquad
m\geq 1.
$$

The index $j\in\{1,\ldots,m\}$ identifies a stage’s position in the execution order.

Each $\omega_j$ declares:

- Stage kind.
- Script.
- Inputs.
- Parameters.
- Outputs.
- Optional environment override.

The selected `VariantSpec` supplies the typed parameters implemented by the corresponding stage specs.

The complete plan is:

```text
run plan q
├── metadata m_q
│   └── fixes α, β, Dq, the run identities, and global seed ζq
├── reproducibility c_q
│   └── fixes deterministic-algorithm, precision, and parallelism controls
├── environment h_q
│   └── shared environment
└── stages ω_q = ⟨ω₁, …, ωₘ⟩
    └── exact ordered stage specifications
```

Together, the experiment, variant, replicate, and experiment decisions determine
$q$.

## 3. Permitted runtime states

Each stage uses the shared environment $h_q$ or an environment override declared
by its stage specification. Let $h_{q,j}$ denote the environment selected for
stage $j$.

Let $E_j$ be the set of possible runtime states for stage $j$. The states
permitted by $q$ are:

$$
E_{q,j}
=
\left\{
e_j\in E_j:
e_j\text{ satisfies }h_{q,j}
\text{ and }c_q
\right\}.
$$

The complete permitted runtime-state set is:

$$
E_q
=
\prod_{j=1}^{m}
E_{q,j}.
$$

One execution realizes:

$$
e
=
\left(
e_1,\ldots,e_m
\right)
\in
E_q.
$$

A valid run plan requires:

$$
E_q
\neq
\varnothing.
$$

```text
q
├── shared environment
├── global reproducibility controls
└── exact stage specifications
        │
        ▼
permitted stage states E_q,1, …, E_q,m
        │
        ▼
permitted complete run states E_q
        │
        ▼
one execution realizes e ∈ E_q
```

## 4. Initial training state

The index $j\in\{1,\ldots,m\}$ continues to identify a stage position. Let
$\Omega_{\mathrm{train}}\subseteq\Omega$ be the set of valid training-stage
specifications. Fix one position $k$ such that:

$$
\omega_k
\in
\Omega_{\mathrm{train}}.
$$

The stage $\omega_k$ is therefore a training stage. Let
$T_k\in\mathbb{N}_{>0}$ be its number of optimizer updates. The index
$t\in\{0,\ldots,T_k\}$ identifies a training state within $\omega_k$.
For each $t$, let $\mathcal{S}_{k,t}$ be the set of possible training states
after $t$ updates in $\omega_k$.

Its realized runtime state is:

$$
e_k
\in
E_{q,k}.
$$

When $\omega_k$ begins from initialization, the stage specification and
runtime state produce its initial model parameters:

$$
\theta_k^{(0)}
=
I^\theta_{\alpha,\beta,q}
\left(
\omega_k,
e_k
\right).
$$

The global seed $\zeta_q$ and the realized runtime state initialize the
random-number-generator state:

$$
r_k^{(0)}
=
I^r
\left(
\zeta_q,
e_k
\right).
$$

The stage specification and initial parameters initialize the optimizer state:

$$
o_k^{(0)}
=
I^o_{\beta,q}
\left(
\omega_k,
\theta_k^{(0)}
\right).
$$

The stage specification, dataset, and random-number-generator state initialize the batch state:

$$
b_k^{(0)}
=
I^b_q
\left(
\omega_k,
D_q,
r_k^{(0)}
\right).
$$

The initial training state is:

$$
s_k^{(0)}
=
\left(
\theta_k^{(0)},
o_k^{(0)},
r_k^{(0)},
b_k^{(0)}
\right).
$$

```text
ωₖ + eₖ ───────────────→ θₖ⁽⁰⁾
                             │
                             ▼
                            oₖ⁽⁰⁾

ζq + eₖ ──────────────→ rₖ⁽⁰⁾
                             │
                  ωₖ + Dq ──┴──→ bₖ⁽⁰⁾

sₖ⁽⁰⁾ = (θₖ⁽⁰⁾, oₖ⁽⁰⁾, rₖ⁽⁰⁾, bₖ⁽⁰⁾)
```

When $\omega_k$ continues from an earlier checkpoint, Section 7 defines
$s_k^{(0)}$ as the state reconstructed from that checkpoint.

## 5. Training-state transition

At update $t+1$, compute the gradient:

$$
g_k^{(t+1)}
=
G_{\alpha,\beta,q,t}
\left(
\omega_k,
D_q,
e_k,
\theta_k^{(t)},
r_k^{(t)},
b_k^{(t)}
\right).
$$

Update the optimizer state:

$$
o_k^{(t+1)}
=
A_{\beta,q,t}
\left(
\omega_k,
e_k,
o_k^{(t)},
g_k^{(t+1)}
\right).
$$

Update the model parameters:

$$
\theta_k^{(t+1)}
=
P_{\beta,q,t}
\left(
\omega_k,
e_k,
\theta_k^{(t)},
o_k^{(t+1)}
\right).
$$

Advance the random-number-generator and batch states:

$$
\left(
r_k^{(t+1)},
b_k^{(t+1)}
\right)
=
C_{\alpha,\beta,q,t}
\left(
\omega_k,
D_q,
e_k,
s_k^{(t)}
\right).
$$

Reassemble the next training state:

$$
s_k^{(t+1)}
=
\left(
\theta_k^{(t+1)},
o_k^{(t+1)},
r_k^{(t+1)},
b_k^{(t+1)}
\right).
$$

For the fixed training stage $\omega_k$, these component updates define:

$$
U_{\alpha,\beta,q,t}
\left(
\omega_k,
\cdot,
\cdot,
\cdot
\right)
:
\mathcal{D}
\times
E_{q,k}
\times
\mathcal{S}_{k,t}
\longrightarrow
\mathcal{S}_{k,t+1},
$$

with:

$$
s_k^{(t+1)}
=
U_{\alpha,\beta,q,t}
\left(
\omega_k,
D_q,
e_k,
s_k^{(t)}
\right).
$$

Repeated application for $t=0,\ldots,T_k-1$ produces the training-state
sequence:

$$
s_k^{(0)}
\longmapsto
s_k^{(1)}
\longmapsto
\cdots
\longmapsto
s_k^{(T_k)}.
$$

The complete training-stage dependency is:

$$
q
\longrightarrow
\boldsymbol{\omega}_q
\longrightarrow
\omega_k
\longrightarrow
E_{q,k}
\ni
e_k
\longrightarrow
U_{\alpha,\beta,q,t}
\left(
\omega_k,D_q,e_k,s_k^{(t)}
\right)
\longrightarrow
s_k^{(t+1)}.
$$

## 6. Estimator and strict reproducibility

Let $k_*$ be the position of the training stage whose `model_parameters`
artifact is selected as the estimator output by $q$. The run estimator is:

$$
T_{\alpha,\beta,q}
:
E_q
\longrightarrow
\Theta_\alpha.
$$

It applies the stages fixed by $q$ and returns the terminal model-parameter
value produced by $\omega_{k_*}$:

$$
T_{\alpha,\beta,q}(e)
=
\theta_{k_*}^{(T_{k_*})}.
$$

The plan provides strict parameter reproducibility exactly when:

$$
\forall e,e'\in E_q,
\qquad
T_{\alpha,\beta,q}(e)
=
T_{\alpha,\beta,q}(e').
$$

The common value is:

$$
\widehat{\theta}_q.
$$

Therefore:

$$
\forall e\in E_q,
\qquad
T_{\alpha,\beta,q}(e)
=
\widehat{\theta}_q.
$$

Because $\alpha$ is fixed by $q$, strict parameter reproducibility also gives:

$$
I_\alpha
\left(
T_{\alpha,\beta,q}(e)
\right)
=
I_\alpha
\left(
\widehat{\theta}_q
\right)
=
\widehat{g}_q.
$$

## 7. Stage outputs and terminal training checkpoints

The ordered sequence $\boldsymbol{\omega}_q$ defines the stages of the run. For
each $j\in\{1,\ldots,m\}$, let $y_j$ denote the declared output state produced
by $\omega_j$. A later stage may consume one or more artifacts from $y_j$.

```text
stages of the run

ω₁ ──→ y₁
ω₂ ──→ y₂
⋮
ωₘ ──→ yₘ
```

MANTRA permits replay from a training state when a later stage or attempt may
consume that state as its initial state. A training stage is the maximal
contiguous sequence of updates ending at the next permitted replay state.

The training stage $\omega_k$ therefore has the sequence:

```text
training stage ωₖ

sₖ⁽⁰⁾ → sₖ⁽¹⁾ → ··· → sₖ⁽ᵀᵏ⁾
```

Its single checkpoint is its terminal state:

$$
s_k^{(T_k)}.
$$

The artifacts representing $s_k^{(T_k)}$ belong to the declared stage output
$y_k$. A later training stage $\omega_\ell$ that continues from this checkpoint
begins from the reconstructed state:

$$
s_\ell^{(0)}
=
s_k^{(T_k)}.
$$

If $q$ permits replay from $s_k^{(i)}$ for some $0<i<T_k$, that state terminates
$\omega_k$ and the remaining updates belong to another training stage. Each
run plan contains finitely many stages, while the run-plan space places no fixed
upper bound on $m$.

```text
training stage ωₖ
├── begins at sₖ⁽⁰⁾
├── applies Tₖ updates
└── ends at checkpoint sₖ⁽ᵀᵏ⁾
    └── represented by artifacts in yₖ
```

For a training stage, the stage boundary and terminal checkpoint identify the
same replay boundary.

## 8. Artifact partition of a training checkpoint

An artifact is one named value that a required use can load independently. Let
$A(y_j)$ be the set of artifact names in stage output $y_j$. Each
$a\in A(y_j)$ identifies one value $v_a^{(j)}$.

For the checkpoint of training stage $\omega_k$, let
$a_\theta$ denote the `model_parameters` artifact and let $a_c$ denote the
`continuation_state` artifact. Then:

$$
A
\left(
s_k^{(T_k)}
\right)
=
\left\{
a_\theta,
a_c
\right\}
\subseteq
A(y_k).
$$

Their values are:

$$
v_{a_\theta}^{(k)}
=
\theta_k^{(T_k)},
$$

and:

$$
v_{a_c}^{(k)}
=
\left(
o_k^{(T_k)},
r_k^{(T_k)},
b_k^{(T_k)}
\right).
$$

```text
sₖ⁽ᵀᵏ⁾
├── model_parameters
│   └── θₖ⁽ᵀᵏ⁾
│       └── sufficient for evaluation
│
└── continuation_state
    └── (oₖ⁽ᵀᵏ⁾, rₖ⁽ᵀᵏ⁾, bₖ⁽ᵀᵏ⁾)
        └── combined with model_parameters for exact continuation
```

This is the coarsest artifact partition satisfying the two required uses:

- Evaluation loads `model_parameters`.
- Exact continuation loads `model_parameters` and `continuation_state`.

## 9. File representation of an artifact

For artifact $a\in A(y_j)$, let:

$$
F_j(a)
=
\left\{
f_1,\ldots,f_n
\right\},
\qquad
n\geq 1,
$$

be the files assigned to that artifact.

Let $L_a$ be the artifact’s loader. The files must reconstruct the artifact value:

$$
L_a
\left(
F_j(a)
\right)
=
v_a^{(j)}.
$$

Every member of $F_j(a)$ is required. Removing any member either prevents loading or changes the reconstructed value.

The cardinality determines the physical form:

$$
\left|F_j(a)\right|
=
1
\quad\Longrightarrow\quad
\text{single-file artifact},
$$

and:

$$
\left|F_j(a)\right|
\geq
2
\quad\Longrightarrow\quad
\text{bundle artifact}.
$$

```text
artifact name a
└── artifact value v_a⁽ʲ⁾
    ▲
    │ loader L_a
    │
    └── files F_j(a)
        ├── one file: single-file artifact
        └── two or more files: bundle artifact
```

## 10. Boundary rules

The protocol applies completeness and parsimony at three nested boundaries:

1. Every state from which $q$ permits replay creates a stage boundary. A
   training stage ends at its single terminal checkpoint $s_k^{(T_k)}$.
2. A separate artifact exists for every value that a required use loads
   independently.
3. A file belongs to an artifact exactly when its loader requires that file to
   reconstruct the artifact value.

These rules supply direct parsimony tests:

- Two adjacent training stages can be merged exactly when their shared state is
  not a permitted replay state.
- Two artifacts can be merged exactly when no required use loads either value
  independently.
- A file can be removed from $F_j(a)$ exactly when $L_a$ still reconstructs
  $v_a^{(j)}$ from the remaining files.

With the permitted replay states and required uses fixed, the resulting stage
sequence, artifact partition, and file sets are the coarsest complete
representation.

## 11. Complete dependency chain

```text
ExperimentSpec + VariantSpec + ReplicateSpec
+ experiment decisions
                │
                ▼
run plan q
├── metadata m_q, including the selected replicate and global seed ζq
├── reproducibility c_q, applied to every stage
├── shared environment h_q
└── ordered stage specs ⟨ω₁, …, ωₘ⟩
                │
                ▼
permitted runtime states E_q
                │
                ▼
one execution realizes e = (e₁, …, eₘ) ∈ E_q
                │
                ▼
           stage ωⱼ ∈ Ω
                │
        produces output yⱼ
                │
                ▼
     artifact partition A(yⱼ)
                │
                ▼
    file representation F_j(a)

If ωⱼ = ωₖ ∈ Ω_train:

       training stage ωₖ
                │
     sₖ⁽⁰⁾ → ··· → sₖ⁽ᵀᵏ⁾
                │
                ▼
 terminal checkpoint sₖ⁽ᵀᵏ⁾
                │
                ▼
artifact partition A(sₖ⁽ᵀᵏ⁾)
                │
                ▼
  file representation F_k(a)
                │
                ▼
Tα,β,q(e) = θₖ*⁽ᵀₖ*⁾ = θ̂q
                │
                ▼
          Iα(θ̂q) = ĝq
```

## 12. Protocol mapping

The terminal checkpoint of every training stage is represented by two reserved
artifacts:

```python
MODEL_PARAMETERS: ArtifactName = "model_parameters"
CONTINUATION_STATE: ArtifactName = "continuation_state"
```

The first artifact reconstructs $\theta_k^{(T_k)}$. The second reconstructs:

$$
\left(
o_k^{(T_k)},
r_k^{(T_k)},
b_k^{(T_k)}
\right).
$$

Together they reconstruct the single terminal checkpoint $s_k^{(T_k)}$.
Additional artifact names identify auxiliary outputs of the same stage.

### Training request

`TrainSpec.artifacts` must contain both reserved names exactly once. A
`TrainSpec` validator enforces:

```python
{
    MODEL_PARAMETERS,
    CONTINUATION_STATE,
} <= set(train_spec.artifacts)
```

Each name maps to one `SingleFileArtifactSpec` or `BundleArtifactSpec`. The
artifact loaders define how their verified files reconstruct the two checkpoint
values.

A training stage that continues from an earlier checkpoint declares two
reserved inputs:

```python
CHECKPOINT_MODEL_INPUT: InputName = "checkpoint_model_parameters"
CHECKPOINT_STATE_INPUT: InputName = "checkpoint_continuation_state"
```

The two inputs must occur together and must have the same input kind. For
same-run continuation, they satisfy:

```text
TrainSpec.inputs[checkpoint_model_parameters]
├── producer_stage_id = producer stage ID
└── producer_artifact = model_parameters

TrainSpec.inputs[checkpoint_continuation_state]
├── producer_stage_id = producer stage ID
└── producer_artifact = continuation_state
```

Their common `producer_stage_id` identifies the single checkpoint-producing
stage. A training stage initialized without a prior checkpoint omits both
reserved inputs.

### Resolved stage result

The `RunStageRef` at position $k$ identifies the exact `TrainSpec` $\omega_k$.
The corresponding successful stage result satisfies:

```text
ResolvedStageRef.stage_id
==
RunStageRef.stage_id

ResolvedTrainSpec.spec
==
TrainSpec loaded through RunStageRef.spec
```

The successful execution of $\omega_k$ publishes one stage-result snapshot:

```text
ResolvedStageRef
├── stage_id
├── snapshot
└── resolved_spec
    └── loads ResolvedTrainSpec
        └── artifacts
            ├── model_parameters
            ├── continuation_state
            └── auxiliary artifacts, when declared
```

The resolved artifact names satisfy:

```text
keys(ResolvedTrainSpec.spec.artifacts)
==
keys(ResolvedTrainSpec.artifacts)
```

`ResolvedStageRef.snapshot` identifies the immutable commit containing the
resolved stage spec and every file reached through its resolved artifacts. The
executor adds the stage to `RunAttempt.resolved_stages` after that complete
snapshot has been published and verified.

### Continuation

For same-run continuation from $\omega_k$ to $\omega_\ell$, the external
verifier requires $k<\ell$ and:

```text
ResolvedTrainSpec.inputs[checkpoint_model_parameters].producer
==
ResolvedTrainSpec.inputs[checkpoint_continuation_state].producer
==
ResolvedStageRef for ωₖ
```

The verifier retrieves the producer's resolved spec, selects the two reserved
artifacts, and verifies every file and loader identity. The replay executor
invokes the loaders. Their returned values satisfy:

$$
L_{a_\theta}
\left(
F_k(a_\theta)
\right)
=
\theta_k^{(T_k)},
$$

and:

$$
L_{a_c}
\left(
F_k(a_c)
\right)
=
\left(
o_k^{(T_k)},
r_k^{(T_k)},
b_k^{(T_k)}
\right).
$$

The executor assembles the initial state of $\omega_\ell$ from those values:

$$
s_\ell^{(0)}
=
s_k^{(T_k)}.
$$

For stored continuation from an earlier run, both `ArtifactPointer` records
must select the same resolved run, successful attempt, and producer stage. One
pointer selects `model_parameters`; the other selects `continuation_state`.

### Estimator selection

`RunSpec.estimator` must select the `model_parameters` artifact of a training
stage. The verifier loads the selected producer spec, confirms its `train`
kind, and verifies the artifact files and loader identity. The replay executor
invokes the loader and obtains:

```text
RunSpec.estimator.artifact_name
==
model_parameters

RunSpec.estimator.stage_id
==
producer ResolvedStageRef.stage_id
```

$$
\widehat{\theta}_q
=
\theta_{k_*}^{(T_{k_*})}.
$$

The enforcement path is:

```text
TrainSpec validator
└── enforces one reserved checkpoint pair

ResolvedTrainSpec validator
└── enforces equality between declared and resolved artifact names

external verifier
├── verifies both artifacts belong to one producer snapshot
├── verifies every referenced file
├── verifies both artifact-loader identities
└── verifies the continuation-input and estimator selectors

replay executor
├── invokes both artifact loaders
└── reconstructs sₗ⁽⁰⁾ from sₖ⁽ᵀᵏ⁾

parity check
└── compares the resumed computation and terminal estimator exactly
```
