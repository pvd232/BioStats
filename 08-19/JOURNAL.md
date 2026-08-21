# MANTRA End-of-Day Journal — 2026-08-19

## Current position

The current Stage 1 implementation is complete through external-verifier Step
15.7. Step 15.8, same-run future-input verification, has implementation work in
progress and remains unchecked in the authoritative Stage 1 checklist.

The version 2 provenance contract now derives stage, artifact, and file
boundaries from one reproducibility objective using completeness and parsimony.
The v2 contract remains under review. Its model and verifier changes have not
been applied to `models_v4.py` or `verifier.py`.

## Completed today

### External verifier

- Implemented and tested artifact-manifest verification before the input
  verifiers that depend on it.
- Implemented stored-input traversal:
  - retrieve and verify the Git-tracked artifact pointer;
  - parse `ArtifactPointer`;
  - follow `ArtifactPointer.manifest`;
  - verify the complete manifest chain and artifact bytes; and
  - return the exact bytes and local materialization path.
- Reordered Steps 15.6 through 15.8 around their actual dependency:

  ```text
  verify artifact manifest
  → verify stored input
  → verify same-run future input
  ```

- Added shared YAML-byte construction for typed tests and removed repeated
  `yaml.safe_dump(...).encode(...)` typing failures.
- Added concise comments and focused test records explaining pointer, manifest,
  artifact, spec, resolved-spec, and source traversal.
- Kept the future-input test target narrow: one successful producer binding and
  one rejection for a nonproducer manifest.

### Model and verifier documentation

- Removed `authored` terminology from the active Stage 1 contract and aligned
  stage-spec terminology across models, verifier code, tests, and documentation.
- Clarified the two immutable snapshots:

  ```text
  source commit A
  └── source, experiment, variant, metric code, lockfile, input pointers

  run-plan commit B
  └── run.yaml and concrete stage specs
  ```

- Clarified the artifact publication sequence through artifact bytes, resolved
  stage spec, artifact manifest, and completed-stage reference.
- Reworked the external data root so `RemoteFileRef` remains a retrieval
  location and the download output becomes MANTRA's first byte-identified
  artifact.
- Reworked source-identity documentation around exact record traversal and
  equalities.
- Added project-scoped Pyright configuration and targeted suppressions for
  intentional Pydantic field narrowing.

### Version 2 artifact contract

- Created `ProvenanceS1_v2.md` as a separate review surface.
- Generalized a stage from one output file to a named artifact mapping.
- Defined one artifact as a durable value represented by either:
  - one `ResolvedArtifactFile`; or
  - one `ResolvedArtifactBundle` containing at least two members.
- Coupled each completed stage with its resolved spec and named artifact-manifest
  mapping through the proposed `ResolvedStageRef.artifacts` field.
- Added `FutureInputRef.producer_artifact` so a same-run consumer identifies the
  exact producer artifact.
- Preserved promoted-input selection through `ArtifactPointer →
  ArtifactManifest → ResolvedArtifact`.

### Foundational reproducibility contract

- Distinguished model selection from provenance partitioning:

  ```text
  benchmark requirements
  → select fixed computation P*

  reproducibility objective R
  → partition P* for replay and verification
  ```

- Defined the reproducibility objective from:
  - the fixed computation `P*`;
  - complete replay state `Ω₀`;
  - final estimator `W`;
  - exact parity relation; and
  - ordered replay roots `B_R`.
- Applied the same completeness-parsimony rule at three levels:

  ```text
  fewest complete stages
  → fewest complete artifacts per replay state
  → fewest complete files per artifact under its fixed loader
  ```

- Derived the stage partition from required replay roots.
- Derived the artifact partition from the replay and parity claims attached to
  each replay state.
- Defined file, artifact, replay-state, and final-estimator parity.
- Added the compositional replay proof from `Ω₀′ ≡ Ω₀` through `W′ ≡ W`.
- Added the induced minimal contract:

  ```text
  no intermediate replay roots
  → one stage
  → one final-estimator artifact
  → one file or one minimal complete bundle
  → exact SHA-256 and byte-count parity
  ```

