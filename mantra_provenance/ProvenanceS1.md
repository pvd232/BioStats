# MANTRA Provenance Protocol — Stage 1

## 1. Scope

Stage 1 implements:

- Experiment definitions.
- Variant definitions.
- Frozen run plans.
- Operational retry attempts.
- Ordered execution stages.
- Authored and resolved stage specifications.
- Exact source, environment, and execution context.
- Stored and same-run inputs.
- One primary artifact per stage.
- Metric declarations and measurements.
- Artifact manifests and promoted-input pointers.
- Terminal resolved-run records.
- Local Pydantic validation.
- External provenance verification.

Stage 1 defers:

- Final held-out evaluation.
- Diagnostics.
- Benchmark definitions.
- Two-run benchmark confirmation.
- Benchmark result records.
- Automatic promotion gates.
- Complete MANTRA model parameter classes.

Until benchmark gating exists, promotion remains a manual decision.

---

## 2. Core invariants

1. Every successfully completed stage produces exactly one primary artifact;
   every authored stage declares exactly one intended output.
2. Every completed artifact has a lowercase SHA-256, byte count, and immutable storage location.
3. SHA-256 identifies exact file contents.
4. Byte count is a secondary integrity check.
5. Every SHA-256 is calculated from the exact published file bytes.
6. Every artifact manifest binds the artifact to its authored spec, resolved spec, and source.
7. Every artifact pointer selects exactly one artifact manifest.
8. Every internal input is resolved to verified artifact bytes before execution.
9. Every resolved stage record embeds the authored spec it resolves.
10. Every run binds one experiment variant and replicate seed to one source repository and Git commit.
11. Every attempt executes the same frozen run plan.
12. Retries are attempts, not experimental replicates.
13. Only a successful attempt contributes the run’s accepted stage records, artifact manifests, and measurements.
14. Pydantic validates local structure.
15. A separate verifier retrieves referenced files and proves cross-file relationships.
16. Strict mode expects replay under the recorded conditions to reproduce artifact bytes.
17. Relaxed mode records what happened without promising byte-identical replay.

---

## 3. Protocol hierarchy

```text
Git revision
└── exact experiment definitions, variants, source code,
    metric implementations, lockfile, and input pointers

Experiment
├── constants
├── factors
│   └── levels
├── metric declarations
├── variants
└── replicate seeds

Variant
└── one valid assignment of levels to factors

Run
├── experiment
├── variant
├── replicate and seed
├── source repository and commit
└── ordered authored stage specs

Attempt
└── one effort to execute the frozen run plan

Stage
├── authored spec
├── exactly one intended primary output
└── successful completion
    ├── resolved spec
    ├── exactly one primary artifact
    └── zero or more measurement streams

Artifact
├── SHA-256
├── byte count
├── immutable storage location
└── manifest

Promoted input
└── pointer
    └── selected artifact manifest

Measurement
├── metric ID
├── observed value
├── producing stage
├── run and attempt identity
└── optional epoch or step

ResolvedRun
├── terminal status
├── attempts
├── successful attempt, if any
├── resolved stage-spec files
├── artifact-manifest files
├── measurement files
└── completion timestamp
```

---

## 4. File identity and storage

### Storage locations

A durable file may be stored at an immutable Git or Hugging Face commit:

```python
StorageRef = Annotated[
    GitFileRef | HuggingFaceFileRef,
    Field(discriminator="kind"),
]
```

A storage reference answers:

```text
Where can this file be retrieved?
```

A resolved file reference answers:

```text
Where can this file be retrieved?
What exact bytes should be there?
How long is the file?
```

```python
class ResolvedFileRef(ProtocolModel):
    sha256: SHA256
    bytes: int = Field(ge=0)
    stored_at: StorageRef
```

### SHA-256 rule

For every resolved file:

```text
sha256 = SHA-256 of the exact stored file bytes
```

This applies to:

- Artifacts.
- Authored specs.
- Resolved specs.
- Manifests.
- Pointers.
- Measurement files.
- Published logs.
- Run plans.
- Resolved-run records.

The protocol does not substitute a separately normalized model representation for the actual stored file bytes.

### Mirrored paths

The artifact’s local repository-relative path and remote repository-relative path are identical:

```text
Local:
experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/weights.pt

Remote:
experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/weights.pt
```

The remote reference additionally contains the immutable storage commit.

Local bytes may be removed after publication. MANTRA can restore them from remote storage and verify their SHA-256 and byte count.

---

## 5. Artifact manifest and pointer

Role-specific resolved references state what schema the referenced file is
expected to contain:

```python
class ArtifactPointerRef(GitFileRef):
    """A Git reference to the pointer selecting a promoted artifact manifest."""


class ResolvedArtifactManifestRef(ResolvedFileRef):
    kind: Literal["artifact_manifest"] = "artifact_manifest"


class ResolvedArtifactPointerRef(ResolvedFileRef):
    kind: Literal["artifact_pointer"] = "artifact_pointer"
    stored_at: ArtifactPointerRef
```

The external verifier still retrieves each referenced file, verifies its
SHA-256 and byte count, and parses it using the stated schema.

### Manifest

```python
class ArtifactManifest(ProtocolModel):
    schema_version: Literal[1] = 1

    artifact: ResolvedFileRef
    spec: ResolvedFileRef
    resolved_spec: ResolvedFileRef
    source: ResolvedGitFileRef

    created_at: AwareDatetime
```

The manifest answers:

```text
What exact artifact was produced?
What authored spec requested it?
What resolved spec records its execution?
What exact source produced it?
```

The source reference records:

- Git repository.
- Full Git commit.
- Entry-point path.
- Entry-point SHA-256.
- Entry-point byte count.

The Git commit covers project source imports from the repository tree.

### Pointer

```python
class ArtifactPointer(ProtocolModel):
    schema_version: Literal[1] = 1

    manifest: ResolvedArtifactManifestRef
```

The pointer separates the stable, version-controlled selection of a promoted
input from the immutable storage location of the artifact and its production
manifest.

