# MANTRA Provenance Protocol — Stage 1 Version 2

Status: design draft for iterative review

This document defines the target Stage 1 provenance contract. The current
implementation remains in `models_v4.py` and `verifier.py` until the contracts
in this document are frozen and migrated.

---

## 1. Scope

Stage 1 records and verifies one model-building run from its fixed inputs to its
fitted estimator. It defines:

1. A run plan.
2. The runtime states permitted by that plan.
3. The condition under which the plan provides strict parameter
   reproducibility.
4. The ordered stage partition declared by the plan.
5. The artifact partition produced by each successful stage.
6. The physical-file partition representing each artifact.
7. The exact files connecting a run, stage, artifact, and measured result.
8. The validators and cross-file verifier checks enforcing those relationships.

Benchmark definitions, benchmark reproducibility, diagnostics, evaluation
records, promotion gates, and SOTA selection belong to the next protocol stage.

---

## 2. Fitted estimator under runtime variation

Let ${\alpha}$ identify a parameterized prediction-function family. It fixes a
parameter space ${\Theta_{\alpha}}$.

Let ${\beta \in \mathcal{B}_\alpha}$ identify the chosen estimator.

Let ${D \in \mathcal{D}}$ be an arbitrary dataset. 

Let ${e \in E}$ be a runtime state, defined as a particular assignment of execution parameters that can
vary between two executions.

The runtime-indexed estimator is:

$$
\widetilde{T}_{\alpha,\beta}
:
\mathcal{D}\times E
\rightarrow
\Theta_{\alpha}.
$$

It defines the map from the chosen runtime state and dataset to the fitted parameter.

---

## 3. Run plan and strict parameter reproducibility

Let $q$ be a run plan. The plan fixes $\alpha$, $\beta$, and
$D_q\in\mathcal D$, and induces a nonempty set of permitted runtime states
$E_q\subseteq E$.

Define the estimator restricted by $q$ as:

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

Because $E_q$ is nonempty, this common value exists. Denote it by
$\widehat\theta_q$. Therefore:

$$
\forall e\in E_q,
\qquad
T_{\alpha,\beta,q}(e)
=
\widehat\theta_q.
$$

---

## 4. Protocol hierarchy

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

Pydantic models validate each loaded record. The external verifier retrieves
referenced files, verifies their bytes, and checks the relationships among the
experiment, run, stages, inputs, artifacts, measurements, source, environment,
and runtime controls.

---

## 5. Stage partition

The run plan declares the finite ordered stage sequence:

$$
\Pi(q)
=
\left\langle
s_1,
\ldots,
s_m
\right\rangle,
\qquad
m\geq 1.
$$

`RunSpec.stages` records this order. Each stage spec records one execution
request. A valid stage sequence satisfies:

1. Every `stage_id` is unique.
2. Every stage-spec path is unique.
3. Every `FutureInputRef` names an earlier stage.
4. Every successfully completed stage records all artifact outputs declared by
   its stage spec.
5. The successful attempt completes every stage in the declared order.

Stage 1 accepts `Pi(q)` as declared by the run plan.

---

## 6. Artifact and physical-file partitions

Let `s` be a successfully completed stage.

The stage spec inside `q` declares the artifact names and output paths for `s`.
Execution realizes those declarations as physical files. The following
definitions connect the declared outputs to their resolved representations.

Let `O_s` be the finite, nonempty set of physical files declared as artifact
outputs of `s`.

Let `N_s` be the finite, nonempty set of artifact names declared by `s`.

For every artifact name `a` in `N_s`, let:

$$
F_s(a)\subseteq O_s
$$

be the minimal complete set of physical files required to reconstruct artifact
`a` under its declared loading contract.

The artifact partition of stage `s` is:

$$
A(s)
=
\left\{
F_s(a)
:
a\in N_s
\right\}.
$$

### Partition invariants

The partition satisfies:

$$
\lvert A(s)\rvert\geq 1,
$$

$$
\lvert F_s(a)\rvert\geq 1
\quad
\text{for every }a\in N_s,
$$

$$
\bigcup_{a\in N_s}F_s(a)=O_s,
$$

and, for distinct artifact names `a` and `b`,

$$
F_s(a)\cap F_s(b)=\varnothing.
$$

The resulting hierarchy is:

