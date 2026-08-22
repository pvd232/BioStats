# MANTRA Provenance Protocol — Stage 1 Version 2

Status: design draft for iterative review

This document defines the target Stage 1 provenance contract. The current
implementation remains in `records.py` and `verifier.py` until the contracts
in this document are frozen and migrated.

---

## 1. Scope

Stage 1 records and verifies one model-building run from its fixed inputs to its
fitted estimator. It defines:

1. A run plan.
2. The runtime states induced by that plan.
3. The condition under which the plan provides strict parameter
   reproducibility.
4. The ordered stage partition declared by the plan.
5. The artifact partition produced by each successful stage.
6. The physical-file partition representing each artifact.
7. The exact files connecting a run, stage, artifact, and measured result.
8. The validators and cross-file verifier checks enforcing those relationships.

Benchmark definitions, benchmark reproducibility, diagnostics, evaluation
records, promotion gates, and SOTA selection belong to the next protocol stage.

### How to read schema names

Protocol files contain records validated by Pydantic models. The following
naming rules identify each record's role.

| Form | Role |
|---|---|
| `*Spec` | Declares requested state. |
| `Resolved*` | Records realized state. |
| `*Ref` | Identifies another object. |
| `ArtifactPointer` | Selects one promoted artifact. |
| `ResolvedArtifact` | Records the physical files representing one named artifact. |
| `Measurement` | Records one metric value. |
| `RunAttempt` | Records one execution attempt. |
| `ResolvedRun` | Records the terminal run result. |

```text
RunSpec + ordered stage specs
→ form q
→ q declares requested state and induces E_q

Resolved records
→ record realized state e

Verifier
→ checks e ∈ E_q
```

The protocol identifies exact files in two forms:

```text
Standalone file
└── ResolvedFileRef
    ├── stored_at
    ├── sha256
    └── bytes

File in a stage-result snapshot
├── StageResultSnapshotRef
│   └── repository + commit
└── SnapshotFileRef
    ├── path
    ├── sha256
    └── bytes
```

Role-specific file references state the expected contents of the referenced
file. For example, `ResolvedRunRef` identifies a file that parses as
`ResolvedRun`.

An artifact pointer illustrates the distinction between a stored object and
references to its file:

```text
ArtifactPointerRef
└── Git repository + commit + path of the pointer file

ResolvedArtifactPointerRef
├── sha256 + bytes of the pointer file
└── stored_at: ArtifactPointerRef

retrieved pointer-file bytes
└── parse as ArtifactPointer
    ├── run: ResolvedRunRef
    └── artifact: StageArtifactRef
```

---

## 2. Fitted estimator under runtime variation

Let $\alpha$ identify a parameterized prediction-function family. It fixes a
parameter space $\Theta_{\alpha}$.

Let $\beta\in\mathcal{B}_\alpha$ identify the chosen estimator.

Let $D\in\mathcal{D}$ be an arbitrary dataset.

Let $e\in E$ be a runtime state: one assignment of the execution parameters
that may vary between executions.

The runtime-indexed estimator is:

$$
\widetilde{T}_{\alpha,\beta}
:
\mathcal{D}\times E
\rightarrow
\Theta_{\alpha}.
$$

It maps a dataset and runtime state to a fitted parameter value.

---

## 3. Run plan, strict parameter reproducibility, and induced partitions

### Run plan

A `RunSpec` and its ordered stage specs form one run plan. Let $r$ denote the
`RunSpec`, and let $\omega_1,\ldots,\omega_m$ denote its stage specs in
`RunSpec.stages` order, where $m\geq 1$. Then:

$$
q
=
\left(
r,
\omega_1,
\ldots,
\omega_m
\right).
$$

Each `RunStageRef` in $r$ identifies its corresponding $\omega_i$ by stage ID,
path, SHA-256, and byte count.

### Strict parameter reproducibility

The plan $q$ selects an exact root dataset $D_0$ and declares a deterministic
data-selection map $S_q$. The dataset supplied to the estimator is:

$$
D_q = S_q(D_0).
$$

$S_q$ contains every operation that determines which observations and features
enter estimation, including dataset selection, quality-control filtering,
perturbation selection, and highly variable gene selection.

The plan $q$ fixes $\alpha$, $\beta$, and $D_q\in\mathcal D$, and induces a
nonempty set of permitted runtime states $E_q\subseteq E$.

Define:

$$
T_{\alpha,\beta,q}:E_q\rightarrow\Theta_\alpha,
$$

where:

$$
T_{\alpha,\beta,q}(e)
=
\widetilde T_{\alpha,\beta}(D_q,e).
$$

The plan $q$ provides strict parameter reproducibility exactly when:

