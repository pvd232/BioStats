# MANTRA Provenance Protocol — Stage 1

## 1. Scope

Stage 1 implements one complete provenance path:

```text
ExperimentSpec + VariantSpec
            ↓
     frozen RunSpec
            ↓
        RunAttempt
            ↓
ordered stage specs and resolved stage specs
            ↓
artifacts + manifests + measurements
            ↓
       ResolvedRun
            ↓
    provenance verifier
```

1. **Define the experiment**
   - `ExperimentSpec` records factors, permitted levels, variants, replicates,
     seeds, and metric IDs.
   - `VariantSpec` assigns one permitted level to every experiment factor.

2. **Freeze the run**
   - `RunSpec` binds one experiment, variant, replicate, source commit, and
     ordered stage plan.
   - Each `RunStageRef` identifies one exact stage-spec file.

3. **Execute the run**
   - `StoredInputRef` selects a promoted input.
   - `FutureInputRef` selects an earlier stage's output.
   - `RunAttempt` records each execution attempt against the frozen `RunSpec`.

4. **Record the result**
   - Each successful stage writes one resolved stage spec and one primary
     artifact.
   - The resolved stage spec records the exact inputs, source, environment,
     execution context, command, output, and completion time.
   - `ResolvedFileRef` records each file's SHA-256, byte count, and immutable
     storage location.
   - `ArtifactManifest` connects each artifact to its stage spec, resolved
     stage spec, and source.
   - `Measurement` records metric values produced during execution.
   - `ResolvedRun` records the attempts and identifies the successful attempt.
   - `ArtifactPointer` selects an artifact manifest when an artifact is promoted
     for reuse.

5. **Verify the provenance chain**
   - Pydantic models enforce each document's field and relationship rules.
   - The provenance verifier retrieves every referenced file, verifies its
     bytes, and checks the relationships among the run, stages, inputs,
     artifacts, manifests, measurements, source, and environment.

Future stages add:

1. **Evaluation and diagnostics**
   - Final held-out evaluation.
   - Diagnostic records.

2. **Benchmarking and promotion**
   - Benchmark definitions and result records.
   - Two-run confirmation and artifact parity.
   - Automatic promotion gates.

3. **Complete model integration**
   - Concrete parameter classes for the MANTRA model stages.

Promotion is manual during Stage 1.

---

## 2. Core invariants

1. Every stage spec declares exactly one output path. Successful stage
   completion produces exactly one primary artifact at that path.

2. Every completed artifact is represented by a `ResolvedFileRef` containing
   its lowercase SHA-256, byte count, and immutable `stored_at` location.

3. Retrieving `ResolvedFileRef.stored_at` yields bytes whose SHA-256 equals
   `ResolvedFileRef.sha256` and whose length equals `ResolvedFileRef.bytes`.
   SHA-256 identifies the contents; byte count provides a secondary integrity
   check.

4. `ResolvedBaseSpec.output.stored_at.path` equals
   `ResolvedBaseSpec.spec.output`.

5. Every completed stage has one `ResolvedStageRef`. Its `resolved_spec` field
   identifies the resolved-spec file, and its `artifact_manifest` field
   identifies the stage artifact's `ArtifactManifest`. The manifest identifies
   the artifact, stage-spec file, resolved-spec file, and source entry point.

6. `ArtifactPointer` is created when an artifact is selected for promotion or
   reuse. Each pointer selects exactly one `ResolvedArtifactManifestRef`.

7. Every stage input resolves to verified artifact bytes before execution:

   - `StoredInputRef` resolves through `ResolvedStoredInputRef.pointer` →
     `ArtifactPointer.manifest` → `ArtifactManifest.artifact`.
   - `FutureInputRef` resolves through `ResolvedFutureInputRef.manifest` → the
     referenced producer stage's `ArtifactManifest.artifact`.

8. Every resolved stage spec embeds its stage spec and records the exact inputs,
   source, environment, execution context, command, output, and completion time.

9. Every `RunSpec` binds:

   - One experiment.
   - One variant declared by that experiment.
   - One replicate and seed declared by that experiment.
   - One source repository and Git commit.
   - One ordered sequence of `RunStageRef` records.

10. Every `RunAttempt` executes the same frozen `RunSpec`. A retry creates a new
    attempt ID. An experimental replicate creates a separate run.

11. A succeeded `ResolvedRun` identifies exactly one successful attempt through
    `successful_attempt_id`. That attempt contains every declared stage in
    order. Failed and cancelled runs identify no successful attempt. Partial
    records remain attached to the attempt that produced them.

12. Every `Measurement` identifies its `RunSpec.run_id`,
    `RunAttempt.attempt_id`, stage ID, and a metric ID declared by
    `ExperimentSpec.metric_ids`.

13. A strict replay succeeds when every reproduced stage artifact matches the
    recorded SHA-256 and byte count under the recorded execution conditions.

14. A relaxed execution records the same provenance chain while permitting
    replayed artifact bytes to differ.

---

## 3. Protocol hierarchy

### Protocol records

```text
ExperimentSpec
├── factors
│   └── levels
├── variant IDs
├── replicates
│   └── seeds
└── metric IDs

VariantSpec
└── one valid assignment of levels to factors

RunSpec
├── experiment ID
├── variant ID
├── replicate ID and seed
├── source repository and commit: RunSpec.source
└── ordered stages: RunStageRef[]

RunAttempt
└── one effort to execute the frozen RunSpec
    ├── resolved_stages: ResolvedStageRef[]
    │   ├── resolved_spec: ResolvedFileRef
    │   └── artifact_manifest: ResolvedArtifactManifestRef
    ├── measurement_files: ResolvedFileRef[]
    └── log_files: ResolvedFileRef[]

Stage
├── stage spec
├── exactly one intended primary output
└── successful completion
    ├── resolved spec
    ├── exactly one primary artifact
    ├── artifact manifest
    └── zero or more measurement streams

Artifact
├── SHA-256
├── byte count
├── immutable storage location
└── ArtifactManifest
    ├── artifact
    ├── stage spec
    ├── resolved spec
    └── source entry point

Promoted input
└── ArtifactPointer
    └── selected artifact manifest

Measurement
├── metric ID
├── observed value
├── stage ID
├── run ID
├── attempt ID
└── optional epoch or step

ResolvedRun
├── run: embedded RunSpec
├── run_file: verified file containing the same RunSpec
├── terminal status
├── successful_attempt_id
├── attempts: RunAttempt[]
└── completion timestamp
```

### Files frozen together

A file group is frozen by publishing every file in the group at one repository
commit. Changing any file creates a new commit.