```text
pointer
└── manifest
    ├── artifact
    ├── authored spec
    ├── resolved spec
    └── source
```

A promoted artifact is represented by a Git-tracked pointer under `inputs/`.
The artifact bytes and production manifest remain in immutable remote storage.
Ordinary stage outputs receive manifests but not pointers. Creating or updating
a pointer is an explicit promotion or reusable-input selection step.

---

## 6. Input types

An internal stage can consume either:

```text
StoredInputRef
└── an artifact that exists before this run

FutureInputRef
└── an artifact that an earlier stage in this run will produce
```

### Stored input

```python
class StoredInputRef(ProtocolModel):
    kind: Literal["stored"] = "stored"
    pointer: ArtifactPointerRef
    path: RepoRelPath
```

- `pointer` identifies an immutable Git revision of a tracked
  `*.pointer.yaml` file under `inputs/`.
- `path` identifies where the consuming command receives the artifact locally.

Example:

```yaml
inputs:
  initial_weights:
    kind: stored

    pointer:
      kind: git
      repository: https://github.com/example/mantra
      commit: <full-git-commit>
      path: inputs/models/baseline_weights.pt.pointer.yaml

    path: inputs/models/baseline_weights.pt
```

The executor:

1. Retrieves the pointer file.
2. Validates it as an `ArtifactPointer`.
3. Retrieves and validates the referenced `ArtifactManifest`.
4. Retrieves the artifact identified by that manifest.
5. Verifies every retrieved file's SHA-256 and byte count.
6. Materializes the artifact at the declared local path.

Materialization means ensuring that the command can read the verified bytes at
the declared path. If matching bytes already exist there, the executor may
reuse them. Otherwise, it may retrieve the artifact or create a symlink into a
MANTRA-managed cache. Existing bytes with the wrong SHA-256 must not be used.

A stored-input pointer lives under `inputs/`. Its selected manifest may identify
an artifact produced by any earlier run, but the producing run does not create
the pointer automatically.

### Same-run stage output

```python
class FutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    producer_stage_id: StageId
```

Example:

```yaml
inputs:
  embedding:
    kind: future
    producer_stage_id: embed
```

The upstream artifact does not exist when the run plan is frozen, so the
authored reference identifies the producer stage rather than a pointer file or
a second local path. MANTRA resolves `producer_stage_id` through the run's
stage list, loads that stage's authored spec, and uses its declared `output`
path as the consumer's input path.

Execution proceeds as follows:

1. Validate that `embed` precedes the consuming stage.
2. Execute `embed`.
3. Hash and publish the embedding.
4. Publish its resolved spec and manifest.
5. Verify that the producer's declared output path still contains the recorded
   bytes, restoring those bytes there if necessary.
6. Execute the consuming stage.

### Authored input union

```python
InternalInputRef = Annotated[
    StoredInputRef | FutureInputRef,
    Field(discriminator="kind"),
]
```

### Resolved internal input

The two authored forms resolve to role-specific representations containing
only the exact file identity learned during resolution:

```python
class ResolvedStoredInputRef(ProtocolModel):
    kind: Literal["stored"] = "stored"
    pointer: ResolvedArtifactPointerRef


class ResolvedFutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    manifest: ResolvedArtifactManifestRef


ResolvedInternalInputRef = Annotated[
    ResolvedStoredInputRef | ResolvedFutureInputRef,
    Field(discriminator="kind"),
]
```

The embedded authored spec remains authoritative for a stored input's local
materialization path and a future input's producer stage. A future input's
local path is the producer spec's declared output path. The resolved input does
not duplicate those fields.

Input invariants:

- Authored and resolved input names match.
- Stored-input materialization paths are unique within a stage.
- No stored-input path collides with the stage script or stage output path.
- Because these names denote files, equality and ancestor-descendant overlap
  both count as collisions: `data.bin` cannot coexist with `data.bin/part`.
- A stored input's local `path` and its pointer's remote Git `path` are separate
  namespaces. They may use the same relative spelling without colliding.
- Stage output paths are unique within a run.
- A future input's producer output does not collide with the consumer's stored
  input paths, script, or output path.
- A same-run reference identifies an earlier stage.
- A resolved stored-input pointer selects a valid artifact manifest.
- A resolved future-input manifest is the manifest published by its producer
  stage.
- The artifact identified by a future-input manifest equals the producer
  stage’s output.
- Materialized bytes equal the artifact identified through the pointer or
  manifest chain.
- Every retrieved file passes SHA-256 and byte-count verification.

---

## 7. Download boundary

A download stage begins with an external URL rather than an existing artifact:

```text
RemoteFileRef
    ↓ fetch
exact downloaded bytes
    ↓ hash and publish
ResolvedFileRef
```

The resolved download record retains the URL as its input.

Its output is the first verified artifact created from that URL.

A mutable URL is acceptable as a retrieval source because the downloaded output is independently hashed and stored immutably. Replaying the download must verify the downloaded bytes against the recorded artifact identity.

---

## 8. Source identity

A run records its exact source repository and commit:

```yaml
source:
  repository: https://github.com/example/mantra
  commit: <full-git-commit>
```

A resolved stage additionally records the exact source entry point:

```text
repository
commit
entry-point path
entry-point SHA-256
entry-point byte count
```

The executor must:

- Check out the exact commit.
- Reject modified tracked files.
- Reject relevant untracked source files.
- Resolve submodules at their recorded commits.
- Verify required Git LFS objects.
- Prevent imports from uncontrolled source directories.
- Execute the recorded entry point from the clean checkout.

Installed libraries are covered by the recorded environment.

Dynamically loaded output-affecting files must be covered by:

- The source commit.
- The environment.
- Or a declared execution input.

---

## 9. Environment, reproducibility, and execution context

### Environment

The environment records the software supplied to execution:

```text
GCEEnvironmentSpec
├── requested GCE machine image
└── Git-tracked dependency lockfile

ResolvedGCEEnvironment
├── exact GCE machine-image ID
└── verified Git lockfile
```

