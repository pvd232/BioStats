# VIPER 0.1 release roadmap

This file is the authoritative implementation checklist for VIPER 0.1. The
[protocol](ProvenanceS1_v3.md) defines provenance semantics. The
[application API](APPLICATION_API.md) defines the public application surface.
Focused design documents created during this roadmap own their named runtime
contracts.

A checked item means the implementation, focused tests, public documentation,
and installed-wheel behavior all agree. Every completed increment receives a
task-scoped Git commit and a successful push.

## Contents

1. [Release outcome](#release-outcome)
2. [Release priorities](#release-priorities)
3. [Completed foundation](#completed-foundation)
4. [Phase 0: contract freeze](#phase-0-freeze-the-blocking-contracts)
5. [Phase 1: public package surface](#phase-1-repair-ci-and-define-the-public-package-surface)
6. [Phase 2: application errors and JSON](#phase-2-freeze-application-errors-and-json-encoding)
7. [Phase 3: application API and CLI](#phase-3-implement-the-application-api-and-cli)
8. [Phase 4: workspace, storage, and publication](#phase-4-implement-workspace-storage-and-publication-primitives)
9. [Phase 5: project extensions](#phase-5-implement-project-extension-interfaces)
10. [Phase 6: OCI isolation](#phase-6-implement-the-oci-isolation-worker)
11. [Phase 7: preflight and input materialization](#phase-7-implement-preflight-and-verified-input-materialization)
12. [Phase 8: runtime bootstrap](#phase-8-implement-the-runtime-bootstrap-and-controls)
13. [Phase 9: durable orchestration](#phase-9-implement-durable-run-orchestration)
14. [Phase 10: benchmark execution](#phase-10-implement-benchmark-execution-and-recomputation)
15. [Phase 11: agent operations](#phase-11-add-agent-inspection-and-controlled-mutation)
16. [Phase 12: internal modules](#phase-12-split-internals-at-established-dependency-boundaries)
17. [Phase 13: documentation and release](#phase-13-complete-documentation-and-release-validation)
18. [Current execution charter](#current-execution-charter)

## Release outcome

VIPER 0.1 is ready when a user can freeze a run plan, execute it on a
pre-provisioned GCE host, publish its immutable results, verify its complete
lineage, execute a benchmark confirmation, and inspect the result through the
Python API or JSON CLI.

The shortest release path is:

```text
contract freeze
-> typed stage invocation
-> controlled HTTP retrieval
-> metric and artifact closure
-> failed attempts and retry
-> benchmark execution
-> single-host GCE execution
-> project scaffold
-> release validation
```

## Release priorities

The [implementation-contract index](contracts/README.md) owns the approved
mechanics for every 0.1 release gate.

| Priority | Work | Reason |
|---|---|---|
| 0.1 required | Typed stage invocation | Connects validated project parameters to the callable that receives them. |
| 0.1 required | Controlled HTTP retrieval | Connects each declared request to the response bytes consumed by a download stage. |
| 0.1 required | Metric and artifact closure | Fixes metric dependencies and states the exact artifact guarantee established by each check. |
| 0.1 required | Failed attempts and retry | Preserves failures and lets a user rerun the same frozen plan safely. |
| 0.1 required | Benchmark execution | Produces the independent confirmation already represented by the verifier. |
| 0.1 required | Single-host GCE execution | Runs real workloads on a pre-provisioned cloud VM and verifies the realized host. |
| 0.1 required | Distribution acceptance | Proves the installed wheel and CLI complete the documented user path. |
| 0.1 convenience | `viper init` | Creates a runnable starter project while preserving repository-relative source paths. |
| Stable hardening | OCI mounts and network confinement | Supports a strong information-flow claim against untrusted project code. |
| Stable reliability | Crash adoption, publication recovery, cancellation, and preemption | Preserves remote attempts across coordinator and host failures. |
| Later scale | Distributed execution and durable object-store publication | Supports multi-host training and long-lived remote results. |
| Later autonomy | Epoch-completion oversight and agent mutation dry-runs | Adds supervised execution claims for highly autonomous runs. |
| Later maintenance | Internal protocol and verifier splits | Reduces maintenance cost after public boundaries stabilize. |
| Later interface | Additional built-ins and graphical interfaces | Lowers setup effort after the execution contract is complete. |

The minimal GCE contract uses one trusted, pre-provisioned VM. It extends the
working local coordinator to remote compute. The OCI worker supplies a separate
confinement guarantee and is scheduled after 0.1.

## Completed foundation

- [x] Define authored stage specs, resolved stage specs, run attempts, terminal
  resolved runs, artifact pointers, evaluations, and benchmark results.
- [x] Verify file identity, stage order, input lineage, artifact declarations,
  runtime controls, attempt files, promoted artifacts, and benchmark
  confirmation.
- [x] Capture and restore `ResumeState` for zero-worker and multiprocess
  `StatefulDataLoader` execution.
- [x] Provide extensible JSON-shaped stage parameter bases.
- [x] Define training, validation, evaluation, and benchmark data roles.
- [x] Enforce training-stage data-use rules during plan verification.
- [x] Store evaluation identity, metric IDs, and split inputs on `EvaluateSpec`.
- [x] Bind each benchmark to one evaluation while allowing the same benchmark
  to govern many candidate run plans.
- [x] Reserve `predictions` as the evaluation artifact name while leaving its
  file or bundle representation to its declared loader.
- [x] Reserve `parameters` and `resume_state` as the two training-checkpoint
  artifacts.
- [x] Freeze run plans into canonical stage and run documents.
- [x] Execute one stage entrypoint and identify every produced artifact file.
- [x] Provide duplicate-key-safe YAML parsing and canonical document encoding.
- [x] Package runtime code under `viper` and repository utilities under
  `tools/`.
- [x] Resolve project scripts, metric implementations, parameter models, and
  artifact loaders through repository-relative paths.
- [x] Use `spec.yaml` and `resolved.yaml` inside run and stage identity
  directories.
- [x] Document active modules, classes, functions, methods, and tests and
  enforce that coverage through Ruff.
- [x] Add focused protocol, verifier, resume, metric, loader, authoring, CLI,
  and single-stage execution tests.

## Trusted-local milestone: August 22, 2026

The current package provides a complete successful-run path on one trusted
local host:

```text
freeze
-> preflight
-> execute ordered stages
-> materialize verified inputs
-> invoke frozen metrics
-> publish immutable local evidence
-> write resolved.yaml
-> verify the terminal run
```

The validated boundary includes 129 tests and 13 subtests, Ruff, Pyright,
source and wheel builds, metadata checks, and an installed-wheel capability
smoke test. The release path still requires failed-attempt recovery, live GCE
validation, benchmark execution, complete extension binding, and publication
credentials.

## Phase 0. Freeze the blocking contracts

Every unfinished release increment consumes one contract from
[`docs/contracts/`](contracts/README.md). Existing application and runner code
must migrate through those contracts as each increment lands.

### 0.1 Artifact guarantees

VIPER 0.1 uses three explicit guarantee levels:

```text
verified file set
-> exact representation identity

verified file set + successful loader return
-> loadability

verified file set + core artifact validator
-> semantic validity for the reserved artifact type
```

- [ ] Update [the protocol](ProvenanceS1_v3.md) to state that a generic artifact
  loader proves loadability from the exact verified file set.
- [ ] Reserve core semantic validation for protocol-owned artifact values such
  as `resume_state`.
- [ ] Define bundle completeness as enumeration of every regular file beneath
  the declared artifact root at publication time.
- [ ] Define bundle minimality as an authoring and review requirement tied to
  actual consumer needs.
- [ ] Update verifier errors and documentation to use `loadability` and
  `semantic validity` at their exact scopes.
- [ ] Add `test_generic_loader_establishes_loadability` to
  [verifier tests](../tests/test_verifier.py).
- [ ] Add `test_resume_state_receives_core_semantic_validation` to
  [verifier tests](../tests/test_verifier.py).

### 0.2 Metric semantics

- [ ] Freeze `MetricKind` as `training`, `evaluation`, or `diagnostic`.
- [ ] Freeze `MetricProduction` as `during_stage` or `after_stage`.
- [ ] Freeze `MetricVerification` as `execution` or `recompute`.
- [ ] Define `execution` as provenance for the producing stage invocation and
  immutable measurement bytes.
- [ ] Define `recompute` as a fresh invocation from the frozen implementation,
  declared dependencies, frozen parameters, and effective runtime contract.
- [ ] Require every recomputed floating-point metric to declare an exact,
  absolute-tolerance, or relative-tolerance comparator.
- [ ] Require benchmark criteria to use `kind=evaluation`,
  `production=after_stage`, and `verification=recompute`.
- [ ] Define metric dependency bindings by exact input or artifact name and
  data role.
- [ ] Define the immutable recomputation evidence stored with a benchmark
  result.

### 0.3 Execution backends

The 0.1 cloud backend runs on one trusted, pre-provisioned GCE host. The OCI
worker becomes the stable-release confinement backend.

The [HTTP retrieval contract](contracts/HTTP_RETRIEVAL.md) defines the frozen
request, resolved exchange, controlled-client, and verifier changes for
download stages.

The [cloud execution contract](contracts/CLOUD_EXECUTION.md) defines the 0.1
GCE transport, remote runtime evidence, and live acceptance profile.

- [ ] Extract the working local orchestration into a backend-neutral
  coordinator.
- [ ] Add the `run_gce` application and CLI operation.
- [ ] Build and verify the bounded GCE execution bundle.
- [ ] Transfer the bundle and invoke the remote runner through the documented
  Google Cloud transport.
- [ ] Record and verify realized GCE host state.
- [ ] Pull and verify remote result revisions when requested.
- [ ] Run one live GCE acceptance profile from the installed wheel.

Phase 6 owns OCI mounts, network confinement, secrets, resource limits, and
adversarial tests.

### 0.4 Durable attempt lifecycle

VIPER 0.1 assigns one active coordinator to each run. The coordinator owns an
exclusive workspace lock while an attempt is active.

The durable states are:

```text
allocated
-> preflighting
-> running_stage
-> publishing_stage
-> closing_attempt
-> publishing_attempt_files
-> publishing_terminal_run
-> terminal
```

- [ ] Implement the transition and retry rules in
  [Attempt execution](contracts/ATTEMPT_EXECUTION.md).
- [ ] Replace the stale-file lock with an operating-system-managed advisory
  lock.
- [ ] Allocate the next attempt ID from terminal history and attempt journals.
- [ ] Publish failed attempts with available stage snapshots and logs.
- [ ] Reconcile one abandoned nonterminal journal after lock acquisition.
- [ ] Add explicit retry through the Python API and JSON CLI.
- [ ] Preserve every previous attempt in the next terminal run.

Phase 9 owns complete crash adoption, publication recovery, cancellation, and
preemption.

### 0.5 Runtime information flow

- [ ] Define the permitted data roles for every stage kind in one versioned
  policy.
- [ ] Give each worker access to the declared inputs permitted for that stage.
- [ ] Keep evaluation and benchmark inputs outside training-stage contexts.
- [ ] Bind every metric dependency to an exact input or artifact and data role.
- [ ] Return a stable preflight failure for every prohibited dependency.
- [ ] Add one plan-level test and one context test for each prohibited
  information flow.

Phase 6 adds filesystem and network enforcement against project code.

### 0.6 Contract-freeze gate

- [ ] The protocol, application API, execution-security design, and attempt
  lifecycle use one vocabulary.
- [ ] Every proposed field has one producing actor and one consuming actor.
- [ ] Every verification claim names the values compared and the code that
  compares them.
- [ ] Every downstream roadmap item links to its governing contract.
- [ ] The contract commit passes Ruff, Pyright, protocol tests, and verifier
  tests.

**Executable gate**

```text
python -m pytest tests/test_protocol.py tests/test_verifier.py tests/test_execution_policy.py tests/test_attempt_lifecycle.py -q
```

**Commit boundaries**

1. `Freeze artifact and metric contracts`
2. `Freeze execution, information-flow, and attempt contracts`

## Phase 1. Repair CI and define the public package surface

### 1.1 Public import inventory

- [ ] List every supported public module and name in `docs/PUBLIC_API.md`.
- [ ] Add explicit `__all__` declarations to each supported public module.
- [x] Keep root `viper` exports limited to supported modules and convenience
  names.
- [x] Add installed-wheel import tests for every listed public name.
- [x] Add application and runner exports in the commits that create those
  modules.

### 1.2 Serialization terminology

`serialize_record()` appears in the current README and therefore receives a
compatibility path.

- [x] Add `serialize_document()` as the canonical public name.
- [x] Retain `serialize_record()` as a deprecated alias through the 0.1 release.
- [x] Emit one documented deprecation warning from the alias.
- [x] Test identical bytes from both names.
- [x] Schedule alias removal through the version policy.

### 1.3 Continuous integration

- [x] Replace the stale `viper.records` wheel import in
  [CI](../.github/workflows/ci.yml) with a supported public import.
- [x] Run the CI matrix for every Python version advertised by
  [package metadata](../pyproject.toml).
- [x] Keep Ruff, Pyright, pytest, build, metadata, and installed-wheel checks in
  every matrix entry where the dependency set supports them.
- [ ] Require successful remote CI for the exact release commit.

**Executable gate**

```text
python -m pytest tests/test_public_api.py tests/test_cli.py -q
python -m build
python -m twine check dist/*
```

**Commit boundaries**

1. `Define supported VIPER imports`
2. `Rename document serialization with compatibility`
3. `Repair the supported Python CI matrix`

## Phase 2. Freeze application errors and JSON encoding

### 2.1 Call boundaries

- [x] Typed Python functions accept validated Pydantic request objects.
- [x] Pydantic raises request-construction errors to typed Python callers.
- [x] A raw `dispatch(operation, payload)` entrypoint validates mappings for CLI
  and agent callers.
- [x] Application operations raise `ViperError` for expected operational
  failures.
- [x] Python callers receive unexpected implementation exceptions with their
  original types.
- [x] The CLI converts parser, request, expected operation, and unexpected
  failures into their corresponding result types.

### 2.2 Failure model

- [x] Define `FailureOrigin` as `request`, `application`, `cli`, or `internal`.
- [x] Keep `OperationName` limited to callable application operations.
- [x] Permit `operation=None` for syntax failures that occur before subcommand
  resolution.
- [ ] Define stable error codes for parsing, validation, retrieval, conflict,
  execution, verification, publication, cancellation, and internal faults.
- [ ] Define a cause-redaction policy that emits approved messages and fields.
- [ ] Keep credentials, local secret-bearing paths, raw subprocess output, and
  unapproved URLs outside serialized failures.

### 2.3 Deterministic JSON

- [x] Encode UTF-8 with one trailing newline.
- [x] Emit fields in model-definition order.
- [ ] Encode paths with POSIX separators.
- [ ] Encode datetimes as UTC RFC 3339 values.
- [ ] Encode bytes with URL-safe Base64.
- [ ] Encode sets as sorted arrays.
- [ ] Preserve mapping order only where the schema assigns semantic order.
- [ ] Add golden JSON fixtures for every success and failure family.

**Executable gate**

```text
python -m pytest tests/test_application_errors.py tests/test_application_json.py -q
```

**Commit:** `Define application failures and JSON encoding`

## Phase 3. Implement the application API and CLI

### 3.1 Application operations

- [x] Implement `validate_stage()` for one authored stage document.
- [x] Implement `validate_resolved_stage()` for one resolved stage document.
- [x] Implement `validate_run_spec()` for one `RunSpec` document.
- [x] Implement `freeze_run()` for canonical plan authoring.
- [x] Implement `execute_stage()` as the existing single-stage operation.
- [x] Implement `verify_run()`, `verify_benchmark()`, and `verify_pointer()`.
- [x] Implement `get_schema()` through an explicit name-to-model registry.
- [x] Implement `get_capabilities()` through an explicit capability registry.
- [x] Return one validated success model from every operation.
- [x] Document each operation beside its implementation.

### 3.2 CLI parser and rendering

- [x] Make `--json` a global option accepted before the subcommand.
- [x] Override parser exit behavior and convert syntax failures into
  `ViperFailure` with `origin="cli"`.
- [x] Emit usage text in human mode.
- [x] Emit one JSON document in JSON mode.
- [ ] Route warnings into the result model in JSON mode.
- [x] Limit CLI responsibilities to parsing, request construction, dispatch,
  rendering, and exit-code selection.
- [ ] Capture standard output, standard error, and exit status for every command
  in [CLI tests](../tests/test_cli.py).

**Executable gate**

```text
python -m pytest tests/test_application.py tests/test_cli.py -q
```

**Commit boundaries**

1. `Implement the VIPER application API`
2. `Route the VIPER CLI through the application API`

## Phase 4. Implement workspace, storage, and publication primitives

### 4.1 Frozen plan reference

- [ ] Make `RunRequest` identify the frozen plan through a Git repository,
  commit, and `RunSpec` path.
- [ ] Retrieve the `RunSpec` and every `RunStageRef` from that immutable plan
  snapshot.
- [ ] Verify the relationship between the plan snapshot and
  `RunSpec.source`.
- [ ] Keep local draft paths inside the authoring operation.

### 4.2 Attempt workspace

- [ ] Define the workspace root, control directory, source mount, verified input
  cache, stage directories, artifact roots, measurement files, logs, and local
  terminal document.
- [ ] Resolve every path beneath the workspace root.
- [ ] Reject path escape, symlink escape, and overlapping roots.
- [ ] Write control files atomically.
- [ ] Acquire one exclusive run lock before attempt allocation.
- [ ] Preserve recovery inputs until terminal publication succeeds.

### 4.3 Retrieval

- [ ] Define a byte-retrieval protocol for Git and Hugging Face references.
- [ ] Verify every retrieved SHA-256 and byte count.
- [ ] Store verified content in a content-addressed local cache.
- [ ] Reuse verified cached bytes during materialization.
- [ ] Add in-memory, Git, and Hugging Face retrieval tests.

### 4.4 Publication

Each publication request contains repository, repository type, expected parent
revision, canonical path set, content digests, and idempotency key.

- [ ] Publish stage snapshots, attempt files, terminal runs, and benchmark
  results through one interface.
- [ ] Record the idempotency key in the remote commit metadata.
- [ ] Adopt an existing commit carrying the same key after verifying its
  complete file set.
- [ ] Reject an existing key paired with different content.
- [ ] Define publication idempotence as one logical result reference for one
  idempotency key and content set.
- [ ] Verify every returned immutable reference after publication.
- [ ] Add in-memory and Hugging Face publication tests for first write, replay,
  conflict, crash adoption, and parent-revision movement.

### 4.5 Durable journal

- [ ] Append state transitions and external-effect intents before execution.
- [ ] Append verified results after each effect.
- [ ] Flush and synchronize each journal entry.
- [ ] Reconstruct the active attempt solely from the journal and verified remote
  references.
- [ ] Add crash-recovery tests at every external-effect boundary.

### 4.6 Worker interface and development backend

- [ ] Define one worker request containing the frozen source, effective
  environment, execution policy, mounts, context path, command, timeout, and
  cancellation channel.
- [ ] Define one worker result containing runtime evidence, output identities,
  exit status, signal, timestamps, and captured logs.
- [ ] Implement `trusted_local` for development execution through the worker
  interface.
- [ ] Report its host filesystem and network scope through capability
  discovery.
- [ ] Add lifecycle, timeout, cancellation, context, and output-discovery tests.

**Executable gate**

```text
python -m pytest tests/test_workspace.py tests/test_storage.py tests/test_publication.py tests/test_journal.py tests/test_worker.py -q
```

**Commit boundaries**

1. `Define immutable run requests and workspaces`
2. `Implement verified retrieval and caching`
3. `Implement idempotent result publication`
4. `Implement durable attempt journaling`
5. `Define workers and trusted local execution`

## Phase 5. Implement project extension interfaces

Each increment lands with its protocol fields, public interface, worker
behavior, focused tests, guide, and executable example.

Project code may use any repository layout. Every frozen implementation is
identified by a repository-relative Python path and top-level symbol. The
decorator, subclass, and parameter-model interfaces add authoring metadata to
ordinary project code.

### 5.1 Stage entrypoints

- [ ] Set `VIPER_CONTEXT_PATH` to the versioned context JSON file.
- [ ] Set the worker current directory to the attempt workspace.
- [ ] Add the frozen source root to `sys.path`.
- [ ] Select the interpreter from the effective environment.
- [ ] Map each input name to one mounted path in the context.
- [ ] Map each artifact name to one writable path in the context.
- [ ] Define exit status, timeout, termination signal, and cancellation result.
- [ ] Add a minimal project entrypoint example and worker test.

### 5.2 Artifact loaders

- [ ] Load the selected module and top-level `load(path)` symbol from the frozen
  source snapshot.
- [ ] Verify source repository, commit, path, SHA-256, and byte count before
  invocation.
- [ ] Invoke the loader through the worker interface.
- [ ] Supply one materialized file path or bundle root.
- [ ] Validate reserved artifact values through their core validators.
- [ ] Return a typed loadability result for generic artifacts.
- [ ] Add tests for trust, tampering, import failure, callable failure, and
  reserved-value validation.

### 5.3 Metrics

- [ ] Implement `MetricImplementationRef` with path, symbol, SHA-256, and byte
  count.
- [ ] Implement the stateless metric decorator.
- [ ] Implement `StatefulMetric` for values accumulated across updates.
- [ ] Resolve imports from the frozen source snapshot and effective
  environment.
- [ ] Build typed contexts from the metric's declared dependency bindings.
- [ ] Provide the runner-owned sink path through the execution context.
- [ ] Write one sequence-numbered JSON Lines measurement per append.
- [ ] Flush and synchronize each accepted append before acknowledging it.
- [ ] Close and validate the complete stream before publication.
- [ ] Recompute post-stage metrics through the worker interface.
- [ ] Apply the metric's declared comparator.
- [ ] Add stateless, stateful, diagnostic, recomputation, comparator, crash,
  ordering, and tampering tests.

### 5.4 Parameter validation

- [x] Keep the universal stage parameter classes fieldless and extensible.
- [x] Require each internal stage to bind a concrete project Pydantic class.
- [x] Resolve parameter classes from the frozen source snapshot.
- [x] Execute project validators through the trusted-local worker interface.
- [x] Record path, symbol, SHA-256, and byte count in the frozen stage spec.
- [x] Validate stage parameters during authoring, preflight, and execution.
- [x] Require strict types and exact equality between validated and frozen values.
- [x] Verify parameter-model identity during terminal run verification.
- [x] Add import, base-class, value-validation, worker, and tampering tests.

**Executable gate**

```text
python -m pytest tests/test_parameter_models.py tests/test_authoring.py tests/test_preflight.py tests/test_verifier.py tests/test_runner_acceptance.py -q
```

**Commit boundaries**

1. `Define project stage entrypoints`
2. `Define loadable artifact implementations`
3. `Implement frozen project metrics`
4. `Implement project parameter validation`

## Phase 6. Implement the OCI isolation worker

This phase targets the stable confinement release. VIPER 0.1 ships the trusted,
single-host GCE backend defined by the cloud execution contract.

- [ ] Detect the OCI runtime and required GCE host capabilities.
- [ ] Build the worker image from the frozen environment lock.
- [ ] Mount source and inputs read-only.
- [ ] Mount declared outputs and control files at explicit writable paths.
- [ ] Apply user, group, process, memory, CPU, GPU, and timeout limits.
- [ ] Disable network access for internal stages, loaders, metrics, and
  parameter validators.
- [ ] Route download traffic through the allow-list proxy.
- [ ] Supply operation-specific credentials through ephemeral mounted secrets.
- [ ] Capture command, image digest, mount map, capabilities, environment, exit
  status, signal, and timestamps.
- [ ] Implement graceful cancellation followed by enforced termination after
  the declared grace period.
- [ ] Run the adversarial matrix from `contracts/EXECUTION_CONFINEMENT.md`.

**Executable gate**

```text
python -m pytest tests/test_isolation_worker.py -q
```

A live GCE isolation smoke test also passes before release.

**Commit:** `Implement the GCE OCI execution worker`

## Phase 7. Implement preflight and verified input materialization

### 7.1 Preflight result

- [ ] Define stable `PreflightCheckCode` values.
- [ ] Return one `PreflightReport` containing every check result, target,
  severity, and evidence reference.
- [ ] Use `pass`, `warning`, and `failure` statuses.
- [ ] Define `ready` as the absence of failure results.
- [ ] Reserve application failures for conditions that prevent preflight from
  completing its report.

### 7.2 Complete checks

- [ ] Retrieve and verify the plan, stage specs, experiment, variant, benchmark,
  source implementations, environment lock, stored pointers, and stored
  artifacts.
- [ ] Reuse the verified content-addressed cache during execution.
- [ ] Validate stage order, unique identities, future-input producers, data
  roles, output paths, environment selection, runtime controls, metric
  dependencies, loader bindings, parameter bindings, and isolation
  capabilities.
- [ ] Inspect static source properties directly.
- [ ] Execute project validators through isolated workers.
- [ ] Give every check one fixture mutation and expected result in
  `tests/test_preflight.py`.

### 7.3 Materialization

- [ ] Materialize stored inputs at `StoredInputRef.path`.
- [ ] Materialize future artifacts at their canonical producer paths inside the
  consumer workspace.
- [ ] Include the input-name-to-path mapping in the execution context.
- [ ] Verify each materialized file after writing it.
- [ ] Preserve read-only permissions on source and inputs.
- [ ] Enumerate bundle members from the complete resolved member list.

**Executable gate**

```text
python -m pytest tests/test_preflight.py tests/test_materialization.py -q
```

**Commit boundaries**

1. `Implement complete-plan preflight`
2. `Materialize verified stage inputs`

## Phase 8. Implement the runtime bootstrap and controls

```text
runner
-> launch VIPER bootstrap
-> apply process controls
-> initialize supported generator services
-> load frozen project entrypoint
-> pass typed context
-> execute stage
```

- [ ] Apply environment variables and process-level numerical controls before
  importing project code.
- [ ] Initialize Python, NumPy, PyTorch CPU, PyTorch CUDA, and loader generators
  from the global run seed.
- [ ] Expose generator services through the public VIPER runtime context.
- [ ] Require stateful training loaders to use
  `torchdata.stateful_dataloader.StatefulDataLoader` for resumable execution.
- [ ] Record the realized GCE machine type, machine image, GPU model, GPU count,
  driver, CUDA runtime, Python interpreter, package lock digest, parallelism,
  and numerical controls.
- [ ] Compare the realized evidence with the effective stage environment and
  run-wide reproducibility controls.
- [ ] Capture one checkpoint at the terminal boundary of each training stage.
- [ ] State checkpoint continuation as inter-stage continuation.
- [ ] Add deterministic initialization, next-batch restoration, terminal
  checkpoint, environment mismatch, and GCE evidence tests.

**Executable gate**

```text
python -m pytest tests/test_runtime_bootstrap.py tests/test_resume.py -q
```

**Commit:** `Apply runtime controls through the VIPER bootstrap`

## Phase 9. Implement durable run orchestration

### 9.1 Attempt execution

- [ ] Acquire the run lock and allocate the next attempt ID.
- [ ] Create and synchronize the initial journal entry.
- [ ] Run complete preflight and store its report.
- [ ] Execute each stage selected by `RunSpec.stages` in order.
- [ ] Publish and verify each stage snapshot before recording its
  `ResolvedStageRef`.
- [ ] Invoke during-stage and post-stage metrics at their declared production
  points.
- [ ] Close measurements and logs before attempt-file publication.
- [ ] Construct the final `RunAttempt` with `succeeded`, `failed`, `preempted`,
  or `cancelled` status.
- [ ] Publish attempt files and verify their references.
- [ ] Construct and publish terminal `resolved.yaml`.
- [ ] Set `successful_attempt_id` exactly when one attempt succeeds.

### 9.2 Recovery

- [ ] Resume from every durable state using the journal.
- [ ] Adopt verified stage and attempt-file snapshots created before a crash.
- [ ] Resume terminal publication from the preserved local document.
- [ ] Reconcile orphaned snapshots by idempotency key.
- [ ] Require an explicit retry policy after failed, preempted, or cancelled
  attempts.
- [ ] Preserve each previous attempt in the next terminal run.

### 9.3 Logs

- [ ] Write one standard-output file and one standard-error file per stage
  invocation.
- [ ] Include attempt ID and stage ID in each canonical log path.
- [ ] Preserve logs from interrupted stages.
- [ ] Publish every closed log in the attempt-file snapshot.

### 9.4 Acceptance

- [ ] Add one complete two-stage run using a stored input and a future input.
- [ ] Produce one metric, stage snapshots, attempt files, and terminal
  `resolved.yaml`.
- [ ] Verify the terminal run through the public application operation.
- [ ] Reject tampered input, artifact, metric, log, and resolved-spec bytes.
- [ ] Add crash recovery after each publication boundary.
- [ ] Add preemption, cancellation, retry, and resume-publication tests.

**Executable gate**

```text
python -m pytest tests/test_runner.py tests/test_run_acceptance.py -q
```

**Commit boundaries**

1. `Execute frozen multi-stage runs`
2. `Publish terminal run provenance`
3. `Recover interrupted VIPER attempts`

## Phase 10. Implement benchmark execution and recomputation

- [ ] Implement `execute_benchmark()` to run one independent confirmation from
  the same frozen candidate plan.
- [ ] Keep `verify_benchmark()` as verification of supplied immutable evidence.
- [ ] Recompute each benchmark metric from its declared dependency list, typed
  context, frozen implementation, parameters, and comparator.
- [ ] Publish recomputed values and implementation identities in one immutable
  benchmark evidence file.
- [ ] Add the evidence reference to `BenchmarkResult`.
- [ ] Define estimator parity and prediction parity as equality of the complete
  resolved artifact descriptions: canonical paths, hashes, byte counts, and
  bundle membership.
- [ ] Apply benchmark thresholds after recomputation and parity checks.
- [ ] Add pass, threshold failure, recomputation mismatch, estimator mismatch,
  prediction mismatch, source mismatch, and reused-attempt tests.

**Executable gate**

```text
python -m pytest tests/test_benchmark_execution.py tests/test_benchmark_verification.py -q
```

**Commit boundaries**

1. `Execute independent benchmark confirmations`
2. `Verify recomputed benchmark evidence`

## Phase 11. Add agent inspection and controlled mutation

### 11.1 Immutable inspection

- [x] Implement `plan_diff()` from two frozen plans.
- [x] Implement upstream `lineage()` from supplied immutable records.
- [x] Implement `compare_runs()` from two verified terminal runs.
- [x] Return validated JSON models with stable field names and ordering.

### 11.2 Active coordination

- [x] Expose read-only `status()` for one local durable attempt journal.
- [ ] Implement `status()` from a coordinator identity, workspace identity, and
  access policy.
- [ ] Derive the next permitted operation from the durable attempt state.
- [ ] Build downstream lineage through an explicit published index.
- [ ] Add dry-run result models that list exact reads and writes for `run`,
  `retry`, `resume-publication`, and `promote`.
- [ ] Require the caller to submit the matching dry-run identity with each
  mutation.

**Executable gate**

```text
python -m pytest tests/test_inspection.py tests/test_coordination.py -q
```

**Commit boundaries**

1. `Add immutable VIPER inspection operations`
2. `Add coordinator status and dry-run mutations`

## Phase 12. Split internals at established dependency boundaries

This phase changes internal ownership and lowers maintenance cost. Runtime
behavior stays unchanged. Begin it after the 0.1 public surface and verifier
rules stabilize.

- [ ] Use the Phase 1 public import inventory as the compatibility contract.
- [ ] Keep pure Pydantic protocol validation separate from retrieval, worker
  execution, and remote verification.
- [ ] Split `protocol.py` only where the frozen metric and runner contracts
  produce stable module boundaries.
- [ ] Split verifier internals into file, plan, stage, run, promoted-artifact,
  and benchmark verification modules.
- [ ] Re-export supported names through `viper.protocol` and `viper.verifier`.
- [ ] Run installed-wheel import and complete verifier acceptance tests after
  each split.
- [ ] Defer any split whose boundary remains coupled after Phase 11.

**Executable gate**

```text
python -m pytest tests/test_public_api.py tests/test_verifier_acceptance.py -q
```

**Commit boundaries**

1. `Modularize VIPER protocol internals`
2. `Modularize VIPER verifier internals`

## Phase 13. Complete documentation and release validation

Documentation lands with each public increment. Phase 13 performs the final
cross-document pass.

### 13.1 Documentation

- [ ] Reconcile README, protocol, application API, public API, execution
  security, attempt lifecycle, development guide, examples, and this roadmap.
- [ ] Include one complete user-project example from authoring through verified
  execution.
- [ ] Include extension guides for entrypoints, loaders, metrics, and parameter
  models.
- [ ] Include agent guides for schema discovery, preflight, inspection, dry-run,
  and mutation.
- [ ] Implement and document the `viper init` starter project defined by the
  [package release contract](contracts/PACKAGE_RELEASE.md).
- [ ] Run link, example, prose, and rendered-document checks.

### 13.2 Deterministic release checks

- [ ] Run Ruff, Pyright, and the complete pytest suite.
- [ ] Build the source distribution and wheel from a temporary checkout.
- [ ] Run metadata checks on both distributions.
- [ ] Install the wheel into a clean environment for every advertised Python
  version.
- [ ] Run public-import, CLI, schema, capability, and complete-run smoke tests
  from each installed wheel.
- [ ] Confirm successful remote CI for the exact release commit.

### 13.3 Platform and publication checks

- [ ] Run a complete live GCE execution through the trusted single-host backend.
- [ ] Verify the published run from a clean client environment.
- [ ] Add owner-approved license and author metadata.
- [ ] Publish to TestPyPI with owner-provided credentials.
- [ ] Install and verify the TestPyPI distribution.
- [ ] Publish the approved release to PyPI.
- [ ] Install and verify the PyPI distribution.
- [ ] Tag the verified release commit according to the version policy.

### 13.4 Release report

Publish one report with separate results for:

- deterministic local validation;
- installed-wheel validation;
- remote CI matrix;
- live GCE execution;
- TestPyPI publication; and
- PyPI publication.

**Commit:** `Prepare VIPER 0.1 release candidate`

## Current execution charter

The active six-hour session is defined in the
[August 22 execution charter](8-22-OVERNIGHT_PLAN.md). The charter selects the
largest coherent prefix of this roadmap that fits the available time and ends
with a complete validation and Git handoff.
