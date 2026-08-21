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

The estimator specification $\beta$ determines the map from datasets to
parameter values:

$$
T_{\alpha,\beta}
:
\mathcal{D}
\longrightarrow
\Theta_\alpha.
$$

The run plan $q$ fixes:

- The family specification $\alpha$.
- The estimator specification $\beta$.
- The dataset selection $D_q$.

The exact dataset artifacts selected by the stage inputs, together with the
stage scripts and typed parameters that select samples, features, quality
controls, and transformations, determine $D_q$.

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
estimator output, and optional benchmark. Each experiment replicate has one
seed. The run uses the selected replicate's seed, denoted $\zeta_q$, as its
global seed.

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
│   └── identifies the run, experiment, variant, replicate, source,
│       estimator output, optional benchmark, and global seed ζq
├── reproducibility c_q
│   └── fixes deterministic-algorithm, precision, and parallelism controls
├── environment h_q
│   └── shared environment
└── stages ω_q = ⟨ω₁, …, ωₘ⟩
    └── exact ordered stage specifications that complete α, β, and Dq
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
E_{q,1}
\times
\cdots
\times
E_{q,m}.
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

Experiment design declares the required replay positions and independently
loadable uses. Plan authoring applies these tests before $q$ is frozen. Once
$q$ is frozen, its stage boundaries, artifact names, and file sets are the
selected representation enforced by Pydantic and the external verifier.

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

## 12. Protocol record roles

Protocol files contain records validated by Pydantic models. Their names state
their roles:

| Form | Role |
|---|---|
| `*Spec` | Declares requested state. |
| `Resolved*` | Records realized state. |
| `*Ref` | Identifies another protocol object. |
| `ArtifactPointer` | Selects one promoted artifact. |
| `ResolvedArtifact` | Records the files representing one named artifact. |
| `Measurement` | Records one metric value. |
| `RunAttempt` | Records one execution attempt. |
| `ResolvedRun` | Records the terminal run result. |

```text
Spec
└── declares requested state and contributes to q
        │
        ▼
q induces E_q

Resolved
└── records one realized e ∈ E_q

Verifier
├── checks e ∈ E_q
└── verifies every referenced file against its recorded identity
```

The protocol identifies exact files in two forms:

```text
standalone file
└── ResolvedFileRef
    ├── stored_at
    ├── sha256
    └── bytes

file in a stage-result snapshot
├── StageResultSnapshotRef
│   └── repository + commit
└── SnapshotFileRef
    ├── path
    ├── sha256
    └── bytes
```

A role-specific file reference states the record type expected from the
retrieved bytes. For example, `ResolvedRunRef` identifies a standalone file
that parses as `ResolvedRun`.

`ArtifactPointer`, `ArtifactPointerRef`, and `ResolvedArtifactPointerRef` have
separate roles:

```text
ArtifactPointer
└── selects one artifact from one successful run

ArtifactPointerRef
└── identifies the Git file containing that ArtifactPointer

ResolvedArtifactPointerRef
├── stored_at: ArtifactPointerRef
├── sha256
└── bytes
```

## 13. File, artifact, and stage-result records

Every protocol record is closed and immutable after validation:

```python
class ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

The records below use these shared types:

| Type | Accepted value |
|---|---|
| `HumanId` | A lowercase identifier matching `^[a-z][a-z0-9_]*$`. |
| `RepoRelPath` | A normalized POSIX path relative to the repository root. |
| `SHA256` | A 64-character lowercase hexadecimal digest. |
| `GitCommit` | A 40- or 64-character lowercase hexadecimal commit ID. |
| `NonEmptyStr` | A string containing at least one character. |

### Exact file identity

A standalone file is stored at an immutable Git or Hugging Face revision:

```python
class GitSource(ProtocolModel):
    kind: Literal["git"] = "git"
    repository: HttpUrl
    commit: GitCommit


class GitFileRef(GitSource):
    path: RepoRelPath


class HuggingFaceFileRef(ProtocolModel):
    kind: Literal["huggingface"] = "huggingface"
    repository: NonEmptyStr
    commit: GitCommit
    path: RepoRelPath
    repo_type: Literal["model", "dataset", "space"]


StorageRef = Annotated[
    GitFileRef | HuggingFaceFileRef,
    Field(discriminator="kind"),
]
```

A standalone file records its storage location and content identity:

```python
class ResolvedFileRef(ProtocolModel):
    sha256: SHA256
    bytes: int = Field(ge=0)
    stored_at: StorageRef
```

A completed stage is published as one immutable snapshot:

```python
class StageResultSnapshotRef(ProtocolModel):
    kind: Literal["huggingface"] = "huggingface"
    repository: NonEmptyStr
    commit: GitCommit
    repo_type: Literal["model", "dataset", "space"]
```

Each file within that snapshot records its repository-relative path and content
identity:

```python
class SnapshotFileRef(ProtocolModel):
    path: RepoRelPath
    sha256: SHA256
    bytes: int = Field(ge=0)
```

The exact storage location of a snapshot file is determined by:

```text
StageResultSnapshotRef.repository
+ StageResultSnapshotRef.commit
+ SnapshotFileRef.path
```

The verifier retrieves that file and requires equality with
`SnapshotFileRef.sha256` and `SnapshotFileRef.bytes`.

### Artifact declarations

```python
ArtifactName = HumanId
ArtifactLoaderId = HumanId


class SingleFileArtifactSpec(ProtocolModel):
    kind: Literal["file"] = "file"
    path: RepoRelPath
    loader: ArtifactLoaderId


class BundleArtifactSpec(ProtocolModel):
    kind: Literal["bundle"] = "bundle"
    path: RepoRelPath
    loader: ArtifactLoaderId


ArtifactSpec = Annotated[
    SingleFileArtifactSpec | BundleArtifactSpec,
    Field(discriminator="kind"),
]


class BaseSpec(ProtocolModel):
    kind: str
    schema_version: Literal[1] = 1
    script: RepoRelPath
    environment: GCEEnvironmentSpec | None = None
    artifacts: dict[ArtifactName, ArtifactSpec] = Field(min_length=1)
```

For a single-file artifact, `path` identifies its file. For a bundle artifact,
`path` identifies its directory root. Every artifact path has the form:

```text
experiments/<experiment_id>/runs/<variant_id>/<run_id>/artifacts/
    <category>/<entity_id>/<file_or_bundle_path>
