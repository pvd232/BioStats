# MANTRA Workday Charter — 2026-08-20

## Day charter

Finish the Stage 1 provenance framework by freezing the v2 contract, migrating
the models and verifier, and passing one complete dummy provenance chain plus
one corrupted-chain rejection.

## Capacity

The completion path has a 7.5-hour execution budget and 1 hour of reserved
slack. Exact clock time and hard stops are unknown, so the plan uses elapsed
time. If less than 8.5 hours is available, stop at a block boundary and resume
from the next named block.

Current verified baseline:

```text
/Users/machina/miniconda3/envs/mantra/bin/python -m pytest -q
82 tests passed, 51 subtests passed in 0.56 seconds
```

## Execution plan

| Budget | Work block | Deliverable | Done condition |
|---:|---|---|---|
| 45 min | 1. Freeze the remaining v2 decisions | Final definitions for $D_q$, artifact reconstruction, and parsimony | [The v2 specification](../mantra_provenance/ProvenanceS1_v2.md) states $D_q=S_q(D_0)$; defines the artifact loading contract; distinguishes verifier-enforced validity from the parsimony design objective; and contains final class and field shapes |
| 2 hr | 2. Migrate the data model | One authoritative v2 Pydantic model graph | [`models_v4.py`](../mantra_provenance/models_v4.py), [`ids.py`](../mantra_provenance/ids.py), and [`yaml_io.py`](../mantra_provenance/yaml_io.py) compile; schemas generate; artifact manifests are absent; snapshot, multi-artifact, pointer, input, seed, variant-parameter, and run-reference relationships validate |
| 2.5 hr | 3. Migrate and finish the verifier | One `verify_resolved_run()` path implementing the v2 traversal | [`verifier.py`](../mantra_provenance/verifier.py) verifies the run plan, stage-result snapshots, artifacts, stored inputs, same-run inputs, measurements, source checkout, environment controls, command, seed chain, attempts, and selected estimator |
| 1.5 hr | 4. Build the minimum completion fixture | One deterministic dummy provenance tree and two acceptance tests | The fixture contains a promoted stored input, a same-run future input, multiple named artifacts including one bundle, a measurement, a successful attempt, and a terminal run; the full verifier accepts it; changing one referenced byte makes it fail |
| 45 min | 5. Close the package boundary | Importable package and final deterministic gate | Package exports and YAML loading use the v2 models; authoritative modules compile; Pydantic schemas generate; the complete focused suite passes |
| 1 hr | Reserved slack | Debugging, migration fallout, and short breaks | Used only for work required by Blocks 1–5 |

## Minimum testing policy

Keep existing tests that still exercise a live invariant without modification.
Remove or rewrite tests whose objects disappear from v2. Add only these two
acceptance tests:

1. `test_complete_dummy_run_passes_full_verification`
2. `test_complete_verifier_rejects_tampered_referenced_file`

The successful dummy chain must exercise the core branches directly:

```text
stored promoted input
+ same-run future input
+ single-file artifact
+ bundle artifact
+ measurement
+ terminal ResolvedRun
→ verify_resolved_run()
```

Do not add separate round-trip tests, constructor-success tests, orchestration
mocks, duplicate error-path matrices, or tests of Pydantic and PyYAML library
behavior. Add a focused rejection test only when the two acceptance tests cannot
exercise a protocol invariant.

## Replan rule

If the model migration is not complete after 2.5 hours, preserve the full v2
model and verifier scope, perform all remaining validation through the two
acceptance tests, and defer package prose, example-file refreshes, and legacy
cleanup to the next session.

## Not today

- Full README rewrite.
- Migration of every historical example and fixture.
- Broad negative-test coverage.
- Pyright cleanup that does not block execution.
- Legacy-file and cache cleanup.
- Cloud publication.
- Real training-data acquisition and live model execution.
- Performance measurement or optimization.

## Shutdown

Record:

1. the last completed block;
2. the exact failing command and first error, if any;
3. any contract decision still blocking implementation; and
4. the next file and symbol to change.

The framework-completion gate is:

```text
v2 contract frozen
+ authoritative modules compile
+ Pydantic schemas generate
+ complete dummy run verifies
+ one changed referenced file is rejected
= Stage 1 framework complete
```

## Proposed four-hour compression

### Day charter

Freeze the remaining v2 contract decisions and complete the v2 Pydantic model
migration to a compiling, schema-generating state.