### Reproducibility controls

The reproducibility specification records how the software is instructed to execute:

```text
ReproducibilitySpec
├── mode: strict | relaxed
├── Python seed
├── NumPy seed
├── PyTorch seed
├── DataLoader seed
├── deterministic-algorithm controls
├── cuDNN controls
├── cuBLAS workspace configuration
├── TF32 controls
├── matmul precision
└── autocast controls
```

Strict mode requires:

- Deterministic algorithms enabled.
- Warning-only behavior disabled.
- cuDNN deterministic behavior enabled.
- cuDNN benchmarking disabled.
- Valid cuBLAS workspace configuration for CUDA.
- Concrete output-affecting parameters.

Relaxed mode records the same categories while permitting optimized or nondeterministic execution.

### Execution context

Each resolved stage records the conditions actually observed during that stage:

```text
ExecutionContext
├── GCE host
│   ├── machine type
│   ├── zone
│   ├── guest OS
│   └── kernel
├── CPU
│   ├── architecture
│   ├── model
│   └── instruction features
├── compute backend
│   ├── CPU
│   └── CUDA
│       ├── GPU device
│       ├── compute capability
│       ├── memory
│       ├── NVIDIA driver
│       ├── PyTorch CUDA version
│       ├── CUDA runtime version
│       ├── cuDNN version
│       └── cuBLAS version
├── numerical runtime
│   ├── Python
│   ├── PyTorch
│   ├── NumPy
│   ├── BLAS
│   ├── LAPACK
│   └── native thread pools
└── parallelism
    ├── one process
    ├── one PyTorch intra-op thread
    ├── one PyTorch inter-op thread
    └── zero DataLoader workers
```

Stage 1 is explicitly single-process and single-threaded.

Execution context remains on resolved stage specs. It is not duplicated in attempt records.

---

## 10. Experiment, variant, and run

### Experiment

An experiment declares:

- Experiment ID.
- Constants held fixed.
- Factors intentionally varied.
- Permitted levels.
- Variant definitions.
- Replicate seeds.
- Metric declarations.

Concrete output-affecting values remain in typed stage specifications.

### Variant

A variant selects one level for every factor:

```yaml
variant_id: low_rank_32

levels:
  rank: rank_32
  aggregation: low_rank
```

### Run

A run binds one variant and one replicate seed to an exact source revision and ordered stage plan:

```yaml
run_id: 01JABC
experiment_id: e001_low_rank
variant_id: low_rank_32

replicate_id: replicate_01
seed: 42

source:
  repository: https://github.com/example/mantra
  commit: <full-git-commit>

stages:
  - stage_id: build
    spec: stages/build.spec.yaml
    sha256: <build-spec-sha256>
    bytes: <build-spec-byte-count>

  - stage_id: embed
    spec: stages/embed.spec.yaml
    sha256: <embed-spec-sha256>
    bytes: <embed-spec-byte-count>

  - stage_id: train
    spec: stages/train.spec.yaml
    sha256: <train-spec-sha256>
    bytes: <train-spec-byte-count>
```

Each stage-plan entry uses this model:

```python
class RunStageRef(ProtocolModel):
    stage_id: StageId
    spec: RepoRelPath
    sha256: SHA256
    bytes: int = Field(ge=0)
```

Two immutable snapshots have separate roles:

```text
source snapshot
└── source code, experiment, variants, lockfile, and input pointers

run-plan snapshot
└── run.yaml and the generated authored stage specs
```

`RunSpec.source` identifies the source snapshot. `ResolvedRun.run_file.stored_at`
identifies the run-plan snapshot. Every `RunStageRef.spec` is resolved within
the run-plan snapshot, while its `sha256` and `bytes` verify the exact stage
file. The run plan does not contain its own run-plan commit because that commit
depends on the bytes of the run plan itself.

A new run is required if any planned scientific input changes:

- Experiment.
- Variant.
- Replicate seed.
- Source repository or commit.
- Stage order.
- Stage specification.
- Output-affecting parameter.
- Input pointer.
- Requested environment.
- Deliberate independent confirmation execution.

### Experiment and variant locations

Experiment and variant IDs resolve to deterministic repository-relative paths:

```text
Experiment:
experiments/<experiment_id>/<experiment_id>.experiment.yaml

Variant:
experiments/<experiment_id>/variants/<variant_id>.variant.yaml
```

For example:

```yaml
experiment_id: e001_low_rank
variant_id: low_rank_32
```

resolves within the run's recorded source repository and commit to:

```text
experiments/e001_low_rank/e001_low_rank.experiment.yaml
experiments/e001_low_rank/variants/low_rank_32.variant.yaml
```

The fixed path convention lets `RunSpec` bind the exact experiment and variant
using their IDs, source repository, and source commit without adding separate
file-reference fields.

---

## 11. Attempts

An attempt is one operational effort to execute an unchanged run plan.

Examples include retries after:

- VM preemption.
- Transient network failure.
- Process crash.
- Temporary storage failure.

A retry preserves the run ID and receives a new attempt ID.

```python
AttemptStatus = Literal[
    "succeeded",
    "failed",
    "preempted",
    "cancelled",
]


class ResolvedStageRef(ProtocolModel):
    stage_id: StageId
    resolved_spec: ResolvedFileRef


class RunAttempt(ProtocolModel):
    attempt_id: int = Field(ge=1)
    status: AttemptStatus

    started_at: AwareDatetime
    completed_at: AwareDatetime

    resolved_stages: tuple[ResolvedStageRef, ...]
    artifact_manifests: tuple[ResolvedArtifactManifestRef, ...]
    measurement_files: tuple[ResolvedFileRef, ...]
    log_files: tuple[ResolvedFileRef, ...]

    failure_reason: str | None
```

Attempt invariants:

- Attempt IDs are unique within a run.
- Attempts appear in execution order, and their IDs strictly increase.
- An attempt cannot begin before the preceding attempt finishes.
- Every attempt has a completion timestamp.
- Resolved-stage IDs are unique and preserve the run's declared stage order.
- Each `ResolvedStageRef` explicitly binds its stage ID to the resolved-spec
  file produced by that stage.
