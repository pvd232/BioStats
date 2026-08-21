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
- $\Omega^+$ as the set of nonempty ordered stage-specification sequences.

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

Fix a training stage:

$$
\omega_j
\in
\Omega_{\mathrm{train}},
$$

where $\Omega_{\mathrm{train}}$ is the set of valid training-stage specifications.

Its realized runtime state is:

$$
e_j
\in
E_{q,j}.
$$

Initialization produces the initial model parameters:

$$
\theta^{(0)}
=
I^\theta_{\alpha,\beta,q}
\left(
\omega_j,
e_j
\right).
$$

The global seed $\zeta_q$ and the realized runtime state initialize the
random-number-generator state:

$$
r^{(0)}
=
I^r
\left(
\zeta_q,
e_j
\right).
$$

The stage specification and initial parameters initialize the optimizer state:

$$
o^{(0)}
=
I^o_{\beta,q}
\left(
\omega_j,
\theta^{(0)}
\right).
$$

The stage specification, dataset, and random-number-generator state initialize the batch state:

$$
b^{(0)}
=
I^b_q
\left(
\omega_j,
D_q,
r^{(0)}
\right).
$$

The initial training state is:

$$
s^{(0)}
=
\left(
\theta^{(0)},
o^{(0)},
r^{(0)},
b^{(0)}
\right).
$$

```text
ωⱼ + eⱼ ───────────────→ θ⁽⁰⁾
                             │
                             ▼
                            o⁽⁰⁾

ζq + eⱼ ──────────────→ r⁽⁰⁾
                             │
                  ωⱼ + Dq ──┴──→ b⁽⁰⁾

s⁽⁰⁾ = (θ⁽⁰⁾, o⁽⁰⁾, r⁽⁰⁾, b⁽⁰⁾)
```

## 5. Training-state transition

At update $t+1$, compute the gradient:

$$
g^{(t+1)}
=
G_{\alpha,\beta,q,t}
\left(
\omega_j,
D_q,
e_j,
\theta^{(t)},
r^{(t)},
b^{(t)}
\right).
$$

Update the optimizer state:

$$
o^{(t+1)}
=
A_{\beta,q,t}
\left(
\omega_j,
e_j,
o^{(t)},
g^{(t+1)}
\right).
$$

Update the model parameters:

$$
\theta^{(t+1)}
=
P_{\beta,q,t}
\left(
\omega_j,
e_j,
\theta^{(t)},
o^{(t+1)}
\right).
$$

Advance the random-number-generator and batch states:

$$
\left(
r^{(t+1)},
b^{(t+1)}
\right)
=
C_{\alpha,\beta,q,t}
\left(
\omega_j,
D_q,
e_j,
s^{(t)}
\right).
$$

Reassemble the next training state:

$$
s^{(t+1)}
=
\left(
\theta^{(t+1)},
o^{(t+1)},
r^{(t+1)},
b^{(t+1)}
\right).
$$

These component updates define:

$$
U_{\alpha,\beta,q,t}
:
\Omega_{\mathrm{train}}
\times
\mathcal{D}
\times
E_{q,j}
\times
\mathcal{S}_t
\longrightarrow
\mathcal{S}_{t+1},
$$

with:

$$
s^{(t+1)}
=
U_{\alpha,\beta,q,t}
\left(
\omega_j,
D_q,
e_j,
s^{(t)}
\right).
$$

If $\omega_j$ governs updates $i_{j-1}$ through $i_j-1$, repeated application produces:

$$
s^{(i_{j-1})}
\longmapsto
s^{(i_j)}.
$$

The complete stage dependency is:

$$
q
\longrightarrow
\boldsymbol{\omega}_q
\longrightarrow
\omega_j
\longrightarrow
E_{q,j}
\ni
e_j
\longrightarrow
U_{\alpha,\beta,q,t}
\left(
\omega_j,D_q,e_j,s^{(t)}
\right)
\longrightarrow
s^{(t+1)}.
$$

## 6. Estimator and strict reproducibility

The run estimator is:

$$
T_{\alpha,\beta,q}
:
E_q
\longrightarrow
\Theta_\alpha.
$$