### Capacity

The session has 4 hours: 3.5 hours of planned work and 30 minutes of reserved
slack. Every coding block uses the pair-vibe loop:

```text
Codex explains one bounded change
→ user applies it
→ user runs the named check
→ Codex inspects the result
→ choose the next bounded change
```

The original 1-hour buffer contains 30 minutes of removable slack. The other
30 minutes remains reserved for explanation, user editing, checks, inspection,
debugging, and short breaks. The original 45-minute package-close block can
move to the next session. Completing the verifier and end-to-end fixture also
moves to the next session; those blocks contain required implementation work,
not slack.

### Execution plan

| Elapsed time | Budget | Work block | Deliverable | Done condition |
|---:|---:|---|---|---|
| 0:00–0:30 | 30 min | 1. Freeze the remaining v2 decisions | Final definitions for $D_q$, artifact reconstruction, and the status of parsimony | [The v2 specification](../mantra_provenance/ProvenanceS1_v2.md) contains the agreed definitions and exact model shapes needed for implementation |
| 0:30–2:45 | 2 hr 15 min | 2. Pair-migrate the Pydantic model graph | Snapshot storage, named single-file and bundle artifacts, stage inputs and outputs, run records, pointers, seed authority, variant parameters, and environment controls represented by one coherent model graph | Each conceptual edit has been applied and inspected; obsolete manifest relationships are absent; the authoritative model modules compile |
| 2:45–3:30 | 45 min | 3. Close the model validation gate | Schemas and the smallest model-focused test surface agree with the migrated graph | Pydantic schemas generate and the focused model tests required to exercise the changed relationships pass |
| 3:30–4:00 | 30 min | Reserved slack | Pairing overhead, migration fallout, debugging, and short breaks | Used only to finish Blocks 1–3 |

### Replan rule

If the model modules do not compile by 3:15 elapsed, use the final 45 minutes
only to restore compilation and schema generation. Defer model-test migration
with the verifier work.

### Not in the four-hour session

- Verifier migration.
- Complete dummy provenance tree.
- End-to-end acceptance and tamper-rejection tests.
- Package export and YAML-loading closure beyond changes required by the model
  migration.
- Every item already listed under **Not today**.

### Shutdown

Record the last model class completed, the exact check result, any remaining
schema mismatch, and the first verifier function to migrate next. The next
session begins by replacing manifest traversal with stage-result snapshot and
named-artifact traversal in `verifier.py`.

## Revised five-hour compression

### Day charter

Close the remaining v2 path and execution contracts, establish the steady-state
repository structure, and complete the authoritative Pydantic model graph,
including evaluation and benchmarking plans.

### Capacity and remaining slack

The session has 5 hours: 4.5 hours of mandatory work and 30 minutes of reserved
slack. The added hour is assigned to evaluation and benchmarking. No additional
discretionary slack remains.

Every implementation block includes the full pair-vibe cycle:

```text
Codex inspects and explains one bounded change
→ user applies the change
→ user runs the smallest relevant check
→ Codex reinspects the file or output
→ pair selects the next change
```

### Mandatory execution plan

| Elapsed time | Budget | Work block | Deliverable | Done condition |
|---:|---:|---|---|---|
| 0:00–0:45 | 45 min | 1. Freeze the remaining contract and repository-layout decisions | Complete repository tree, stage-entrypoint chain, run-scoped artifact paths, source/run-plan workspace assembly, and evaluation/benchmark placement | [The v2 specification](../mantra_provenance/ProvenanceS1_v2.md) contains the approved tree; complete `BaseSpec` and `ResolvedBaseSpec` fields; the `BaseSpec.script` → `ResolvedBaseSpec.source` → `ResolvedBaseSpec.command` chain; the exact source-commit-A/run-plan-commit-B materialization sequence; and enforceable run, artifact, pointer, measurement, and log paths |
| 0:45–2:30 | 1 hr 45 min | 2. Pair-migrate the core Pydantic graph and repository structure | Snapshot storage, named artifacts, inputs, run records, pointer paths, source entrypoints, identity-oriented source directories, and governed repository utilities | The model graph compiles; manifest relationships are absent; dataset, prior, model, metric, and artifact-loader code uses the approved `src/mantra/` hierarchy as concrete files are created; `scripts/README.md` limits `scripts/` to thin maintenance and migration callers; every scientific or artifact-producing entrypoint lives under `src/mantra/` and is named by `BaseSpec.script` |
| 2:30–3:45 | 1 hr 15 min | 3. Add evaluation and benchmarking plans | Typed evaluation and benchmark records reuse the unified plan, resolution, artifact, measurement, and verification structure | Both plan types can be constructed, serialized, and parsed through their authoritative unions; each declares its inputs, metrics, outputs, and reproducibility controls without duplicating the core provenance graph |
| 3:45–4:30 | 45 min | 4. Close the model and path validation gate | The migrated graph, repository paths, and minimum focused tests agree | Authoritative modules compile; Pydantic schemas generate; path validators accept the approved run tree and reject one path outside its run root; one evaluation plan and one benchmark plan construct successfully |
| 4:30–5:00 | 30 min | Reserved slack | Pairing overhead, migration fallout, debugging, and short breaks | Used only to finish Blocks 1–4 |