```

The artifact category is `datasets` for a download stage, `priors` for a build
stage, `models` for an embed or train stage, and `evaluations` for an evaluate
stage. A single-file artifact includes a filename after `<entity_id>`. A bundle
root may equal the identity directory or a directory beneath it.

The stage entrypoints are:

```text
DownloadSpec → src/mantra/datasets/<dataset_id>/download.py
BuildSpec    → src/mantra/priors/<prior_id>/build.py
EmbedSpec    → src/mantra/models/<model_id>/embed.py
TrainSpec    → src/mantra/models/<model_id>/train.py
EvaluateSpec → src/mantra/models/<model_id>/evaluate.py
```

An artifact loader is a Python file at:

```text
src/mantra/artifact_loaders/<loader_id>.py
```

`RunSpec.source` identifies the exact repository revision containing the loader.
The loader defines:

```python
def load(path: Path) -> object:
    ...
```

For a single-file artifact, the executor supplies the materialized file path.
For a bundle artifact, the executor supplies the materialized directory path.

### Resolved artifacts

```python
class ResolvedSingleFileArtifact(ProtocolModel):
    kind: Literal["file"] = "file"
    file: SnapshotFileRef


class ResolvedBundleMember(ProtocolModel):
    relative_path: RepoRelPath
    file: SnapshotFileRef


class ResolvedBundleArtifact(ProtocolModel):
    kind: Literal["bundle"] = "bundle"
    members: tuple[ResolvedBundleMember, ...] = Field(min_length=2)


ResolvedArtifact = Annotated[
    ResolvedSingleFileArtifact | ResolvedBundleArtifact,
    Field(discriminator="kind"),
]


class ResolvedBaseSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    kind: str
    spec: BaseSpec
    source: ResolvedGitFileRef
    environment: ResolvedGCEEnvironment
    execution_context: ExecutionContext
    command: tuple[str, ...] = Field(min_length=1)
    artifacts: dict[ArtifactName, ResolvedArtifact] = Field(min_length=1)
    completed_at: AwareDatetime
```

The artifact-name sets are equal:

```text
keys(ResolvedBaseSpec.spec.artifacts)
==
keys(ResolvedBaseSpec.artifacts)
```

The cardinality of $F_j(a)$ determines the resolved form:

$$
\left|F_j(a)\right|
=
1
\quad\Longleftrightarrow\quad
\text{ResolvedSingleFileArtifact},
$$

and:

$$
\left|F_j(a)\right|
\geq
2
\quad\Longleftrightarrow\quad
\text{ResolvedBundleArtifact}.
$$

For a single-file artifact:

```text
ResolvedSingleFileArtifact.file.path
==
SingleFileArtifactSpec.path
```

For every bundle member:

```text
ResolvedBundleMember.file.path
==
BundleArtifactSpec.path / ResolvedBundleMember.relative_path
```

Bundle-member paths are unique, pairwise non-overlapping, remain beneath the
bundle root, and appear in canonical `relative_path` order. Artifact roots
within one stage are pairwise non-overlapping.

The verifier verifies every file in $F_j(a)$, materializes the file or
directory, invokes the loader named by the corresponding `ArtifactSpec`, and
requires the loader to return successfully:

$$
L_a
\left(
F_j(a)
\right)
=
v_a^{(j)}.
$$

### Stage-result snapshot

```python
class ResolvedStageRef(ProtocolModel):
    stage_id: StageId
    snapshot: StageResultSnapshotRef
    resolved_spec: SnapshotFileRef
```

`ResolvedStageRef.snapshot` contains:

```text
one resolved stage-spec file
+ every file in every resolved artifact
```

`ResolvedStageRef.resolved_spec` identifies the resolved stage-spec file within
that snapshot. The loaded resolved spec identifies every artifact file through
its `artifacts` mapping.

```text
ResolvedStageRef
├── snapshot
├── resolved_spec
│   └── loads one ResolvedBaseSpec subtype
└── snapshot + resolved artifact file paths
    └── identifies every physical artifact file
```

A completed stage has one `ResolvedStageRef`. Its snapshot commit therefore
binds the resolved execution record and every file representing the stage's
declared output $y_j$.

## 14. Run, input, and attempt records

### Run plan

```python
RNGSeed = Annotated[int, Field(ge=0, le=2**32 - 1)]


class StageArtifactRef(ProtocolModel):
    stage_id: StageId
    artifact_name: ArtifactName


class RunStageRef(ProtocolModel):
    stage_id: StageId
    spec: RepoRelPath
    sha256: SHA256
    bytes: int = Field(ge=0)


class RunSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    run_id: RunId
    experiment_id: ExperimentId
    variant_id: VariantId
    replicate_id: ReplicateId
    benchmark_id: BenchmarkId | None = None

    seed: RNGSeed
    source: GitSource
    environment: GCEEnvironmentSpec
    reproducibility: ReproducibilitySpec

    stages: tuple[RunStageRef, ...] = Field(min_length=1)
    estimator: StageArtifactRef
```

`RunSpec.seed` is the global seed $\zeta_q$ assigned to the selected replicate.
Its range is the shared domain accepted by NumPy's legacy
[random-state seeding](https://numpy.org/doc/2.0/reference/random/legacy.html)
and PyTorch's
[generator seeding](https://docs.pytorch.org/docs/stable/generated/torch.Generator.html).
The executor applies it to each generator according to
`RunSpec.reproducibility`.

`RunSpec.environment` supplies $h_q$. For stage $\omega_j$:

```text
BaseSpec.environment is present
→ h_q,j = BaseSpec.environment

BaseSpec.environment is absent
→ h_q,j = RunSpec.environment
```

`RunSpec.reproducibility` supplies $c_q$ to every stage. A stage environment
override changes $h_{q,j}$ and leaves $c_q$ unchanged.

The ordered `RunStageRef` records identify the exact stage-spec files in
$\boldsymbol{\omega}_q$. Stage IDs and stage-spec paths are unique. Each stage
spec path equals:

```text
experiments/<experiment_id>/runs/<variant_id>/<run_id>/stages/<stage_id>/spec.yaml
```

The `RunSpec` file and the stage-spec files it identifies constitute $q$.

### Artifact selection and promotion

The terminal run record and run-plan record use role-specific file references:

```python
class ResolvedRunSpecRef(ResolvedFileRef):
    kind: Literal["run_spec"] = "run_spec"
    stored_at: GitFileRef


class ResolvedRunRef(ResolvedFileRef):
    kind: Literal["resolved_run"] = "resolved_run"
    stored_at: HuggingFaceFileRef
```

An `ArtifactPointer` selects one artifact accepted for reuse:

```python
class ArtifactPointer(ProtocolModel):
    schema_version: Literal[1] = 1
    run: ResolvedRunRef
    artifact: StageArtifactRef
    benchmark_result: ResolvedBenchmarkResultRef | None = None


class ArtifactPointerRef(GitFileRef):
    pass


class ResolvedArtifactPointerRef(ResolvedFileRef):
    kind: Literal["artifact_pointer"] = "artifact_pointer"
    stored_at: ArtifactPointerRef
