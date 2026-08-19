# MANTRA Provenance Protocol — Stage 1, Version 2

Status: draft for iterative review

## 1. Scope

This document defines the Stage 1 contract for artifacts produced by one stage
execution. It fixes:

1. The boundary between one artifact and multiple artifacts.
2. The physical representation of one artifact as one file or a file bundle.
3. The artifact records carried by a stage spec, resolved stage spec, manifest,
   completed-stage reference, and downstream input.
4. The equalities verified across those records.
5. The publication and parity rules for the resulting files.

The current Stage 1 specification remains in `ProvenanceS1.md`. This draft is
the review surface for the version 2 contract. After this contract is frozen,
its changes will be mapped onto the current specification section by section.

---

## 2. Terms

### Stage

A stage is one execution of the command recorded by a stage spec.

### Artifact

An artifact is one named, durable computational value with one selection,
consumption, promotion, replacement, and parity lifecycle.

Examples:

- A trained model.
- A perturbation-embedding matrix.
- A reusable prior.
- A prediction matrix retained for downstream use.
- A resumable training checkpoint.

### Artifact file

An artifact file is one artifact represented by exactly one physical file.

```text
artifact: perturbation_embeddings
└── perturbation_embeddings.pt
```

### Artifact bundle

An artifact bundle is one artifact represented by at least two physical files
that must be selected, materialized, consumed, promoted, and parity-checked
together.

```text
artifact: model
├── model.pt
└── config.pkl
```

Each bundle member has a repository-relative path beneath the bundle root. A
bundle manifest identifies the complete member set.

### Artifact boundary

Two durable values are separate artifacts when either value has an independent
lifecycle:

- A downstream stage may consume either value independently.
- Promotion may select either value independently.
- Replacement may update either value independently.
- A reproducibility policy may parity-check either value independently.

Multiple files form one bundle when all of the following hold:

- The files collectively implement one named value.
- A consumer requires the complete file set.
- One manifest selects the complete file set.
- Partial materialization is invalid.
- Promotion and parity apply to the complete file set.

The stage command defines one execution. Artifact names define the durable
values produced by that execution. Bundle membership defines the physical files
required to represent one durable value.

---

## 3. Core invariant

Every successfully completed Stage 1 stage declares a nonempty set of uniquely
named artifacts before execution. Each artifact is independently selectable and
is represented by either:

1. Exactly one file; or
2. One bundle containing at least two files that share one consumption,
   promotion, and parity lifecycle.

The stage spec, resolved stage spec, and completed-stage reference contain
exactly the same artifact names. Each artifact name maps to exactly one
manifest. Each manifest maps to the same resolved stage execution and the exact
artifact produced by that execution.

A stage is accepted after:

1. Every declared artifact has been published.
2. Every declared artifact has been verified.
3. Every artifact manifest has been published and verified.
4. Every retained stage-created file has been classified as an artifact member,
   measurement file, log file, or protocol record.

---

## 4. Identifiers and artifact declarations

```python
ArtifactName = HumanId
```

`ArtifactName` identifies one durable value within a stage.

### Single-file declaration

```python
class ArtifactFileSpec(ProtocolModel):
    kind: Literal["file"] = "file"
    path: RepoRelPath
```

`path` is the canonical local and mirrored remote path of the artifact file.

### Bundle declaration

```python
class ArtifactBundleSpec(ProtocolModel):
    kind: Literal["bundle"] = "bundle"
    path: RepoRelPath
```

`path` is the canonical local and mirrored remote root of the artifact bundle.

### Declaration union

```python
ArtifactSpec = Annotated[
    ArtifactFileSpec | ArtifactBundleSpec,
    Field(discriminator="kind"),
]
```

### Stage declaration

```python
class BaseSpec(ProtocolModel):
    artifacts: dict[ArtifactName, ArtifactSpec] = Field(min_length=1)
```

Example:

```yaml
artifacts:
  model:
    kind: bundle
    path: artifacts/model

  perturbation_embeddings:
    kind: file
    path: artifacts/perturbation_embeddings.pt
```