- Retrying may not modify the frozen run plan.
- A successful attempt completes every stage in order and has no failure
  reason.
- A failed, preempted, or cancelled attempt has a nonempty failure reason.
- No attempt may occur after a successful attempt.
- An unsuccessful attempt may retain partial stage, manifest, measurement, and
  log references.
- Partial unsuccessful-attempt outputs do not become accepted run outputs.
- Deliberate reproducibility confirmations are separate runs, not attempts.

Mutable `running` state belongs to the executor’s operational state rather than the immutable resolved-run record.

Different attempts may publish the same relative path at different immutable Hugging Face commits. Each attempt retains the exact commit references it produced. The resolved run selects the successful attempt’s references.

---

## 12. Authored and resolved stage specifications

An authored stage spec records the requested execution:

```text
AuthoredSpec
├── inputs
├── script
├── requested environment
├── reproducibility controls
├── typed parameters
└── intended output path
```

A resolved stage spec records the completed execution:

```text
ResolvedSpec
├── embedded AuthoredSpec
├── exact resolved inputs
├── exact source entry point
├── resolved environment
├── observed execution context
├── actual command
├── exact output artifact
└── completion timestamp
```

There is no `spec_id`. The resolved-spec file is identified by its
`ResolvedFileRef`. The associated `stage_id` belongs to the `ResolvedStageRef`
that binds the file into a `RunAttempt`; the containing `ResolvedRun` and
`RunAttempt` supply the run and attempt identities.

Current concrete stage types are:

- `DownloadSpec`
- `BuildSpec`
- `EmbedSpec`
- `TrainSpec`

There is no `EvaluateSpec` in Stage 1.

A stage type is added only when the implementation contains a distinct executable operation with its own inputs and output.

---

## 13. Parameters

Every output-affecting parameter belongs in a typed stage-specific class.

Rules:

- No generic parameter dictionary in the execution contract.
- No recursive untyped JSON parameter structure.
- No generic `effective_params` field.
- A resolved parameter class exists only when parameter resolution occurs.
- Strict mode may not leave choices such as `auto` unresolved.
- Relaxed mode may delegate choices to pinned libraries but cannot promise byte-identical replay.
- `BuildParams` and `EmbedParams` remain parent classes until their real MANTRA implementations are modeled.
- Algorithm-specific random states belong in their typed parameter classes.
- Run-wide Python, NumPy, PyTorch, and DataLoader seeds remain in the reproducibility specification.

Training-time validation and early termination belong inside `TrainSpec` when the concrete training parameters are implemented.

Final held-out evaluation remains outside Stage 1.

---

## 14. Metrics and measurements

### Metric declarations

A metric ID identifies one mathematical function:

```text
src/mantra/metrics/<metric_id>.py
```

Examples:

```text
src/mantra/metrics/mean_squared_error.py
src/mantra/metrics/pearson_correlation.py
src/mantra/metrics/kl_divergence.py
```

Each module exposes the callable used by MANTRA:

```python
def compute(...):
    ...
```

Stage 1 does not create separate objective, statistic, similarity, or distance-function IDs. They all use `metric_id`.

An experiment declares the metrics used to compare its runs:

```yaml
metrics:
  - metric_id: mean_squared_error
    direction: minimize

  - metric_id: pearson_correlation
    direction: maximize
```

The source commit fixes the exact implementation.

### Measurements

A measurement is one observed application of a declared metric:

```json
{
  "run_id": "01JABC",
  "attempt_id": 1,
  "stage_id": "train",
  "metric_id": "mean_squared_error",
  "value": 0.184,
  "epoch": 4,
  "step": 100,
  "measured_at": "2026-08-14T08:30:00Z"
}
```

Measurement filenames use:

```text
<stage_id>.<metric_id>.jsonl
```

Examples:

```text
train.mean_squared_error.jsonl
train.pearson_correlation.jsonl
embed.reconstruction_error.jsonl
```

A stage may produce zero or more measurement streams.

Every measurement must identify:

- Run ID.
- Attempt ID.
- Stage ID.
- Metric ID.
- Finite numeric value.
- Measurement timestamp.
- Optional nonnegative epoch or step.

Measurement files are published and recorded as `ResolvedFileRef` values.

---

## 15. Resolved run

A resolved run records the terminal outcome of the frozen run plan:

```python
class ResolvedRun(ProtocolModel):
    schema_version: Literal[1] = 1

    run: RunSpec
    run_file: ResolvedFileRef

    status: Literal["succeeded", "failed", "cancelled"]

    attempts: tuple[RunAttempt, ...] = Field(min_length=1)
    successful_attempt_id: int | None

    completed_at: AwareDatetime
```

Resolved-run invariants:

- Attempt IDs are unique.
- Attempts appear in execution order, their IDs strictly increase, and their
  time intervals do not overlap.
- The resolved run cannot complete before any of its attempts completes.
- A succeeded run has exactly one successful attempt.
- A succeeded run requires `successful_attempt_id`, and that ID identifies the
  successful attempt.
- A failed or cancelled run has no successful attempt and requires
  `successful_attempt_id` to be null.
- A failed or cancelled run has no accepted successful attempt.
- The successful attempt completed every declared stage in order.
- Failed attempts may retain partial references inside their attempt records.
- Retrying never modifies the embedded `RunSpec`.

`ResolvedRun` validators check only the embedded `RunSpec` and `RunAttempt`
records. The external verifier defined in Section 21 loads the referenced files
and confirms that:

- `run_file` parses as a `RunSpec` equal to the `RunSpec` embedded in
  `ResolvedRun`;
- each `ResolvedStageRef` binds the declared stage ID to an exact resolved-spec
  file whose embedded authored spec matches the corresponding run-plan stage;
- each resolved stage uses the run's source snapshot and completed within the
  successful attempt's time interval;