## Notable decisions

1. **The reproducibility objective is the external root.** It states the fixed
   replay state, final estimator, parity relation, and intermediate replay
   roots.
2. **Completeness and parsimony derive the boundaries.** Stage and artifact
   counts are consequences of the objective.
3. **Replay roots force stage boundaries.** An internal tensor becomes a replay
   root when the objective promises independent replay beginning from that
   state.
4. **Artifact mappings represent replay states.** Artifact parity over the
   complete mapping establishes the input-state parity required by the next
   stage.
5. **The loading contract fixes an artifact's representation space.** File
   parsimony selects the minimal complete member set within that fixed loader.
6. **Model performance selects the computation.** Reproducibility partitions
   the selected computation.
7. **The v2 schema migration waits for contract freeze.** This protects the
   verifier implementation from another structural rewrite during conceptual
   review.

## Validation recorded today

The following checks passed in the `mantra` Conda environment after the v2
rewrite:

```text
Python compilation: passed
Tests: 82 passed, 51 subtests passed
git diff --check: passed
KaTeX display-equation validation: 44 passed
Markdown code fences: 92, balanced
Display-math fences: 88, forming 44 balanced pairs
```

## Tomorrow: immediate work

### 1. Freeze the v2 foundation

Review `ProvenanceS1_v2.md` in order:

1. Scope and fixed model-building computation.
2. Reproducibility objective and replay roots.
3. Unified completeness-parsimony rule.
4. Stage, artifact, and file derivations.
5. Parity and compositional replay proof.
6. Minimal-contract example and protocol hierarchy.

Done condition: Sections 1 through 10 contain agreed terminology, axioms,
derivations, and diagrams with no unresolved boundary question.

### 2. Freeze the v2 record contract

Review Sections 11 through 20 against real estimator layouts:

- one-file estimator;
- estimator bundle;
- sharded checkpoint;
- atomic continuation checkpoint;
- independently replayed embedding;
- multiple independently replayed outputs.

Done condition: class names, field shapes, equalities, paths, and publication
rules cover every accepted probe without special-case ambiguity.

### 3. Map the frozen contract to the implementation

Write the exact propagation checklist for:

1. `ArtifactName`, `ArtifactSpec`, and `ResolvedArtifact`.
2. `BaseSpec.artifacts` and `ResolvedBaseSpec.artifacts`.
3. `ArtifactManifest.artifact_name` and generalized artifact payload.
4. `ResolvedStageRef.artifacts` and removal of the parallel attempt-level
   manifest inventory.
5. `FutureInputRef.producer_artifact`.
6. Verifier traversal and the two focused future-input tests.

Done condition: every code and test edit has one named target and one governing
v2 invariant before implementation begins.

## Not tomorrow

- Benchmark and diagnostic schema implementation.
- Real training-data download and live pipeline execution.
- README migration.
- Legacy package removal.
- Broad test expansion beyond the focused invariants required by the frozen v2
  contract.

## Shutdown handoff

The v2 foundation has been rewritten and mechanically validated. The current
implementation remains green through Step 15.7. Step 15.8 and the multi-artifact
code migration remain intentionally pending behind the v2 contract freeze.

Tomorrow's first action is to open
[`ProvenanceS1_v2.md`](../mantra_provenance/ProvenanceS1_v2.md) at Section 1 and
review Sections 1 through 4 line by line before changing code.

## Key files

- [`ProvenanceS1_v2.md`](../mantra_provenance/ProvenanceS1_v2.md)
- [`ProvenanceS1.md`](../mantra_provenance/ProvenanceS1.md)
- [`models_v4.py`](../mantra_provenance/models_v4.py)
- [`verifier.py`](../mantra_provenance/verifier.py)
- [`test_models_v4.py`](../tests/test_models_v4.py)
- [`test_verifier.py`](../tests/test_verifier.py)

---

## Late-session continuation

The August 19 workday continued through approximately 4 a.m. on August 20. The
following work belongs to the August 19 journal.

### Formal foundation