```text
successful stage s
└── artifact partition A(s), containing one or more named artifacts
    └── artifact a
        └── minimal complete file set F_s(a)
            ├── one file     → ResolvedSingleFileArtifact
            └── two or more → ResolvedBundleArtifact
```

### Artifact boundary

`BaseSpec.artifacts` supplies `N_s`. Each name identifies one output value that
a consumer may reference. The files jointly required to reconstruct that value
form its `F_s(a)`. Distinct artifact names therefore induce distinct blocks in
`A(s)`.

Examples:

```text
model.pt + config.pkl
→ both files required by the model loader
→ one artifact named model
→ ResolvedBundleArtifact
```

```text
model.pt + perturbation_embeddings.pt
→ either value may be consumed independently
→ artifacts named model and perturbation_embeddings
→ two ResolvedSingleFileArtifact records
```

The declaration asserts semantic completeness and minimality. The verifier
enforces the structural consequences: cardinality, complete member inventory,
disjoint membership, path containment, atomic materialization, and exact file
identity.

`O_s` contains artifact files only. Measurement files, logs, and protocol
records retain their separate roles in `RunAttempt` and `ResolvedRun`.

---

## 7. Runtime coordinates represented by the protocol

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

## 8. Source snapshot and run-plan snapshot

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
├── <run_id>.run.yaml
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

## 9. File identity and storage

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

Role-specific references preserve the general file identity while identifying
the type of document expected at that location:

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

---

## 10. Artifact declarations and resolved artifacts

```python
ArtifactName = HumanId
```

### Stage declaration

```python
class SingleFileArtifactSpec(ProtocolModel):
    kind: Literal["file"] = "file"
    path: RepoRelPath


class BundleArtifactSpec(ProtocolModel):
    kind: Literal["bundle"] = "bundle"
    path: RepoRelPath


ArtifactSpec = Annotated[
    SingleFileArtifactSpec | BundleArtifactSpec,
    Field(discriminator="kind"),
]


class BaseSpec(ProtocolModel):
    artifacts: dict[ArtifactName, ArtifactSpec] = Field(min_length=1)
```

For a file artifact, `path` is its canonical file path. For a bundle artifact,
`path` is its canonical directory root.

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

## 11. Stage-result snapshots and promotion pointers

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
  path: experiments/e001/runs/01JABC/attempts/1/train.resolved.yaml
  sha256: <resolved-spec-sha256>
  bytes: 8421
```

The snapshot contains:

```text
ResolvedStageRef.snapshot
├── ResolvedStageRef.resolved_spec
│   └── loads ResolvedBaseSpec
└── every SnapshotFileRef reached through
    ResolvedBaseSpec.artifacts[artifact_name]