- each artifact manifest identifies the corresponding resolved stage's recorded
  output; and
- each measurement row identifies the expected run, attempt, stage, and metric.

The verifier also recalculates every referenced file's SHA-256 and byte count.

---

## 16. Publication order

### Before execution

1. Freeze the run plan.
2. Freeze all authored stage specs.
3. Validate the run plan and all authored stage specs as one complete set.
4. Calculate each file's exact SHA-256 and byte count.
5. Publish the run plan and all authored stage specs together in one immutable
   remote commit.
6. Verify that the published bytes match the calculated SHA-256 values and byte
   counts.
7. Record their immutable storage references.

Publishing the plan and its stage specs in one commit guarantees that every
stage-spec path in `<run_id>.run.yaml` resolves within the same fixed remote
snapshot. The resulting run-file location records the snapshot's repository
and commit; each `RunStageRef` records its stage file's path, SHA-256, and byte
count.

### After each successful stage

1. Close the primary output file.
2. Calculate its SHA-256.
3. Calculate its byte count.
4. Upload it to immutable remote storage.
5. Write and publish `<stage_id>.spec.resolved.yaml`.
6. Write and publish `<artifact>.manifest.yaml`.
7. Close and publish measurement files.
8. Record all resulting exact references in the attempt.

### After an attempt terminates

1. Close and publish its logs.
2. Record its terminal status.
3. Record `ResolvedStageRef` values for stages that completed successfully.
4. Record exact stage, manifest, measurement, and log references.
5. Record a failure reason when applicable.
6. Retry under a new attempt ID only if the run plan remains unchanged.

### After the run terminates

1. Validate all attempt records.
2. Identify the successful attempt, if one exists.
3. Collect its resolved stages, artifact manifests, and measurements.
4. Write and publish `<run_id>.run.resolved.yaml`.

---

## 17. Execution sequence

1. Define the experiment’s constants, factors, levels, metric IDs, variants, and replicate seeds.
2. Implement every source path required by every variant.
3. Implement every declared metric under `src/mantra/metrics/`.
4. Commit the experiment, variants, source, metrics, lockfile, and canonical input pointers to Git.
5. Use that source repository and commit for all comparable runs.
6. Allocate one run ID for each variant and replicate seed.
7. Generate the run’s authored stage specs.
8. Write `<run_id>.run.yaml`.
9. Validate, hash, publish, and verify the run plan and stage specs together in
   one immutable remote commit, following Section 16.
10. Allocate attempt ID `1`.
11. Check out the exact source commit into a clean workspace.
12. Retrieve and validate stored input pointers.
13. Materialize and verify stored artifacts.
14. Resolve same-run inputs from earlier stage outputs.
15. Execute stages in declared order.
16. Record observed metric values as measurements.
17. Publish each successful stage’s artifact, resolved spec, manifest, and
    measurements.
18. If execution fails:

    - Finish the attempt record.
    - Record the failure.
    - Preserve partial exact references.
    - Allocate a new attempt ID if retrying.
    - Execute the unchanged run plan again.

19. When the run reaches a terminal state, publish `<run_id>.run.resolved.yaml`.
20. Repeat for every variant and replicate seed.
21. Compare measurements across variants.
22. Summarize variation across replicates.
23. Select candidate code or artifacts.
24. Perform any Stage 1 promotion manually by creating or updating a
    Git-tracked pointer under `inputs/` that selects the accepted artifact's
    manifest. Commit the pointer without moving or copying the artifact or its
    manifest.

---

## 18. File tree

```text
repository/
├── src/
│   └── mantra/
│       ├── models/
│       ├── metrics/
│       │   ├── mean_squared_error.py
│       │   ├── pearson_correlation.py
│       │   └── <metric_id>.py
│       └── <other production source>
│
├── inputs/
│   ├── data/
│   │   └── <artifact>.pointer.yaml
│   ├── priors/
│   │   └── <artifact>.pointer.yaml
│   ├── embeddings/
│   │   └── <artifact>.pointer.yaml
│   └── models/
│       └── <artifact>.pointer.yaml
│
└── experiments/
    └── e001_low_rank/
        ├── e001_low_rank.experiment.yaml
        ├── README.md
        │
        ├── variants/
        │   ├── baseline.variant.yaml
        │   ├── low_rank_32.variant.yaml
        │   └── low_rank_64.variant.yaml
        │
        └── runs/
            └── low_rank_32/
                └── 01JABC/
                    ├── 01JABC.run.yaml
                    ├── 01JABC.run.resolved.yaml
                    │
                    ├── stages/
                    │   ├── build.spec.yaml
                    │   ├── build.spec.resolved.yaml
                    │   ├── embed.spec.yaml
                    │   ├── embed.spec.resolved.yaml
                    │   ├── train.spec.yaml
                    │   └── train.spec.resolved.yaml
                    │
                    ├── artifacts/
                    │   ├── prior.pt
                    │   ├── prior.pt.manifest.yaml
                    │   ├── embedding.pt
                    │   ├── embedding.pt.manifest.yaml
                    │   ├── weights.pt
                    │   └── weights.pt.manifest.yaml
                    │
                    ├── measurements/
                    │   ├── build.<metric_id>.jsonl
                    │   ├── embed.<metric_id>.jsonl
                    │   └── train.<metric_id>.jsonl
                    │
                    └── logs/
                        ├── 001.build.stdout.log
                        ├── 001.build.stderr.log
                        ├── 001.embed.stdout.log
                        ├── 001.embed.stderr.log
                        ├── 001.train.stdout.log
                        ├── 001.train.stderr.log
                        ├── 002.build.stdout.log
                        └── 002.build.stderr.log
```

Attempts remain embedded in `run.resolved.yaml`. Attempt IDs appear in log filenames so retries cannot overwrite previous logs.

Artifact, resolved-spec, manifest, and measurement paths remain stable.
Immutable storage commits distinguish files published by different attempts.

---

## 19. Naming conventions