```text
Source files
└── one Git commit identified by RunSpec.source
    ├── experiment file
    ├── variant files
    ├── source code
    ├── metric implementations
    ├── lockfile
    └── promoted-input pointers

Run-plan files
└── one commit identified by ResolvedRun.run_file.stored_at
    ├── <run_id>.run.yaml
    └── every stage spec referenced by RunSpec.stages
```

The artifact publication chain for one successful stage is:

```text
Commit A: producer source
└── source code, experiment, variants, metrics, lockfile,
    and promoted-input pointers
        │
        ▼
select the experiment, variant, and replicate
        │
        ▼
create the concrete stage specs and RunSpec
        │
        ▼
Commit B: run plan
└── <run_id>.run.yaml and its stage specs
        │
        ▼
execute commit B's plan using commit A's source
        │
        ▼
Commit C: artifact
└── the exact output bytes produced by the stage
        │
        ▼
Commit D: resolved spec
└── the execution record containing the artifact reference from C
        │
        ▼
Commit E: artifact manifest
└── the manifest linking the artifact, stage spec, resolved spec,
    and source from C, B, D, and A
        │
        └── optional promotion for later reuse
                │
                ▼
Commit F: consumer source
└── a Git-tracked ArtifactPointer selecting the manifest from E
        │
        └── serves as commit A for the consuming run
                │
                ▼
          create the consuming run's commit B
                │
                └── continue the same A → B → C → D → E cycle
```

Measurement and log files are published separately and recorded by
`RunAttempt`. The resolved-run file is published after the run terminates.

`RunSpec.source.commit` records source commit A. The stage specs are created
after A has been selected. The stage specs and `RunSpec` are then validated,
serialized, hashed, and published together as run-plan commit B.

Stage 1 uses this storage policy:

| Commit | Repository | When it is created |
|---|---|---|
| A | Git source repository | When source, experiment definitions, or selected input pointers change |
| B | MANTRA Hugging Face dataset repository | Once per run |
| C | Same Hugging Face repository | Once per successful stage |
| D | Same Hugging Face repository | Once per successful stage, after C |
| E | Same Hugging Face repository | Once per successful stage, after D |
| F | Git source repository | Only when an artifact is promoted for later reuse |

One successful stage creates commits C, D, and E. Commit A already exists,
commit B belongs to the complete run, and commit F occurs only after promotion.

The references record the commits as follows:

| Commit | Files fixed by the commit | Reference fields |
|---|---|---|
| A | Producer source files | `RunSpec.source.commit`; `ArtifactManifest.source.stored_at.commit` |
| B | Run file and stage specs | `ResolvedRun.run_file.stored_at.commit`; `ArtifactManifest.spec.stored_at.commit` |
| C | Stage artifact | `ResolvedBaseSpec.output.stored_at.commit`; `ArtifactManifest.artifact.stored_at.commit` |
| D | Resolved stage spec | `ResolvedStageRef.resolved_spec.stored_at.commit`; `ArtifactManifest.resolved_spec.stored_at.commit` |
| E | Artifact manifest | `ResolvedStageRef.artifact_manifest.stored_at.commit`; `ArtifactPointer.manifest.stored_at.commit` |
| F | Promoted pointer used by a later run | `StoredInputRef.pointer.commit`; `ResolvedStoredInputRef.pointer.stored_at.commit` |

The letters identify dependency order and file roles. A and F belong to the
Git source repository. B through E belong to one MANTRA Hugging Face dataset
repository.

Commit F becomes the source commit for a later run that consumes the promoted
pointer. For that later run, F occupies the same role that A occupied for the
producing run.

`ResolvedRun.run` embeds the parsed `RunSpec`. `ResolvedRun.run_file` records
the exact published file containing that `RunSpec`, including its storage
location, SHA-256, and byte count. The external verifier retrieves `run_file`,
verifies its bytes, parses it as a `RunSpec`, and requires it to equal
`ResolvedRun.run`.

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

Example artifact reference:

```yaml
sha256: <weights-sha256>
bytes: 123456

stored_at:
  kind: huggingface
  repository: machina/mantra-artifacts
  commit: <commit-c-artifact>
  path: experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/weights.pt
  repo_type: dataset
```

`stored_at.path` identifies the file inside the remote repository.
`stored_at.commit` selects the exact repository revision containing those
bytes.

### SHA-256 rule

For every resolved file:

```text
sha256 = SHA-256 of the exact stored file bytes
```

This applies to:

- Artifacts.
- Stage specs.
- Resolved specs.
- Manifests.
- Pointers.
- Measurement files.
- Published logs.
- Run plans.

SHA-256 is calculated directly from the bytes read from storage.

### Mirrored paths

The artifact’s local repository-relative path and remote repository-relative path are identical:

```text
Local:
experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/weights.pt

Remote:
experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/weights.pt
```

The remote reference records the repository and exact commit in addition to
the mirrored path.

Local bytes may be removed after publication. MANTRA can restore them from remote storage and verify their SHA-256 and byte count.

Stored inputs use two independent paths:

```text
StoredInputRef.pointer.path
└── remote Git path of the ArtifactPointer file

StoredInputRef.path
└── local path where MANTRA places the selected artifact bytes
```

The pointer file and the artifact received by the stage are different files,
so these paths may have different repository-relative values.

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

The reference types and document types have separate roles:

| Type | Meaning |
|---|---|
| `ArtifactPointerRef` | Git location where a pointer file can be retrieved |
| `ResolvedArtifactPointerRef` | Exact pointer file: location, SHA-256, and byte count |
| `ArtifactPointer` | Parsed contents of that pointer file |
| `ResolvedArtifactManifestRef` | Exact manifest file: location, SHA-256, and byte count |
| `ArtifactManifest` | Parsed contents of that manifest file |

The external verifier retrieves each referenced file, verifies its
SHA-256 and byte count, and parses it using the stated schema.

The A–F publication sequence maps onto these records as follows:

```text
Commit A ── ArtifactManifest.source
Commit B ── ArtifactManifest.spec
Commit C ── ArtifactManifest.artifact
Commit D ── ArtifactManifest.resolved_spec
Commit E ── ResolvedStageRef.artifact_manifest
Commit F ── ArtifactPointer file
```

When the stage artifact is promoted, the pointer published at F records the
same manifest reference carried by the producing stage:

```text
ArtifactPointer.manifest
    ==
producing ResolvedStageRef.artifact_manifest
```

Both fields contain the `ResolvedArtifactManifestRef` for the manifest file
published at E.

### Manifest

```python
class ArtifactManifest(ProtocolModel):
    schema_version: Literal[1] = 1

    artifact: ResolvedFileRef
    resolved_spec: ResolvedFileRef
    spec: ResolvedFileRef
    source: ResolvedGitFileRef

    created_at: AwareDatetime
```