```

The selection path is:

```text
ArtifactPointer.run
→ ResolvedRun
→ successful RunAttempt
→ ResolvedStageRef selected by StageArtifactRef.stage_id
→ loaded ResolvedBaseSpec
→ ResolvedBaseSpec.artifacts[StageArtifactRef.artifact_name]
→ exact artifact files
```

Every `ArtifactPointerRef.path` has the form:

```text
inputs/<category>/<entity_id>/<selection_name>.pointer.yaml
```

The permitted categories are `benchmarks`, `datasets`, `models`, and `priors`.

When the selected run names a benchmark and `ArtifactPointer.artifact` equals
`RunSpec.estimator`, `ArtifactPointer.benchmark_result` identifies the passed
`BenchmarkResult` that authorizes promotion.

### Stage inputs

A stored input selects an artifact promoted from a completed run:

```python
class StoredInputRef(ProtocolModel):
    kind: Literal["stored"] = "stored"
    pointer: ArtifactPointerRef
    path: RepoRelPath


class ResolvedStoredInputRef(ProtocolModel):
    kind: Literal["stored"] = "stored"
    pointer: ResolvedArtifactPointerRef
```

The planned and resolved pointer locations are equal:

```text
ResolvedStoredInputRef.pointer.stored_at
==
StoredInputRef.pointer
```

`StoredInputRef.path` identifies the local file path or bundle root supplied to
the consuming stage. Its category and entity ID equal those in
`StoredInputRef.pointer.path`.

A same-run input selects one artifact from an earlier stage:

```python
class FutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    producer_stage_id: StageId
    producer_artifact: ArtifactName


class ResolvedFutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    producer: ResolvedStageRef
```

For a consumer at stage position $j$, the producer occurs at a position
$i<j$. The verifier requires:

```text
ResolvedFutureInputRef.producer.stage_id
==
FutureInputRef.producer_stage_id

FutureInputRef.producer_artifact
in
keys(producer ResolvedBaseSpec.artifacts)
```

The selected artifact's declared path is its local file path or bundle root.

### Attempts and terminal run result

```python
AttemptStatus = Literal[
    "succeeded",
    "failed",
    "preempted",
    "cancelled",
]


class RunAttempt(ProtocolModel):
    attempt_id: int = Field(ge=1)
    status: AttemptStatus
    started_at: AwareDatetime
    completed_at: AwareDatetime

    resolved_stages: tuple[ResolvedStageRef, ...]
    measurement_files: tuple[ResolvedFileRef, ...]
    log_files: tuple[ResolvedFileRef, ...]
    failure_reason: str | None


class ResolvedRun(ProtocolModel):
    schema_version: Literal[1] = 1
    spec: ResolvedRunSpecRef
    status: Literal["succeeded", "failed", "cancelled"]
    attempts: tuple[RunAttempt, ...] = Field(min_length=1)
    successful_attempt_id: int | None
    completed_at: AwareDatetime
```

Attempt IDs are unique and strictly increasing. Each attempt's
`resolved_stages` is an ordered prefix of `RunSpec.stages`. Its stage snapshots
are unique. Measurement-file storage locations and log-file storage locations
are unique and disjoint.

A successful attempt satisfies:

1. Its `failure_reason` is null.
2. Its `resolved_stages` is nonempty and contains every declared stage exactly
   once and in order.
3. Every `ResolvedStageRef` identifies a verified stage-result snapshot.

A failed, preempted, or cancelled attempt records a nonempty `failure_reason`.

A successful `ResolvedRun` identifies exactly one successful attempt through
`successful_attempt_id`. A failed or cancelled `ResolvedRun` has no successful
attempt. `ResolvedRun.spec` identifies the exact `RunSpec` file whose stages
govern every attempt.

```text
ResolvedRun.spec
→ RunSpec
→ ordered RunStageRef records

ResolvedRun.attempts
→ ordered RunAttempt records
→ ordered ResolvedStageRef prefixes

ResolvedRun.successful_attempt_id
→ complete successful RunAttempt
```

## 15. Environment, reproducibility, and execution records

### Requested environment

```python
class GCEMachineImageRef(ProtocolModel):
    project: NonEmptyStr
    name: NonEmptyStr


class CPUComputeSpec(ProtocolModel):
    kind: Literal["cpu"] = "cpu"


class CUDAComputeSpec(ProtocolModel):
    kind: Literal["cuda"] = "cuda"
    model: NonEmptyStr
    count: int = Field(ge=1)


ComputeSpec = Annotated[
    CPUComputeSpec | CUDAComputeSpec,
    Field(discriminator="kind"),
]


class GCEEnvironmentSpec(ProtocolModel):
    kind: Literal["gce"] = "gce"
    machine_image: GCEMachineImageRef
    machine_type: NonEmptyStr
    compute: ComputeSpec
    lockfile: GitFileRef
```

`RunSpec.environment` supplies the shared `GCEEnvironmentSpec`. A stage-level
`BaseSpec.environment` supplies the selected stage's environment override.

### Run-wide reproducibility controls

```python
class TorchDeterminismSpec(ProtocolModel):
    deterministic_algorithms: bool
    deterministic_warn_only: bool
    cudnn_deterministic: bool
    cudnn_benchmark: bool
    cublas_workspace_config: Literal[":16:8", ":4096:8"] | None


class TorchPrecisionSpec(ProtocolModel):
    float32_matmul_precision: Literal["highest", "high", "medium"]
    cudnn_allow_tf32: bool
    autocast_enabled: bool
    autocast_dtype: Literal["float16", "bfloat16"] | None


class ParallelismSpec(ProtocolModel):
    process_count: int = Field(ge=1)
    torch_intraop_threads: int = Field(ge=1)
    torch_interop_threads: int = Field(ge=1)
    dataloader_workers: int = Field(ge=0)


class ReproducibilitySpec(ProtocolModel):
    determinism: TorchDeterminismSpec
    precision: TorchPrecisionSpec
    parallelism: ParallelismSpec
```

The global seed occurs once in `RunSpec.seed`. `ReproducibilitySpec` records
the remaining numerical controls shared by every stage.

### Realized environment and runtime state

```python
class ResolvedGCEMachineImageRef(GCEMachineImageRef):
    id: NonEmptyStr


class ResolvedGitFileRef(ResolvedFileRef):
    stored_at: GitFileRef


class ResolvedGCEEnvironment(ProtocolModel):
    kind: Literal["gce"] = "gce"
    machine_image: ResolvedGCEMachineImageRef
    machine_type: NonEmptyStr
    compute: ComputeSpec
    lockfile: ResolvedGitFileRef