### Replan rule

If evaluation and benchmarking implementation has not begun by 2:45 elapsed,
stop repository-layout propagation after the model graph compiles and
`scripts/README.md` fixes the utility boundary. Use the remaining time to
define, implement, compile, and schema-check the evaluation and benchmark plan
types. Defer their focused construction tests to the first optional
continuation.

### Optional continuations

Use time remaining after all four mandatory blocks pass, in this order:

| Priority | Budget | Continuation | Done condition |
|---:|---:|---|---|
| 1 | 2.5 hr | Migrate and finish `verify_resolved_run()` | The verifier traverses the v2 run plan, stage-result snapshots, named artifacts, stored and same-run inputs, measurements, source entrypoint and command, environment controls, seed chain, attempts, selected estimator, evaluation plans, and benchmark plans; it enforces the approved repository paths |
| 2 | 1.5 hr | Build the complete dummy provenance tree and two acceptance tests | One dummy run exercises promoted and same-run inputs, single-file and bundle artifacts, evaluation, benchmarking, measurements, and terminal resolution; the verifier accepts it; changing one referenced byte makes it fail |
| 3 | 45 min | Close package exports and YAML loading | Public imports and YAML parsing use the v2 models; authoritative modules compile; schemas generate; the complete focused suite passes |

Enter an optional continuation only after the mandatory model and schema gates
pass. Stop at a bounded pair-vibe edit when the five-hour limit is reached.

### Shutdown

Record the last completed mandatory block, the exact check result, the first
unfinished class or verifier function, and the next bounded edit. If all
mandatory blocks pass, record which optional continuation is next.

## End-of-day closeout

### Outcome

Stage 1 is complete at the provenance-framework boundary. The active contract,
Pydantic graph, external verifier, evaluation records, benchmark records, and
acceptance fixture now implement one connected v3 protocol.

The authoritative files are:

- [ProvenanceS1_v3.md](../mantra_provenance/ProvenanceS1_v3.md)
- [models_v4.py](../mantra_provenance/models_v4.py)
- [verifier.py](../mantra_provenance/verifier.py)
- [test_acceptance.py](../tests/test_acceptance.py)
- [mantra_provenance/README.md](../mantra_provenance/README.md)

### Contract frozen today

The formal foundation now begins with the plan space:

$$
\mathcal{Q}
=
\mathcal{M}
\times
\mathcal{C}
\times
\mathcal{H}
\times
\Omega^{+}.
$$

A plan $q$ contains run metadata, one run-wide reproducibility specification,
one shared environment, and an ordered nonempty sequence of stage specs. A
stage may declare an environment override. The shared reproducibility controls
and selected stage environment induce each permitted runtime-state set
$E_{q,j}$; their Cartesian product induces $E_q$.

Each training stage produces one terminal checkpoint. The reserved artifacts
are:

```text
model_parameters
└── terminal model parameters

continuation_state
└── optimizer, RNG, and batch state required for exact continuation
```

Named artifacts partition the state exposed at a stage boundary. A single-file
artifact has one physical file. A bundle has at least two members. Each declared
loader reconstructs the named value from its verified file set.

Completed stages publish one immutable stage-result snapshot containing the
resolved stage spec and every file of every named artifact. Promotion pointers
select a resolved run, producer stage, and artifact name. Same-run inputs select
an earlier producer stage and artifact name directly. Artifact manifests are
absent from the v3 graph.