The manifest answers:

```text
What exact artifact was produced?
What stage spec requested it?
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

Example `weights.pt.manifest.yaml`:

```yaml
schema_version: 1

artifact:
  sha256: <weights-sha256>
  bytes: 123456
  stored_at:
    kind: huggingface
    repository: machina/mantra-artifacts
    commit: <commit-c-artifact>
    path: experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/weights.pt
    repo_type: dataset

resolved_spec:
  sha256: <resolved-train-spec-sha256>
  bytes: <resolved-train-spec-bytes>
  stored_at:
    kind: huggingface
    repository: machina/mantra-artifacts
    commit: <commit-d-resolved-spec>
    path: experiments/e001_low_rank/runs/low_rank_32/01JABC/stages/train.spec.resolved.yaml
    repo_type: dataset

spec:
  sha256: <train-spec-sha256>
  bytes: <train-spec-bytes>
  stored_at:
    kind: huggingface
    repository: machina/mantra-artifacts
    commit: <commit-b-run-plan>
    path: experiments/e001_low_rank/runs/low_rank_32/01JABC/stages/train.spec.yaml
    repo_type: dataset

source:
  sha256: <train-source-sha256>
  bytes: <train-source-bytes>
  stored_at:
    kind: git
    repository: https://github.com/example/mantra
    commit: <commit-a-producer-source>
    path: src/mantra/train.py

created_at: 2026-08-18T20:30:00Z
```

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
    ├── stage spec
    ├── resolved spec
    └── source
```

A promoted artifact is represented by a Git-tracked pointer under `inputs/`.
The artifact bytes and production manifest remain in immutable remote storage.
Ordinary stage outputs receive manifests but not pointers. Creating or updating
a pointer is an explicit promotion or reusable-input selection step.

Example `ArtifactPointer` file at
`inputs/models/current_weights.pt.pointer.yaml`:

```yaml
schema_version: 1

manifest:
  kind: artifact_manifest
  sha256: <weights-manifest-sha256>
  bytes: <weights-manifest-bytes>
  stored_at:
    kind: huggingface
    repository: machina/mantra-artifacts
    commit: <commit-e-manifest>
    path: experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/weights.pt.manifest.yaml
    repo_type: dataset
```

When a later run consumes that pointer file, it records a
`ResolvedArtifactPointerRef` containing the file's SHA-256, byte count, and Git
location:

```yaml
kind: artifact_pointer
sha256: <pointer-file-sha256>
bytes: <pointer-file-bytes>

stored_at:
  kind: git
  repository: https://github.com/example/mantra
  commit: <commit-f-consumer-source>
  path: inputs/models/current_weights.pt.pointer.yaml
```

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
  current_weights:
    kind: stored

    pointer:
      kind: git
      repository: https://github.com/example/mantra
      commit: <commit-f-consumer-source>
      path: inputs/models/current_weights.pt.pointer.yaml

    path: inputs/models/current_weights.pt
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

The run plan represents the upstream artifact with `producer_stage_id`.
MANTRA resolves that ID through the run's stage list, loads the producer stage
spec, and uses its declared `output` path as the consumer's input path.

Execution proceeds as follows:

1. Validate that `embed` precedes the consuming stage.
2. Execute `embed`.
3. Hash and publish the embedding as artifact commit C.
4. Publish its resolved spec as commit D and its manifest as commit E.
5. Verify that the producer's declared output path still contains the recorded
   bytes, restoring those bytes there if necessary.
6. Execute the consuming stage.

### Stage input union

```python
InternalInputRef = Annotated[
    StoredInputRef | FutureInputRef,
    Field(discriminator="kind"),
]
```

### Resolved internal input

The two input forms resolve to role-specific representations containing
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

Resolved form of the stored `current_weights` input:

```yaml
kind: stored

pointer:
  kind: artifact_pointer
  sha256: <pointer-file-sha256>
  bytes: <pointer-file-bytes>
  stored_at:
    kind: git
    repository: https://github.com/example/mantra
    commit: <commit-f-consumer-source>
    path: inputs/models/current_weights.pt.pointer.yaml
```

Resolved form of the same-run `embedding` input:

```yaml
kind: future

manifest:
  kind: artifact_manifest
  sha256: <embedding-manifest-sha256>
  bytes: <embedding-manifest-bytes>
  stored_at:
    kind: huggingface
    repository: machina/mantra-artifacts
    commit: <commit-e-embedding-manifest>
    path: experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/embedding.pt.manifest.yaml
    repo_type: dataset
```

`ResolvedInternalSpec.spec.inputs` and `ResolvedInternalSpec.inputs` are joined
by input name:

```text
ResolvedInternalSpec
├── spec.inputs[input_name]
│   └── requested input
└── inputs[input_name]
    └── resolved input
```

Both dictionaries must contain the same input names. The requested and resolved
records for each input must also have the same `kind`.

For a stored input, the requested pointer location must equal the storage
location of the resolved pointer file:

```text
StoredInputRef
├── pointer ───────────────────────────────┐
└── path                                   │
                                           ==
ResolvedStoredInputRef                     │
└── pointer.stored_at ─────────────────────┘
```

For a stored input, `StoredInputRef.path`, reached through
`ResolvedInternalSpec.spec.inputs[input_name]`, records the local path where the
artifact bytes are placed.

For a future input, `FutureInputRef.producer_stage_id` and
`ResolvedFutureInputRef.manifest` connect through the successful `RunAttempt`:

```text
FutureInputRef.producer_stage_id
→ selects producer ResolvedStageRef from successful RunAttempt.resolved_stages
→ producer ResolvedStageRef.artifact_manifest
     ==
  ResolvedFutureInputRef.manifest
→ loads ArtifactManifest

producer ResolvedStageRef.resolved_spec
     ==
ArtifactManifest.resolved_spec

ArtifactManifest.artifact
     ==
producer ResolvedBaseSpec.output
```

`ResolvedStageRef.resolved_spec` loads the producer's `ResolvedBaseSpec`. The
local path comes from that producer record:

```text
ResolvedBaseSpec.spec.output
    ==
ResolvedBaseSpec.output.stored_at.path
```

### Input validation sequence

1. **Validate one `InternalSpec`.**

   `InternalSpec` checks the paths visible inside one stage:

   - No two `StoredInputRef.path` values overlap.
   - No `StoredInputRef.path` overlaps `InternalSpec.script`.
   - No `StoredInputRef.path` overlaps `InternalSpec.output`.
   - `InternalSpec.output` does not overlap `InternalSpec.script`.

   Equality and ancestor–descendant overlap both count:

   ```text
   inputs/data.bin
   inputs/data.bin/part
   ```