class GCEHostContext(ProtocolModel):
    provider: Literal["gce"] = "gce"
    machine_type: NonEmptyStr
    zone: NonEmptyStr
    guest_os_name: NonEmptyStr
    guest_os_version: NonEmptyStr
    kernel_release: NonEmptyStr


class CPUContext(ProtocolModel):
    architecture: NonEmptyStr
    model: NonEmptyStr
    instruction_features: tuple[NonEmptyStr, ...] = Field(min_length=1)


class CPUBackendContext(ProtocolModel):
    kind: Literal["cpu"] = "cpu"
    device: Literal["cpu"] = "cpu"


class CUDADeviceContext(ProtocolModel):
    ordinal: int = Field(ge=0)
    model: NonEmptyStr
    compute_capability_major: int = Field(ge=0)
    compute_capability_minor: int = Field(ge=0)
    memory_bytes: int = Field(gt=0)


class CUDABackendContext(ProtocolModel):
    kind: Literal["cuda"] = "cuda"
    gpu_devices: tuple[CUDADeviceContext, ...] = Field(min_length=1)
    nvidia_driver_version: NonEmptyStr
    pytorch_cuda_version: NonEmptyStr
    cudnn_version: NonEmptyStr


ComputeBackendContext = Annotated[
    CPUBackendContext | CUDABackendContext,
    Field(discriminator="kind"),
]


class NativeLibraryContext(ProtocolModel):
    implementation: NonEmptyStr
    version: NonEmptyStr


class NativeThreadPoolContext(NativeLibraryContext):
    threads: int = Field(ge=1)


class NumericalRuntimeContext(ProtocolModel):
    python_version: NonEmptyStr
    pytorch_version: NonEmptyStr
    numpy_version: NonEmptyStr
    blas: NativeLibraryContext
    lapack: NativeLibraryContext
    native_thread_pools: tuple[NativeThreadPoolContext, ...]


class RandomnessContext(ProtocolModel):
    python_seed: RNGSeed
    numpy_seed: RNGSeed
    torch_seed: RNGSeed
    dataloader_seed: RNGSeed


class ExecutionContext(ProtocolModel):
    host: GCEHostContext
    cpu: CPUContext
    backend: ComputeBackendContext
    numerical_runtime: NumericalRuntimeContext
    randomness: RandomnessContext
    determinism: TorchDeterminismSpec
    precision: TorchPrecisionSpec
    parallelism: ParallelismSpec
```

CUDA device ordinals are unique within one `CUDABackendContext`.

For stage $\omega_j$, let $\widetilde{h}_j$ denote its resolved environment and
let $x_j$ denote its execution context. The realized runtime state recorded by
the protocol is:

$$
e_j
=
\left(
\widetilde{h}_j,
x_j
\right).
$$

The verifier establishes $e_j\in E_{q,j}$ through these equalities:

```text
ResolvedGCEEnvironment.machine_image.project
== selected GCEEnvironmentSpec.machine_image.project

ResolvedGCEEnvironment.machine_image.name
== selected GCEEnvironmentSpec.machine_image.name

ResolvedGCEEnvironment.machine_type
== selected GCEEnvironmentSpec.machine_type
== ExecutionContext.host.machine_type

ResolvedGCEEnvironment.compute
== selected GCEEnvironmentSpec.compute

ResolvedGCEEnvironment.lockfile.stored_at
== selected GCEEnvironmentSpec.lockfile

ExecutionContext.determinism
== RunSpec.reproducibility.determinism

ExecutionContext.precision
== RunSpec.reproducibility.precision

ExecutionContext.parallelism
== RunSpec.reproducibility.parallelism

ExecutionContext.randomness.python_seed
== ExecutionContext.randomness.numpy_seed
== ExecutionContext.randomness.torch_seed
== ExecutionContext.randomness.dataloader_seed
== RunSpec.seed
```

For a CPU environment, `ExecutionContext.backend.kind` is `cpu`. For a CUDA
environment, the backend is `cuda`, its number of devices equals
`CUDAComputeSpec.count`, and each device model equals `CUDAComputeSpec.model`.

The verifier checks the resolved machine-image identity and verifies the
lockfile and source-entrypoint bytes. `ExecutionContext` records the runtime
library implementations and versions used by the stage.

### Source and command

`ResolvedBaseSpec.source` identifies `BaseSpec.script` at `RunSpec.source`:

```text
ResolvedBaseSpec.source.stored_at.repository
== RunSpec.source.repository

ResolvedBaseSpec.source.stored_at.commit
== RunSpec.source.commit

ResolvedBaseSpec.source.stored_at.path
== ResolvedBaseSpec.spec.script
```

For the `RunStageRef` belonging to stage $\omega_j$, the executor constructs:

```text
python <BaseSpec.script> <RunStageRef.spec>
```

The resolved record satisfies:

```python
ResolvedBaseSpec.command == (
    "python",
    str(ResolvedBaseSpec.spec.script),
    str(run_stage_ref.spec),
)
```

## 16. Experiment, variant, replicate, and measurement records

### Experiment and replicate declarations

```python
class FactorSpec(ProtocolModel):
    factor_id: FactorId
    levels: tuple[LevelId, ...] = Field(min_length=2)


class ReplicateSpec(ProtocolModel):
    replicate_id: ReplicateId
    seed: RNGSeed


class ExperimentSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    experiment_id: ExperimentId
    factors: tuple[FactorSpec, ...]
    variant_ids: tuple[VariantId, ...] = Field(min_length=1)
    replicates: tuple[ReplicateSpec, ...] = Field(min_length=1)
    metric_ids: tuple[MetricId, ...]
```

Factor IDs are unique. Level IDs are unique within each factor. Variant IDs,
replicate IDs, replicate seeds, and metric IDs are unique within the
experiment.

The experiment file and its variant files occur at:

```text
experiments/<experiment_id>/spec.yaml
experiments/<experiment_id>/variants/<variant_id>.spec.yaml
```

`RunSpec.source` identifies the exact repository revision containing these
files.

### Variant declaration

```python
class BuildVariantStageParams(ProtocolModel):
    kind: Literal["build"] = "build"
    stage_id: StageId
    params: BuildParams


class EmbedVariantStageParams(ProtocolModel):
    kind: Literal["embed"] = "embed"
    stage_id: StageId
    params: EmbedParams


class TrainVariantStageParams(ProtocolModel):
    kind: Literal["train"] = "train"
    stage_id: StageId
    params: TrainParams


class EvaluateVariantStageParams(ProtocolModel):
    kind: Literal["evaluate"] = "evaluate"
    stage_id: StageId
    params: EvaluateParams


VariantStageParams = Annotated[
    BuildVariantStageParams
    | EmbedVariantStageParams
    | TrainVariantStageParams
    | EvaluateVariantStageParams,
    Field(discriminator="kind"),
]


class VariantSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    experiment_id: ExperimentId
    variant_id: VariantId
    levels: dict[FactorId, LevelId]
    stage_params: tuple[VariantStageParams, ...] = Field(min_length=1)
```

The factor names in `VariantSpec.levels` equal the factor names in the selected
`ExperimentSpec`. Each selected level belongs to its factor's permitted level
set. Stage IDs are unique within `VariantSpec.stage_params`.

The verifier requires:

```text
RunSpec.experiment_id
== ExperimentSpec.experiment_id
== VariantSpec.experiment_id

RunSpec.variant_id
== VariantSpec.variant_id

RunSpec.variant_id
in ExperimentSpec.variant_ids

set(VariantSpec.stage_params.stage_id)
== set(stage IDs whose loaded stage specs contain params)

VariantSpec.stage_params[stage_id].params
== loaded stage spec.params
```

The selected level IDs state the experimental assignment. The typed parameter
records state how the selected variant is implemented by its stage specs.

### Seed authority

`RunSpec.replicate_id` selects one `ReplicateSpec`. Its seed is the run's global
seed:

```text
RunSpec.seed
== selected ReplicateSpec.seed
== ζq
```

The executor applies this value before every stage. Section 15 defines the
corresponding `ExecutionContext.randomness` equalities.

### Measurements

```python
class Measurement(ProtocolModel):
    run_id: RunId
    attempt_id: int = Field(ge=1)
    stage_id: StageId
    metric_id: MetricId
    value: float = Field(allow_inf_nan=False)
    measured_at: AwareDatetime
    epoch: int | None = Field(default=None, ge=0)
    step: int | None = Field(default=None, ge=0)
```

Each file in `RunAttempt.measurement_files` contains `Measurement` rows. For
every row, the verifier requires:

```text
Measurement.run_id
== RunSpec.run_id

Measurement.attempt_id
== containing RunAttempt.attempt_id

Measurement.stage_id
in completed stage IDs of that attempt

Measurement.metric_id
in ExperimentSpec.metric_ids

RunAttempt.started_at
<= Measurement.measured_at
<= RunAttempt.completed_at
```

Measurement JSON objects have unique field names. A successful evaluation stage
records exactly one row for each metric in `EvaluateSpec.params.metric_ids`.

## 17. Concrete stage records

### Planned stage inputs

```python
class RemoteFileRef(ProtocolModel):
    kind: Literal["remote"] = "remote"
    url: HttpUrl
    version: NonEmptyStr


InternalInputRef = Annotated[
    StoredInputRef | FutureInputRef,
    Field(discriminator="kind"),
]
```

A download stage consumes one versioned external source. Build, embed, and
train stages consume stored or same-run artifacts.

### Planned stage specifications

```python
class DownloadSpec(BaseSpec):
    kind: Literal["download"] = "download"
    inputs: dict[InputName, RemoteFileRef] = Field(min_length=1, max_length=1)


class InternalSpec(BaseSpec):
    inputs: dict[InputName, InternalInputRef] = Field(min_length=1)


class BuildSpec(InternalSpec):
    kind: Literal["build"] = "build"
    params: BuildParams


class EmbedSpec(InternalSpec):
    kind: Literal["embed"] = "embed"
    params: EmbedParams


class TrainSpec(InternalSpec):
    kind: Literal["train"] = "train"
    params: TrainParams


class EvaluateParams(ProtocolModel):
    metric_ids: tuple[MetricId, ...] = Field(min_length=1)
    split_inputs: tuple[InputName, ...] = Field(min_length=1)


class EvaluateSpec(InternalSpec):
    kind: Literal["evaluate"] = "evaluate"
    params: EvaluateParams


Spec = Annotated[
    DownloadSpec | BuildSpec | EmbedSpec | TrainSpec | EvaluateSpec,
    Field(discriminator="kind"),
]
```

`BuildParams`, `EmbedParams`, and `TrainParams` are typed parameter records.
Their exact values are fixed by the selected `VariantSpec` and checked against
the loaded stage spec as defined in Section 16.

Within one stage spec:

1. Input names are unique.
2. Artifact names are unique.
3. Stored-input paths are pairwise non-overlapping.
4. Artifact roots are pairwise non-overlapping.
5. Input paths, artifact roots, and `BaseSpec.script` are pairwise
   non-overlapping.

After resolving same-run inputs, the external verifier applies the same path
checks to their materialized paths.

### Resolved stage inputs

```python
ResolvedInternalInputRef = Annotated[
    ResolvedStoredInputRef | ResolvedFutureInputRef,
    Field(discriminator="kind"),
]
```

The resolved input-name set equals the planned input-name set. Each resolved
input has the same discriminated kind as its planned input. Section 14 defines
the pointer equality for stored inputs and the producer equality for same-run
inputs.

### Resolved stage specifications

```python
class ResolvedDownloadSpec(ResolvedBaseSpec):
    kind: Literal["download"] = "download"
    spec: DownloadSpec
    inputs: dict[InputName, RemoteFileRef]
    retrieved_at: AwareDatetime


class ResolvedInternalSpec(ResolvedBaseSpec):
    spec: InternalSpec
    inputs: dict[InputName, ResolvedInternalInputRef]


class ResolvedBuildSpec(ResolvedInternalSpec):
    kind: Literal["build"] = "build"
    spec: BuildSpec


class ResolvedEmbedSpec(ResolvedInternalSpec):
    kind: Literal["embed"] = "embed"
    spec: EmbedSpec


class ResolvedTrainSpec(ResolvedInternalSpec):
    kind: Literal["train"] = "train"
    spec: TrainSpec


class ResolvedEvaluateSpec(ResolvedInternalSpec):
    kind: Literal["evaluate"] = "evaluate"
    spec: EvaluateSpec


ResolvedSpec = Annotated[
    ResolvedDownloadSpec
    | ResolvedBuildSpec
    | ResolvedEmbedSpec
    | ResolvedTrainSpec
    | ResolvedEvaluateSpec,
    Field(discriminator="kind"),
]
```

For a download stage:

```text
ResolvedDownloadSpec.inputs
== ResolvedDownloadSpec.spec.inputs

ResolvedDownloadSpec.retrieved_at
<= ResolvedDownloadSpec.completed_at
```

The completed download snapshot records the exact retrieved bytes. A promoted
download artifact can then serve as a stored input selected by a later run.

For every resolved stage:

```text
ResolvedStageRef.resolved_spec
→ loads the matching ResolvedSpec subtype

ResolvedBaseSpec.spec
== stage spec identified by the matching RunStageRef