```text
<experiment_id>.experiment.yaml
<variant_id>.variant.yaml

<run_id>.run.yaml
<run_id>.run.resolved.yaml

<stage_id>.spec.yaml
<stage_id>.spec.resolved.yaml

<artifact-native-name>
<artifact-native-name>.manifest.yaml

inputs/<category>/<selection-name>.pointer.yaml

<stage_id>.<metric_id>.jsonl

<attempt_id>.<stage_id>.stdout.log
<attempt_id>.<stage_id>.stderr.log
```

The resolved qualifier follows the entity type:

```text
train.spec.resolved.yaml
01JABC.run.resolved.yaml
```

Fixture status belongs in the containing test directory, not in the filename.

---

## 20. Git-tracked and generated files

Git tracks:

```text
src/
inputs/**/*.pointer.yaml
experiments/*/*.experiment.yaml
experiments/*/variants/*.variant.yaml
experiment README files
environment lockfile
```

Git does not track:

```text
experiments/*/runs/
artifact bytes
resolved stage specs
run-scoped manifests
measurement files
logs
resolved-run records
__pycache__/
*.pyc
```

The generated run tree is materialized locally and published under the same relative paths in immutable remote storage.

Local generated files may be removed after publication.

---

## 21. Validation boundary

### Pydantic validators

Pydantic validates facts available inside loaded objects:

- Repository-relative paths.
- SHA-256 format.
- Git-commit format.
- Frozen models.
- Unexpected-field rejection.
- Discriminated unions.
- Unique factor, variant, replicate, metric, stage, and attempt IDs.
- Unique stage-spec paths within a run.
- Input-name and stored-input materialization-path uniqueness.
- Locally visible stored-input, script, and output path collisions.
- Valid `FutureInputRef` structure.
- Authored and resolved input names and kinds correspond.
- A resolved stored-input pointer has the same Git storage location as its
  authored pointer.
- Valid experiment, variant, stage, and metric ID syntax.
- Attempt terminal-status consistency.
- Attempt completion timestamps.
- Unique resolved-stage IDs within each attempt.
- Strictly increasing attempt IDs in execution order.
- Nonoverlapping attempt time intervals.
- A resolved-run completion time no earlier than any attempt completion time.
- Successful attempts have no failure reason.
- Failed, preempted, and cancelled attempts have a nonempty failure reason.
- No attempt occurs after a successful attempt.
- Successful-run and successful-attempt consistency.
- Failed and cancelled runs have no accepted successful attempt.
- Measurement IDs and finite values.
- Source entry point matches the authored script.
- Output storage path matches the authored output path.
- Requested and resolved environments correspond.
- Strict reproducibility controls are internally valid.

### External verifier

The verifier performs filesystem, Git, and network operations:

- Retrieve referenced files.
- Recalculate SHA-256 and byte count.
- Load and verify artifact pointers used by stored inputs.
- Load and verify artifact manifests.
- Verify authored and resolved spec files.
- Verify that `run_file` parses as a `RunSpec` equal to the `RunSpec` embedded
  in `ResolvedRun`.
- Resolve experiment and variant IDs at their deterministic paths in the
  recorded source repository and commit.
- Verify that the variant assigns exactly one permitted level to every factor
  defined by the experiment.
- Verify that the run's experiment and variant IDs match the loaded experiment
  and variant files.
- Resolve every stage path within the immutable snapshot identified by
  `ResolvedRun.run_file.stored_at`, then verify the stage file against the
  corresponding `RunStageRef.sha256` and `RunStageRef.bytes`.
- Verify that every `FutureInputRef` names an earlier stage in the run.
- Verify that stage output paths are unique within the run.
- Verify that each future input's producer output path does not collide with
  the consumer's stored-input paths, script, or output path.
- Verify that each stored-input pointer selects a valid artifact manifest.
- Verify same-run producer-output edges.
- Verify that each future-input manifest was published by the referenced
  producer stage.
- Verify that every accepted artifact manifest corresponds to an output of a
  referenced resolved stage.
- Verify that measurement rows contain the expected run, attempt, stage, and
  metric IDs.
- Verify that every published file matches its recorded SHA-256 and byte count.
- Verify exact clean source checkout.
- Verify Git submodules and LFS objects.
- Verify every stage, manifest, measurement, and log reference retained by the
  successful attempt.

The verifier proves:

```text
pointer.manifest == retrieved manifest

retrieved artifact == manifest.artifact
manifest.artifact == producing resolved-spec output
manifest.spec == producing authored-spec file
manifest.resolved_spec == producing resolved-spec file
manifest.source == producing resolved-spec source

future-input manifest == producer manifest
future-input manifest.artifact == producer output

resolved run.run_file == resolved run.run
accepted artifact manifest.artifact == resolved-stage output
measurement run, attempt, stage, and metric IDs == containing records
```

Pydantic validators must not fetch remote files or inspect the filesystem.

---

## 22. Implementation order

The checked items are implemented in [the authoritative models](models_v4.py),
[the identifier definitions](ids.py), and [the focused model tests](../tests/test_models_v4.py).

### Artifact and input foundation

- [x] **1.** Define the Stage 1 identifier types.
- [x] **2.** Add `ArtifactPointerRef`, `ResolvedArtifactPointerRef`, and
  `ResolvedArtifactManifestRef`.
- [x] **3.** Update `ArtifactPointer` to select only a manifest.
- [x] **4.** Add primitive and file-reference tests.
- [x] **5.** Implement `StoredInputRef`.
- [x] **6.** Implement `FutureInputRef`.
- [x] **7.** Implement the discriminated authored input union.
- [x] **8.** Implement `ResolvedStoredInputRef`, `ResolvedFutureInputRef`, and
  their discriminated union.
- [x] **9.** Add authored-to-resolved input correspondence validators.
- [x] **10.** Add local input-path and collision validators.

### Deterministic dummy-data completion pass

Steps 11–22 use small deterministic dummy artifacts to complete and verify the
implementation skeleton. The data and stage calculations may be trivial, but
the pass must use the real models, serialization, hashing, byte counting,
pointer and manifest traversal, stage execution, measurement recording,
attempt handling, resolved-run construction, and cross-file verification.