2. **Validate one `ResolvedInternalSpec`.**

   `ResolvedInternalSpec` checks its embedded stage spec against its resolved
   inputs:

   ```text
   ResolvedInternalSpec.inputs.keys()
   ==
   ResolvedInternalSpec.spec.inputs.keys()
   ```

   For each input:

   ```text
   resolved input kind
   ==
   stage-spec input kind
   ```

   For a stored input:

   ```text
   ResolvedStoredInputRef.pointer.stored_at
   ==
   StoredInputRef.pointer
   ```

3. **Verify the complete `RunSpec`.**

   `verify_stage_plan()` checks relationships requiring every stage spec:

   - Stage output paths do not overlap.
   - Every `FutureInputRef.producer_stage_id` identifies an earlier stage.
   - The producer's output path does not overlap the consumer's script, output,
     or stored-input paths.

4. **Verify the input bytes and provide them to the executor.**

   `verify_stored_inputs()` and `verify_future_inputs()` return a
   `VerifiedInput` containing:

   ```text
   VerifiedInput
   ├── path
   ├── artifact
   └── content
   ```

   The verifier establishes the artifact's identity and returns its verified
   bytes as `VerifiedInput.content`. The executor makes those bytes available
   to the stage command at `VerifiedInput.path`.

   A stored input follows:

   ```text
   ResolvedStoredInputRef.pointer
   → ArtifactPointer.manifest
   → ArtifactManifest.artifact
   → verified artifact bytes
   → StoredInputRef.path
   ```

   A same-run future input follows:

   ```text
   FutureInputRef.producer_stage_id
   → producer ResolvedStageRef.artifact_manifest
                    ==
      ResolvedFutureInputRef.manifest
   → ArtifactManifest
      ├── resolved_spec
      │        ==
      │  producer ResolvedStageRef.resolved_spec
      └── artifact
                    ==
         producer ResolvedBaseSpec.output
   → verified artifact bytes
   → producer stage's output path
   ```

   Every retrieved pointer, manifest, artifact, stage spec, resolved spec, and
   source file must match its recorded SHA-256 and byte count.

---

## 7. External data roots

Each `RemoteFileRef` is an external data root. A `DownloadSpec` retrieves
exactly one remote file. `ResolvedDownloadSpec.output` is the first
`ResolvedFileRef` in the lineage rooted at that URL.

```text
DownloadSpec
├── inputs
│   └── input_name → RemoteFileRef.url
├── script
└── output
        │
        ▼
executor runs DownloadSpec.script as the entry point
├── retrieve the single RemoteFileRef.url
└── write those bytes at DownloadSpec.output
        │
        ▼
calculate output SHA-256 and byte count
→ publish output at an immutable storage location
        │
        ▼
ResolvedDownloadSpec
├── spec: DownloadSpec
├── inputs: dict[InputName, RemoteFileRef]
├── command
└── output: ResolvedFileRef
```

Example `DownloadSpec.inputs`:

```yaml
inputs:
  raw_data:
    kind: remote
    url: https://example.org/datasets/perturbations.h5ad
```

`ResolvedDownloadSpec` and its `ArtifactManifest` must satisfy:

```text
ResolvedDownloadSpec.inputs
    ==
ResolvedDownloadSpec.spec.inputs

ResolvedDownloadSpec.output.stored_at.path
    ==
ResolvedDownloadSpec.spec.output

ArtifactManifest.artifact
    ==
ResolvedDownloadSpec.output
```

`ResolvedDownloadSpec.output.sha256` and `ResolvedDownloadSpec.output.bytes`
identify the output contents. `ResolvedDownloadSpec.output.stored_at` identifies
where that exact file is stored at an immutable repository commit.

Repeating the acquisition requires:

1. Executing `ResolvedDownloadSpec.command` using its recorded `source` and
   `environment`.
2. `ResolvedDownloadSpec.spec.script` retrieving the `RemoteFileRef` in
   `ResolvedDownloadSpec.inputs` and writing the returned bytes at
   `ResolvedDownloadSpec.spec.output`.
3. Calculating the SHA-256 and byte count of the file written at
   `ResolvedDownloadSpec.spec.output`.
4. Comparing both values with `ResolvedDownloadSpec.output`.

After the artifact is promoted as a reusable input, a later stage reaches it
through:

```text
StoredInputRef.pointer
→ ArtifactPointer.manifest
→ ArtifactManifest.artifact
     ==
  ResolvedDownloadSpec.output
```

---

## 8. Source repository and entry point

`RunSpec.source` identifies the complete tracked repository snapshot used by the
run. `ResolvedBaseSpec.source` identifies the exact entry-point file used by one
stage.

```text
RunSpec.source
├── repository
└── commit
    └── complete tracked repository snapshot

ResolvedBaseSpec.source
├── sha256
├── bytes
└── stored_at: GitFileRef
    ├── repository
    ├── commit
    └── path
        └── stage entry-point file
```

Example `RunSpec.source` and `ResolvedBaseSpec.source` values for one train
stage:

```yaml
# RunSpec.source
source:
  kind: git
  repository: https://github.com/example/mantra
  commit: <commit-a-producer-source>

---

# ResolvedBaseSpec.source
source:
  sha256: <train-source-sha256>
  bytes: <train-source-bytes>
  stored_at:
    kind: git
    repository: https://github.com/example/mantra
    commit: <commit-a-producer-source>
    path: src/mantra/train.py
```

The verifier reaches the run source and each resolved stage through the `ResolvedRun`:

```text
ResolvedRun
├── run: RunSpec
│   └── source
├── successful_attempt_id
└── attempts
    └── RunAttempt where attempt_id == successful_attempt_id
        └── resolved_stages
            └── ResolvedStageRef
                ├── resolved_spec
                │   └── loads ResolvedBaseSpec
                │       └── source
                └── artifact_manifest
                    └── loads ArtifactManifest
                        └── source
```

The records must satisfy:

```text
ResolvedBaseSpec.source.stored_at.repository
    ==
ResolvedRun.run.source.repository

ResolvedBaseSpec.source.stored_at.commit
    ==
ResolvedRun.run.source.commit

ResolvedBaseSpec.source.stored_at.path
    ==
ResolvedBaseSpec.spec.script

ArtifactManifest.source
    ==
ResolvedBaseSpec.source
```

The verifier checks the entry-point file through:

```text
ResolvedBaseSpec.source.stored_at
→ retrieve entry-point bytes
→ compare byte count with ResolvedBaseSpec.source.bytes
→ compare SHA-256 with ResolvedBaseSpec.source.sha256
```