keys(ResolvedBaseSpec.spec.artifacts)
== keys(ResolvedBaseSpec.artifacts)
```

## 18. Training checkpoint mapping

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

## 19. Evaluation stage

Evaluation applies a fitted prediction function to fixed evaluation inputs. It
uses the same stage, input, artifact, snapshot, measurement, and runtime records
defined above.

The reserved names are:

```python
EVALUATION_MODEL_INPUT: InputName = "model_parameters"
EVALUATION_DATASET_INPUT: InputName = "evaluation_dataset"
PREDICTIONS: ArtifactName = "predictions"
```

An `EvaluateSpec` satisfies:

```text
model_parameters
in EvaluateSpec.inputs

evaluation_dataset
in EvaluateSpec.inputs

set(EvaluateSpec.params.split_inputs)
is a subset of
set(EvaluateSpec.inputs)

predictions
in EvaluateSpec.artifacts
```

The split-input names are unique and differ from `model_parameters` and
`evaluation_dataset`. The evaluation dataset and every split input are
`StoredInputRef` records.

The `model_parameters` input is a `FutureInputRef` or `StoredInputRef`. A
same-run model input selects:

```text
FutureInputRef.producer_artifact
== model_parameters
```

A stored model input resolves through its `ArtifactPointer` to a
`model_parameters` artifact. The evaluation dataset and every declared split
are stored inputs selected before execution.

The executor materializes every evaluation input as read-only. `EvaluateSpec`
does not declare `model_parameters` or `continuation_state` as outputs. Its
artifact mapping contains `predictions` and may contain additional evaluation
outputs.

```text
model_parameters artifact
+ evaluation_dataset artifact
+ split artifacts
        │
        ▼
    EvaluateSpec
        │
        ├── predictions artifact
        └── Measurement rows
```

`EvaluateSpec.params.metric_ids` contains unique metric IDs and satisfies:

```text
set(EvaluateSpec.params.metric_ids)
is a subset of
set(ExperimentSpec.metric_ids)
```

Every measurement produced by the evaluation stage uses one of those metric
IDs. `predictions` is verified through its resolved artifact and stage-result
snapshot. Metric values remain `Measurement` records.

The resolved record is `ResolvedEvaluateSpec`. It embeds the exact
`EvaluateSpec`, resolves every input, records the selected environment and
runtime state, and records the `predictions` artifact in the same snapshot as
the resolved spec.

## 20. Benchmark specification and confirmation

A benchmark fixes the evaluation data, splits, metrics, acceptance criteria,
and confirmation count applied to candidate run plans.

```python
BenchmarkId = HumanId


class MetricCriterion(ProtocolModel):
    metric_id: MetricId
    comparison: Literal["ge", "le"]
    threshold: float = Field(allow_inf_nan=False)


class BenchmarkSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    benchmark_id: BenchmarkId
    evaluation_dataset: ArtifactPointerRef
    splits: dict[InputName, ArtifactPointerRef] = Field(min_length=1)
    metrics: tuple[MetricCriterion, ...] = Field(min_length=1)
    confirmation_count: Literal[2] = 2
```

Benchmark split names and metric IDs are unique. The benchmark file is:

```text
benchmarks/<benchmark_id>.spec.yaml
```

`RunSpec.source` identifies the exact benchmark file. A benchmark run satisfies:

```text
RunSpec.benchmark_id
== BenchmarkSpec.benchmark_id

exactly one loaded stage spec has kind evaluate

EvaluateSpec.inputs[evaluation_dataset].pointer
== BenchmarkSpec.evaluation_dataset

set(EvaluateSpec.params.split_inputs)
== set(BenchmarkSpec.splits)

EvaluateSpec.inputs[split_name].pointer
== BenchmarkSpec.splits[split_name]

set(EvaluateSpec.params.metric_ids)
== set(BenchmarkSpec.metrics.metric_id)
```

The benchmark executor completes one successful `ResolvedRun` and one separate
confirmation execution of the same frozen $q$. The successful attempt selected
by `ResolvedRun.successful_attempt_id` and the confirmation attempt use the same
`RunSpec`, exact stage-spec files, source, seed, reproducibility controls,
shared environment, stage overrides, and inputs.

The confirmation record is:

```python
class ResolvedBenchmarkSpecRef(ResolvedFileRef):
    kind: Literal["benchmark_spec"] = "benchmark_spec"
    stored_at: GitFileRef


class BenchmarkResult(ProtocolModel):
    schema_version: Literal[1] = 1
    benchmark: ResolvedBenchmarkSpecRef
    run: ResolvedRunRef
    confirmation: RunAttempt
    status: Literal["passed", "failed"]
    completed_at: AwareDatetime


class ResolvedBenchmarkResultRef(ResolvedFileRef):
    kind: Literal["benchmark_result"] = "benchmark_result"
    stored_at: HuggingFaceFileRef
```

The benchmark reference satisfies:

```text
ResolvedBenchmarkSpecRef.stored_at.repository
== RunSpec.source.repository

ResolvedBenchmarkSpecRef.stored_at.commit
== RunSpec.source.commit

ResolvedBenchmarkSpecRef.stored_at.path
== benchmarks/<RunSpec.benchmark_id>.spec.yaml
```

The selected run attempt and `BenchmarkResult.confirmation` have distinct
attempt IDs, `succeeded` status, and every stage declared by the shared
`RunSpec`. `BenchmarkResult.completed_at` is at or after the completion times of
the selected `ResolvedRun` and confirmation attempt.

Let their realized runtime states be $e,e'\in E_q$. Estimator parity requires:

$$
T_{\alpha,\beta,q}(e)
=
T_{\alpha,\beta,q}(e')
=
\widehat{\theta}_q.
$$

The verifier establishes this equality by loading the artifact selected by
`RunSpec.estimator` from the selected run attempt and confirmation attempt and
comparing every file's SHA-256, byte count, relative path, and bundle
membership.

Prediction parity applies the same comparison to the `predictions` artifact
produced by each attempt's evaluation stage.

For every `MetricCriterion`, each attempt must contain a matching
evaluation-stage `Measurement`. A `ge` criterion requires a value greater than
or equal to its threshold. An `le` criterion requires a value less than or
equal to its threshold.

`BenchmarkResult.status` is `passed` exactly when estimator parity, prediction
parity, and every metric criterion hold across both executions. A promoted
benchmark estimator uses an `ArtifactPointer` satisfying:

```text
ArtifactPointer.run
== BenchmarkResult.run

ArtifactPointer.artifact
== selected RunSpec.estimator

ArtifactPointer.benchmark_result
== ResolvedBenchmarkResultRef for the passed BenchmarkResult
```

## 21. Validation and external verification

Pydantic rejects a protocol record before publication when the record violates
its own schema or internal invariants. The external verifier retrieves every
referenced file, verifies its identity, parses its expected record type, and
checks relationships that cross file boundaries.

```text
Pydantic
└── establishes that each loaded record satisfies its model