- [x] **11.** Add metric declarations and measurement records.
- [x] **12.** Add experiment and variant models.
- [x] **13.** Add run and attempt models.
- [x] **14.** Add `ResolvedRun` and its validators.
- [ ] **15. Complete the external verifier.**

  - [x] **15.1. Retrieve and verify referenced files.**
    - Dispatch `GitFileRef` and `HuggingFaceFileRef` values to their respective
      retrieval backends.
    - Retrieve the file from the recorded repository, commit, and path.
    - Reject files whose byte count or SHA-256 differs from the corresponding
      `ResolvedFileRef`.
    - Handle Git-only resolved references through the same
      `stored_at`/SHA-256/byte-count interface.

  - [x] **15.2. Verify the resolved run's authored run file.**
    - Retrieve and verify `ResolvedRun.run_file`.
    - Parse it as `RunSpec`.
    - Require the parsed `RunSpec` to equal `ResolvedRun.run`.

  - [x] **15.3. Verify the experiment and variant.**
    - Load the experiment and variant from their deterministic paths at the
      run's recorded source commit.
    - Require the run, experiment, and variant IDs to agree.
    - Require the variant to assign exactly one permitted level to every factor
      defined by the experiment.
    - Require the run's replicate ID and seed to match one replicate declared by
      the experiment.

  - [x] **15.4. Verify the authored stage plan.**
    - Resolve every authored stage path in the immutable run-plan snapshot
      identified by `ResolvedRun.run_file.stored_at`.
    - Verify each stage file against the SHA-256 and byte count in its
      `RunStageRef` before parsing it.
    - Bind each loaded authored spec to the `stage_id` carried by its enclosing
      `RunStageRef` and preserve the declared run order.
    - Require every `FutureInputRef` to name an earlier stage in the run.
    - Require stage output paths to be unique within the run.
    - Reject future-output paths that collide with the consumer's stored-input
      paths, script, or output path.

  - [x] **15.5. Verify every resolved stage.**
    - Retrieve and parse the resolved-stage spec in every `ResolvedStageRef`
      retained by the successful attempt.
    - Require resolved-stage IDs to equal the run's declared stage IDs in
      order.
    - Require its embedded authored spec to equal the corresponding loaded
      authored stage spec.
    - Require its source, environment, inputs, script, and output to correspond
      to the authored request.
    - Require its output path to equal the authored output path.
    - Require its source repository and commit to equal the run's source
      snapshot.
    - Require its completion timestamp to fall inside the successful attempt.
    - Retrieve and verify the source entry point, environment lockfile, and
      output using their recorded SHA-256 values and byte counts.

  - [ ] **15.6. Verify stored inputs.**
    - Retrieve the `ArtifactPointer` selected by each stored input.
    - Require the resolved pointer location to equal the authored pointer
      location.
    - Retrieve the pointer's `ArtifactManifest` and require the pointer to select
      that manifest.
    - Retrieve the manifest's artifact and require its SHA-256 and byte count to
      match `manifest.artifact`.
    - Require the verified artifact to be materialized at the stored input's
      local `path` before execution.

  - [ ] **15.7. Verify same-run future inputs.**
    - Locate the resolved spec and artifact manifest belonging to the referenced
      producer stage.
    - Require the future input's manifest to equal the producer's manifest.
    - Require `manifest.artifact` to equal the producer's resolved output.
    - Retrieve and verify the artifact before the consumer stage executes.
    - Do not require an `ArtifactPointer` for a same-run dependency.

  - [ ] **15.8. Verify artifact manifests.**
    - Require `manifest.artifact` to equal the producing resolved stage's
      output.
    - Require `manifest.spec` to equal the producing authored stage-spec file.
    - Require `manifest.resolved_spec` to equal the producing resolved-stage
      file.
    - Require `manifest.source` to equal the producing resolved stage's source.
    - Retrieve and verify every file referenced by the manifest.

  - [ ] **15.9. Verify measurement files.**
    - Retrieve and verify every measurement file referenced by the successful
      attempt.
    - Parse every row as `Measurement`.
    - Require every row's run, attempt, stage, and metric IDs to match the
      containing records.
    - Require every measurement's metric ID to belong to the experiment.
    - Require every measurement to belong to a referenced successful stage.

  - [ ] **15.10. Verify the source checkout.**
    - Fetch the exact recorded Git commit.
    - Require every stage entry point to exist at that commit.
    - Reject modified tracked source and uncontrolled source files in the
      execution checkout.
    - Verify Git submodules at their recorded commits.
    - Verify referenced Git LFS objects.

  - [ ] **15.11. Orchestrate complete resolved-run verification.**
    - Implement one `verify_resolved_run()` entry point that performs checks
      15.1 through 15.10 in dependency order.
    - Select the successful attempt and verify every file referenced by that
      attempt.
    - Raise `VerificationError` on the first broken reference or relationship.
    - Return successfully only after the complete provenance chain passes.

- [ ] **16.** Point package exports at the authoritative model module.
- [ ] **17.** Update YAML loading and exact-byte serialization.
- [ ] **18.** Replace legacy fixtures with a complete Stage 1 dummy provenance
  tree.
- [ ] **19.** Add construction, rejection, round-trip, verifier, successful
  attempt, and controlled failed-attempt tests.
- [ ] **20.** Rewrite the README from the implemented and tested protocol.
- [ ] **21.** Remove legacy package wiring and tracked Python cache files.
- [ ] **22. Run the Stage 1 end-to-end completion gate.**
  - Compile the authoritative protocol modules.
  - Generate the Pydantic schemas.
  - Execute the complete deterministic dummy run.
  - Verify its complete provenance chain using `verify_resolved_run()`.
  - Run the complete test suite in the `mantra` Conda environment.

The dummy end-to-end run must exercise this complete chain:

```text
run plan and authored stage specs
→ stored input pointer
→ stored artifact manifest and bytes
→ successful stage output and manifest
→ same-run future input
→ measurements
→ attempt record
→ resolved run
→ external verifier passes
```

