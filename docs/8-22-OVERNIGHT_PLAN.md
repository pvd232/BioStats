# VIPER overnight completion plan

- **Date:** 2026-08-22
- **Status:** Final plan review
- **Objective:** Complete every repository-owned requirement for a usable VIPER
  release candidate, validate each completed subsystem, and synchronize every
  coherent increment to Git.

This plan expands the [publication checklist](PUBLICATION_TODO.md). The
[protocol specification](ProvenanceS1_v3.md) defines the provenance contract.
The [application API](APPLICATION_API.md) defines the public Python and command
interfaces.

## Contents

1. [Completion contract](#completion-contract)
2. [Non-negotiable invariants](#non-negotiable-invariants)
3. [Execution and Git policy](#execution-and-git-policy)
4. [Phase 1: publication roadmap](#phase-1-expand-and-freeze-the-publication-roadmap)
5. [Phase 2: public surface](#phase-2-repair-the-current-public-surface)
6. [Phase 3: application API](#phase-3-implement-viperapplication)
7. [Phase 4: CLI](#phase-4-route-the-cli-through-the-application-api)
8. [Phase 5: project extensions](#phase-5-finalize-project-extension-contracts)
9. [Phase 6: runner substrate](#phase-6-build-the-runner-substrate)
10. [Phase 7: preflight](#phase-7-implement-complete-plan-preflight)
11. [Phase 8: input materialization](#phase-8-materialize-verified-stage-inputs)
12. [Phase 9: runtime controls](#phase-9-apply-and-inspect-runtime-controls)
13. [Phase 10: run orchestration](#phase-10-implement-run-attempt-orchestration)
14. [Phase 11: benchmarks](#phase-11-implement-benchmark-execution)
15. [Phase 12: agent operations](#phase-12-add-agent-first-operations)
16. [Phase 13: internal modules](#phase-13-split-large-internal-modules)
17. [Phase 14: documentation](#phase-14-complete-user-and-agent-documentation)
18. [Phase 15: release validation](#phase-15-release-validation)
19. [Validation budget](#validation-budget)
20. [Optional continuations](#optional-continuations)

## Completion contract

Repository-owned completion requires:

- A stable public Python API.
- A CLI that calls the same application functions and emits validated JSON.
- Complete run preflight, input materialization, execution, publication, and
  verification.
- Evaluation and benchmark execution.
- Project-defined stages, artifact loaders, parameters, and metrics through
  frozen repository-relative implementations.
- Agent-oriented discovery, inspection, lineage, and comparison operations.
- Stable public imports over modular internal implementations.
- Current user, extension-author, security, and agent documentation.
- Passing lint, types, tests, builds, metadata checks, installed-wheel checks,
  and complete example execution.
- A clean local branch synchronized with `origin/main` after every coherent
  increment.

The owner supplies the final license choice, author metadata, and package-index
credentials. The repository will contain every file and validated distribution
required for those release actions.

## Non-negotiable invariants

### Frozen plans

- `RunSpec` and its exact ordered stage specifications form the complete frozen
  run plan.
- The run plan fixes the source commit, dataset selections, parameters,
  environment requirements, global reproducibility controls, stage order,
  artifact declarations, metric declarations, and estimator selection.
- Every referenced file is retrieved and checked against its recorded identity
  before use.

### Requested and realized state

- Authored specifications declare requested state.
- Resolved specifications describe realized execution state.
- The verifier establishes that the realized state satisfies the frozen plan
  and that every referenced file matches its identity.

### Stage results

- Each stage has one terminal checkpoint.
- Each successful stage publishes one immutable snapshot containing its
  resolved stage specification and every physical file belonging to every
  declared artifact.
- Training-stage checkpoints reserve the artifact names `parameters` and
  `resume_state`.
- Evaluation stages reserve the artifact name `predictions` while preserving a
  project-selected file or bundle format.

### Metrics

- Decorators and subclasses provide user-facing authoring syntax.
- `MetricSpec` remains the frozen authority.
- The run source commit, implementation path, implementation symbol, SHA-256,
  and byte count identify the exact metric implementation.
- VIPER supplies measurement identity fields from the active run and attempt.
- Benchmark metrics use post-stage production and independent recomputation.

### Executable project code

- Stage entrypoints, artifact loaders, and metric implementations execute from
  exact source bytes selected by the frozen plan.
- The applicable trust policy authorizes the source repository before code
  execution.
- Project code executes in an isolated worker with explicit readable inputs,
  writable outputs, credentials, network policy, and timeout.
- The verifier process validates worker inputs and outputs and keeps project
  code outside its own process.

### Data use

- Every stored input and produced artifact has a data-use role.
- Training stages consume training and permitted validation inputs.
- Evaluation and benchmark inputs remain outside training-stage execution.
- Preflight validates the declared information flow.
- Process isolation enforces the approved materialized inputs and writable
  outputs during execution.

### Public API

- Python callers, CLI callers, and agents use the same application operations.
- Every success and expected failure has a validated JSON representation.
- Public imports remain stable through internal module splits.

## Execution and Git policy

1. Inspect the branch, upstream, and worktree before the first edit.
2. Fetch and fast-forward before implementation.
3. Preserve unrelated worktree changes.
4. Implement one coherent increment.
5. Run its focused acceptance checks.
6. Run Ruff and Pyright at each code commit boundary.
7. Run the complete test suite after each major subsystem.
8. Inspect and stage only the intended paths.
9. Commit the validated increment.
10. Fetch, integrate an advanced upstream safely, and push.
11. Confirm local and upstream commit equality.
12. Finish with a clean synchronized worktree.

---

## Phase 1. Expand and freeze the publication roadmap

Rewrite [PUBLICATION_TODO.md](PUBLICATION_TODO.md) so each unfinished item has:

- A dependency position.
- An exact implementation output.
- A focused validation requirement.
- A release-blocking or optional-continuation classification.
- A link to the defining code or specification.
- A completion checkbox updated only after implementation and validation.

Add the complete metric contract, runner isolation, publication sequence, agent
operations, and release gates defined in this plan.

**Acceptance gate**

- Every phase in this plan maps to one or more checklist items.
- Every release-blocking checklist item maps back to a phase in this plan.
- Implemented and planned behavior use distinct language.

**Commit:** `Expand VIPER completion roadmap`

## Phase 2. Repair the current public surface

### Imports and continuous integration

- Replace the stale `viper.records` import in the wheel smoke test with
  `viper.protocol`.
- Confirm the wheel contains `viper/protocol.py`.
- Confirm every documented public import resolves from an installed wheel.
- Export the completed application and runner modules through the intended
  package surface.

### Terminology

- Complete the public terminology sweep after the `records.py` to
  `protocol.py` rename.
- Rename `serialize_record()` to `serialize_document()` across implementation,
  tests, examples, and documentation.
- Use the exact protocol class name when a concrete class is intended.
- Use protocol document, specification, result, measurement, or reference when
  that term identifies the object more precisely.

### Application error contract

- Resolve the mismatch between `ViperFailure.target: str` and CLI parsing
  failures whose target is absent.
- Define the field as `str | None` and document the exact operations that use
  `None`.

**Acceptance gate**

- Focused package-export tests pass.
- Serialization tests pass under the new name.
- Ruff passes.
- Pyright passes.
- The built wheel imports every supported public path.
- The CI workflow references current package paths.

**Commit:** `Finalize public package vocabulary`

## Phase 3. Implement `viper.application`

Create the operation-first interface defined in
[APPLICATION_API.md](APPLICATION_API.md).

### Initial operations

- `validate_stage()`
- `validate_resolved_stage()`
- `validate_run()`
- `freeze_run()`
- `execute_stage()`
- `verify_run()`
- `verify_benchmark()`
- `verify_pointer()`
- `get_schema()`
- `get_capabilities()`

### Shared application types

- Frozen Pydantic request types.
- Frozen Pydantic success types.
- `ViperFailure` with operation, stable code, target, and concrete cause.
- `ViperError` carrying one `ViperFailure`.
- Stable operation-name and error-code types.
- URL-safe Base64 JSON serialization for captured byte streams.
- Unknown-field rejection.

### Exception translation

Map expected lower-level failures into the stable application codes:

- Request validation to `invalid_request`.
- YAML and protocol validation to `invalid_document`.
- Missing local or referenced files to `not_found`.
- Immutable-path conflicts to `write_conflict`.
- Local or remote transfer failures to `io_failed`.
- Stage timeout, exit, or artifact failures to `execution_failed`.
- Provenance, loader-policy, and benchmark failures to
  `verification_failed`.

Unexpected Python exceptions retain their original type for Python callers.
The CLI converts an uncaught implementation failure into `internal_error`.

### Schema discovery

- Maintain one registry of public authored, resolved, request, success, and
  failure types.
- Generate Pydantic JSON Schema using the Draft 2020-12 dialect.
- Derive `SchemaTypeName` from the registry.
- Reject an unknown schema name as `invalid_request`.

### Capability discovery

Return the installed:

- Package version.
- Protocol schema versions.
- Application operations.
- Discoverable schema types.
- Stage kinds.
- Environment kinds.
- Storage kinds.
- Metric kinds, production modes, and verification modes.

**Acceptance gate**

- Every operation has a success test.
- Every expected error family has a focused translation test.
- Every success and failure serializes to deterministic JSON.
- Every registered type produces JSON Schema.
- Capability output equals the actual registries.

**Commits**

1. `Add typed application operations`
2. `Add schema and capability discovery`

## Phase 4. Route the CLI through the application API

- Replace direct CLI calls into authoring, execution, and verification
  internals with application calls.
- Add `--json` to every operation.
- Preserve concise human-readable output.
- Write exactly one success object to standard output in JSON mode.
- Write exactly one failure object to standard error in JSON mode.
- Use exit status `0` for success.
- Use exit status `1` for an expected VIPER failure.
- Use exit status `2` for command syntax and request validation failures.
- Add `schema` and `capabilities` commands.
- Extend the same dispatch structure with run-level and agent operations in
  later phases.

**Acceptance gate**

- Python and CLI calls return equivalent application results.
- Human output remains concise.
- JSON output validates through the corresponding result type.
- Parsing failures produce the documented CLI failure object.
- Standard output and standard error tests cover every exit status.

**Commit:** `Route CLI through application API`

## Phase 5. Finalize project extension contracts

VIPER accepts repository-relative project implementations while preserving a
fixed core package and a project-selected directory layout.

### Stage entrypoints

Define the exact process contract:

- `BaseSpec.script` identifies one repository-relative Python file.
- The frozen stage-spec path is the stage command argument.
- Inputs appear only at their declared materialization paths.
- Outputs appear only at their declared artifact paths.
- The process receives the active run, attempt, and stage context through a
  VIPER-owned context file.
- The process emits captured standard output and standard error.
- Exit status, timeout, cancellation, and missing-output behavior have typed
  application failures.

### Artifact loaders

Define the exact callable contract:

```python
def load(path: Path) -> object:
    ...
```

- The artifact declaration identifies a repository-relative loader file.
- The source commit fixes the loader bytes.
- A single-file loader receives the materialized file path.
- A bundle loader receives the materialized directory root.
- The verifier invokes loader code only from a source repository approved by
  `VerificationPolicy`.
- The loader executes in an isolated worker with the materialized artifact as
  its only data input.
- Loader success establishes reconstruction from the complete verified file
  set.

### Metric authoring surface

Use a decorator on an ordinary function for stateless metrics:

```python
@viper.metric(
    metric_id="mean_squared_error",
    kind="evaluation",
)
def mean_squared_error(context: EvaluationMetricContext) -> float:
    ...
```

Use a decorated subclass for state accumulated across updates:

```python
@viper.metric(
    metric_id="epoch_accuracy",
    kind="training",
)
class EpochAccuracy(StatefulMetric):
    def update(self, predictions, targets) -> None:
        ...

    def compute(self) -> float:
        ...
```

The user may place either implementation in any repository-relative Python
file. File naming and project package layout remain project-defined.

### Frozen metric contract

Add:

```python
def validate_python_symbol_name(value: str) -> str:
    if not value.isidentifier() or keyword.iskeyword(value):
        raise ValueError("metric implementation symbol must be a Python identifier")
    return value


PythonSymbolName = Annotated[str, AfterValidator(validate_python_symbol_name)]


class MetricImplementationRef(ProtocolModel):
    path: PythonRepoRelPath
    symbol: PythonSymbolName
    sha256: SHA256
    bytes: int = Field(gt=0)
```

The symbol names one top-level decorated function or class and excludes Python
keywords. Nested functions, lambdas, dynamically generated callables, and
runtime-only registry entries lack a stable source symbol and therefore fail
authoring validation.

Revise `MetricSpec` to contain:

```python
class MetricSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    metric_id: MetricId
    kind: MetricKind
    implementation: MetricImplementationRef
    params: MetricParams
    production: MetricProduction
    verification: MetricVerification
```

The complete implementation identity is:

```text
RunSpec.source.repository
+ RunSpec.source.commit
+ MetricImplementationRef.path
+ MetricImplementationRef.symbol
+ MetricImplementationRef.sha256
+ MetricImplementationRef.bytes
→ exact metric implementation
```

`kind` defines semantic use:

- `training`
- `evaluation`
- `diagnostic`

`production` defines invocation time:

- `during_stage`
- `after_stage`

`verification` defines the value claim:

- `execution`
- `recompute`

Enforce:

- Benchmark criteria select evaluation metrics.
- Benchmark metrics use `production="after_stage"`.
- Benchmark metrics use `verification="recompute"`.
- A during-stage metric writes through the VIPER measurement sink.
- An after-stage metric is invoked by the runner with verified persisted
  inputs.
- A recomputed metric preserves every input required to calculate its value.
- The verifier recomputes the value and compares it with
  `Measurement.value`.
- An execution metric claims production by the verified stage execution and
  exact measurement-file identity.
- Training metrics may use either a stateless function or a stateful subclass.
- An after-stage metric returns exactly one finite value.
- A during-stage metric may append multiple finite values with their applicable
  epoch and step positions.
- A recomputed metric is deterministic under the effective runtime contract
  used for verification.
- The runner validates the loaded symbol, decorator metadata, callable
  signature, result type, and finite value.

VIPER supplies:

- `run_id`
- `attempt_id`
- `stage_id`
- `metric_id`
- `measured_at`

The user supplies the calculation and, for during-stage measurements, the
applicable epoch and step.

### Metric authoring

- `@viper.metric(...)` attaches metric identity, role, and parameter-type
  metadata to the function or class.
- An authoring helper resolves the decorated object to its repository-relative
  file and top-level symbol.
- The helper hashes the implementation file and constructs
  `MetricImplementationRef`.
- The helper constructs the complete `MetricSpec` embedded in
  `ExperimentSpec`.
- Plan freeze retrieves the implementation from `RunSpec.source` and checks
  its bytes, symbol, decorator metadata, and signature against the embedded
  `MetricSpec`.
- Runtime decorator registries serve discovery during authoring; the frozen
  `MetricSpec` supplies execution and verification authority.

### Metric contexts

Define exact context types for:

- Training metrics.
- Evaluation metrics.
- Diagnostic metrics.

Each context contains verified artifact selections and frozen parameters.
Context construction applies the existing data-use rules. Benchmark contexts
contain the verified prediction, target, and split artifacts required for
recomputation.

### Measurement sink

- Create one runner-owned append-only sink per attempt.
- Accept values only for metrics declared by the active stage.
- Supply run, attempt, stage, metric, and time identity fields.
- Validate epoch and step according to the metric production mode.
- Reject non-finite values.
- Close the sink before measurement publication.
- Publish the exact resulting JSONL bytes.

### Parameter sets

- Core `ParameterSet` supplies schema versioning and JSON-value validation.
- User code may validate a project-specific Pydantic parameter type before
  constructing the core parameter mapping.
- A metric decorator may declare its project parameter type.
- A stage entrypoint may expose its project parameter type through the defined
  entrypoint contract.
- Authoring validates the mapping through that exact project type before
  constructing the core parameter mapping.
- Preflight retrieves the validator from the frozen source snapshot and applies
  it again before execution.
- The frozen protocol stores the complete JSON-shaped parameter mapping.
- Core stage and metric types remain independent of user-package imports.

### Predictions

- Reserve the logical artifact name `predictions`.
- Preserve project-selected single-file or bundle representation.
- Validate reconstruction through the declared artifact loader.
- Compare the complete resolved file identities during benchmark
  confirmation.

### Protocol and documentation alignment

- Update `ProvenanceS1_v3.md` with the metric implementation, production,
  verification, context, and measurement-sink contracts.
- Update `protocol.py`, verifier relationships, examples, and schemas together.
- Apply the schema change once before the first public release, without a
  compatibility alias for the prior provisional metric shape.

**Acceptance gate**

- One custom stage executes from an arbitrary project path.
- One custom single-file loader reconstructs an artifact.
- One custom bundle loader reconstructs an artifact.
- One decorated stateless evaluation metric produces a measurement.
- One decorated stateful training metric produces step- or epoch-indexed
  measurements.
- One diagnostic metric exercises its declared production mode.
- One recomputed metric passes and fails exact value comparison.
- Metric implementation tampering fails before invocation.
- One custom parameter mapping survives freeze, execution, and verification.
- Invalid project-specific stage and metric parameters fail during authoring
  and preflight.
- One format-neutral prediction artifact completes evaluation verification.

**Commit:** `Finalize project extension contracts`

## Phase 6. Build the runner substrate

### Interfaces

Define typed interfaces for:

- Immutable file retrieval.
- Local file and bundle materialization.
- Stage-result snapshot publication.
- Attempt-file publication.
- Terminal-run publication.
- Benchmark-result publication.
- Attempt workspace creation.
- Attempt progress journaling.
- Effective environment selection.
- Runtime inspection.
- Execution-context capture.
- Process isolation.
- Isolated artifact-loader and metric workers.

### Run request and publication target

Add a typed run request containing:

- The local frozen `RunSpec` path.
- The repository root containing the plan snapshot.
- The Hugging Face result repository.
- The Hugging Face repository type.
- Trusted loader-source repositories.
- Stage timeout policy.
- Retry or resume selection.

Credentials remain process inputs and never enter a protocol document, log,
application result, or resolved run.

Preflight resolves two distinct Git revisions:

- Source snapshot A, selected by `RunSpec.source`, contains experiment,
  variant, metric implementation, artifact-loader implementation, stage
  entrypoint, lockfile, and production source files.
- Plan snapshot B contains the frozen `RunSpec` and every exact stage
  specification it identifies.

The plan repository and source repository identities must satisfy the protocol
relationship verified by `verify_run_plan()`.

### Workspace contract

- Resolve every path beneath one attempt workspace root.
- Materialize source as a read-only snapshot.
- Materialize approved inputs as read-only files or directory trees.
- Reserve writable paths for declared artifacts, measurements, and logs.
- Reject path escape, symlinks, and overlapping input/output roots.
- Write temporary files atomically.
- Preserve a failed attempt workspace until its output references are
  published or the failure is reported.
- Append state changes to a machine-readable local progress journal so
  `status` can report an active attempt before terminal publication.

### Execution isolation

- Expose only the frozen source snapshot and approved materialized inputs.
- Expose only the credentials required by the selected operation.
- Disable network access for every `InternalSpec` stage.
- Restrict a `DownloadSpec` stage to the host declared by its
  `RemoteFileRef`.
- Restrict writable paths to the active attempt workspace.
- Capture the exact command, environment selection, and execution context.
- Apply timeout and cancellation through the process supervisor.
- Run artifact loaders and after-stage metric implementations in isolated
  workers governed by the same trust, filesystem, credential, network, and
  timeout controls.
- Return only validated loader or metric results to the main runner and
  verifier processes.

The initial isolation adapter may use the operating system and container
facilities available to the active environment. Its capability result must
state which controls were applied. A run requiring an unavailable isolation
control fails preflight.

### Publication behavior

- Publish identical bytes idempotently.
- Reject different bytes at an occupied canonical identity.
- Publish one stage snapshot containing the resolved stage specification and
  every file belonging to every declared artifact.
- Publish closed measurement and log files after attempt completion.
- Publish terminal `resolved.yaml` after every attempt reference is fixed.
- Publish stage results, attempt files, terminal runs, and benchmark results to
  immutable Hugging Face repository commits.
- Publish promoted-input pointer documents through a later Git source snapshot.
- Keep source and plan documents in Git snapshots.
- Verify every returned commit and file identity after publication.
- Provide an in-memory backend for focused tests.

The immutable publication topology is:

```text
Git source snapshot A
├── experiment and variant specifications
├── metric and loader implementations
├── stage entrypoints
└── environment lockfile

Git plan snapshot B
├── RunSpec
└── ordered stage specifications

Hugging Face stage snapshots C_i,j
├── resolved stage specification
└── complete artifact files

Hugging Face attempt-file snapshot D_i
├── closed measurement files
└── closed log files

Hugging Face terminal-run snapshot E
└── resolved.yaml

Hugging Face benchmark-result snapshot F
└── benchmark result

later Git source snapshot G
└── optional promoted-input pointer
```

### Environment boundary

VIPER executes inside a provisioned environment. The runner:

1. Resolves the shared `RunSpec.environment` or stage override.
2. Inspects the active runtime.
3. Requires the active runtime to satisfy the selected specification.
4. Captures the realized environment and execution context.

Cloud resource creation lives behind a provider interface. This release
implements the active-runtime contract and leaves provider-specific resource
lifecycle adapters as optional continuations.

The initial active-runtime implementation is `GCEActiveRuntimeAdapter`. It
reads the current GCE machine identity, resolves the immutable machine-image
identity and lockfile, inspects CPU or CUDA resources, and constructs the
resolved environment and execution context. Focused tests use injected GCE
metadata and runtime observations. A live GCE smoke run is reported separately
because it requires a provisioned instance.

**Acceptance gate**

- File and bundle materialization round trips.
- Immutable snapshot round trip.
- Identical republish succeeds.
- Conflicting republish fails.
- Path escape, symlink, and overlap attempts fail.
- Isolation capability failures stop preflight.
- Project loader and metric code cannot write outside its declared worker
  output path or access undeclared materialized inputs.
- Published references retrieve the original bytes.
- Stage snapshot, attempt-file, and terminal-run publication follow the
  required dependency order.
- Source, plan, stage, attempt-file, terminal-run, benchmark-result, and pointer
  snapshots use the storage types fixed by the protocol.

**Commit:** `Add runner storage and workspace interfaces`

## Phase 7. Implement complete-plan preflight

Preflight retrieves and validates every dependency required before execution:

- `RunSpec`.
- Experiment specification.
- Variant specification.
- Ordered stage specifications.
- Benchmark specification when selected.
- Metric specifications and implementation files.
- Stored-input pointers.
- Artifact loaders.
- Source commit.
- Plan repository and immutable plan commit.
- Environment lockfile.
- Effective environment for every stage.

Preflight checks:

- Stage order.
- Future-input producer order.
- Stored-input availability.
- Data-use roles.
- Evaluation and benchmark leakage into training.
- Artifact names, kinds, and canonical paths.
- Input, output, source, measurement, and log path collisions.
- Reserved artifact names.
- Metric declaration, production, and verification compatibility.
- Evaluation and benchmark identity alignment.
- Global reproducibility controls.
- Environment override selection.
- Active-runtime and isolation capabilities.
- Estimator selection.
- Required source files.
- Exact `RunSpec` and stage-spec bytes in the plan snapshot.
- Planned output paths.
- Trusted executable-source policy.

Return a typed preflight result containing:

- Run identity.
- Ordered stage identities.
- Exact dependency identities.
- Resolved source and plan snapshot identities.
- Effective environment per stage.
- Approved input materializations.
- Planned write paths.
- Required isolation controls.
- Warnings and failures with stable codes and exact targets.

**Acceptance gate**

- One complete valid plan passes.
- Each preflight rule has one focused rejection test.
- Preflight performs no stage execution or publication.
- Preflight JSON validates through its public result schema.

**Commit:** `Add complete run preflight`

## Phase 8. Materialize verified stage inputs

### Stored inputs

1. Retrieve the exact pointer document.
2. Verify its producer run.
3. Select the named stage artifact.
4. Verify every referenced file.
5. Materialize the files beneath the consuming stage's declared input path.
6. Invoke the declared loader against the complete materialized representation.
7. Construct `ResolvedStoredInputRef`.

### Same-run inputs

1. Select the completed earlier stage.
2. Select the named artifact from its resolved stage specification.
3. Retrieve its files from the immutable stage snapshot.
4. Verify every file.
5. Materialize the representation for the consuming stage.
6. Invoke the declared loader.
7. Construct `ResolvedFutureInputRef`.

### Materialization invariants

- Materialized bytes match the verified source bytes.
- Bundle membership is complete, ordered, and contained beneath its root.
- Data-use roles propagate to the consuming stage.
- A consuming stage receives only its declared inputs.
- Input materialization finishes before its stage process begins.

**Acceptance gate**

- Stored single-file input.
- Stored bundle input.
- Same-run single-file input.
- Same-run bundle input.
- Data-role propagation.
- Tampered bytes.
- Missing bundle member.
- Extra bundle member.
- Materialization collision.
- Loader reconstruction failure.

**Commit:** `Materialize verified stage inputs`

## Phase 9. Apply and inspect runtime controls

- Apply the run's global seed.
- Apply PyTorch determinism controls.
- Apply precision controls.
- Apply process and thread controls.
- Apply DataLoader worker, prefetch, persistence, and ordering controls.
- Initialize the declared Python, NumPy, PyTorch CPU, PyTorch CUDA, and loader
  generator states.
- Select the shared environment or stage override.
- Inspect the realized host, backend, devices, native libraries, generators,
  and parallelism.
- Resolve the exact machine image and dependency lockfile identities.
- Construct `ResolvedGCEEnvironment`.
- Construct `ExecutionContext`.
- Reject an active runtime that violates the effective specification.

### Resume-state integration

- Restore `parameters` and `resume_state` before creating the next DataLoader
  iterator.
- Require the saved worker count, prefetch configuration, persistence, and
  ordering settings to match the run plan.
- Restore main-process and stateful-loader state.
- Save one terminal checkpoint per training stage.
- Verify uninterrupted and resumed next-update parity.

**Acceptance gate**

- Effective-environment fallback and override tests.
- Global-control propagation tests.
- Runtime mismatch rejection.
- Zero-worker continuation parity.
- Multiprocess continuation parity.
- Resume configuration mismatch rejection.
- Injected GCE metadata and runtime-inspection acceptance.
- Live GCE execution status reported separately from the deterministic local
  suite.

**Commit:** `Apply and inspect run controls`

## Phase 10. Implement run-attempt orchestration

Add `run()` to the Python API and `viper run` to the CLI.

### Attempt lifecycle

1. Preflight the complete run plan.
2. Allocate the next attempt ID.
3. Create the isolated attempt workspace.
4. Execute `RunSpec.stages` in order.
5. Materialize each stage's verified inputs.
6. Apply the effective environment and global reproducibility controls.
7. Invoke the exact stage entrypoint.
8. Construct the concrete resolved stage specification.
9. Publish the complete stage-result snapshot.
10. Add its `ResolvedStageRef` to the active `RunAttempt`.
11. Execute declared after-stage metrics.
12. Accept declared during-stage measurements from the measurement sink.
13. Close the attempt and its standard-output, standard-error, and measurement
    streams.
14. Publish the closed measurement and log files.
15. Set attempt status and completion time.
16. Write terminal `resolved.yaml` containing every attempt.
17. Set `successful_attempt_id` exactly when one attempt completed
    successfully.

### Resolved stage construction

Each resolved stage specification contains:

- The exact authored stage specification.
- The exact source entrypoint identity.
- Resolved stored and same-run inputs.
- Realized environment.
- Execution context.
- Exact command.
- Complete resolved artifacts.
- Completion time.
- Download retrieval time for a download stage.

### Publication sequence

```text
stage process completes
        │
        ▼
resolved stage specification + artifact files
        │
        ▼
one immutable stage-result snapshot
Hugging Face commit C_i,j
        │
        ▼
ResolvedStageRef added to active RunAttempt
        │
        ▼
attempt terminates and streams close
        │
        ▼
measurement and log files published
as one Hugging Face commit D_i
        │
        ▼
RunAttempt receives exact file references
        │
        ▼
terminal resolved.yaml published
as Hugging Face commit E
```

### Failure handling

Preserve a failed or cancelled attempt when execution has allocated an attempt
ID. Capture:

- Preflight failure before attempt allocation as an application failure.
- Input retrieval or materialization failure.
- Runtime-control failure.
- Timeout.
- Cancellation.
- Nonzero stage exit.
- Missing or invalid artifact.
- Metric failure.
- Snapshot publication failure.
- Measurement or log publication failure.
- Terminal publication failure.

### Retry behavior

- Preserve every prior attempt.
- Allocate a new attempt ID.
- Reuse immutable completed-stage snapshots only through an explicit resume or
  retry policy.
- Prevent new bytes from replacing a prior immutable result.
- Recompute terminal `successful_attempt_id` from completed attempts.

**Acceptance gate**

- Complete download, build, train, and evaluate run.
- Stored input.
- Same-run input.
- Training and evaluation metrics.
- Parameters and resume-state checkpoint.
- Stage snapshots.
- Closed measurement and log publication.
- Terminal `resolved.yaml`.
- Failed attempt preservation.
- Cancelled attempt preservation.
- Retry with a new attempt ID.
- Tampered stage artifact rejection.
- Terminal run verification through `verify_run_result()`.

**Commits**

1. `Add run attempt orchestration`
2. `Publish stage results and attempt files`
3. `Write terminal resolved runs`

## Phase 11. Implement benchmark execution

- Load the governing `BenchmarkSpec`.
- Retrieve and verify the completed candidate run.
- Confirm its evaluation stage selects the benchmark evaluation ID, dataset,
  splits, and metric IDs.
- Execute one complete independent confirmation attempt against the same frozen
  plan snapshot.
- Verify estimator artifact parity.
- Verify prediction artifact parity.
- Recompute every benchmark metric from verified persisted inputs.
- Apply every metric threshold.
- Construct and publish `BenchmarkResult`.
- Expose benchmark execution through Python and CLI operations.

**Acceptance gate**

- Passing benchmark.
- Prediction mismatch.
- Estimator mismatch.
- Recomputed-value mismatch.
- Threshold failure.
- Missing confirmation.
- Benchmark result verification through `verify_benchmark_result()`.

**Commit:** `Add benchmark execution`

## Phase 12. Add agent-first operations

Implement typed, JSON-native operations:

- `preflight`
- `status`
- `plan_diff`
- `lineage`
- `compare_runs`

### Preflight

Return every dependency, planned write, environment selection, isolation
requirement, warning, and blocking failure before execution.

### Status

Return the current run status, attempts, completed stages, active stage,
published files, and next permitted operation.

### Plan diff

Compare two frozen plans across:

- Experiment, variant, and replicate identity.
- Source commit.
- Dataset and stored-input selections.
- Ordered stage specifications.
- Parameters.
- Environment.
- Reproducibility controls.
- Metrics.
- Estimator selection.

### Lineage

Traverse from a run, stage, artifact, measurement, or pointer to its exact
upstream and downstream references. Return identities, paths, hashes, and join
fields.

### Compare runs

Compare resolved runs across:

- Frozen plans.
- Realized environments.
- Execution contexts.
- Inputs.
- Artifact identities.
- Measurements.
- Attempt outcomes.

### Agent-facing requirements

- Deterministic JSON.
- Stable operation and error codes.
- Schema and capability discovery.
- Noninteractive invocation.
- Idempotent inspection operations.
- Explicit write sets before mutation.
- Machine-readable progress.
- Leakage findings tied to exact stage and input identities.
- Results that contain the next permitted operation where one exists.

An agent-protocol adapter remains an optional continuation after the complete
Python and JSON command surface passes acceptance.

**Acceptance gate**

- Every operation has a validated result schema.
- CLI and Python results agree.
- One fixture exercises each operation.
- Plan and run comparison identify every intentionally changed field.
- Lineage reaches exact source, input, artifact, measurement, and terminal-run
  identities.

**Commits**

1. `Add agent inspection operations`
2. `Add run comparison and lineage queries`

## Phase 13. Split large internal modules

Preserve:

```python
from viper.protocol import RunSpec
from viper.verifier import verify_run_result
```

### Protocol internals

Move implementation into private modules grouped by:

- Shared types and references.
- Environments and reproducibility.
- Experiments and variants.
- Stages and inputs.
- Artifacts and snapshots.
- Attempts and runs.
- Measurements and benchmarks.

Re-export the supported names from `viper.protocol`.

### Verifier internals

Move implementation into private modules grouped by:

- File retrieval and identity.
- Plan verification.
- Stage verification.
- Run verification.
- Promoted artifacts.
- Benchmark verification.

Re-export the supported operations and result types from `viper.verifier`.

**Acceptance gate**

- Capture the public import inventory before the split.
- The same import inventory passes after the split.
- The complete suite passes before and after each split.
- The built wheel exports the same public paths.
- Circular-import checks pass.

**Commits**

1. `Split protocol internals`
2. `Split verifier internals`

## Phase 14. Complete user and agent documentation

Add or finalize:

- Five-minute quickstart.
- Run authoring guide.
- Project extension guide.
- Stage entrypoint contract.
- Artifact-loader contract.
- Metric decorator and stateful-metric contract.
- Metric production and verification modes.
- Complete runner lifecycle.
- Evaluation and benchmark guide.
- Resume-state guide.
- Trust and executable-code policy.
- Process-isolation and credential policy.
- Leakage-prevention rules.
- Agent-operation guide.
- Error-code reference.
- JSON and schema examples.
- Canonical file tree.
- Optional `viper init` project template with no required user package name or
  source-tree layout.
- Public API reference.
- Release checklist.

Update:

- The root README directory map and public operations.
- The documentation table of contents.
- The application API status from proposed to implemented when its acceptance
  gate passes.
- The publication checklist after each validated phase.

Complete a prose audit for:

- Undefined terms.
- Stale names.
- Repeated explanations.
- Missing causal connectors.
- Claims exceeding implementation.
- Inconsistent paths or examples.
- Invalid Markdown and LaTeX rendering.

**Acceptance gate**

- Every public operation links to its defining guide or reference.
- Every project extension has one complete executable example.
- Every documented command passes as written.
- Repository-relative links resolve.
- The README describes the implemented release surface exactly.

**Commit:** `Complete VIPER publication documentation`

## Phase 15. Release validation

### Static and automated validation

- Ruff over package, tests, examples, and tools.
- Pyright.
- Complete pytest suite.
- Source distribution build.
- Wheel build.
- Metadata inspection with Twine.
- Clean installed-wheel import test.
- Installed CLI smoke tests.
- Installed Python API smoke tests.
- JSON Schema discovery for every registered type.
- Capability discovery.
- Complete example run.
- Complete benchmark.
- Generated-file and package-content inspection.
- CI validation for every Python version supported by the resolved dependency
  set.
- Deterministic runner acceptance with injected GCE metadata.

### Release artifacts

- Final version.
- Release notes.
- Owner-selected license.
- Author metadata.
- Project URLs and classifiers.
- Built source distribution and wheel.
- Recorded checksums.
- TestPyPI installation instructions.
- PyPI publication command and verification instructions.

### Release rehearsal

1. Build from a clean source tree.
2. Inspect both distributions.
3. Install the wheel into a clean target.
4. Run import, CLI, schema, capability, execution, and verification smoke tests.
5. Confirm the installed package contains only intended runtime files.
6. Confirm the repository remains clean.

**Acceptance gate**

- Every repository-owned publication-checklist item is checked.
- Full validation passes from a clean source tree.
- The final local commit equals `origin/main`.
- The release report states whether a live provisioned-GCE smoke run was
  executed.
- The final handoff enumerates only owner-selected legal metadata,
  provisioned-GCE validation, TestPyPI publication, and PyPI publication as
  external actions.

**Commit:** `Prepare VIPER release candidate`

## Validation budget

Execution speed governs test selection during implementation:

- Run the smallest focused test set after each code edit.
- Run Ruff and Pyright at each coherent commit boundary.
- Run the complete suite after the application API, extension contracts,
  runner, agent operations, and internal splits.
- Run build, metadata, wheel installation, and complete examples at the final
  release boundary.
- Add tests for contract-critical success, failure, tampering, and publication
  behavior.

## Optional continuations

These items begin after every release-blocking acceptance gate passes:

- Provider-specific environment provisioning and teardown adapters.
- Agent-protocol adapter over the stable application API.
- Additional immutable storage backends.
- Additional isolation adapters.
- Built-in adapters for common third-party metrics.
- Hosted documentation publication.
- Automated TestPyPI and PyPI release workflows after credentials and release
  policy are supplied.