The executor handles the stage source in this order:

```text
RunSpec.source
→ check out repository at commit
→ confirm checkout HEAD equals RunSpec.source.commit
→ before input materialization, confirm the checkout is clean
  ├── no modified tracked files
  └── no untracked files
→ locate BaseSpec.script inside the checkout
→ calculate the entry point's SHA-256 and byte count
→ materialize the stage's declared inputs
→ launch BaseSpec.script as the stage entry point from that checkout
→ record ResolvedBaseSpec.source
```

Files that can affect the stage output connect to the provenance record through:

```text
tracked project code and imports
→ RunSpec.source

stage entry-point file
→ ResolvedBaseSpec.source

installed Python and native libraries
→ ResolvedBaseSpec.environment

external file retrieved by a download stage
→ DownloadSpec.inputs

runtime files outside the tracked source and installed environment
→ InternalSpec.inputs
```

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
  commit: <commit-a-producer-source>

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

Before execution, the run uses two fixed commits:

```text
Commit A: producer source
└── source code, experiment, variants, lockfile, and input pointers

Commit B: run plan
└── run.yaml and the stage specs
```

`RunSpec.source` identifies commit A. `ResolvedRun.run_file.stored_at`
identifies commit B. Every `RunStageRef.spec` is resolved within B, while its
`sha256` and `bytes` verify the exact stage file. The run plan does not contain
commit B because that commit depends on the bytes of the run plan itself.

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

An attempt is a successful or unsuccesful execution of the run spec.

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
    artifact_manifest: ResolvedArtifactManifestRef


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

Example completed `embed` stage reference:

```yaml
stage_id: embed

resolved_spec:
  sha256: <resolved-embed-spec-sha256>
  bytes: <resolved-embed-spec-bytes>
  stored_at:
    kind: huggingface
    repository: machina/mantra-artifacts
    commit: <commit-d-embedding-resolved-spec>
    path: experiments/e001_low_rank/runs/low_rank_32/01JABC/stages/embed.spec.resolved.yaml
    repo_type: dataset

artifact_manifest:
  kind: artifact_manifest
  sha256: <embedding-manifest-sha256>
  bytes: <embedding-manifest-bytes>
  stored_at:
    kind: huggingface
    repository: machina/mantra-artifacts
    commit: <commit-e-embedding-manifest>
    path: experiments/e001_low_rank/runs/low_rank_32/01JABC/artifacts/embedding.pt.manifest.yaml
    repo_type: dataset
```

Attempt invariants:

- Attempt IDs are unique within a run.
- Attempts appear in execution order, and their IDs strictly increase.
- An attempt cannot begin before the preceding attempt finishes.
- Every attempt has a completion timestamp.
- Resolved-stage IDs are unique and preserve the run's declared stage order.
- Each `ResolvedStageRef` binds one stage ID to its resolved-spec file and
  artifact-manifest file.
- Artifact-manifest references are unique within an attempt.
- Retrying may not modify the frozen run plan.
- A successful attempt completes every stage in order and has no failure
  reason.
- A failed, preempted, or cancelled attempt has a nonempty failure reason.
- No attempt may occur after a successful attempt.
- An unsuccessful attempt may retain completed-stage, measurement, and log
  references.
- Partial unsuccessful-attempt outputs do not become accepted run outputs.
- Deliberate reproducibility confirmations are separate runs, not attempts.

Mutable `running` state belongs to the executor’s operational state rather than the immutable resolved-run record.

Different attempts may publish the same relative path at different immutable Hugging Face commits. Each attempt retains the exact commit references it produced. The resolved run selects the successful attempt’s references.

---

## 12. Stage specifications and resolved stage specifications

A stage spec records the requested execution:

```text
Spec
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
├── embedded Spec
├── exact resolved inputs
├── exact source entry point
├── resolved environment
├── observed execution context
├── actual command
├── exact output artifact
└── completion timestamp
```

The resolved-spec file is identified by its `ResolvedFileRef`. The associated
`stage_id` belongs to the `ResolvedStageRef` that binds the file into a
`RunAttempt`; the containing `ResolvedRun` and `RunAttempt` supply the run and
attempt identities.

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
  file and artifact-manifest file;
- each resolved-spec file embeds the stage spec corresponding to the declared
  run-plan stage;
- each resolved stage uses the run's source commit A and was completed within the
  successful attempt's time interval;
- each `ResolvedStageRef.artifact_manifest` identifies its resolved stage's
  recorded output; and
- each measurement row identifies the expected run, attempt, stage, and metric.

The verifier also recalculates every referenced file's SHA-256 and byte count.

---

## 16. Publication order

### Before execution

1. Freeze the run plan.
2. Freeze all stage specs.
3. Validate the run plan and all stage specs as one complete set.
4. Calculate each file's exact SHA-256 and byte count.
5. Publish the run plan and all stage specs together in one immutable
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
4. Publish the artifact bytes and record artifact commit C.
5. Construct `<stage_id>.spec.resolved.yaml` using the artifact reference from
   C.
6. Publish the resolved spec and record resolved-spec commit D.
7. Construct `<artifact>.manifest.yaml` using the source reference from A, the
   stage-spec reference from B, the artifact reference from C, and the
   resolved-spec reference from D.
8. Publish the manifest and record manifest commit E.
9. Close and publish measurement files.
10. Construct one `ResolvedStageRef` containing the stage ID, resolved-spec
    reference from D, and artifact-manifest reference from E.
11. Record the `ResolvedStageRef` and measurement-file references in the
    attempt.

### After an attempt terminates

1. Close and publish its logs.
2. Record its terminal status.
3. Record `ResolvedStageRef` values for stages that completed successfully.
4. Record exact measurement and log references.
5. Record a failure reason when applicable.
6. Retry under a new attempt ID while preserving the run plan.

### After the run terminates

1. Validate all attempt records.
2. Identify the successful attempt, if one exists.
3. Collect its resolved stages and measurements. Each `ResolvedStageRef`
   contains its artifact-manifest reference.
4. Write and publish `<run_id>.run.resolved.yaml`.

---

## 17. Execution sequence

1. Define the experiment’s factors, levels, metric IDs, variants, and replicate seeds.
2. Implement every source path required by every variant.
3. Implement every declared metric under `src/mantra/metrics/`.
4. Commit the experiment, variants, source, metrics, lockfile, and canonical input pointers to Git.
5. Use that source repository and commit for all comparable runs.
6. Allocate one run ID for each variant and replicate seed.
7. Create the run’s concrete stage specs.
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
17. Publish each successful stage’s artifact, resolved spec, and manifest in
    commit order C, D, and E, then publish its measurements.
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

### Model validation