The example declares two artifacts. `model` is one bundle artifact.
`perturbation_embeddings` is one file artifact.

---

## 5. Resolved artifacts

### Resolved file artifact

```python
class ResolvedArtifactFile(ProtocolModel):
    kind: Literal["file"] = "file"
    file: ResolvedFileRef
```

`file` records the exact artifact bytes through:

- `ResolvedFileRef.sha256`.
- `ResolvedFileRef.bytes`.
- `ResolvedFileRef.stored_at`.

### Resolved bundle member

```python
class ResolvedArtifactBundleMember(ProtocolModel):
    relative_path: RepoRelPath
    file: ResolvedFileRef
```

`relative_path` identifies one member beneath the bundle root declared by
`ArtifactBundleSpec.path`. `file` records that member's exact bytes and storage
location.

### Resolved bundle artifact

```python
class ResolvedArtifactBundle(ProtocolModel):
    kind: Literal["bundle"] = "bundle"
    members: tuple[ResolvedArtifactBundleMember, ...] = Field(min_length=2)
```

The two-member minimum gives `file` and `bundle` disjoint physical meanings:

```text
one physical file       → ResolvedArtifactFile
two or more files       → ResolvedArtifactBundle
```

### Resolved artifact union

```python
ResolvedArtifact = Annotated[
    ResolvedArtifactFile | ResolvedArtifactBundle,
    Field(discriminator="kind"),
]
```

### Resolved stage spec

```python
class ResolvedBaseSpec(ProtocolModel):
    spec: BaseSpec
    artifacts: dict[ArtifactName, ResolvedArtifact] = Field(min_length=1)
```

Concrete resolved stage-spec classes retain their existing source,
environment, execution-context, command, input, and completion fields.

---

## 6. Artifact manifest

Each named artifact receives one manifest.

```python
class ArtifactManifest(ProtocolModel):
    schema_version: Literal[1] = 1

    artifact_name: ArtifactName
    artifact: ResolvedArtifact
    resolved_spec: ResolvedFileRef
    spec: ResolvedFileRef
    source: ResolvedGitFileRef

    created_at: AwareDatetime
```

The manifest binds:

```text
artifact name
├── exact file or bundle
├── stage spec that declared the artifact
├── resolved stage spec that recorded the completed execution
└── source entry point used by that execution
```

For a bundle, `ArtifactManifest.artifact` contains the complete member
inventory. The verifier establishes member-path uniqueness independently of
tuple order. Canonical serialization sorts members by `relative_path`.

---

## 7. Completed-stage reference

```python
class ResolvedStageRef(ProtocolModel):
    stage_id: StageId
    resolved_spec: ResolvedFileRef
    artifacts: dict[
        ArtifactName,
        ResolvedArtifactManifestRef,
    ] = Field(min_length=1)
```

One `ResolvedStageRef` binds the completed stage to:

```text
ResolvedStageRef
├── stage_id
├── resolved_spec
└── artifacts
    ├── artifact_name_a → manifest reference
    └── artifact_name_b → manifest reference
```

Each dictionary value identifies the exact manifest file for that artifact
name. Loading the manifest reaches the exact file or bundle.

---

## 8. Cross-record contracts

For one successfully completed stage `S`, define:

```text
D(S) = set(ResolvedBaseSpec.spec.artifacts)
R(S) = set(ResolvedBaseSpec.artifacts)
M(S) = set(ResolvedStageRef.artifacts)
```

The artifact-name sets satisfy:

```text
D(S) == R(S) == M(S)
D(S) != ∅
```

For every `artifact_name` in that set:

```text
ResolvedStageRef.artifacts[artifact_name]
→ retrieve and verify manifest bytes
→ parse ArtifactManifest
```

The loaded records satisfy:

```text
ArtifactManifest.artifact_name
==
artifact_name
```

```text
ArtifactManifest.artifact
==
ResolvedBaseSpec.artifacts[artifact_name]
```

```text
ArtifactManifest.resolved_spec
==
ResolvedStageRef.resolved_spec
```

```text
ArtifactManifest.source
==
ResolvedBaseSpec.source
```