```

The artifact names satisfy:

```text
keys(BaseSpec.artifacts)
==
keys(ResolvedBaseSpec.artifacts)
==
N_s
```

For every artifact name `a`, the verifier performs:

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

## 12. Stage inputs

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
StoredInputRef.pointer
→ retrieve and verify ArtifactPointer
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

A `DownloadSpec` receives one external URL and creates the first
byte-identified artifact inside MANTRA. Later runs consume that artifact through
an `ArtifactPointer` after promotion.

---

## 13. Experiment, variant, replicate, and seed

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
same seed. A different replicate seed produces a different run.

---

## 14. Environment, numerical controls, and command

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

For the `RunStageRef` and loaded stage spec belonging to stage `s`, the executor
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

## 15. Run, attempt, and measurement records

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
`theta_hat_q`.

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

## 16. Validation and external verification

### Pydantic validators

Pydantic validates relationships visible inside one loaded object:

1. Identifier and path syntax.
2. SHA-256 and Git-commit syntax.
3. Required fields and discriminated unions.
4. Nonempty artifact mappings.
5. File-versus-bundle cardinality.
6. Unique IDs, paths, artifact names, and bundle-member paths.
7. Matching key sets embedded within one resolved stage spec.
8. Attempt status, timestamp, ordering, and successful-attempt invariants.

### External verifier

The external verifier loads referenced files and checks relationships spanning
multiple records.

#### Run plan

1. Retrieve `ResolvedRun.spec` and verify its SHA-256 and byte count.
2. Parse the file as `RunSpec`.
3. Load the deterministic experiment and variant paths from `RunSpec.source`.
4. Verify the experiment, variant, replicate, metric, and seed relationships.
5. Retrieve each stage spec from the run-plan snapshot and verify its
   `RunStageRef.sha256` and `RunStageRef.bytes`.
6. Verify stage order, future-input order, output-path separation, and typed
   variant parameters.
7. Verify that each attempt's resolved stages form an ordered prefix of
   `RunSpec.stages` and that the successful attempt contains every run stage.

#### Resolved execution

1. Retrieve every resolved stage spec by combining
   `ResolvedStageRef.snapshot` with `ResolvedStageRef.resolved_spec.path`.
2. Parse each file through the resolved-stage-spec union.
3. Verify the canonical command.
4. Verify the resolved source, environment, execution context, inputs, and
   completion time.
5. Verify that each constrained runtime coordinate satisfies its plan policy.

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
5. Materialize the complete artifact before executing the consumer.

#### Run result

1. Verify attempt order, timestamps, status, and completed-stage prefixes.
2. Verify every measurement and log reference retained by each attempt.
3. Verify that the successful attempt completed every declared stage in order.
4. Load `RunSpec.estimator` through the successful attempt's
   `ResolvedStageRef`, resolved stage spec, and artifact mapping.

---

## 17. Execution and publication sequence

### Before execution

1. Commit source code, experiment and variant files, metric implementations,
   lockfile, and promoted-input pointers as source commit A.
2. Select the experiment, variant, and replicate.
3. Create the concrete stage specs.
4. Construct `RunSpec` with source commit A, the selected seed, ordered
   `RunStageRef` records, and the estimator artifact reference.
5. Validate the complete run plan.
6. Calculate the SHA-256 and byte count of every stage-spec file.
7. Publish `RunSpec` and every stage spec together as run-plan commit B.
8. Retrieve commit B and verify every published file.

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
   6. Classify the declared artifact outputs into `A(s)` and `F_s(a)`.
   7. Record measurements and logs.
   8. Publish and verify the stage-result snapshot described below.
6. Publish and verify the attempt's measurement and log files.
7. Record the attempt's terminal status and completion time.
8. After the run reaches a terminal status, write and publish `ResolvedRun`.

### Successful-stage publication

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
└── inputs/<name>.pointer.yaml
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

## 18. Reference cases

| Stage output | Artifact partition |
|---|---|
| Final estimator stored in `model.pt` | One `ResolvedSingleFileArtifact` named `model` |
| Estimator requiring `model.pt` and `config.pkl` | One `ResolvedBundleArtifact` named `model` |
| Sharded estimator plus its index | One `ResolvedBundleArtifact` |
| Model and independently consumed embeddings | Two named artifacts |
| Model and exact-continuation state selected independently | Two named artifacts |
| Checkpoint whose loader requires model, optimizer, scheduler, RNG, and sampler files together | One checkpoint bundle |
| Persisted prediction matrix consumed independently | One named artifact |
| Loss or correlation value | Measurement |
| Forward-pass activation reconstructed during the stage | Stage-local value |
| Activation explicitly consumed by another stage | Named artifact |

Example with two artifacts:

```yaml
artifacts:
  model:
    kind: bundle
    path: artifacts/model

  perturbation_embeddings:
    kind: file
    path: artifacts/perturbation_embeddings.pt
```

The resolved records satisfy:

```text
A(train)
├── F_train(model)
│   ├── artifacts/model/config.pkl
│   └── artifacts/model/model.pt
└── F_train(perturbation_embeddings)
    └── artifacts/perturbation_embeddings.pt
```

---

## 19. Migration sequence

1. Freeze the runtime-state definition and strict-reproducibility condition.
2. Freeze the exact requested-environment and execution-context field shapes.
3. Freeze the typed `VariantStageParams` models.
4. Freeze `StageArtifactRef` and the final-estimator selector.
5. Freeze the stage, artifact, and physical-file partition contracts.
6. Freeze `StageResultSnapshotRef`, `SnapshotFileRef`, `ResolvedStageRef`, and
   `ResolvedRunRef`.
7. Propagate direct artifact selection through stage specs, resolved stage
   specs, future inputs, attempts, resolved runs, and promotion pointers.
8. Map the frozen contract onto `ProvenanceS1.md`.
9. Update `models_v4.py`.
10. Update `verifier.py`.
11. Replace affected tests with focused tests of the new invariants.
12. Execute one complete dummy run and reject one deliberately corrupted
    referenced file.
