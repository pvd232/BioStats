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
2. The runtime states permitted by that plan
2. The condition under which the plan provides strict parameter
   reproducibility.
3. The ordered stage partition declared by the plan.
4. The artifact partition produced by each successful stage.
5. The physical-file partition representing each artifact.
6. The exact files connecting a run, stage, artifact, and measured result.
7. The validators and cross-file verifier checks enforcing those relationships.

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

The run plan $q$ defined in Section 3 consists of one `RunSpec` and the exact
stage-spec files identified by its ordered `RunStageRef` records.

```text
ExperimentSpec
├── factors
│   └── FactorSpec.levels
├── variant_ids
├── replicates
│   └── ReplicateSpec.seed
└── metric_ids

VariantSpec
├── levels
└── stage_params

RunSpec
├── experiment_id
├── variant_id
├── replicate_id
├── seed
├── source
├── stages → ordered RunStageRef records
└── estimator: StageArtifactRef

BaseSpec subclass
├── inputs
├── script
├── environment
├── reproducibility
├── params
└── artifacts
    └── artifact name → ArtifactSpec

ResolvedRun
├── run
│   └── embedded RunSpec
├── run_file
│   └── ResolvedFileRef identifying the serialized RunSpec
├── attempts
│   └── RunAttempt
│       ├── resolved_stages
│       │   └── ResolvedStageRef
│       │       ├── resolved_spec
│       │       │   └── loads ResolvedBaseSpec
│       │       └── artifacts
│       │           └── artifact name
│       │               → ResolvedArtifactManifestRef
│       │               → loads ArtifactManifest
│       │               → identifies ResolvedArtifact
│       ├── measurement_files
│       └── log_files
├── successful_attempt_id
├── status
└── completed_at

ResolvedArtifact
├── ResolvedArtifactFile
│   └── one ResolvedFileRef
└── ResolvedArtifactBundle
    └── two or more ResolvedArtifactBundleMember records

StoredInputRef
└── pointer → ArtifactPointerRef
    └── loads ArtifactPointer
        └── manifest → ResolvedArtifactManifestRef

FutureInputRef
├── producer_stage_id
└── producer_artifact
    └── producer ResolvedStageRef.artifacts[producer_artifact]

Measurement
├── run_id
├── attempt_id
├── stage_id
├── metric_id
└── value
```

A successful `RunAttempt` records one execution under some $e\in E_q$.
`RunSpec.stages` supplies the ordered stage partition $\Pi(q)$.
`BaseSpec.artifacts`, `ResolvedBaseSpec.artifacts`, and
`ResolvedStageRef.artifacts` jointly represent the artifact partition $A(s)$.
Each loaded `ArtifactManifest.artifact` represents the physical-file partition
$F_s(a)$ for one named artifact.

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
            ├── one file     → ResolvedArtifactFile
            └── two or more → ResolvedArtifactBundle
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
→ ResolvedArtifactBundle
```

```text
model.pt + perturbation_embeddings.pt
→ either value may be consumed independently
→ artifacts named model and perturbation_embeddings
→ two ResolvedArtifactFile records
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

`RunSpec.source` identifies commit A. `ResolvedRun.run_file.stored_at` identifies
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
```

Role-specific references preserve the general file identity while identifying
the type of document expected at that location:

```python
class ResolvedGitFileRef(ResolvedFileRef):
    stored_at: GitFileRef


class ResolvedArtifactManifestRef(ResolvedFileRef):
    kind: Literal["artifact_manifest"] = "artifact_manifest"


class ArtifactPointerRef(GitFileRef):
    pass


class ResolvedArtifactPointerRef(ResolvedFileRef):
    kind: Literal["artifact_pointer"] = "artifact_pointer"
    stored_at: ArtifactPointerRef
```

`stored_at` identifies an immutable Git or Hugging Face repository revision and
repository-relative path. `sha256` and `bytes` identify the retrieved file
contents.

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
class ArtifactFileSpec(ProtocolModel):
    kind: Literal["file"] = "file"
    path: RepoRelPath


class ArtifactBundleSpec(ProtocolModel):
    kind: Literal["bundle"] = "bundle"
    path: RepoRelPath


ArtifactSpec = Annotated[
    ArtifactFileSpec | ArtifactBundleSpec,
    Field(discriminator="kind"),
]


class BaseSpec(ProtocolModel):
    artifacts: dict[ArtifactName, ArtifactSpec] = Field(min_length=1)
```

For a file artifact, `path` is its canonical file path. For a bundle artifact,
`path` is its canonical directory root.

### Resolved representation