The verifier retrieves `ArtifactManifest.spec`, parses the stage spec, and
requires:

```text
loaded ArtifactManifest.spec
==
ResolvedBaseSpec.spec
```

---

## 9. Path contracts

### File artifact

For an artifact declared as `ArtifactFileSpec`:

```text
ResolvedArtifactFile.file.stored_at.path
==
ArtifactFileSpec.path
```

### Bundle artifact

For each member of an artifact declared as `ArtifactBundleSpec`:

```text
ResolvedArtifactBundleMember.file.stored_at.path
==
ArtifactBundleSpec.path
/
ResolvedArtifactBundleMember.relative_path
```

Bundle requirements:

1. `members` contains at least two records.
2. Every `relative_path` is unique within the bundle.
3. Every member is a regular file.
4. Every member path remains beneath `ArtifactBundleSpec.path`.
5. Every retained artifact file beneath the bundle root appears exactly once in
   `members`.

Stage-level path requirements:

1. Artifact declaration paths are pairwise non-overlapping.
2. Two artifact names cannot claim the same stored file path.
3. Distinct paths may contain identical bytes and therefore the same SHA-256.

Valid roots:

```text
artifacts/model
artifacts/perturbation_embeddings.pt
```

Overlapping roots:

```text
artifacts/model
artifacts/model/embeddings
```

---

## 10. Same-run future inputs

A future input identifies both the producing stage and the named artifact it
will consume.

```python
class FutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    producer_stage_id: StageId
    producer_artifact: ArtifactName
```

Example:

```yaml
inputs:
  embeddings:
    kind: future
    producer_stage_id: train
    producer_artifact: perturbation_embeddings
```

The resolved input records the exact manifest consumed:

```python
class ResolvedFutureInputRef(ProtocolModel):
    kind: Literal["future"] = "future"
    manifest: ResolvedArtifactManifestRef
```

The verifier traverses:

```text
FutureInputRef.producer_stage_id
→ producer ResolvedStageRef

FutureInputRef.producer_artifact
→ producer ResolvedStageRef.artifacts[producer_artifact]
```

The requested and resolved input records satisfy:

```text
ResolvedFutureInputRef.manifest
==
producer ResolvedStageRef.artifacts[
    FutureInputRef.producer_artifact
]
```

The loaded manifest then satisfies:

```text
ArtifactManifest.artifact_name
==
FutureInputRef.producer_artifact
```

```text
ArtifactManifest.resolved_spec
==
producer ResolvedStageRef.resolved_spec
```

```text
ArtifactManifest.artifact
==
producer ResolvedBaseSpec.artifacts[
    FutureInputRef.producer_artifact
]
```

The executor materializes:

- A file artifact at its canonical file path.
- Every bundle member beneath its canonical bundle root.

---

## 11. Stored inputs and promotion pointers

`ArtifactPointer` continues to select one artifact manifest:

```python
class ArtifactPointer(ProtocolModel):
    schema_version: Literal[1] = 1
    manifest: ResolvedArtifactManifestRef
```

The pointer traversal remains:

```text
StoredInputRef.pointer
→ ArtifactPointer.manifest
→ ArtifactManifest.artifact
→ ResolvedArtifactFile | ResolvedArtifactBundle
```

For a file artifact, `StoredInputRef.path` is the local file path supplied to
the consuming stage.

For a bundle artifact, `StoredInputRef.path` is the local bundle root. The
executor places each member at:

```text
StoredInputRef.path
/
ResolvedArtifactBundleMember.relative_path
```

The pointer selects the complete artifact. A pointer to a bundle therefore
selects every member recorded by the bundle manifest.

---

## 12. Retained-file classification

Every file retained as part of successful stage completion belongs to exactly
one protocol role:

1. A member of one named artifact.
2. A measurement file.
3. A log file.
4. A protocol record.

The executor removes stage-local temporary files from the accepted workspace
state.

A tensor or other computational value receives an artifact name when any of the
following apply:

1. The value crosses a stage or run boundary.
2. A downstream operation consumes the value independently.
3. Promotion or selection targets the value independently.
4. A reproducibility policy names the value as parity evidence.
5. Exact continuation requires the value.
6. The value affects a promised output and cannot be reconstructed exactly from
   the recorded inputs and execution contract.