It initializes $s^{(0)}$, applies the transitions fixed by $q$, and returns the model-parameter component of the terminal training state:

$$
T_{\alpha,\beta,q}(e)
=
\theta^{(T)}.
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

## 7. Replay states and stage boundaries

A stage boundary identifies a training state from which the contract permits replay.

If stage $\omega_j$ ends at update $i$, its replay state is:

$$
s^{(i)}
=
\left(
\theta^{(i)},
o^{(i)},
r^{(i)},
b^{(i)}
\right).
$$

Exact continuation from that boundary begins from $s^{(i)}$ and applies the remaining transitions fixed by $q$.

```text
Dq + e
   │
   ▼
s⁽⁰⁾
   │
   ├── stage ω₁ ──→ s⁽ⁱ¹⁾
   │                  └── replay may begin here
   ├── stage ω₂ ──→ s⁽ⁱ²⁾
   │                  └── replay may begin here
   └── stage ωₘ ──→ s⁽ᵀ⁾
                      └── contains θ̂q
```

The ordered stage specifications in $q$ therefore fix the replay positions represented by the protocol.

## 8. Artifact partition of a replay state

An artifact is one named value that a required use can load independently.

For a training checkpoint supporting evaluation and exact continuation, let
$a_\theta$ denote the `model_parameters` artifact and let $a_c$ denote the
`continuation_state` artifact. Then:

$$
A
\left(
s^{(i)}
\right)
=
\left\{
a_\theta,
a_c
\right\}.
$$

Their values are:

$$
v_{a_\theta}^{(i)}
=
\theta^{(i)},
$$

and:

$$
v_{a_c}^{(i)}
=
\left(
o^{(i)},
r^{(i)},
b^{(i)}
\right).
$$

```text
s⁽ⁱ⁾
├── model_parameters
│   └── θ⁽ⁱ⁾
│       └── sufficient for evaluation
│
└── continuation_state
    └── (o⁽ⁱ⁾, r⁽ⁱ⁾, b⁽ⁱ⁾)
        └── combined with model_parameters for exact continuation
```

This is the coarsest artifact partition satisfying the two required uses:

- Evaluation loads `model_parameters`.
- Exact continuation loads `model_parameters` and `continuation_state`.

## 9. File representation of an artifact

For artifact $a$ at replay position $i$, let:

$$
F_i(a)
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
F_i(a)
\right)
=
v_a^{(i)}.
$$

Every member of $F_i(a)$ is required. Removing any member either prevents loading or changes the reconstructed value.

The cardinality determines the physical form:

$$
\left|F_i(a)\right|
=
1
\quad\Longrightarrow\quad
\text{single-file artifact},
$$

and:

$$
\left|F_i(a)\right|
\geq
2
\quad\Longrightarrow\quad
\text{bundle artifact}.
$$

```text
artifact name a
└── artifact value v_a⁽ⁱ⁾
    ▲
    │ loader L_a
    │
    └── files F_i(a)
        ├── one file: single-file artifact
        └── two or more files: bundle artifact
```

## 10. Boundary rules

The three protocol boundaries follow the same completeness-and-parsimony rule:

1. A stage boundary exists for every intermediate state from which the contract permits replay.
2. A separate artifact exists for every value that a required use loads independently.
3. A file belongs to an artifact exactly when its loader requires that file to reconstruct the artifact value.

Therefore:

- The stage sequence contains the fewest boundaries supporting the required replay starts.
- $A(s^{(i)})$ contains the fewest independently loadable artifacts supporting the required uses.
- $F_i(a)$ contains the files required by $L_a$ to reconstruct $v_a^{(i)}$.

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
U(ωⱼ, Dq, eⱼ, s⁽ᵗ⁾) = s⁽ᵗ⁺¹⁾
                │
                ▼
declared replay state s⁽ⁱ⁾
                │
                ▼
artifact partition A(s⁽ⁱ⁾)
                │
                ▼
file representation F_i(a)
                │
                ▼
loader reconstructs v_a⁽ⁱ⁾
                │
                ▼
Tα,β,q(e) = θ⁽ᵀ⁾ = θ̂q
                │
                ▼
Iα(θ̂q) = ĝq
```