Loading a provenance document constructs its Pydantic model and enforces the
field and relationship rules defined by that model.

### Step 15 verification data flow

Step 15 starts from a `ResolvedRun`, follows every reference retained by its
successful attempt, verifies the referenced bytes, and confirms that the run,
stages, inputs, artifacts, manifests, measurements, source, and environment
form one consistent provenance chain.

#### Run and attempt hierarchy

```text
ResolvedRun
├── run: RunSpec
│   ├── experiment_id
│   ├── variant_id
│   ├── replicate_id and seed
│   ├── source: GitSource
│   └── stages: RunStageRef[]
│       ├── stage_id
│       ├── stage spec path
│       ├── stage spec SHA-256
│       └── stage spec byte count
│
├── run_file: ResolvedFileRef
│   └── exact serialized RunSpec
│
└── attempts: RunAttempt[]
    ├── status and timestamps
    ├── resolved_stages: ResolvedStageRef[]
    ├── measurement_files: ResolvedFileRef[]
    └── log_files: ResolvedFileRef[]
```

`RunSpec` is the frozen execution plan. `RunAttempt` records one attempt to
execute that plan. Step 15 verifies the files retained by the successful
attempt.

#### Stage records

```text
RunStageRef
├── stage_id
└── exact stage-spec identity
    ├── path
    ├── SHA-256
    └── byte count

ResolvedStageRef
├── stage_id
├── resolved_spec: ResolvedFileRef
│   └── exact resolved-spec identity and storage location
└── artifact_manifest: ResolvedArtifactManifestRef
    └── exact artifact-manifest identity and storage location
```

The resolved-spec file parses as one of:

```text
ResolvedDownloadSpec
ResolvedBuildSpec
ResolvedEmbedSpec
ResolvedTrainSpec
```

Every resolved stage contains:

```text
resolved stage
├── spec                 embedded stage spec
├── inputs               exact inputs used
├── source               exact source entry point
├── environment          exact machine image and lockfile
├── execution_context    observed execution conditions
├── command              executed argument vector
├── output               exact output artifact
└── completed_at         completion timestamp
```

#### Artifact-to-producer relationship

```text
ResolvedStageRef
├── resolved_spec ───────────────────────────────┐
│                                                │ same ResolvedFileRef
└── artifact_manifest                            │
    └── loads ArtifactManifest                   │
        ├── resolved_spec ───────────────────────┘
        ├── spec              exact stage-spec file
        ├── source            exact source entry point
        └── artifact          exact produced artifact
```

`ResolvedStageRef.artifact_manifest` identifies the stage's manifest file. The
equality between `ResolvedStageRef.resolved_spec` and
`ArtifactManifest.resolved_spec` confirms that the manifest describes the same
stage execution. The manifest identifies the exact artifact, stage spec, and
source associated with that execution.

`ResolvedArtifactManifestRef` identifies the manifest file itself:

```text
manifest storage location
+ manifest SHA-256
+ manifest byte count
```

#### Stored-input verification

A stored input selects an artifact that was promoted before the run began.

```text
StoredInputRef
├── pointer: ArtifactPointerRef
└── path: local execution path
          │
          ▼
ResolvedStoredInputRef
└── pointer: ResolvedArtifactPointerRef
             │
             ▼ retrieve and verify
          ArtifactPointer
          └── manifest: ResolvedArtifactManifestRef
                         │
                         ▼ retrieve and verify
                      ArtifactManifest
                      └── artifact: ResolvedFileRef
                                      │
                                      ▼ retrieve and verify
                                   artifact bytes
                                      │
                                      ▼
                            materialize at specified path
```

The spec reference selects the pointer location and local execution path.
The resolved reference records the exact pointer-file bytes used. The pointer
selects the manifest; the manifest identifies the artifact.

#### Same-run future-input verification

A future input consumes the output of an earlier stage in the same run.

```text
FutureInputRef
└── producer_stage_id
          │
          ▼
producer ResolvedStageRef
├── resolved_spec ─────────────────────┐
└── artifact_manifest ─────────────┐   │
                                   │   │
ResolvedFutureInputRef
└── manifest ──────────────────────┘   │
              same reference           │
                     │                  │
                     ▼                  │
              ArtifactManifest          │
              ├── resolved_spec ────────┘
              └── artifact
                     │
                     ▼ retrieve and verify
              verified artifact bytes
                     │
                     ▼
producer stage spec.output path
```

The spec input names the producer stage. The resolved input records the
exact manifest consumed from that stage. The consumer reads the verified
artifact at the producer's stage spec output path.

#### Verifier-only return values

These objects exist only in memory while verification runs. They are not
serialized provenance records.

| Object | Contains | Consumer |
|---|---|---|
| `VerifiedArtifactManifest` | Parsed manifest, stage spec, resolved spec, exact artifact reference, and verified artifact bytes | Stored- and future-input verification |
| `VerifiedInput` | Local input path, exact artifact reference, and verified bytes | Stage executor |

#### Step-to-model contract

| Step | Records checked | Relationship proved |
|---|---|---|
| 15.1 | `ResolvedFileRef` and retrieved bytes | Retrieved byte count and SHA-256 equal the recorded values |
| 15.2 | `ResolvedRun.run_file` and `ResolvedRun.run` | The published run file equals the embedded run plan |
| 15.3 | `RunSpec`, `ExperimentSpec`, and `VariantSpec` | The run selects a declared variant, factor assignment, and replicate |
| 15.4 | `RunSpec.stages` and `RunStageRef` | Stage specs are exact, ordered, and path-compatible |
| 15.5 | `ResolvedStageRef.resolved_spec` for the successful `RunAttempt` | Every declared stage has the correct resolved execution record and exact referenced files |
| 15.6 | `ResolvedStageRef.artifact_manifest` and `ArtifactManifest` | Each stage manifest identifies one verified stage output and its producing records |
| 15.7 | `StoredInputRef` and `ResolvedStoredInputRef` | A promoted input resolves through its pointer and manifest to verified bytes |
| 15.8 | `FutureInputRef`, `ResolvedFutureInputRef`, producer stage, and producer manifest | A same-run input resolves to the referenced earlier stage's verified output |
| 15.9 | `RunAttempt.measurement_files` and `Measurement` rows | Measurements belong to the expected run, attempt, stage, and metric |
| 15.10 | `RunSpec.source` and the execution checkout | Execution used the recorded source commit without source changes |
| 15.11 | All preceding records | The complete successful-run provenance chain passes every check |

### External verifier

Every referenced file follows one verification rule:

```text
recorded storage location
        ↓ retrieve
exact bytes
        ↓ verify
recorded byte count and SHA-256
        ↓ parse
typed provenance record
```