A tensor remains stage-local when all of the following hold:

1. Its lifetime ends within the stage execution.
2. The recorded stage execution reconstructs it exactly when required.
3. No downstream operation consumes it directly.
4. No promotion, parity, or continuation contract names it.

---

## 13. Publication contract

For one successful stage:

```text
Commit C — artifact bytes
├── artifact_name_a
│   └── file or complete bundle member set
└── artifact_name_b
    └── file or complete bundle member set

Commit D — resolved stage spec
└── ResolvedBaseSpec.artifacts
    ├── artifact_name_a → exact resolved artifact
    └── artifact_name_b → exact resolved artifact

Commit E — artifact manifests
├── artifact_name_a.manifest.yaml
└── artifact_name_b.manifest.yaml

ResolvedStageRef
├── resolved_spec → commit D
└── artifacts
    ├── artifact_name_a → manifest at commit E
    └── artifact_name_b → manifest at commit E
```

Publication sequence:

1. Execute the stage command.
2. Classify every retained stage-created file.
3. Calculate the SHA-256 and byte count of every artifact file and bundle
   member.
4. Publish all artifact bytes at commit C.
5. Construct and publish the resolved stage spec at commit D.
6. Construct one manifest per artifact name.
7. Publish all artifact manifests at commit E.
8. Retrieve and verify commits C, D, and E.
9. Construct `ResolvedStageRef` from the verified resolved-spec and manifest
   references.
10. Attach `ResolvedStageRef` to the current `RunAttempt`.

All artifact files produced by the stage share commit C. All artifact manifests
produced by the stage share commit E.

An interrupted stage retains operational failure evidence through its attempt
record. A completed `ResolvedStageRef` represents a stage whose complete
declared artifact set passed the publication and verification sequence.

---

## 14. Artifact parity

### File artifact fingerprint

```text
(
    kind = "file",
    sha256,
    bytes,
)
```

### Bundle artifact fingerprint

```text
(
    kind = "bundle",
    sorted(
        (
            member.relative_path,
            member.file.sha256,
            member.file.bytes,
        )
        for member in members
    ),
)
```

### Stage parity

Two stage executions have artifact parity when:

1. Their artifact-name sets are equal.
2. The artifact kind is equal for every artifact name.
3. The artifact fingerprint is equal for every artifact name.

Repository, storage path, and storage commit identify where verified bytes are
retrieved. Artifact parity is calculated from artifact kind, member identity,
SHA-256, and byte count.

---

## 15. Reference-model probes

The contract produces the following classifications:

| Durable result | Artifact classification |
|---|---|
| One checkpoint file | One `ResolvedArtifactFile` |
| `model.pt` plus required `config.pkl` | One `ResolvedArtifactBundle` named `model` |
| Sharded checkpoint plus index | One `ResolvedArtifactBundle` |
| Model plus independently reusable embeddings | Two named artifacts |
| Shared trunk plus independently deployable heads | One artifact per independently consumed component |
| Best inference model plus resumable training state | Two named artifacts |
| Persisted prediction matrix | Separate named artifact |
| Loss or correlation values | Measurements |
| Forward-pass activations used only inside the stage | Stage-local values |
| Persisted activation trace used as parity evidence | Named artifact |

The model-plus-embeddings case resolves as:

```text
train stage
├── artifact: model
│   └── file or bundle
└── artifact: perturbation_embeddings
    └── file or bundle
```

The `model` and `perturbation_embeddings` values have separate manifest,
consumption, promotion, replacement, and parity lifecycles.

---

## 16. Review sequence

The version 2 review proceeds in this order:

1. Freeze the artifact definitions and boundary.
2. Freeze the class names and field shapes.
3. Freeze the cross-record equalities.
4. Freeze path, publication, and parity rules.
5. Probe additional real model-output layouts.
6. Map the frozen contract onto each affected section of `ProvenanceS1.md`.
7. Map the frozen contract onto `models_v4.py`, `verifier.py`, and focused
   tests.