Stage 1 is complete only when the implementation can build this chain from
scratch, verify every referenced file's SHA-256 and byte count, and reproduce
the strict dummy run's stage-output SHA-256 values under the same recorded
conditions.

### Real-data handoff

After the dummy-data completion gate passes:

- [ ] Implement the real training-data download stage.
- [ ] Download, hash, and publish the training-data artifact and manifest.
- [ ] Create the Git-tracked pointer that selects the training-data manifest.
- [ ] Run the complete pipeline on a small real-data smoke-test subset.
- [ ] Run the complete live training workflow.

Only after Stage 1 passes should MANTRA implement final evaluation, diagnostics,
benchmarks, confirmation parity, and automatic promotion gating.

---

## 23. Future work: execution context, observability, benchmarks, and promotion

### Execution-context extensions

Add observed CUDA-runtime fields only when MANTRA can collect them reliably.
These extensions do not block the Stage 1 provenance skeleton or its dummy
end-to-end completion gate.

### Observability

After Stage 1 passes, MANTRA will extend its metric and measurement records
with an observability layer that groups the records used to inspect and
formally evaluate completed executions:

```text
Observability
├── metrics and measurements
├── diagnostics
└── benchmarks
```

Diagnostics and benchmarks remain separate record types with different roles:

- A diagnostic analyzes a specified artifact using one or more metrics and may
  produce structured data, tables, or visualizations.
- A benchmark fixes a formal evaluation protocol and determines whether a
  candidate is eligible for promotion.

### Benchmark reproducibility

Benchmark execution will use a benchmark-specific reproducibility class that
extends `StrictReproducibilitySpec`:

```python
class BenchmarkParityArtifact(ProtocolModel):
    name: NonEmptyStr
    path: RepoRelPath


class BenchmarkReproducibilitySpec(StrictReproducibilitySpec):
    confirmation_runs: Literal[2] = 2
    parity_artifacts: tuple[BenchmarkParityArtifact, ...] = Field(min_length=1)
```

`parity_artifacts` declares every persisted artifact whose exact contents must
match between the two independent confirmation runs. Each entry gives the
artifact's logical name and repository-relative path.

For every declared parity artifact, benchmark confirmation will require:

```text
first execution SHA-256 == second execution SHA-256
first execution byte count == second execution byte count
```

Both executions must independently recompute the declared artifacts. They may
reuse only canonical root inputs and explicitly permitted priors. They may not
consume derived transformations, embeddings, checkpoints, weights,
predictions, or outputs from an earlier execution or from the other
confirmation run.

### Benchmark definitions

Benchmark definitions will live under the repository's root `benchmarks/`
directory. The working naming convention is:

```text
benchmarks/
├── benchmark.strand.yaml
└── benchmark.gears.yaml
```

Each benchmark definition will specify at least:

- Benchmark ID.
- Cell line.
- Benchmark reproducibility specification.
- Metric IDs.
- Perturbation split.
- Highly variable gene split.
- Canonical dataset or root-input pointer.

The initial split layout will be:

```text
inputs/
└── benchmarks/
    └── k562/
        ├── hvg.strand.split.json
        ├── pert.strand.split.json
        ├── hvg.gears.split.json
        └── pert.gears.split.json
```

The split files are immutable benchmark inputs. Their exact Git commit and file
SHA-256 values will be recorded when the benchmark is resolved. If a split
later becomes too large for Git, the same logical path may be represented by an
artifact pointer without changing the benchmark's role.

### Benchmark results

Resolved benchmark results will be run artifacts under a run-scoped
`benchmarks/` directory:

```text
experiments/<experiment_id>/runs/<variant_id>/<run_id>/
└── benchmarks/
    ├── benchmark.strand.resolved.yaml
    └── benchmark.gears.resolved.yaml
```

A resolved benchmark will contain exact references to:

- The authored benchmark definition.
- The candidate source commit and artifact manifests.
- Both resolved confirmation runs.
- The measurement files produced by each confirmation run.
- The declared parity artifacts from each confirmation run.
- Per-artifact SHA-256 and byte-count parity decisions.
- Per-metric measurement parity decisions.
- The final benchmark status.

### Diagnostics

Diagnostic definitions will live under the repository's root `diagnostics/`
directory and will specify at least:

- Diagnostic ID.
- Input artifact or artifacts.
- Metric ID or metric IDs.
- Typed diagnostic parameters, when needed.
- Intended diagnostic output.

Resolved diagnostic records will be run artifacts under a run-scoped
`diagnostics/` directory:

```text
experiments/<experiment_id>/runs/<variant_id>/<run_id>/
└── diagnostics/
    └── diagnostic.<metric_id>.resolved.yaml
```

A resolved diagnostic will reference the exact measurement file and the exact
diagnostic output artifact. It will not duplicate the measurement value as a
second authoritative copy. If a diagnostic computes a new numerical result,
that result will be written as its own measurement file and referenced by the
resolved diagnostic.

### Promotion gate and SOTA pointer

Once the benchmark layer is enabled, promotion to either `src/` or `inputs/`
will require successful completion of every benchmark required by the
experiment.

The current state-of-the-art benchmark result will have one stable entry point:

```text
benchmarks/
└── sota/
    └── result.pointer.yaml
```

`benchmarks/sota/` will contain only this pointer. Updating the state of the art
means replacing the pointer in a new Git commit after the candidate passes the
required benchmarks.

This file will validate as a future `BenchmarkResultPointer`, not as an
`ArtifactPointer`: it selects a resolved benchmark-result record rather than an
artifact manifest.

The pointer will lead through the complete provenance chain:

```text
SOTA result pointer
└── resolved benchmark result
    ├── confirmation resolved runs
    ├── measurement files
    ├── diagnostic records and artifacts
    └── parity artifact manifests
        └── stage resolved specs
            └── input pointers and manifests
                └── download resolved specs
                    └── original remote sources
```
