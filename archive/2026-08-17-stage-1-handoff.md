# MANTRA Provenance Stage 1 Handoff — 2026-08-17

> Historical handoff: this document records the implementation state on
> 2026-08-17. The active contract is
> [ProvenanceS1_v3.md](../docs/ProvenanceS1_v3.md), and the active package interface
> is documented in the [package README](../README.md). The manifest-based steps
> below belong to the earlier contract recorded here.

## Current position

Stage 1 external verification is complete through Step 15.5. The next task is
Step 15.6, stored-input verification. The authoritative checklist is in the
[Stage 1 protocol](ProvenanceS1.md#deterministic-dummy-data-completion-pass).

## Completed today

Today's work began at Step 11 and completed Steps 11 through 14 plus external
verifier Steps 15.1 through 15.5.

### Step 11 — metrics and measurements

- Wrote the first two PyTorch metric functions:
  - [`compute()`](../examples/project/src/example_project/metrics/training/mean_squared_error/compute.py), which validates compatible real
    tensors and returns mean squared error;
  - [`compute()`](../examples/project/src/example_project/metrics/evaluation/pearson_correlation/compute.py), which computes
    Pearson correlation along a selected tensor dimension using float64
    arithmetic and rejects constant comparison vectors.
- Added `Measurement`, including run, attempt, stage, and metric IDs; a finite
  numeric value; timestamp; and optional epoch and step.
- Added experiment-scoped metric IDs without introducing separate objective,
  statistic, similarity, or distance-function record types.
- Added acceptance, rejection, JSON, and YAML round-trip tests.

### Step 12 — experiments and variants

- Added `FactorSpec`, `ReplicateSpec`, `ExperimentSpec`, and `VariantSpec`.
- Represented each variant as one explicit assignment of levels to the
  experiment's factors rather than generating a Cartesian product.
- Added validators and tests for duplicate factor, variant, replicate, and
  metric IDs.
- Added external checks that load experiment and variant files from their
  deterministic paths at the run's source commit, validate the selected factor
  levels, and match the run's replicate and seed.

### Step 13 — runs and attempts

- Added the run plan and attempt models.
- Replaced `CompletedStageRef` with `ResolvedStageRef` and renamed the attempt
  field from `completed_stages` to `resolved_stages`.
- Replaced the misleading `StageSpec` run-plan entry with `RunStageRef`.
  `RunStageRef` records the stage ID, stage-spec path, SHA-256, and byte
  count.
- Added run-plan validators for nonempty stages, unique stage IDs, and unique
  stage-spec paths.
- Added attempt validators for terminal status, timestamps, resolved-stage
  uniqueness, and failure-reason consistency.

### Step 14 — resolved runs

- Added `ResolvedRun` and its local validators.
- Enforced exactly one successful attempt for a successful run and no
  successful attempt for a failed or cancelled run.
- Required the successful attempt to resolve every declared stage in order.
- Required attempt IDs to be unique and strictly increasing in execution order.
- Prevented attempts from overlapping or following a successful attempt.
- Required `ResolvedRun.completed_at` not to precede an attempt's completion.

### Step 15.1 — referenced-file retrieval and verification

- Added immutable Git and Hugging Face retrieval backends.
- Added shared SHA-256 and byte-count verification for retrieved files.
- Made `ResolvedGitFileRef` inherit from `ResolvedFileRef` and restrict
  `stored_at` to `GitFileRef`, so Git-resident verified files use the same
  `sha256`, `bytes`, and `stored_at` structure as other verified files.

### Step 15.2 — resolved run file

- Added verification that retrieves `ResolvedRun.run_file`, parses it as
  `RunSpec`, and requires it to equal the `RunSpec` embedded in `ResolvedRun`.

### Step 15.3 — experiment and variant

- Added verification of the run's experiment, variant, factor-level
  assignment, replicate, and seed against the exact source snapshot.

### Step 15.4 — stage plan

- Separated the two immutable snapshots used by a run:

  ```text
  source snapshot
  └── source code, experiment, variants, lockfile, and input pointers

  run-plan snapshot
  └── run.yaml and generated stage specs
  ```

- Changed stage verification to retrieve stage specs from the
  snapshot identified by `ResolvedRun.run_file.stored_at`, rather than from the
  earlier source commit.
- Added stage-file SHA-256 and byte-count verification before parsing.
- Added checks for stage order, same-run future-input ordering, unique output
  paths, and local path collisions.

### Step 15.5 — resolved stages

- Implemented [`verify_resolved_stages()`](../viper/verifier.py), which:
  - identifies the successful attempt;
  - checks resolved-stage order against the run plan;
  - retrieves and validates each resolved-stage document;
  - compares its embedded spec with the loaded run-plan spec;
  - checks its source repository and commit against `RunSpec.source`;
  - checks that stage completion occurred inside the successful attempt; and
  - retrieves and verifies the source entry point, lockfile, and output bytes.
- Updated the [Stage 1 protocol](ProvenanceS1.md) to match the implemented
  class names, snapshot boundary, validators, verifier behavior, and checklist
  status.
- Added focused model and verifier tests in
  [`test_records.py`](../tests/test_records.py) and
  [`test_verifier.py`](../tests/test_verifier.py).

## Decisions that remain fixed

- A resolved-stage document does not duplicate run, attempt, or stage IDs.
  `ResolvedStageRef` binds a `stage_id` to the exact resolved-stage file, while
  the containing `RunAttempt` and `ResolvedRun` supply attempt and run identity.
- `RunSpec.source` identifies the source snapshot.
- `ResolvedRun.run_file.stored_at` identifies the run-plan snapshot.
- `RunStageRef` verifies each stage-spec file without making `run.yaml`
  refer to the commit that contains itself.
- Pydantic validators inspect facts present in one loaded object. Retrieval,
  hashing, parsing, and comparisons across files remain in the external
  verifier.

## Validation recorded today

The following checks passed in the `mantra` Conda environment:

```text
Python compilation: passed
Pydantic schema generation: passed
Tests: 74 passed, 51 subtests passed
git diff --check: passed
```

## Tomorrow: immediate work

### Step 15.6 — verify stored inputs

Implement stored-input traversal in the external verifier:

1. For every `StoredInputRef`, retrieve its Git-tracked pointer file.
2. Verify the resolved pointer file's SHA-256 and byte count.
3. Parse the file as `ArtifactPointer`.
4. Require the resolved pointer location to equal the spec
   `ArtifactPointerRef` location.
5. Retrieve and verify the `ResolvedArtifactManifestRef` selected by the
   pointer.
6. Parse it as `ArtifactManifest`.
7. Retrieve the artifact selected by `manifest.artifact`.
8. Verify the artifact's SHA-256 and byte count.
9. Return the verified artifact reference and bytes needed to materialize the
   input at the specified local `path`.

Add rejection tests for:

- Pointer location differing from the spec pointer.
- Pointer-file SHA-256 or byte-count mismatch.
- Invalid pointer schema.
- Manifest SHA-256 or byte-count mismatch.
- Invalid manifest schema.
- Artifact SHA-256 or byte-count mismatch.
- Stored-input name or kind disagreement between specs and resolved specs.

### Then

- Step 15.7: verify same-run `FutureInputRef` dependencies.
- Step 15.8: verify artifact manifests against producing resolved stages.
- Continue Steps 15.9 onward in checklist order.
- Defer package exports, YAML adapters, fixture replacement, README migration,
  and legacy cleanup until the external verifier is complete.

## Restart commands

Run these after tomorrow's changes:

```bash
PYTHONDONTWRITEBYTECODE=1 conda run -n mantra python -m py_compile \
  viper/records.py viper/verifier.py

PYTHONDONTWRITEBYTECODE=1 conda run -n mantra python -m pytest -q

git diff --check
```

## Files changed in today's implementation

- [`records.py`](../viper/records.py)
- [`verifier.py`](../viper/verifier.py)
- [`ProvenanceS1.md`](ProvenanceS1.md)
- [`test_records.py`](../tests/test_records.py)
- [`test_verifier.py`](../tests/test_verifier.py)