```python
class ResolvedArtifactFile(ProtocolModel):
    kind: Literal["file"] = "file"
    file: ResolvedFileRef


class ResolvedArtifactBundleMember(ProtocolModel):
    relative_path: RepoRelPath
    file: ResolvedFileRef


class ResolvedArtifactBundle(ProtocolModel):
    kind: Literal["bundle"] = "bundle"
    members: tuple[ResolvedArtifactBundleMember, ...] = Field(
        min_length=2
    )


ResolvedArtifact = Annotated[
    ResolvedArtifactFile | ResolvedArtifactBundle,
    Field(discriminator="kind"),
]


class ResolvedBaseSpec(ProtocolModel):
    spec: BaseSpec
    artifacts: dict[ArtifactName, ResolvedArtifact] = Field(min_length=1)
```

The cardinality rule is exact:

```text
|F_s(a)| = 1  → ResolvedArtifactFile
|F_s(a)| ≥ 2  → ResolvedArtifactBundle
```

### Path invariants

For a declared file artifact:

```text
ResolvedArtifactFile.file.stored_at.path
==
ArtifactFileSpec.path
```

For every bundle member:

```text
ResolvedArtifactBundleMember.file.stored_at.path
==
ArtifactBundleSpec.path
/
ResolvedArtifactBundleMember.relative_path
```

Bundle member paths are unique, remain beneath the bundle root, and appear in
canonical `relative_path` order. Artifact roots within one stage are pairwise
non-overlapping.

---

## 11. Artifact manifests and promotion pointers

Each artifact name receives one manifest:

```python
class ArtifactManifest(ProtocolModel):
    schema_version: Literal[1] = 1

    artifact_name: ArtifactName
    artifact: ResolvedArtifact
    spec: ResolvedFileRef
    resolved_spec: ResolvedFileRef
    source: ResolvedGitFileRef

    created_at: AwareDatetime
```

The manifest binds one member of `A(s)` to its exact `F_s(a)`, stage spec,
resolved stage spec, and source entry point.

```python
class ResolvedStageRef(ProtocolModel):
    stage_id: StageId
    resolved_spec: ResolvedFileRef
    artifacts: dict[
        ArtifactName,
        ResolvedArtifactManifestRef,
    ] = Field(min_length=1)
```

The artifact names satisfy:

```text
keys(BaseSpec.artifacts)
==
keys(ResolvedBaseSpec.artifacts)
==
keys(ResolvedStageRef.artifacts)
==
N_s
```

For every artifact name `a`:

```text
ResolvedStageRef.artifacts[a]
→ retrieve and verify manifest bytes
→ parse ArtifactManifest
```

The loaded records satisfy:

```text
ArtifactManifest.artifact_name
==
a

ArtifactManifest.artifact
==
ResolvedBaseSpec.artifacts[a]

ArtifactManifest.resolved_spec
==
ResolvedStageRef.resolved_spec

ArtifactManifest.source
==
ResolvedBaseSpec.source

loaded ArtifactManifest.spec
==
ResolvedBaseSpec.spec
```

### Promotion pointer

```python
class ArtifactPointer(ProtocolModel):
    schema_version: Literal[1] = 1
    manifest: ResolvedArtifactManifestRef
```

An `ArtifactPointer` selects the manifest for an artifact accepted as a reusable
input. The pointer is committed under `inputs/` after promotion.

```text
ArtifactPointer
└── manifest
    └── ArtifactManifest
        ├── artifact
        │   └── file or complete bundle
        ├── stage spec
        ├── resolved stage spec
        └── source entry point
```

Stage completion creates artifacts and manifests. Promotion creates the pointer.

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

The traversal is:

```text
StoredInputRef.pointer
→ ArtifactPointer.manifest
→ ArtifactManifest.artifact
→ ResolvedArtifactFile | ResolvedArtifactBundle
```

`StoredInputRef.path` is the local path presented to the stage script. For a
bundle, it is the local bundle root and every member is placed beneath it using
`ResolvedArtifactBundleMember.relative_path`.

### Same-run input

```python
class FutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    producer_stage_id: StageId
    producer_artifact: ArtifactName


class ResolvedFutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    manifest: ResolvedArtifactManifestRef
```

The consumer identifies one exact member of the producer's artifact partition:

```text
FutureInputRef.producer_stage_id
→ producer ResolvedStageRef

FutureInputRef.producer_artifact
→ producer ResolvedStageRef.artifacts[producer_artifact]
```

The verifier requires:

```text
ResolvedFutureInputRef.manifest
==
producer ResolvedStageRef.artifacts[
    FutureInputRef.producer_artifact
]

ArtifactManifest.artifact_name
==
FutureInputRef.producer_artifact

ArtifactManifest.resolved_spec
==
producer ResolvedStageRef.resolved_spec

ArtifactManifest.artifact
==
producer ResolvedBaseSpec.artifacts[
    FutureInputRef.producer_artifact
]
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


class StageArtifactRef(ProtocolModel):
    stage_id: StageId
    artifact_name: ArtifactName


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
```