$$
\forall e,e'\in E_q,
\qquad
T_{\alpha,\beta,q}(e)
=
T_{\alpha,\beta,q}(e').
$$

Because $E_q$ is nonempty, the shared result is one value
$\widehat\theta_q\in\Theta_\alpha$:

$$
\forall e\in E_q,
\qquad
T_{\alpha,\beta,q}(e)
=
\widehat\theta_q.
$$

### Stage partition

The ordered stage specs form the stage partition induced by $q$:

$$
\Pi(q)
=
\left\langle
\omega_1,
\ldots,
\omega_m
\right\rangle.
$$

Each member of $\Pi(q)$ is the exact stage spec identified by the corresponding
`RunStageRef`. Before execution, the verifier establishes:

1. Every `RunStageRef.stage_id` is unique.
2. Every `RunStageRef.spec` path is unique.
3. Every `FutureInputRef.producer_stage_id` names an earlier stage.

For the successful attempt, the verifier establishes:

4. Every successfully completed stage records all artifacts declared by its
   stage spec.
5. The successful attempt completes every stage in the declared order.

### Artifact and physical-file partitions

Let $s\in\Pi(q)$ be a stage spec whose execution completed successfully. Let
$N_s$ be the finite, nonempty set of artifact names in its
`BaseSpec.artifacts` mapping.

The stage's `ResolvedBaseSpec` records the same artifact names:

```text
keys(ResolvedBaseSpec.spec.artifacts)
==
keys(ResolvedBaseSpec.artifacts)
==
N_s
```

For each $a\in N_s$, let $F_s(a)$ be the set of physical files identified by
`ResolvedBaseSpec.artifacts[a]`:

```text
ResolvedBaseSpec.artifacts[a]
├── ResolvedSingleFileArtifact.file
│   └── F_s(a) contains one file
└── ResolvedBundleArtifact.members[].file
    └── F_s(a) contains two or more files
```

Each artifact $a$ has a loading function $L_a$ fixed by its `ArtifactSpec`.
The function receives the materialized files in $F_s(a)$ and reconstructs the
value represented by $a$.

Completeness requires:

$$
L_a\left(F_s(a)\right) = a.
$$

Minimality requires that $L_a$ cannot reconstruct $a$ from any proper subset of
$F_s(a)$:

$$
\forall G \subsetneq F_s(a),
\qquad
L_a(G)\ \text{is undefined}.
$$

The artifact partition is:

$$
A(s)
=
\left\{
F_s(a)
\mid
a\in N_s
\right\}.
$$

The complete set of physical artifact files produced by the execution requested
by $s$ is:

$$
O_s
=
\bigcup_{a\in N_s}F_s(a).
$$

The artifact file sets are pairwise disjoint. For distinct $a,b\in N_s$:

$$
F_s(a)\cap F_s(b)=\varnothing.
$$

The induced structure is:

$$
q
\longrightarrow
\Pi(q)
\longrightarrow
A(s)
\longrightarrow
F_s(a)
\longrightarrow
O_s.
$$

### Validity and parsimony

```text
selected Π(q), A(s), and F_s(a)
├── plan design and protocol review
│   └── compare valid alternatives and select the minimum representation
└── Pydantic, verifier, and replay
    └── establish that the selected representation satisfies its contract
```

---

## 4. Protocol overview

The protocol follows the execution of one experiment.

```text
Define the experiment
├── Experiment Spec
├── Variant Spec
└── Replicate Spec
        │
        ▼ select the variant, replicate, and seed
Freeze the run plan q
├── RunSpec
└── ordered stage-spec files
        │
        ▼ execute each stage spec in order
Execute a RunAttempt
├── materialize stored and same-run inputs
├── run each stage command
└── record measurements and logs
        │
        ▼ publish each completed stage
Record stage results
└── ResolvedStageRef
    └── one stage-result snapshot
        ├── resolved stage spec
        └── every file in each named artifact
        │
        ▼ record the terminal result
Finalize the run
└── ResolvedRun
    ├── exact RunSpec file
    ├── every RunAttempt
    └── successful_attempt_id
        │
        ▼ retrieve files and check relationships
Verify the provenance chain
```

### Define the experiment

`ExperimentSpec` records factors, permitted levels, variant IDs, replicate
specs, seeds, and metric IDs. `VariantSpec` assigns one permitted level to every
factor and records the typed stage parameters implementing that assignment.
`ReplicateSpec` supplies the seed selected for one run.

### Freeze the run plan

`RunSpec` binds one experiment, variant, replicate, source commit, seed, final
estimator artifact, and ordered sequence of `RunStageRef` records. Each
`RunStageRef` identifies one exact stage-spec file. Together, the `RunSpec` and
those stage-spec files form $q$ and declare the stage partition $\Pi(q)$.

### Execute an attempt

`StoredInputRef` selects a promoted artifact. `FutureInputRef` selects a named
artifact produced by an earlier stage. `RunAttempt` records one execution under
some $e\in E_q$.

### Record stage results

Each completed stage publishes one snapshot containing its resolved stage spec
and every physical file in its named artifacts. `ResolvedStageRef` identifies
that snapshot. `ResolvedBaseSpec.artifacts` represents $A(s)$, and each
`ResolvedArtifact` contains one file set $F_s(a)$.

`ResolvedFileRef` records the SHA-256, byte count, and immutable storage
location of a standalone protocol file. `SnapshotFileRef` records the path,
SHA-256, and byte count of one file inside a stage-result snapshot.

### Finalize the run

`Measurement` records a metric value produced during an attempt. `RunAttempt`
records its resolved stages, measurement files, log files, status, and times.
`ResolvedRun` records every attempt and identifies the successful attempt.

### Promote an artifact

`ArtifactPointer` selects one `StageArtifactRef` through the exact terminal
`ResolvedRun` that contains its producing attempt.

```text
ArtifactPointer
├── run → ResolvedRunRef → loads ResolvedRun
└── artifact: StageArtifactRef
        │
        ▼ select the successful RunAttempt
    ResolvedStageRef
        │
        ▼ load its resolved stage spec
    ResolvedBaseSpec.artifacts[artifact_name]
        │
        ▼
    exact artifact files
```

### Verify the provenance chain

The enforcement stack establishes a byte-verified derivation from the fitted
estimator back to the run plan and every persisted input.

Pydantic validates each record before the verifier uses it:

```text
stored record bytes
→ parse as the declared Pydantic model
→ enforce field types, discriminated unions, cardinality, uniqueness,
  and equalities visible within that record
→ typed record
```

The external verifier begins with `ResolvedRun` and follows every reference
needed to reconstruct the producing execution:

```text
ResolvedRun
├── spec
│   └── verify bytes → load RunSpec
│       ├── load ExperimentSpec and VariantSpec
│       └── verify every ordered stage-spec file
└── successful RunAttempt
    ├── ResolvedStageRef
    │   └── verify stage-result snapshot
    │       ├── load ResolvedBaseSpec
    │       │   ├── compare its embedded stage spec with the run-plan stage spec
    │       │   ├── verify source, environment, command, and execution context
    │       │   └── follow each resolved input
    │       │       ├── stored input → ArtifactPointer → producing ResolvedRun
    │       │       └── future input → earlier ResolvedStageRef
    │       └── verify every file in each named artifact
    ├── verify measurement files
    └── verify log files
```

Each file-reference traversal retrieves the target bytes and compares their
SHA-256 and byte count with the reference. The verifier parses the expected
model and checks the cross-record equality that connects it to the preceding
record. Successful traversal binds the estimator files to the successful stage
execution, the stage execution to its requested stage spec and runtime
controls, and every stored or same-run input to the verified artifact that
supplied its bytes.

---

## 5. Runtime coordinates represented by the protocol

The following records connect the plan to one realized runtime state:

| Runtime coordinate | Plan record | Realized record |
|---|---|---|
| Source snapshot | `RunSpec.source` and `BaseSpec.script` | `ResolvedBaseSpec.source` |
| Stage-spec bytes and order | `RunSpec.stages` | `RunAttempt.resolved_stages` |
| Input bytes | `StoredInputRef` or `FutureInputRef` | `ResolvedInternalSpec.inputs` |
| Stage parameters | stage-specific `params` | embedded `ResolvedBaseSpec.spec.params` |
| Provisioned environment | `GCEEnvironmentSpec` | `ResolvedGCEEnvironment` |
| Randomness, algorithms, precision, and parallelism | `ReproducibilitySpec` | applied controls in `ExecutionContext` |
| Executed command | derived from `BaseSpec.script` and `RunStageRef.spec` | `ResolvedBaseSpec.command` |

For Stage 1 strict execution, the plan fixes:

```text
source and dependency bytes
input bytes
stage-spec bytes and order
command
stage parameters
seed
deterministic-algorithm settings
precision settings
machine image
machine type and compute backend
numerical-runtime versions
parallelism
```

Location-only facts such as GCE zone remain unrestricted.

A coordinate omitted from the plan remains variable in $E_q$. If variation in
that coordinate changes the fitted parameters, the resulting pair of executions
is a counterexample to strict parameter reproducibility.

---

## 6. Source snapshot and run-plan snapshot

The protocol uses two immutable Git snapshots.

```text
Source commit A
├── source code
├── experiment file
├── variant files
├── metric implementations
├── lockfile
└── promoted-input pointers
        │
        ▼ create and validate the concrete run plan
Run-plan commit B
├── experiments/<experiment_id>/runs/<variant_id>/<run_id>/spec.yaml
└── stage-spec files
        │
        ▼ execute B's plan using A's source
stage execution
```

`RunSpec.source` identifies commit A. `ResolvedRun.spec.stored_at` identifies
commit B. Every `RunStageRef` supplies the path, SHA-256, and byte count of one
stage spec stored in commit B.

The source snapshot is created first. The concrete `RunSpec` and stage specs are
then validated, hashed, and published together in the run-plan snapshot before
execution begins.

---

## 7. File identity and storage

All protocol models reject unexpected fields and are frozen after validation:

```python
class ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

The shared scalar types include:

```text
RepoRelPath  normalized POSIX path relative to the repository root
SHA256       64 lowercase hexadecimal characters
GitCommit    immutable 40- or 64-character hexadecimal Git commit
HumanId      validated identifier used by run, stage, artifact, and experiment IDs
```

Storage locations are:

```python
class RemoteFileRef(ProtocolModel):
    kind: Literal["remote"] = "remote"
    url: HttpUrl
    version: NonEmptyStr


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


class StageResultSnapshotRef(ProtocolModel):
    kind: Literal["huggingface"] = "huggingface"
    repository: NonEmptyStr
    commit: GitCommit
    repo_type: Literal["model", "dataset", "space"]


StorageRef = Annotated[
    GitFileRef | HuggingFaceFileRef,
    Field(discriminator="kind"),
]
```

An exact file reference records:

```python
class ResolvedFileRef(ProtocolModel):
    sha256: SHA256
    bytes: int = Field(ge=0)
    stored_at: StorageRef


class SnapshotFileRef(ProtocolModel):
    path: RepoRelPath
    sha256: SHA256
    bytes: int = Field(ge=0)
```

Role-specific references restrict the permitted storage location, identify the
expected document type, or perform both roles:

```python
class ResolvedGitFileRef(ResolvedFileRef):
    stored_at: GitFileRef


class ResolvedRunSpecRef(ResolvedFileRef):
    kind: Literal["run_spec"] = "run_spec"
    stored_at: GitFileRef


class ResolvedRunRef(ResolvedFileRef):
    kind: Literal["resolved_run"] = "resolved_run"
    stored_at: HuggingFaceFileRef


class ArtifactPointerRef(GitFileRef):
    pass


class ResolvedArtifactPointerRef(ResolvedFileRef):
    kind: Literal["artifact_pointer"] = "artifact_pointer"
    stored_at: ArtifactPointerRef
```

`ResolvedFileRef.stored_at` identifies an immutable Git or Hugging Face
repository revision and repository-relative path. `sha256` and `bytes` identify
the retrieved file contents.

The verifier retrieves `stored_at`, recalculates SHA-256 and byte count, and
requires equality with the recorded values.

```text
ResolvedFileRef
├── stored_at.repository
├── stored_at.commit
├── stored_at.path
├── sha256
└── bytes
```

`StageResultSnapshotRef` identifies the immutable repository revision containing
one completed stage. `SnapshotFileRef` identifies one file within that revision.
The verifier retrieves a snapshot member by combining:

```text
ResolvedStageRef.snapshot
+ SnapshotFileRef.path
→ exact storage location
```

It then recalculates the member's SHA-256 and byte count and compares them with
`SnapshotFileRef.sha256` and `SnapshotFileRef.bytes`.

Artifact storage paths mirror the declared repository-relative output paths.
Stored-input materialization paths remain independent of the pointer file's Git
path and the artifact's remote storage path.

For a run identified by `experiment_id`, `variant_id`, and `run_id`, every
declared artifact path lies beneath:

```text
experiments/<experiment_id>/runs/<variant_id>/<run_id>/artifacts/
```

---

## 8. Artifact declarations and resolved artifacts

```python
ArtifactName = HumanId
ArtifactLoaderId = HumanId
```

### Stage declaration

```python
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
    artifacts: dict[ArtifactName, ArtifactSpec] = Field(min_length=1)
```

For a file artifact, `path` is its canonical file path. For a bundle artifact,
`path` is its canonical directory root.

An artifact loader is a Python file stored at:

```text
src/mantra/artifact_loaders/<loader_id>.py
```

`ArtifactSpec.loader` supplies the `loader_id`. The verifier retrieves the loader file using:

```text
RunSpec.source.repository
+
RunSpec.source.commit
+
src/mantra/artifact_loaders/<loader_id>.py
```

The loader defines:

```python
def load(path: Path) -> object:
    ...
```

For a single-file artifact, `path` identifies the materialized file.

For a bundle artifact, `path` identifies the materialized directory containing every member of $F_s(a)$.

During replay, the executor:

1. Verifies every file in $F_s(a)$.
2. Materializes the complete file set.
3. Loads the module identified by `ArtifactSpec.loader`.
4. Calls `load(path)`.
5. Supplies the returned value to the consuming stage.

### Resolved representation

```python
class ResolvedSingleFileArtifact(ProtocolModel):
    kind: Literal["file"] = "file"
    file: SnapshotFileRef


class ResolvedBundleMember(ProtocolModel):
    relative_path: RepoRelPath
    file: SnapshotFileRef


class ResolvedBundleArtifact(ProtocolModel):
    kind: Literal["bundle"] = "bundle"
    members: tuple[ResolvedBundleMember, ...] = Field(
        min_length=2
    )


ResolvedArtifact = Annotated[
    ResolvedSingleFileArtifact | ResolvedBundleArtifact,
    Field(discriminator="kind"),
]


class ResolvedBaseSpec(ProtocolModel):
    spec: BaseSpec
    artifacts: dict[ArtifactName, ResolvedArtifact] = Field(min_length=1)
```

The cardinality rule is exact:

```text
|F_s(a)| = 1  → ResolvedSingleFileArtifact
|F_s(a)| ≥ 2  → ResolvedBundleArtifact
```

### Path invariants

For a declared file artifact:

```text
ResolvedSingleFileArtifact.file.path
==
SingleFileArtifactSpec.path
```

For every bundle member:

```text
ResolvedBundleMember.file.path
==
BundleArtifactSpec.path
/
ResolvedBundleMember.relative_path
```

Bundle member paths are unique, remain beneath the bundle root, and appear in
canonical `relative_path` order. Artifact roots within one stage are pairwise
non-overlapping.

---

## 9. Stage-result snapshots and promotion pointers

Each completed stage publishes one stage-result snapshot:

```python
class ResolvedStageRef(ProtocolModel):
    stage_id: StageId
    snapshot: StageResultSnapshotRef
    resolved_spec: SnapshotFileRef
```

```yaml
stage_id: train
snapshot:
  kind: huggingface
  repository: machina/mantra-artifacts
  commit: <stage-result-commit>
  repo_type: dataset
resolved_spec:
  path: experiments/e001/runs/baseline/01JABC/stages/train/resolved.yaml
  sha256: <resolved-spec-sha256>
  bytes: 8421
```

The snapshot contains:

```text
ResolvedStageRef.snapshot
├── ResolvedStageRef.resolved_spec
│   └── loads ResolvedBaseSpec
└── every file identified by a SnapshotFileRef reached through
    ResolvedBaseSpec.artifacts[artifact_name]
```

The artifact names satisfy:

```text
keys(ResolvedBaseSpec.spec.artifacts)
==
keys(ResolvedBaseSpec.artifacts)
==
N_s
```

For every artifact name $a$, the verifier performs:

```text
ResolvedStageRef.snapshot
+ ResolvedStageRef.resolved_spec.path
→ retrieve and verify the resolved stage-spec bytes
→ parse ResolvedBaseSpec
→ select ResolvedBaseSpec.artifacts[a]
→ retrieve and verify every SnapshotFileRef in F_s(a)
```

The loaded resolved stage spec contains the exact stage spec, source file,
resolved inputs, environment, execution context, command, named artifacts, and
completion time.

`ResolvedStageRef.snapshot.commit` supplies the storage commit for
`ResolvedStageRef.resolved_spec` and every artifact `SnapshotFileRef` reached
through the loaded resolved stage spec.

### Promotion pointer

```python
class StageArtifactRef(ProtocolModel):
    stage_id: StageId
    artifact_name: ArtifactName


class ArtifactPointer(ProtocolModel):
    schema_version: Literal[1] = 1
    run: ResolvedRunRef
    artifact: StageArtifactRef
```

An `ArtifactPointer` selects one artifact accepted as a reusable input. The
pointer is committed under `inputs/` after promotion.

```text
ArtifactPointer.run
→ retrieve and verify ResolvedRun
→ select the RunAttempt named by successful_attempt_id

ArtifactPointer.artifact.stage_id
→ select ResolvedStageRef from RunAttempt.resolved_stages
→ retrieve and verify its resolved stage spec

ArtifactPointer.artifact.artifact_name
→ select ResolvedBaseSpec.artifacts[artifact_name]
→ retrieve and verify every file in the artifact
```

The selected `StageArtifactRef.stage_id` must occur in the successful attempt.
The selected `StageArtifactRef.artifact_name` must occur in that stage's loaded
`ResolvedBaseSpec.artifacts` mapping.

---

## 10. Stage inputs

### Stored input

```python
class StoredInputRef(ProtocolModel):
    kind: Literal["stored"] = "stored"
    pointer: ArtifactPointerRef
    path: RepoRelPath


class ResolvedStoredInputRef(ProtocolModel):
    kind: Literal["stored"] = "stored"
    pointer: ResolvedArtifactPointerRef
```

The pointer records satisfy:

```text
ResolvedStoredInputRef.pointer.stored_at
==
StoredInputRef.pointer
```

The traversal is:

```text
ResolvedStoredInputRef.pointer
→ retrieve pointer-file bytes
→ verify SHA-256 and byte count
→ parse ArtifactPointer
→ ArtifactPointer.run
→ retrieve and verify ResolvedRun
→ successful RunAttempt
→ ResolvedStageRef selected by ArtifactPointer.artifact.stage_id
→ loaded ResolvedBaseSpec
→ ResolvedBaseSpec.artifacts[
    ArtifactPointer.artifact.artifact_name
]
→ ResolvedSingleFileArtifact | ResolvedBundleArtifact
```

`StoredInputRef.path` is the local path presented to the stage script. For a
bundle, it is the local bundle root and every member is placed beneath it using
`ResolvedBundleMember.relative_path`.

### Same-run input

```python
class FutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    producer_stage_id: StageId
    producer_artifact: ArtifactName


class ResolvedFutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    producer: ResolvedStageRef
```

The consumer identifies one exact member of the producer's artifact partition:

```text
FutureInputRef.producer_stage_id
→ producer ResolvedStageRef in the current RunAttempt

FutureInputRef.producer_artifact
→ artifact name in the producer's loaded ResolvedBaseSpec.artifacts
```

The verifier requires:

```text
ResolvedFutureInputRef.producer
==
producer ResolvedStageRef

FutureInputRef.producer_artifact
in
keys(producer ResolvedBaseSpec.artifacts)
```

The future input's local path is the path declared by:

```text
producer ResolvedBaseSpec.spec.artifacts[
    FutureInputRef.producer_artifact
].path
```

### Download root

A `DownloadSpec` records the external source URL and source-defined version. Its
resolved record adds the retrieval time:

```python
class ResolvedDownloadSpec(ResolvedBaseSpec):
    retrieved_at: AwareDatetime
```

The resolved record satisfies:

```text
ResolvedDownloadSpec.inputs
==
ResolvedDownloadSpec.spec.inputs

ResolvedDownloadSpec.retrieved_at
<=
ResolvedDownloadSpec.completed_at
```

The completed download stage hashes the retrieved bytes and publishes them in
its stage-result snapshot. The published artifact establishes an exact root
dataset $D_0$. A model-building plan selects those bytes through an
`ArtifactPointer`; its declared data-selection map $S_q$ produces:

$$
D_q = S_q(D_0).
$$

`RemoteFileRef.url`, `RemoteFileRef.version`, and
`ResolvedDownloadSpec.retrieved_at` record the external source. The resulting
`SnapshotFileRef.sha256` and `SnapshotFileRef.bytes` identify the exact dataset
bytes stored in the Hugging Face snapshot.

```text
RemoteFileRef
├── url
└── version
        │
        ▼ execute DownloadSpec
ResolvedDownloadSpec.retrieved_at
        │
        ▼ hash and publish the result
ResolvedStageRef.snapshot
└── SnapshotFileRef
    ├── path
    ├── sha256
    └── bytes
        │
        ▼ promote for later selection
ArtifactPointer
```

---

## 11. Experiment, variant, replicate, and seed

`RunSpec.source` fixes the Git repository and commit containing the selected
experiment and variant files. Their repository-relative paths are:

```text
experiments/<experiment_id>/spec.yaml
experiments/<experiment_id>/variants/<variant_id>.spec.yaml
```

```text
ExperimentSpec
├── factors and permitted levels
├── variant IDs
├── replicate IDs and seeds
└── metric IDs

VariantSpec
├── one selected level per factor
└── exact typed stage parameters implementing the selection
```

### Typed variant implementation

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


VariantStageParams = Annotated[
    BuildVariantStageParams
    | EmbedVariantStageParams
    | TrainVariantStageParams,
    Field(discriminator="kind"),
]


class VariantSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    experiment_id: ExperimentId
    variant_id: VariantId

    levels: dict[FactorId, LevelId]
    stage_params: tuple[VariantStageParams, ...] = Field(min_length=1)
```

`VariantSpec.stage_params` contains one record for every parameterized stage in
the run. Stage IDs are unique within that tuple. The verifier requires:

```text
set(VariantSpec.stage_params.stage_id)
==
set(stage IDs whose loaded stage specs contain params)

VariantSpec.stage_params[stage_id].params
==
loaded stage spec.params
```

The selected level IDs record the scientific factor assignment. The typed
parameter objects record its exact implementation across any number of stages.

### Seed authority

```python
class RNGSeedSpec(ProtocolModel):
    seed: int
```

The complete seed equality is:

```text
selected ReplicateSpec.seed
==
RunSpec.seed
==
every stage's ReproducibilitySpec.randomness.seed
```

Before each stage executes, MANTRA applies the stage's recorded seed to Python,
NumPy, PyTorch, and the DataLoader generator. Every retry of one run uses the
same seed. Selecting another replicate supplies its seed to another `RunSpec`.

---

## 12. Environment, numerical controls, and command

The pre-execution records and realized records have separate roles:

```text
GCEEnvironmentSpec
└── requested provisioning
    ├── exact machine image
    ├── machine type
    ├── compute backend
    └── lockfile

ReproducibilitySpec
└── requested numerical controls
    ├── randomness
    ├── deterministic algorithms
    ├── precision
    └── parallelism

ExecutionContext
└── values recorded during execution
    ├── host and CPU
    ├── compute backend
    ├── numerical runtime
    ├── applied randomness, determinism, and precision controls
    └── parallelism
```

The schema represents an exact policy with one required value, a permitted-set
policy with a nonempty tuple of allowed values, and an unrestricted policy by
omitting that coordinate from the requirement model.

The verifier checks each constrained coordinate against the realized
`ExecutionContext`.

### Canonical command

For the `RunStageRef` and loaded stage spec belonging to stage $s$, the executor
constructs:

```text
python <BaseSpec.script> <RunStageRef.spec>
```

The resolved stage record must satisfy:

```python
ResolvedBaseSpec.command == (
    "python",
    str(ResolvedBaseSpec.spec.script),
    str(run_stage_ref.spec),
)
```

A stage type requiring another argument declares that argument through an
explicit typed field. The executor derives the complete command from the stage
spec.

---

## 13. Run, attempt, and measurement records

```python
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

    seed: int
    source: GitSource
    stages: tuple[RunStageRef, ...] = Field(min_length=1)
    estimator: StageArtifactRef
```

`RunSpec.estimator` identifies the artifact whose loading contract reconstructs
$\widehat\theta_q$.

```python
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

Each `ResolvedStageRef` identifies one stage-result snapshot containing the
resolved stage spec and every file in its named artifacts.

A successful attempt satisfies:

1. `failure_reason` is null.
2. `resolved_stages` contains every run stage exactly once and in order.
3. Every completed stage has at least one named artifact, and every file in each
   artifact has been verified.
4. `measurement_files` and `log_files` identify the files produced by that
   attempt.

A failed, preempted, or cancelled attempt records a nonempty `failure_reason`.
Its `resolved_stages` form an ordered prefix of `RunSpec.stages`.

`ResolvedRun` records all attempts in execution order and identifies the sole
successful attempt when the run succeeds.

### Measurements

A measurement records:

```text
run_id
attempt_id
stage_id
metric_id
finite value
measurement time
optional epoch and step
```

The experiment supplies the permitted `metric_id` values. The verifier checks
every row against the containing run, attempt, stage, and experiment.

---

## 14. Validation and external verification

### Pydantic validators

Pydantic validates relationships visible inside one loaded object:

1. Identifier and path syntax.
2. SHA-256 and Git-commit syntax.
3. Required fields and discriminated unions.
4. Nonempty artifact mappings.
5. File-versus-bundle cardinality.
6. Unique IDs, paths, and bundle-member paths.
7. Matching key sets embedded within one resolved stage spec.
8. Attempt status, timestamp, ordering, and successful-attempt invariants.
9. Download URL and version equality, and retrieval time at or before stage
   completion.

### External verifier

The external verifier loads referenced files and checks relationships spanning
multiple records.

#### Run plan

1. Retrieve `ResolvedRun.spec` and verify its SHA-256 and byte count.
2. Parse the file as `RunSpec`.
3. Derive the experiment and variant paths from `RunSpec.experiment_id` and
   `RunSpec.variant_id`, then load both files from `RunSpec.source`.
4. Verify the experiment, variant, replicate, metric, and seed relationships.
5. Retrieve each stage spec from the run-plan snapshot and verify its
   `RunStageRef.sha256` and `RunStageRef.bytes`.
6. Verify that every `FutureInputRef.producer_stage_id` names an earlier
   `RunStageRef`.
7. Verify that local input paths, `BaseSpec.script`, and declared artifact roots
   are pairwise non-overlapping where the executor materializes files.
8. Verify the typed variant parameters against the loaded stage specs.
9. Verify that each attempt's resolved stages form an ordered prefix of
   `RunSpec.stages` and that the successful attempt contains every run stage.

#### Resolved execution

1. Retrieve every resolved stage spec by combining
   `ResolvedStageRef.snapshot` with `ResolvedStageRef.resolved_spec.path`.
2. Parse each file through the resolved-stage-spec union.
3. Verify the canonical command.
4. Verify that `ResolvedBaseSpec.source` identifies `BaseSpec.script` in
   `RunSpec.source` and matches the retrieved source bytes.
5. Verify that the resolved environment and `ExecutionContext` satisfy every
   requested environment and reproducibility constraint.
6. Verify that the resolved inputs correspond by name and kind to the planned
   inputs.
7. Verify the stage completion time against its containing `RunAttempt`.

#### Artifact partition

1. Compare the artifact-name keys across the stage spec and resolved stage
   spec.
2. Select every `ResolvedArtifact` through
   `ResolvedBaseSpec.artifacts[artifact_name]`.
3. Retrieve every `SnapshotFileRef` from `ResolvedStageRef.snapshot` and verify
   its SHA-256 and byte count.
4. Verify bundle inventory, canonical ordering, path containment, and
   cross-artifact disjointness.

#### Input lineage

1. For each stored input, verify its pointer and load the terminal `ResolvedRun`
   selected by `ArtifactPointer.run`.
2. Select the successful attempt, producer stage, and artifact named by
   `ArtifactPointer.artifact`.
3. For each same-run input, require `ResolvedFutureInputRef.producer` to equal
   the `ResolvedStageRef` named by `FutureInputRef.producer_stage_id`.
4. Select the artifact named by `FutureInputRef.producer_artifact` from the
   producer's loaded `ResolvedBaseSpec.artifacts` mapping.
5. Verify every file in the selected artifact before returning its complete
   file set to the executor.

#### Run result

1. Verify attempt order, timestamps, status, and completed-stage prefixes.
2. Verify every measurement and log reference retained by each attempt.
3. Verify that the successful attempt completed every declared stage in order.
4. Load `RunSpec.estimator` through the successful attempt's
   `ResolvedStageRef`, resolved stage spec, and artifact mapping.

---

## 15. Execution and publication sequence

### Before execution

1. Commit source code, experiment and variant files, metric implementations,
   lockfile, and promoted-input pointers as source commit A.
2. Select the experiment, variant, and replicate.
3. Create the concrete stage specs.
4. Validate and serialize every stage spec.
5. Calculate the SHA-256 and byte count of every serialized stage-spec file.
6. Construct `RunSpec` with source commit A, the selected seed, ordered
   `RunStageRef` records, and the estimator artifact reference.
7. Validate and serialize the complete run plan.
8. Publish `RunSpec` and every stage spec together as run-plan commit B.
9. Retrieve commit B and verify every published file.

### For each attempt

1. Allocate the next `attempt_id`.
2. Check out source commit A into a clean workspace.
3. Retrieve the run plan from commit B.
4. Materialize and verify every stored input.
5. For each stage in order:
   1. Resolve its same-run inputs through earlier `ResolvedStageRef` records.
   2. Verify the environment and numerical controls.
   3. Apply the run seed to every controlled random-number generator.
   4. Construct and record the canonical command.
   5. Execute the stage script with its stage-spec path.
   6. Resolve every declared artifact as a `ResolvedSingleFileArtifact` or
      `ResolvedBundleArtifact`, producing $A(s)$ and each $F_s(a)$.
   7. Record measurements and logs.
   8. Publish and verify the stage-result snapshot described below.
6. Record the attempt's terminal status and completion time, then close its
   measurement and log files.
7. Publish and verify the closed measurement and log files.

### After the final attempt

1. Determine the run's terminal status and `successful_attempt_id`.
2. Construct `ResolvedRun` with the run-plan reference and every closed
   `RunAttempt`.
3. Publish and verify `ResolvedRun`.

### Result publication

```text
Stage-result commit C_s — one stage-result snapshot in the artifact repository
├── resolved stage spec
├── every single-file artifact
└── every member of each bundle artifact
        │
        ▼ identify the completed stage
ResolvedStageRef
├── snapshot → repository and commit C_s
└── resolved_spec → path, SHA-256, and byte count inside C_s

Attempt-files commit D_i — attempt files in the artifact repository
├── measurement files
└── log files

Terminal-run commit E — terminal record in the artifact repository
└── ResolvedRun
    ├── spec → run-plan commit B
    └── attempts
        └── resolved_stages → stage-result commits C_s

Optional promotion commit F — pointer in Git
└── inputs/<producer_type>/<producer_id>/<selection_name>.pointer.yaml
    ├── run → ResolvedRun at commit E
    └── artifact → StageArtifactRef
        │
        └── may become an input pointer in a later source commit A
```

The executor:

1. Hashes every artifact file and bundle member.
2. Constructs the resolved stage spec with one `SnapshotFileRef` for every
   artifact file.
3. Publishes the resolved stage spec and artifact files together at commit
   $C_s$.
4. Constructs `ResolvedStageRef` from the returned snapshot commit and the
   resolved stage spec's path, SHA-256, and byte count.
5. Retrieves and verifies the complete stage-result snapshot.
6. Adds the completed stage to the current `RunAttempt`.

Promotion is a separate selection operation. It commits an `ArtifactPointer`
under `inputs/` at optional commit F. The pointer contains the terminal
`ResolvedRunRef` and selected `StageArtifactRef`.

---

## 16. Repository layout

Pointer filenames use:

```python
SelectionName = HumanId
```

Each `selection_name` is scoped by its `dataset_id`, `prior_id`, or `model_id`.

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
                    │   └── models/
                    │       └── <model_id>/
                    │           ├── embedding.pt
                    │           ├── weights.pt
                    │           └── predictions.pt
                    ├── measurements/
                    │   └── <stage_id>.<metric_id>.jsonl
                    └── logs/
                        ├── <attempt_id>.<stage_id>.stdout.log
                        └── <attempt_id>.<stage_id>.stderr.log
```

The run directory is the durable output root. Its `artifacts/`,
`measurements/`, and `logs/` directories separate the files produced during
execution by protocol role. Stable repository-relative paths identify each
role; immutable storage commits distinguish files published by different
attempts.

---

## 17. Reference cases

| Stage output | Artifact partition |
|---|---|
| Final estimator stored in `model.pt` | One `ResolvedSingleFileArtifact` named `model` |
| Estimator requiring `model.pt` and `config.pkl` | One `ResolvedBundleArtifact` named `model` |
| Sharded estimator plus its index | One `ResolvedBundleArtifact` named `model` |
| Model and independently consumed embeddings | Two artifacts named `model` and `embeddings` |
| Model and independently selected exact-continuation state | Two artifacts named `model` and `continuation_state` |
| Checkpoint whose loader requires model, optimizer, scheduler, RNG, and sampler files together | One `ResolvedBundleArtifact` named `checkpoint` |
| Persisted prediction matrix consumed independently | One artifact named `predictions` |
| Loss or correlation value | Measurement |
| Forward-pass activation reconstructed during the stage | Stage-local value |
| Activation explicitly consumed by another stage | One named artifact |

Example with two artifacts:

```yaml
artifacts:
  model:
    kind: bundle
    path: experiments/e001/runs/baseline/01JABC/artifacts/models/strand/model

  perturbation_embeddings:
    kind: file
    path: experiments/e001/runs/baseline/01JABC/artifacts/models/strand/embedding.pt
```

The resolved records satisfy:

```text
A(train)
├── F_train(model)
│   ├── experiments/e001/runs/baseline/01JABC/artifacts/models/strand/model/config.pkl
│   └── experiments/e001/runs/baseline/01JABC/artifacts/models/strand/model/model.pt
└── F_train(perturbation_embeddings)
    └── experiments/e001/runs/baseline/01JABC/artifacts/models/strand/embedding.pt
```

---

## 18. Migration sequence

1. Freeze the runtime-state definition and strict-reproducibility condition.
2. Freeze `RemoteFileRef.version` and `ResolvedDownloadSpec.retrieved_at`.
3. Freeze the exact requested-environment and execution-context field shapes.
4. Freeze the typed `VariantStageParams` models.
5. Freeze `StageArtifactRef` and the final-estimator selector.
6. Freeze the stage, artifact, and physical-file partition contracts.
7. Freeze `StageResultSnapshotRef`, `SnapshotFileRef`, `ResolvedStageRef`, and
   `ResolvedRunRef`.
8. Propagate direct artifact selection through stage specs, resolved stage
   specs, future inputs, attempts, resolved runs, and promotion pointers.
9. Map the frozen contract onto `ProvenanceS1.md`.
10. Update `records.py`.
11. Update `verifier.py`.
12. Replace affected tests with focused tests of the new invariants.
13. Execute one complete dummy run and reject one deliberately corrupted
    referenced file.