external verifier
├── proves each reference identifies the recorded bytes
├── proves resolved state satisfies requested state
└── proves the complete provenance graph is internally consistent
```

### Pydantic validation

Pydantic enforces:

1. Closed, immutable records.
2. Identifier, path, SHA-256, commit, timestamp, and finite-number syntax.
3. Required fields, nonempty mappings, and discriminated unions.
4. Unique stage, artifact, factor, level, variant, replicate, seed, metric, and
   bundle-member identities within their containing records, plus unique stage
   snapshots, measurement files, and log files within an attempt.
5. Single-file cardinality of one and bundle cardinality of at least two.
6. Matching declared and resolved artifact-name sets inside one resolved stage
   spec.
7. Attempt status, failure-reason, and timestamp relationships.
8. The training checkpoint input pair and reserved output pair.
9. The evaluation model, dataset, split, metric, and predictions requirements.
10. Benchmark split, metric, confirmation, and result requirements.

### Run-plan verification

Starting from a `ResolvedRunSpecRef`, the verifier:

1. Retrieves the `RunSpec` bytes and checks SHA-256 and byte count.
2. Rejects duplicate YAML keys and requires the canonical run-spec path.
3. Loads `ExperimentSpec`, `VariantSpec`, and the optional `BenchmarkSpec` from
   `RunSpec.source`.
4. Checks the experiment, variant, replicate, global-seed, typed-parameter,
   metric, and benchmark equalities in Sections 16 and 20.
5. Retrieves every stage-spec file identified by `RunSpec.stages` and checks
   its SHA-256 and byte count.
6. Requires each stage spec, script, artifact root, and stored-input path to use
   the canonical repository location defined in Section 23.
7. Parses each file through the `Spec` union.
8. Checks that every `FutureInputRef` selects an earlier stage and a declared
   producer artifact.
9. Checks input, script, and artifact-path disjointness after resolving every
   input path.
10. Checks that `RunSpec.estimator` selects `model_parameters` from a training
   stage.

These checks reconstruct the complete frozen $q$ from its root record and exact
stage-spec files.

### Resolved-stage verification

For each `ResolvedStageRef`, the verifier:

1. Retrieves `ResolvedStageRef.resolved_spec` from
   `ResolvedStageRef.snapshot`.
2. Requires its canonical resolved-stage path and checks its SHA-256 and byte
   count.
3. Parses the file through the `ResolvedSpec` union.
4. Requires its embedded stage spec to equal the stage spec selected by the
   corresponding `RunStageRef`.
5. Verifies `ResolvedBaseSpec.source` against `RunSpec.source` and
   `BaseSpec.script`.
6. Resolves the selected stage environment and checks the environment,
   execution context, global seed, and global reproducibility controls defined
   in Section 15.
7. Checks the canonical command.
8. Checks the resolved input names and kinds against the planned inputs.
9. Checks that `completed_at` lies within the containing attempt and does not
   precede the prior completed stage.
10. For a download stage, checks that `retrieved_at` lies between attempt start
    and stage completion.

These checks establish that the recorded runtime state satisfies:

$$
e_j
\in
E_{q,j}.
$$

### Artifact verification

For every artifact name in the loaded resolved stage spec, the verifier:

1. Selects the declared `ArtifactSpec` and matching `ResolvedArtifact`.
2. Checks single-file or bundle cardinality.
3. Checks every path equality, bundle-member order, bundle containment, and
   cross-artifact disjointness.
4. Retrieves every `SnapshotFileRef` from the stage-result snapshot.
5. Checks every file's SHA-256 and byte count.
6. Retrieves the loader from `RunSpec.source` using `ArtifactSpec.loader`.
7. Materializes the verified file or directory and invokes `load(path)`.

This traversal establishes:

$$
L_a
\left(
F_j(a)
\right)
=
v_a^{(j)}.
$$

### Input-lineage verification

For a stored input, the verifier:

1. Retrieves and checks the `ArtifactPointer` file.
2. Retrieves and checks the selected `ResolvedRun`.
3. Selects its successful attempt.
4. Selects the producer `ResolvedStageRef` and named artifact.
5. Verifies and materializes the complete artifact.
6. For checkpoint inputs, requires both pointers to select one resolved run,
   one producer stage, `model_parameters`, and `continuation_state`.
7. For a stored evaluation model, requires the pointer to select
   `model_parameters`.

For a same-run input, the verifier:

1. Selects the earlier `ResolvedStageRef` named by `producer_stage_id`.
2. Loads its resolved stage spec.
3. Selects `producer_artifact` from its artifact mapping.
4. Verifies and materializes the complete artifact.

### Training-continuation verification

For a training stage initialized from a checkpoint, the verifier establishes:

```text
checkpoint_model_parameters producer
== checkpoint_continuation_state producer

checkpoint_model_parameters artifact
== model_parameters

checkpoint_continuation_state artifact
== continuation_state
```

The replay executor invokes both loaders and reconstructs:

$$
s_\ell^{(0)}
=
s_k^{(T_k)}.
$$

### Run-result verification

For a `ResolvedRun`, the verifier:

1. Checks attempt IDs, order, timestamps, statuses, and failure reasons.
2. Requires each attempt's resolved stages to form an ordered prefix of
   `RunSpec.stages`.
3. Requires the successful attempt to contain every stage exactly once and in
   order.
4. Verifies every stored and same-run input consumed by every completed stage
   in every attempt.
5. Verifies every measurement and log file.
6. Requires canonical measurement and log paths.
7. Checks every measurement against the run, attempt, stage, experiment, and
   stage-specific metric identities.
8. Loads the estimator artifact selected by `RunSpec.estimator`.

For a `BenchmarkResult`, the verifier additionally performs the benchmark-spec,
confirmation-attempt, estimator-parity, prediction-parity, metric-criterion,
and promotion relationships defined in Section 20. The confirmation uses a new
attempt ID and stage-result snapshots disjoint from every attempt in the
selected run.

## 22. Execution and publication sequence

The protocol publishes immutable snapshots in dependency order:

| Snapshot | Repository | Contents |
|---|---|---|
| A | Git | Source, experiment records, benchmark specs, loaders, lockfile, and existing promotion pointers. |
| B | Git | One `RunSpec` and every stage-spec file identified by it. |
| $C_{i,j}$ | Artifact repository | The resolved spec and every artifact file for stage $j$ of attempt $i$. |
| $D_i$ | Artifact repository | Closed measurement and log files for attempt $i$. |
| E | Artifact repository | The terminal `ResolvedRun`. |
| F | Artifact repository | The optional `BenchmarkResult`. |
| G | Git | Optional promotion pointers. |

### Freeze the run plan

1. Publish source snapshot A.
2. Select the experiment, variant, replicate, optional benchmark, shared
   environment, reproducibility controls, and ordered stage specs.
3. Set `RunSpec.source` to snapshot A.
4. Validate and serialize every stage spec.
5. Calculate each stage-spec file's SHA-256 and byte count.
6. Construct and validate `RunSpec` with its ordered `RunStageRef` records.
7. Publish `RunSpec` and every stage-spec file together as snapshot B.
8. Retrieve and verify every file in snapshot B.

Snapshot B fixes $q$.

### Execute one attempt

For attempt $i$:

1. Allocate its `attempt_id` and record `started_at`.
2. Retrieve and verify snapshots A and B.
3. Materialize every stored input.
4. Execute stages in `RunSpec.stages` order.
5. Resolve each same-run input through an earlier `ResolvedStageRef`.
6. Apply `RunSpec.seed`, `RunSpec.reproducibility`, and the selected stage
   environment.
7. Construct and record the canonical command.
8. Execute the stage script.
9. Resolve every declared artifact and construct the resolved stage spec.
10. Publish the resolved stage spec and every artifact file together as
    snapshot $C_{i,j}$.
11. Retrieve and verify the complete snapshot.
12. Construct `ResolvedStageRef` from the returned snapshot commit and resolved
    stage-spec file identity.
13. Append the verified stage result to the current attempt.

After the attempt reaches a terminal status:

1. Record `completed_at`, status, and failure reason.
2. Close its measurement and log files.
3. Publish those files as snapshot $D_i$.
4. Retrieve and verify every published file.
5. Construct the complete `RunAttempt`.

```text
stage execution
        │
        ▼