The formal argument was rebuilt from the standard estimator construction:

```text
family design α
→ parameter space Θ_α
→ parameter-to-function map I_α
→ function family G_α

estimator specification β
+ dataset D
→ fitted parameters θ̂
→ fitted function ĝ
```

The run plan $q$ now fixes $\alpha$, $\beta$, and $D_q$ and induces the
nonempty set of permitted runtime states $E_q$. Strict parameter
reproducibility is:

$$
\forall e,e'\in E_q,
\qquad
T_{\alpha,\beta,q}(e)
=
T_{\alpha,\beta,q}(e').
$$

The separate reproducibility-objective symbol $\mathcal R$ was removed from
the target formulation. The run plan and its permitted runtime states express
the required condition directly.

### Induced partitions

The target contract now connects the plan to its physical records through:

```text
q
→ E_q
→ strict parameter reproducibility
→ Π(q)
→ A(s)
→ F_s(a)
→ exact file identity
```

Each completed stage may produce one or more named artifacts. Each artifact is
represented by one physical file or a bundle of at least two jointly required
files. Independently consumed or promoted values receive separate artifact
names.

### Requested, realized, and verified state

The schema roles were fixed as:

```text
Spec
→ declares requested state and induces E_q

Resolved
→ records realized state e

Verifier
→ checks e ∈ E_q
→ verifies recorded file identities and cross-record relationships
```

`Ref` identifies another stored object. `ArtifactPointer` is a stored promotion
record selecting one artifact from one terminal run.

### Runtime controls

The following relationships were accepted:

```text
selected ReplicateSpec.seed
== RunSpec.seed
== every stage ReproducibilitySpec.randomness.seed
```

```text
GCEEnvironmentSpec
→ requested provisioning

ReproducibilitySpec
→ requested numerical controls

ExecutionContext
→ observed runtime values

external verifier
→ checks that the observed values satisfy both requests
```

The canonical stage command is derived from the Python executable, stage
script, and concrete stage-spec path. Typed variant parameters connect each
declared factor level to the exact stage parameters that implement it.

### Stage-result snapshots and promotion

The target v2 design removed artifact manifests and consolidated each completed
stage into one stage-result snapshot:

```text
stage-result snapshot C_s
├── resolved stage spec
└── every physical file for every named stage artifact
```

Same-run inputs select a producer stage ID and artifact name. Promoted inputs
use:

```text
ArtifactPointer
├── run: ResolvedRunRef
└── artifact: StageArtifactRef
    ├── stage_id
    └── artifact_name
```

This traversal reaches the successful attempt, producing stage, exact artifact
files, run plan, source, and upstream inputs.

### Publication sequence

| Commit | Repository | Contents |
|---|---|---|
| A | Git | Source, experiment, variants, metrics, lockfile, and promoted-input pointers |
| B | Git | `RunSpec` and every concrete stage spec |
| $C_s$ | Artifact repository | One completed stage's resolved spec and artifact files |
| $D_i$ | Artifact repository | Closed measurement and log files for attempt $i$ |
| E | Artifact repository | Terminal `ResolvedRun` |
| F | Git, optional | New promotion pointers |

### External dataset identity

The source dataset is denoted $D_0$. The run plan fixes the dataset selection
and construction procedure $S_q$, producing:

$$
D_q=S_q(D_0).
$$

The procedure may fix the source dataset release, cell-quality filters,
selected perturbations, highly variable genes, and pseudobulk construction.
Exact bytes acquired from an external URL become a published MANTRA artifact
before a later training run treats them as fixed input.

### Remaining foundation decisions

1. Define the artifact loading contract that establishes physical
   completeness and reconstruction from $F_s(a)$.
2. State parsimony as a design objective and define the local anti-redundancy
   conditions enforced by the schema and verifier.
3. Finish the exact v2 class and field shapes before migrating implementation.

### Validation

The v1 implementation remained green:

```text
82 tests passed
51 subtests passed
```

The v2 document passed Markdown-fence, display-math, Python-block, Pandoc with
MathJax, and `git diff --check` validation during the session.