The verifier traverses the successful run in this order:

1. **Run root**
   - Retrieve `ResolvedRun.run_file`.
   - Parse it as `RunSpec`.
   - Require it to equal `ResolvedRun.run`.

2. **Experiment and variant**
   - Load the experiment and variant from their deterministic paths at the
     `RunSpec.source` commit.
   - Match `ExperimentSpec.experiment_id`, `VariantSpec.experiment_id`, and
     `VariantSpec.variant_id` to the corresponding `RunSpec` fields.
   - Match `RunSpec.replicate_id` and `RunSpec.seed` to one
     `ExperimentSpec.replicates` entry.
   - Validate every `VariantSpec.levels` assignment against the corresponding
     `FactorSpec.levels`.

3. **Stage plan**
   - Load each stage spec from `ResolvedRun.run_file.stored_at` using
     `RunStageRef.spec`.
   - Verify it using `RunStageRef.bytes` and `RunStageRef.sha256`.
   - Preserve the order of `RunSpec.stages` and require each
     `FutureInputRef.producer_stage_id` to identify an earlier `RunStageRef`.
   - Require unique `BaseSpec.output` paths across the run.
   - Reject overlaps among `StoredInputRef.path`, the producer
     `BaseSpec.output` used by each future input, `InternalSpec.script`, and
     `InternalSpec.output`.

4. **Resolved stages**
   - Select the `RunAttempt` identified by
     `ResolvedRun.successful_attempt_id`.
   - Match `RunAttempt.resolved_stages` to `RunSpec.stages` by `stage_id` and
     order.
   - Retrieve each `ResolvedStageRef.resolved_spec`.
   - Match `ResolvedBaseSpec.spec`, `ResolvedBaseSpec.source`,
     `ResolvedBaseSpec.environment`, and `ResolvedBaseSpec.output` to the stage
     plan.
   - Require `ResolvedBaseSpec.completed_at` to fall between
     `RunAttempt.started_at` and `RunAttempt.completed_at`.

5. **Artifact manifests**
   - Retrieve each `ResolvedStageRef.artifact_manifest`.
   - Verify `ArtifactManifest.artifact`, `ArtifactManifest.spec`,
     `ArtifactManifest.resolved_spec`, and `ArtifactManifest.source`.
   - Match `ArtifactManifest.resolved_spec` to the producing
     `ResolvedStageRef.resolved_spec`.

6. **Stored inputs**
   - For each `StoredInputRef`, retrieve the corresponding
     `ResolvedStoredInputRef.pointer`.
   - Parse those bytes as `ArtifactPointer` and follow
     `ArtifactPointer.manifest`.
   - Return the verified artifact bytes with `StoredInputRef.path`.

7. **Same-run future inputs**
   - Resolve `FutureInputRef.producer_stage_id` to an earlier `RunStageRef`.
   - Resolve the same stage ID to the producer `ResolvedStageRef` in the
     successful `RunAttempt`.
   - Match `ResolvedFutureInputRef.manifest` to
     `ResolvedStageRef.artifact_manifest`.
   - Return the verified `ResolvedBaseSpec.output` bytes at
     `ResolvedBaseSpec.spec.output`.

8. **Measurements and logs**
   - Retrieve every file in `RunAttempt.measurement_files` and
     `RunAttempt.log_files`.
   - Match `Measurement.run_id`, `Measurement.attempt_id`,
     `Measurement.stage_id`, and `Measurement.metric_id` to `RunSpec`,
     `RunAttempt`, the referenced stage, and `ExperimentSpec.metric_ids`.

9. **Source checkout**
   - Check out `RunSpec.source.repository` at `RunSpec.source.commit`.
   - Match every stage entry point to `ResolvedBaseSpec.source`.
   - Reject modified tracked files and untracked files before input
     materialization.

The verified relationships are:

**Run**

- `RunSpec.model_validate(run_file_contents) == ResolvedRun.run`
- Successful `RunAttempt.resolved_stages[*].stage_id == RunSpec.stages[*].stage_id`

**Manifest**

- `ResolvedStageRef.artifact_manifest` identifies the retrieved manifest file.
- Parsed `ArtifactManifest.spec` contents equal `ResolvedBaseSpec.spec`.
- `ArtifactManifest.resolved_spec == ResolvedStageRef.resolved_spec`.
- `ArtifactManifest.source == ResolvedBaseSpec.source`.
- `ArtifactManifest.artifact == ResolvedBaseSpec.output`.

**Stored input**

- `ResolvedStoredInputRef.pointer.stored_at == StoredInputRef.pointer`.
- Parsed `ArtifactPointer.manifest` supplies the
  `ResolvedArtifactManifestRef` passed to artifact-manifest verification.

**Future input**

- `ResolvedFutureInputRef.manifest ==`
  `producer ResolvedStageRef.artifact_manifest`.
- Parsed `ArtifactManifest.resolved_spec ==`
  `producer ResolvedStageRef.resolved_spec`.

**Measurement**

- `Measurement.run_id == RunSpec.run_id`.
- `Measurement.attempt_id == RunAttempt.attempt_id`.
- `Measurement.stage_id == ResolvedStageRef.stage_id`.
- `Measurement.metric_id in ExperimentSpec.metric_ids`.

#### How referenced files are verified

The functions in `viper/verifier.py` follow each
`ResolvedFileRef.stored_at` reference:

```text
ResolvedFileRef
├── stored_at: GitFileRef
│   └── fetch_git_file_bytes()
│
└── stored_at: HuggingFaceFileRef
    └── fetch_huggingface_file_bytes()
                │
                ▼
       verify_resolved_file_bytes()
       ├── len(bytes) == ResolvedFileRef.bytes
       └── sha256(bytes) == ResolvedFileRef.sha256
                │
                ▼
       parse the verified bytes
                │
                ▼
       compare the resulting Pydantic records
```

`read_resolved_file()` performs the retrieval and byte verification for one
reference. Higher-level functions such as `verify_resolved_run_file()`,
`verify_stage_plan()`, `verify_artifact_manifest()`,
`verify_stored_inputs()`, and `verify_future_inputs()` compose that operation
into the provenance traversal described above.

Production calls use the Git and Hugging Face retrieval functions. Tests pass a
`StorageFetcher` that returns controlled bytes from an in-memory mapping; the
same byte-count, SHA-256, parsing, and relationship checks then execute against
those bytes.

Source-checkout verification in Step 15.10 inspects the checked-out repository
for the recorded commit and stage entry points, then requires no modified
tracked files or untracked files before input materialization.

---

## 22. Implementation order

The checked items are implemented in [the authoritative models](records.py),
[the identifier definitions](ids.py), and [the focused model tests](../tests/test_records.py).