snapshot C_i,j
├── resolved stage spec
└── every file in every named artifact
        │
        ▼
ResolvedStageRef
├── snapshot → repository + commit C_i,j
└── resolved_spec → path + SHA-256 + bytes
```

### Finalize the run

1. Determine the terminal run status and `successful_attempt_id`.
2. Construct `ResolvedRun` with the reference to snapshot B and every completed
   `RunAttempt`.
3. Publish `ResolvedRun` as snapshot E.
4. Retrieve and verify the terminal record and its complete provenance graph.

### Confirm a benchmark

For a benchmark run:

1. Execute one additional successful confirmation attempt against the same
   snapshot B.
2. Publish and verify its stage-result snapshots $C_{i,j}$ and attempt files
   $D_i$.
3. Compare estimator and prediction artifacts with the successful attempt in
   snapshot E.
4. Check every benchmark metric criterion.
5. Construct and publish `BenchmarkResult` as snapshot F.
6. Retrieve and verify the benchmark result.

### Promote an artifact

Promotion constructs an `ArtifactPointer` selecting:

```text
ResolvedRun at snapshot E
+ StageArtifactRef
+ passed BenchmarkResult at snapshot F, when benchmark approval is required
```

The pointer is published under `inputs/` in snapshot G. A later source snapshot
may select that pointer through a `StoredInputRef`.

## 23. Repository layout

Pointer filenames use:

```python
SelectionName = HumanId
```

Each selection name is scoped by its dataset, prior, or model identity.

```text
repository/
├── README.md
├── pyproject.toml
├── environment.yml
├── .gitignore
├── docs/
├── scripts/
├── src/
│   └── mantra/
│       ├── datasets/
│       │   └── <dataset_id>/
│       │       └── download.py
│       ├── priors/
│       │   └── <prior_id>/
│       │       └── build.py
│       ├── models/
│       │   └── <model_id>/
│       │       ├── embed.py
│       │       ├── train.py
│       │       └── evaluate.py
│       ├── metrics/
│       │   └── <metric_id>.py
│       └── artifact_loaders/
│           └── <loader_id>.py
├── tests/
├── inputs/
│   ├── benchmarks/
│   │   └── <benchmark_id>/
│   │       └── <selection_name>.pointer.yaml
│   ├── datasets/
│   │   └── <dataset_id>/
│   │       └── <selection_name>.pointer.yaml
│   ├── priors/
│   │   └── <prior_id>/
│   │       └── <selection_name>.pointer.yaml
│   └── models/
│       └── <model_id>/
│           └── <selection_name>.pointer.yaml
├── benchmarks/
│   └── <benchmark_id>.spec.yaml
└── experiments/
    └── <experiment_id>/
        ├── spec.yaml
        ├── README.md
        ├── variants/
        │   └── <variant_id>.spec.yaml
        └── runs/
            └── <variant_id>/
                └── <run_id>/
                    ├── spec.yaml
                    ├── resolved.yaml
                    ├── benchmark.result.yaml
                    ├── stages/
                    │   └── <stage_id>/
                    │       ├── spec.yaml
                    │       └── resolved.yaml
                    ├── artifacts/
                    │   ├── datasets/
                    │   │   └── <dataset_id>/
                    │   │       └── dataset.h5ad
                    │   ├── priors/
                    │   │   └── <prior_id>/
                    │   │       └── prior.pt
                    │   ├── models/
                    │   │   └── <model_id>/
                    │   │       ├── embedding.pt
                    │   │       ├── model_parameters.safetensors
                    │   │       └── continuation_state.pt
                    │   └── evaluations/
                    │       └── <benchmark_id>/
                    │           └── predictions.parquet
                    ├── measurements/
                    │   └── <stage_id>.<metric_id>.jsonl
                    └── logs/
                        ├── <attempt_id>.<stage_id>.stdout.log
                        └── <attempt_id>.<stage_id>.stderr.log
```

`BaseSpec.script` identifies a stage entrypoint beneath the corresponding
identity directory in `src/mantra/`. For example:

```text
src/mantra/priors/depmap/build.py
src/mantra/models/strand/train.py
src/mantra/models/strand/evaluate.py
```

`RunSpec.source` fixes the exact bytes of every entrypoint, imported production
module, metric, and artifact loader.

`scripts/` contains repository-maintenance and developer utilities. Each script
is a thin caller of code in `src/`, has one documented purpose, and remains
outside the stage-entrypoint taxonomy. Scientific transformations executed by
the protocol live under their dataset, prior, or model identity in
`src/mantra/`.

`tests/` contains deterministic checks for protocol models, verifier
relationships, loaders, and production source. Test files are part of snapshot
A and are not stage entrypoints.

The run directory is the durable output root. Artifact files, measurements,
logs, resolved records, and benchmark results use stable repository-relative
paths. Immutable artifact-repository commits distinguish files produced by
different attempts. A separate root `out/` directory is therefore outside the
protocol layout.

A single-file artifact occupies its declared file path. A bundle artifact
occupies its declared directory root, and its loader defines the required
member filenames beneath that root.