Each `ResolvedStageRef` contains the resolved stage-spec reference and its
artifact-manifest mapping. `RunAttempt` therefore stores no parallel manifest
inventory.

A successful attempt satisfies:

1. `failure_reason` is null.
2. `resolved_stages` contains every run stage exactly once and in order.
3. Every completed stage has at least one verified artifact manifest.
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
8. Attempt status, timestamp, and stage-prefix invariants.

### External verifier

The external verifier loads referenced files and checks relationships spanning
multiple records.

#### Run plan

1. Retrieve `ResolvedRun.run_file` and verify its SHA-256 and byte count.
2. Parse the file as `RunSpec` and compare it with `ResolvedRun.run`.
3. Load the deterministic experiment and variant paths from `RunSpec.source`.
4. Verify the experiment, variant, replicate, metric, and seed relationships.
5. Retrieve each stage spec from the run-plan snapshot and verify its
   `RunStageRef.sha256` and `RunStageRef.bytes`.
6. Verify stage order, future-input order, output-path separation, and typed
   variant parameters.

#### Resolved execution

1. Retrieve every `ResolvedStageRef.resolved_spec`.
2. Parse each file through the resolved-stage-spec union.
3. Verify the canonical command.
4. Verify the resolved source, environment, execution context, inputs, and
   completion time.
5. Verify that each constrained runtime coordinate satisfies its plan policy.

#### Artifact partition

1. Compare the artifact-name keys across the stage spec, resolved stage spec,
   and `ResolvedStageRef`.
2. Retrieve every artifact manifest through
   `ResolvedStageRef.artifacts[artifact_name]`.
3. Verify each manifest's artifact name, artifact, stage spec, resolved stage
   spec, and source.
4. Retrieve every artifact file and bundle member and verify SHA-256 and byte
   count.
5. Verify bundle inventory, canonical ordering, path containment, and
   cross-artifact disjointness.

#### Input lineage

1. For each stored input, verify its pointer, selected manifest, complete
   artifact, and local materialization path.
2. For each same-run input, select the producer's manifest directly through
   `ResolvedStageRef.artifacts[FutureInputRef.producer_artifact]`.
3. Verify that the selected manifest belongs to the named producer stage and
   artifact.
4. Materialize the complete artifact before executing the consumer.

#### Run result

1. Verify attempt order, timestamps, status, and completed-stage prefixes.
2. Verify every measurement and log reference retained by each attempt.
3. Verify that the successful attempt completed every declared stage in order.
4. Load `RunSpec.estimator` through the successful attempt's stage and artifact
   mappings.

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
   8. Publish and verify the completed-stage records described below.
6. Record the attempt's terminal status and completion time.
7. After one attempt succeeds, write and publish `ResolvedRun`.

### Successful-stage publication

```text
Commit C — artifact bytes in the artifact repository
└── one file or complete bundle-member set per artifact name

Commit D — resolved stage spec in the artifact repository
└── ResolvedBaseSpec.artifacts

Commit E — artifact manifests in the artifact repository
└── one manifest per artifact name

ResolvedStageRef
├── resolved_spec → commit D
└── artifacts
    └── artifact name → manifest at commit E

Commit F — optional promotion pointer in Git
└── inputs/<name>.pointer.yaml → selected manifest at commit E
        │
        └── may become an input pointer in a later source commit A
```

The executor:

1. Hashes every artifact file and bundle member.
2. Publishes all artifact bytes at commit C.
3. Publishes the resolved stage spec at commit D.
4. Constructs one manifest per artifact name.
5. Publishes all manifests at commit E.
6. Retrieves and verifies commits C, D, and E.
7. Constructs `ResolvedStageRef` from the verified references.
8. Adds the completed stage to the current `RunAttempt`.

Promotion is a separate selection operation. It commits an `ArtifactPointer`
under `inputs/` at optional commit F.

---

## 18. Reference cases

| Stage output | Artifact partition |
|---|---|
| Final estimator stored in `model.pt` | One `ResolvedArtifactFile` named `model` |
| Estimator requiring `model.pt` and `config.pkl` | One `ResolvedArtifactBundle` named `model` |
| Sharded estimator plus its index | One `ResolvedArtifactBundle` |
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
6. Propagate the artifact mapping through stage specs, resolved stage specs,
   manifests, future inputs, attempts, and resolved runs.
7. Map the frozen contract onto `ProvenanceS1.md`.
8. Update `models_v4.py`.
9. Update `verifier.py`.
10. Replace affected tests with focused tests of the new invariants.
11. Execute one complete dummy run and reject one deliberately corrupted
    referenced file.