### Artifact and input foundation

- [x] **1.** Define the Stage 1 identifier types.
- [x] **2.** Add `ArtifactPointerRef`, `ResolvedArtifactPointerRef`, and
  `ResolvedArtifactManifestRef`.
- [x] **3.** Update `ArtifactPointer` to select only a manifest.
- [x] **4.** Add primitive and file-reference tests.
- [x] **5.** Implement `StoredInputRef`.
- [x] **6.** Implement `FutureInputRef`.
- [x] **7.** Implement the discriminated spec input union.
- [x] **8.** Implement `ResolvedStoredInputRef`, `ResolvedFutureInputRef`, and
  their discriminated union.
- [x] **9.** Add spec-to-resolved input correspondence validators.
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

  - [x] **15.2. Verify the resolved run's run file.**
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

  - [x] **15.4. Verify the stage plan.**
    - Resolve every stage spec path in run-plan commit B, identified by
      `ResolvedRun.run_file.stored_at`.
    - Verify each stage file against the SHA-256 and byte count in its
      `RunStageRef` before parsing it.
    - Bind each loaded stage spec to the `stage_id` carried by its enclosing
      `RunStageRef` and preserve the declared run order.
    - Require every `FutureInputRef` to name an earlier stage in the run.
    - Require stage output paths to be unique within the run.
    - Reject future-output paths that collide with the consumer's stored-input
      paths, script, or output path.

  - [x] **15.5. Verify every resolved stage.**
    - Retrieve and parse `ResolvedStageRef.resolved_spec` for every completed
      stage retained by the successful attempt.
    - Require resolved-stage IDs to equal the run's declared stage IDs in
      order.
    - Require its embedded stage spec to equal the corresponding loaded
      stage spec.
    - Require its source, environment, inputs, script, and output to correspond
      to the stage spec.
    - Require its output path to equal the stage spec output path.
    - Require its source repository and commit to equal the run's source
      snapshot.
    - Require its completion timestamp to fall inside the successful attempt.
    - Retrieve and verify the source entry point, environment lockfile, and
      output using their recorded SHA-256 values and byte counts.

  - [x] **15.6. Verify artifact manifests.**
    - Retrieve and verify each `ResolvedStageRef.artifact_manifest` before
      parsing it as an `ArtifactManifest`.
    - Retrieve and verify `manifest.artifact`, `manifest.spec`,
      `manifest.resolved_spec`, and `manifest.source`.
    - Parse `manifest.spec` as a stage spec and
      `manifest.resolved_spec` as a resolved stage spec.
    - Require the resolved stage spec to embed the retrieved stage spec.
    - Require `manifest.artifact` to equal the resolved stage's output.
    - Require `manifest.source` to equal the resolved stage's source.
    - Return the parsed records, exact artifact reference, and verified artifact
      bytes for downstream input verification.

  - [x] **15.7. Verify stored inputs.**
    - Retrieve the `ArtifactPointer` selected by each stored input.
    - Require the pointer's manifest reference to pass artifact-manifest
      verification.
    - Return the verified artifact bytes, exact artifact reference, and specified
      local `path` to the executor.
    - Require the executor to materialize those verified bytes at that local
      `path` before execution.

  - [ ] **15.8. Verify same-run future inputs.**
    - Resolve `FutureInputRef.producer_stage_id` to the producer
      `ResolvedStageRef` in the successful attempt.
    - Require `ResolvedFutureInputRef.manifest` to equal the producer
      `ResolvedStageRef.artifact_manifest`.
    - Verify the manifest through `ResolvedStageRef.artifact_manifest`.
    - Require `ArtifactManifest.resolved_spec` to equal the producer
      `ResolvedStageRef.resolved_spec`.
    - Retrieve and verify the artifact before the consumer stage executes.

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
    - Reject modified tracked files and untracked files in the execution
      checkout before input materialization.

  - [ ] **15.11. Orchestrate complete resolved-run verification.**
    - Implement one `verify_resolved_run()` entry point that performs checks
      15.1 through 15.10 in dependency order.
    - Select the successful attempt and verify every file referenced by that
      attempt.
    - Raise `VerificationError` on the first broken reference or relationship.
    - Return successfully only after the complete provenance chain passes.
    - Exercise this entry point through the two end-to-end tests in Step 22;
      do not add a separate mocked orchestration test.

- [ ] **16.** Point package exports at the authoritative model module.
- [ ] **17.** Update YAML loading and exact-byte serialization.
- [ ] **18.** Build one complete Stage 1 dummy provenance tree.
- [ ] **19. Add and remove the specified Stage 1 tests.**

  Add exactly these tests:

  1. [ ] `test_future_input_resolves_producer_manifest_and_artifact_bytes`
  2. [ ] `test_future_input_rejects_nonproducer_manifest`
  3. [ ] `test_measurement_file_returns_valid_measurements`
  4. [ ] `test_measurement_file_rejects_mismatched_coordinates`, implemented as
     one table-driven test covering run, attempt, stage, and metric IDs
  5. [ ] `test_source_checkout_accepts_exact_clean_commit`
  6. [ ] `test_source_checkout_rejects_modified_tracked_source`
  7. [ ] `test_complete_dummy_run_passes_full_verification`
  8. [ ] `test_complete_verifier_rejects_tampered_referenced_file`


- [ ] **20.** Rewrite the README from the implemented and tested protocol.
- [ ] **21.** Remove legacy package wiring and tracked Python cache files.
- [ ] **22. Run the Stage 1 end-to-end completion gate.**
  - Compile the authoritative protocol modules.
  - Generate the Pydantic schemas.
  - Execute the complete deterministic dummy run.
  - Verify its complete provenance chain using `verify_resolved_run()`.
  - Verify that one deliberately tampered referenced file causes
    `verify_resolved_run()` to fail.
  - Run the complete test suite in the `mantra` Conda environment.

### MANTRA model integration

- [ ] **23. Bind experiment variants to the concrete MANTRA stage parameters.**
  - Define the complete typed parameter classes for the MANTRA build, embed,
    and train stages.
  - Define the exact stage parameter field and value represented by every
    `(factor_id, level_id)` pair used by a MANTRA experiment.
  - Implement a model-specific validation function that compares the selected
    `VariantSpec.levels` with the corresponding fields in the run's stage
    specs.
  - Run that validation before publishing the run plan.
  - Reject a run plan when its stage parameters do not implement the selected
    variant.
  - Test one matching variant and run plan and one deliberate
    variant-to-stage-parameter mismatch.

The dummy end-to-end run must exercise this complete chain:

```text
run plan and stage specs
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

- The benchmark definition.
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