Evaluation consumes fixed model parameters, a stored evaluation dataset, and
stored split inputs; it publishes predictions and records declared metrics.
Benchmarking binds those inputs and metrics, verifies a second execution,
requires estimator and prediction parity, applies metric criteria, and governs
promotion.

### Implementation completed

- Run-wide environment and reproducibility controls with explicit stage
  environment overrides.
- Typed experiment, variant, replicate, run, stage, artifact, input,
  evaluation, benchmark, attempt, measurement, and terminal-result records.
- Exact source, run-plan, stage-result, artifact, measurement, log, benchmark,
  and promotion references.
- Canonical repository paths for run records, stage specs, resolved stage
  specs, artifacts, promoted inputs, measurements, logs, and benchmark results.
- Duplicate-key-safe YAML and JSON parsing.
- Direct artifact reconstruction through loaders fixed by `RunSpec.source`.
- Stored-input lineage, same-run lineage, checkpoint-pair selection, attempt
  ordering, stage ordering, timestamp, environment, seed, command, and file
  identity verification.
- Input-lineage verification for every completed stage in every attempt.
- Strict benchmark confirmation with a new attempt ID and disjoint stage-result
  snapshots.
- Ruff and Pyright in the declared test dependencies and the `mantra` Conda
  environment.

### Full-pass corrections

The final audit found and closed these gaps:

1. Download receipts now record retrieval time.
2. YAML and measurement JSON objects reject duplicate field names.
3. Attempt stage completion, snapshot identity, measurement identity, and log
   identity are constrained.
4. Stored checkpoint pointers select one run, one stage, and the two reserved
   checkpoint artifacts.
5. Successful evaluations emit exactly one row for every declared metric.
6. Every attempt verifies the lineage of each completed stage's inputs.
7. Benchmark confirmation uses a new attempt identity and new stage snapshots.
8. Specification class examples follow canonical Pydantic field order.
9. The runtime-state product equation renders through Pandoc.

### Validation

Executed in `/Users/machina/miniconda3/envs/mantra/bin/python`:

```text
ruff check mantra_provenance tests
→ All checks passed

pyright
→ 0 errors, 0 warnings, 0 informations

python -m pytest -q
→ 26 passed in 0.63s
```

Additional gates:

- `Spec`, `ResolvedSpec`, `RunSpec`, `ResolvedRun`, `BenchmarkSpec`, and
  `BenchmarkResult` JSON schemas generated successfully.
- All 78 classes reproduced in the v3 specification match their source field
  names and order.
- All Python blocks in the active specification parse.
- Repository-relative documentation links resolve.
- The v3 specification and directory README render through Pandoc.
- `git diff --check` passes.

The acceptance suite now proves:

1. A complete provenance chain with a promoted stored input, same-run input,
   bundle artifact, terminal checkpoint, evaluation, measurement, and terminal
   run verifies.
2. A changed referenced artifact byte is rejected.
3. A two-execution strict benchmark verifies.
4. A benchmark confirmation that reuses original stage snapshots is rejected.

### Git record

The v3 implementation spans 39 focused commits from `f943cb8` through
`3358727`. The final audit increments are:

```text
d900b5c  harden resolved execution integrity
0c9059d  add complete provenance acceptance fixture
2835e75  enforce canonical provenance paths
0ba7868  verify stored checkpoint selections
acf7c27  align protocol documentation with verifier
8d56fdc  complete pointer and measurement validation
b78f57c  verify lineage across every run attempt
3358727  require independent benchmark confirmation
```

### Current boundaries

- `GCEEnvironmentSpec` is the implemented environment type.
- `BuildParams` and `EmbedParams` contain no scientific fields until a concrete
  build and embedding procedure supplies them.
- Artifact loaders execute trusted Python from the Git revision selected by
  `RunSpec.source` inside the verifier process.
- This package verifies provenance records and reconstruction. Environment
  provisioning and stage execution belong to the executor that consumes these
  records.
- The acceptance fixture uses an in-memory document store. Live Git and Hugging
  Face retrieval remain an integration exercise.

### Next session

First action: choose the first concrete model pipeline and map its build and
embedding controls into typed `BuildParams` and `EmbedParams`. Then implement
the corresponding `src/mantra/<entity>/<entity_id>/<operation>.py` entrypoints
and artifact loaders, execute one real run through the executor, and submit its
published records to `verify_run_result()` and `verify_benchmark_result()`.
