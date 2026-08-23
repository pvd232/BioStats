# VIPER 0.1 master execution checklist

This file is the single implementation and publication checklist for
`viper-provenance==0.1.0a1`. The
[protocol](ProvenanceS1_v3.md) owns serialized provenance semantics. The
[application API](APPLICATION_API.md) owns public operations. The
[contract index](contracts/README.md) owns the mechanics required to support
each release claim.

## Contents

1. [Release boundary](#release-boundary)
2. [Checklist rules](#checklist-rules)
3. [Contract coverage](#contract-coverage)
4. [Implemented baseline](#implemented-baseline)
5. [Phase 0: specification audit](#phase-0-audit-the-contract-stack)
6. [Phase 1: stage invocation and process startup](#phase-1-implement-stage-invocation-and-process-startup)
7. [Phase 2: controlled HTTP retrieval](#phase-2-implement-controlled-http-retrieval)
8. [Phase 3: artifact validation](#phase-3-close-artifact-validation)
9. [Phase 4: metric provenance](#phase-4-close-metric-provenance)
10. [Phase 5: durable attempts and retry](#phase-5-implement-durable-attempts-and-retry)
11. [Phase 6: benchmark execution](#phase-6-implement-benchmark-execution)
12. [Phase 7: local and GCE execution](#phase-7-generalize-execution-across-local-and-gce-hosts)
13. [Phase 8: public interface and project scaffold](#phase-8-freeze-the-public-interface-and-project-scaffold)
14. [Phase 9: release candidate](#phase-9-build-and-validate-the-release-candidate)
15. [Phase 10: publication](#phase-10-publish-viper-010a1)
16. [Deferred work](#deferred-work)

## Release boundary

VIPER 0.1 is ready when an installed wheel can execute and verify one complete
project on a trusted local machine and a trusted, pre-provisioned GCE instance.
The project may start through its ordinary decorated Python module or the
generic `viper run` command. Both interfaces submit the same frozen plan to one
application coordinator.

The release must complete this path:

```text
author project extensions
-> freeze plan
-> preflight plan
-> execute ordered stages
-> publish stage and attempt evidence
-> verify terminal run
-> execute benchmark confirmation
-> verify benchmark result
```

The alpha release trusts the project source named by `RunSpec.source` and the
single host on which VIPER runs. The user's infrastructure tooling owns VM
provisioning, terminal access, source placement, and cloud-resource lifecycle.

Five owner inputs enter at fixed points:

| Owner input | Required by |
|---|---|
| Package license | Phase 9 metadata gate |
| Author names and contact metadata | Phase 9 metadata gate |
| TestPyPI credentials | Phase 10 TestPyPI upload |
| PyPI publication authorization | Phase 10 PyPI upload |
| Release-tag signing identity and configuration | Phase 10 signed tag |

## Checklist rules

A checkbox closes after its code, tests, examples, and public documentation
agree. Complete each phase in document order.

Every implementation phase ends with this repository gate:

```bash
ruff check viper tests examples/project/src tools
pyright --pythonpath "$(command -v python)"
python -m pytest -q
git diff --check
```

Each listed commit boundary receives a focused commit and a successful push.
The local branch and `origin/main` must identify the same commit before the next
phase begins.

When implementation reveals an incomplete contract, revise the owning file in
`docs/contracts/`, review that revision, and resume implementation from the
approved text.

Each phase also updates the affected sections of `ProvenanceS1_v3.md`. A phase
closes when its implementation contract, formal protocol, public API,
implementation, and tests describe the same fields and guarantees.

Items marked **Owner input** require a licensing, identity, credential, or
publication decision from the package owner.

## Contract coverage

Every implementation contract appears once in the execution sequence.

| Contract | Current status | Execution phase | Completion evidence |
|---|---|---|---|
| [Parameter models](contracts/PARAMETER_MODELS.md) | Implemented | Regression coverage in Phases 1 and 2 | The exact project class validates the frozen parameter mapping. Phase 1 owns typed delivery. |
| [Stage invocation](contracts/STAGE_INVOCATION.md) | Approved | Phase 1 | The frozen callable receives the typed parameters and declared paths. |
| [Process startup](contracts/PROCESS_STARTUP.md) | Approved | Phase 1 | The controlled child records its startup environment, applied controls, generator initialization, generator delivery, and observed runtime. |
| [HTTP retrieval](contracts/HTTP_RETRIEVAL.md) | Approved | Phase 2 | Each declared input binds its frozen request, expected body identity, selected transport, terminal response, external executable identity, and delivered context handle. |
| [Artifact validation](contracts/ARTIFACT_VALIDATION.md) | Approved | Phase 3 | The verifier reports representation identity, loadability, or reserved semantic validity at its established level. |
| [Metric provenance](contracts/METRIC_PROVENANCE.md) | Approved | Phase 4 | Recomputed metrics bind exact dependencies and two run-owned worker executions; live metrics bind a controlled metric handle and measurement sink. |
| [Attempt execution](contracts/ATTEMPT_EXECUTION.md) | Approved | Phase 5 | Each attempt has an immutable document and journal; retry allocates a greater ID and preserves every prior reference. |
| [Benchmark execution](contracts/BENCHMARK_EXECUTION.md) | Approved | Phase 6 | `execute_benchmark()` produces one independent confirmation and persists the artifact and metric comparison receipts accepted by `verify_benchmark()`. |
| [Cloud execution](contracts/CLOUD_EXECUTION.md) | Approved | Phase 7 | The installed wheel executes in place on GCE and verifies the host, backend, and exact Python environment. |
| [Package release](contracts/PACKAGE_RELEASE.md) | Approved | Phases 8–10 | Clean installations complete the documented project path from TestPyPI and PyPI. |

## Implemented baseline

The current repository supplies the foundation consumed by Phase 1:

- [x] Pydantic models for authored stages, resolved stages, run attempts,
  terminal runs, evaluations, artifact pointers, and benchmark results.
- [x] Canonical YAML parsing and run-plan freezing.
- [x] Project-defined parameter classes with source identity and strict value
  validation.
- [x] Training, validation, evaluation, and benchmark data-role enforcement.
- [x] Resume-state capture and restoration for zero-worker and multiprocess
  `StatefulDataLoader` execution.
- [x] Successful trusted-local execution of an ordered two-stage plan.
- [x] Verified input materialization, immutable local snapshots, measurements,
  logs, terminal `resolved.yaml`, and terminal run verification.
- [x] Metric decorators, measurement writing, floating-point comparators, and
  post-stage recomputation.
- [x] Benchmark verification from supplied candidate and confirmation
  evidence.
- [x] Typed application operations, JSON dispatch, CLI parsing, schema
  discovery, capability discovery, plan comparison, run comparison, lineage,
  and attempt status.
- [x] Build configuration, a four-version CI matrix, and installed-wheel import
  smoke commands.
- [x] Ruff, Pyright, 130 tests, and 13 subtests at audit baseline `6228ee6`.

### Named verifier-rule coverage

Each implementation phase must add the rules owned by its contract and the
rejection tests named there.

| Contract | Verifier rules |
|---|---|
| Artifact validation | `artifact.representation`, `artifact.bundle`, `artifact.loader`, `artifact.loadability`, `artifact.semantic.resume_state` |
| Attempt execution | `attempt.order`, `attempt.terminal`, `attempt.identity`, `attempt.files`, `attempt.failure`, `attempt.invocations`, `attempt.retry`, `attempt.purpose` |
| Benchmark execution | `benchmark.plan`, `benchmark.confirmation`, `benchmark.artifacts`, `benchmark.metrics`, `benchmark.status` |
| Cloud execution | `environment.kind`, `gce.boot_image`, `gce.machine_type`, `gce.compute`, `gce.lockfile`, `gce.python`, `runtime.controls`, `run.result` |
| HTTP retrieval | `http.input`, `http.request`, `http.policy`, `http.credentials`, `http.transport.identity`, `http.transport.parameters`, `http.transport.executable`, `http.response`, `http.content`, `http.delivery`, `parameter_model.identity`, `parameter_model.validation`, `stage.source`, `artifact.files` |
| Metric provenance | `metric.implementation`, `metric.dependencies`, `metric.parameters`, `metric.measurement`, `metric.production`, `metric.environment`, `metric.recompute`, `metric.live_execution` |
| Process startup | `startup.plan`, `startup.environment`, `startup.controls`, `startup.randomness`, `startup.callable`, `startup.context`, `startup.runtime`, `startup.backend`, `startup.distributed`, `startup.outcome` |
| Stage invocation | `stage.implementation`, `stage.decorator`, `parameter_model.identity`, `parameter.value`, `stage.context`, `stage.outcome` |

## Phase 0. Audit the contract stack

**Scope:** all ten files in `docs/contracts/`, the formal protocol, the public
API specifications, the master checklist, implementation modules, verifier
rules, and declared acceptance tests.

- [x] Parse every Python model shown in a contract.
- [x] Compare repeated contract and protocol classes field by field.
- [x] Construct every implemented Pydantic protocol schema.
- [x] Trace each claim-bearing value from its producer to verifier
  reconstruction.
- [x] Map each release requirement to its protocol field, runtime operation,
  persisted evidence, verifier rule, and acceptance test.
- [x] Write one minimal counterexample for each contract's required claim and
  name the rejecting check.
- [x] Compare the contract, protocol, public API, checklist, implementation,
  and tests; record every design-state discrepancy.
- [x] Record the results and approval decision in
  `docs/contracts/AUDIT.md`.
- [x] Run `python tools/audit_contracts.py` and its focused tests.

**Focused gate**

```bash
python tools/audit_contracts.py
python -m pytest tests/test_contract_audit.py -q
```

**Commit boundaries**

1. `Consolidate approved VIPER contracts`
2. `Add deterministic contract auditing`
3. `Record the full contract-system audit`

## Phase 1. Implement stage invocation and process startup

**Contracts:** [Stage invocation](contracts/STAGE_INVOCATION.md) and
[Process startup](contracts/PROCESS_STARTUP.md).

### Protocol and authoring

- [x] Add `StageImplementationRef` with repository-relative path, top-level
  symbol, SHA-256, and byte count.
- [x] Replace each parameterized stage's `script` field with
  `implementation: StageImplementationRef`.
- [x] Add `StageContextBinding`, its canonical digest rule, and
  `StageInvocationReceipt` to attempt evidence.
- [ ] Add `ResolvedStageInvocationRef`; store each successful stage's reference
  on its resolved stage and every started invocation on `RunAttempt`.
- [x] Add `ProcessStartupReceipt` with the allowlisted child environment,
  applied controls, and one initialized-state digest for each configured
  generator.
- [x] Update `ProvenanceS1_v3.md` with the callable, context, receipt, and
  process-startup relationships.
- [x] Add one public decorator for each stage kind.
- [x] Resolve decorator metadata into the frozen implementation and parameter
  model references.

### Runtime

- [x] Add generic `StageContext` with typed parameters, materialized input
  paths, writable artifact paths, a metric-handle mapping, run ID, attempt ID,
  and stage ID. Phase 1 supplies an empty mapping; Phase 4 binds the handles.
- [x] Return every configured named NumPy generator from child initialization
  and expose it through `StageContext.numpy_generators`.
- [x] Store the sorted generator names in `StageContextBinding` and verify them
  against `RunSpec.reproducibility` and `ProcessStartupReceipt`.
- [x] Construct the versioned logical `StageContextBinding` before resolving
  attempt-local absolute paths.
- [x] Add `viper.run(stage_callable)` as the ordinary Python adapter.
- [x] Bind `--stage` to the callable launched by the project module and execute
  every stage in `RunSpec.stages` order.
- [x] Rename `run_local()` and its request/result models to the host-neutral
  `run()` operation.
- [x] Rename `viper run-local` to `viper run`.
- [x] Derive the canonical child-process environment from
  `RunSpec.reproducibility` and the stage's effective environment.
- [x] Permit `CPUComputeSpec` and single-device `CUDAComputeSpec` on local
  environments; reject `CUDAComputeSpec.count > 1` with
  `startup.distributed`.
- [x] Launch each stage in one controlled child carrying
  `VIPER_CONTEXT_PATH`.
- [x] Apply library controls before importing the frozen callable.
- [x] Select the CPU or CUDA backend from the effective compute request and
  expose one matching CUDA device to a CUDA child process.
- [x] Observe the host `CPUContext` and the selected
  `ComputeBackendContext` inside the child process.
- [x] Validate parameters into the exact project class and place that object in
  `StageContext.params`.
- [x] Construct `StageContext.inputs` from the stage's declared,
  role-permitted inputs.
- [x] Invoke the frozen callable once and persist its invocation receipt at the
  attempt-level canonical path.

### Verification and acceptance

- [x] Verify implementation identity, decorator metadata, parameter identity,
  parameter digest, canonical context binding, startup environment, applied
  controls, initialized-generator receipts, and invocation outcome.
- [x] Replace constant fixture scripts with decorated functions that consume
  their typed parameters and declared paths.
- [ ] Prove that `python train.py --run RUN --stage train` and `viper run RUN`
  produce terminal results accepted by the same verifier.
- [ ] Prove that a CPU stage on a GPU-capable host records
  `CPUBackendContext`, while a one-L4 CUDA stage records the matching
  `CUDABackendContext`.
- [ ] Reject a changed callable, parameter mapping, context binding, and second
  invocation.
- [ ] Reject unavailable CUDA, a changed device model, and a CUDA device count
  greater than `1` through their named startup checks.

**Focused gate**

```bash
python -m pytest tests/test_stage_invocation.py tests/test_process_startup.py \
  tests/test_runner_acceptance.py tests/test_application.py tests/test_cli.py -q
```

**Commit boundaries**

1. `Define frozen stage callables and typed contexts`
2. `Apply run controls through the stage child process`
3. `Route Python and CLI execution through one coordinator`

## Phase 2. Implement controlled HTTP retrieval

**Contract:** [HTTP retrieval](contracts/HTTP_RETRIEVAL.md).

### Protocol and authoring

- [x] Add `HttpRequestSpec`, `EnvironmentSecretRef`, and
  `HttpRetrievalPolicy`.
- [x] Require an expected SHA-256 and byte count for every experimental HTTP
  request.
- [x] Add `HttpOrigin`; scope each credential reference to one or more
  authorized origins.
- [ ] Replace `RemoteFileRef` inputs on `DownloadSpec` with frozen HTTP request
  specifications.
- [ ] Add the built-in and project `HttpTransportSpec` variants and require one
  selected transport on each `DownloadSpec`.
- [ ] Add `HttpTransportImplementationRef`, `HttpTransportParams`, and the
  `http_transport()` decorator.
- [x] Add frozen external executable requirements to each project transport.
- [ ] Resolve decorated project transports to an exact callable, parameter
  class, and frozen parameter mapping.
- [ ] Store one resolved retrieval per declared input on
  `ResolvedDownloadSpec`.
- [ ] Bind each retrieval to its input name, frozen request, terminal response,
  selected transport, and completed body.
- [x] Add `ResolvedHttpTransport` and `ResolvedExternalExecutable` so a project
  adapter identifies its Python wrapper and every external transfer binary.
- [ ] Expand URL templates during authoring and freeze the canonical request.
- [ ] Reject literal authorization values and preserve secret references.

### Runtime

- [ ] Add HTTPX as the built-in transport and pin it through the package and
  effective Python-environment contracts.
- [ ] Construct `HttpTransportContext` and invoke either the built-in transport
  or the exact decorated project transport selected by the stage.
- [ ] Enforce scheme, host, port, accepted-status, redirect-count, body-size,
  and timeout limits through
  `HttpRetrievalPolicy`.
- [ ] Resolve credentials at execution time through `EnvironmentSecretRef`.
- [ ] Inject each secret into its declared HTTP header and redact its value
  from requests, receipts, logs, errors, and JSON results.
- [ ] Strip a credential on a cross-origin redirect unless the destination
  appears in its frozen authorized-origin set.
- [ ] Assign each transport a dedicated retrieval workspace and exact body
  destination; reject returned path escape and symlinks.
- [ ] Hash and store each completed body before project download code runs.
- [ ] Resolve and verify every frozen external executable before transport
  invocation; supply only verified executable paths to the transport context.
- [ ] Require every successful transport to return its terminal HTTP response.
- [ ] Verify the expected body identity before project download code runs.
- [ ] Add `DownloadContext` as the `StageContext` extension that exposes typed
  `DownloadParams` and one verified retrieval handle per input.
- [ ] Treat redirects and segmented range requests as internal operations of
  one transport invocation.
- [ ] Keep dynamic pagination and scraping in discovery processes that publish
  immutable inputs for later experimental plans.
- [ ] Deliver only verified retrieval handles through the download context.
- [ ] State the 0.1 trusted-project-source boundary in public documentation;
  complete network confinement remains deferred.

### Verification and acceptance

- [ ] Verify every frozen request, credential origin, selected transport,
  transport parameters, preflight executable identity, terminal response,
  expected body identity, resolved body identity, stage implementation, and
  published artifact.
- [ ] Add one reusable transport conformance suite for the built-in HTTPX
  transport and decorated project transports.
- [ ] Require each transport to reject an unaccepted terminal HTTP status.
- [ ] Exercise one static request, redirect, range-capable source, secret
  reference, unauthorized credential origin, request-policy failure, returned
  path escape, missing executable, modified transport source, and same-length
  body tampering.
- [ ] Prove that the acceptance download callable consumes the response selected
  by its frozen request.

**Focused gate**

```bash
python -m pytest tests/test_http_retrieval.py tests/test_stage_invocation.py \
  tests/test_runner_acceptance.py tests/test_verifier.py -q
```

**Commit boundaries**

1. `Define selectable HTTP transports and logical retrievals`
2. `Add decorated project HTTP transports`
3. `Execute retrievals through the selected transport`
4. `Verify HTTP retrieval provenance`

## Phase 3. Close artifact validation

**Contract:** [Artifact validation](contracts/ARTIFACT_VALIDATION.md).

- [ ] Add `ArtifactLoaderRef` with path, symbol, SHA-256, and byte count.
- [ ] Replace artifact loader IDs and paths with exact implementation
  references.
- [ ] Rename the verifier policy field to `trusted_source_repositories` and the
  CLI option to `--trust-source`; apply it to every project code path executed
  during verification.
- [ ] Enumerate every regular bundle member during publication and reject
  symlinks, path escape, missing members, and unrecorded members.
- [ ] Invoke project loaders through the trusted stage-worker boundary.
- [ ] Report generic loader success as `artifact.loadability`.
- [ ] Apply core semantic validation to the reserved `resume_state` artifact.
- [ ] Update verifier errors and protocol prose to distinguish representation
  identity, loadability, and reserved semantic validity.
- [ ] Exercise single-file loading, bundle loading, missing and extra members,
  same-length tampering, loader tampering, loader failure, and invalid
  `resume_state`.
- [ ] Run the maintained project's interruption-and-resumption case and compare
  its resumed terminal state with the uninterrupted execution.

**Focused gate**

```bash
python -m pytest tests/test_artifact_loaders.py tests/test_artifact_validation.py \
  tests/test_verifier.py tests/test_verifier_acceptance.py -q
```

**Commit boundaries**

1. `Bind artifacts to exact loader implementations`
2. `Verify artifact representation and loadability`
3. `Validate reserved artifact semantics`

## Phase 4. Close metric provenance

**Contract:** [Metric provenance](contracts/METRIC_PROVENANCE.md).

### Protocol and authoring

- [ ] Add `MetricImplementationRef`, `MetricDependency`,
  `ResolvedMetricDependency`, `MetricMode`, `MetricExecutionReceipt`, and
  `MetricVerificationReceipt`.
- [ ] Add run ID and attempt ID to `MetricExecutionReceipt`; require both
  worker receipts to select the measurement's run and attempt.
- [ ] Use one `MetricSpec`; its `mode` selects `recompute` or `live` execution.
- [ ] Require one comparator for every recomputed floating-point metric.
- [ ] Freeze decorator metadata, dependencies, parameters, and implementation
  identity into `MetricSpec`.
- [ ] Require benchmark criteria to select evaluation metrics with
  `mode="recompute"`.

### Runtime and verification

- [ ] Construct each recomputed `MetricContext` from its declared file
  dependencies.
- [ ] Inject live metric handles into `StageContext` and bind their
  output to the active `MeasurementSink`.
- [ ] Implement `MetricHandle.update()` and `record()` for function
  and stateful metric implementations.
- [ ] Enforce every dependency's data role before invoking metric code.
- [ ] Record live measurements through the runner-owned
  `MeasurementSink`.
- [ ] Invoke recomputed metrics through a dedicated controlled worker for
  measurement production.
- [ ] Launch a second dedicated worker for independent recomputation.
- [ ] Persist both `MetricExecutionReceipt` values in one
  `MetricVerificationReceipt`.
- [ ] Verify implementation identity, dependency identity, parameters,
  startup evidence, runtime context, measurement ownership, and comparator
  outcome.
- [ ] Exercise stateless evaluation, stateful training, diagnostic,
  recomputation, tolerance, undeclared dependency, ordering, and tampering
  cases.

**Focused gate**

```bash
python -m pytest tests/test_metric_interface.py tests/test_metric_provenance.py \
  tests/test_runner_acceptance.py tests/test_verifier.py -q
```

**Commit boundaries**

1. `Bind metrics to exact implementations and dependencies`
2. `Restrict metric contexts to declared values`
3. `Persist and verify recomputed metric evidence`

## Phase 5. Implement durable attempts and retry

**Contract:** [Attempt execution](contracts/ATTEMPT_EXECUTION.md).

- [ ] Replace the stale-file lock with an operating-system-managed advisory
  lock scoped to one run.
- [ ] Allocate `max(persisted attempt IDs) + 1` while holding that lock.
- [ ] Write the allocation event before preflight begins.
- [ ] Persist every attempt transition before its associated side effect.
- [ ] Write one standard-output file and one standard-error file for each stage
  invocation.
- [ ] Preserve every verified stage snapshot completed before an attempt ends.
- [ ] Persist one `StageInvocationReceipt` for every started stage and include
  its `ResolvedStageInvocationRef` in `RunAttempt.invocations`.
- [ ] Close and publish attempts with `succeeded`, `failed`, `cancelled`, or
  `preempted` status.
- [ ] Replace `failure_reason` with typed `AttemptFailure`.
- [ ] Publish every attempt as
  `attempts/<attempt_id>/resolved.yaml`; place its journal, measurements,
  metric-verification receipts, and logs beneath the same attempt directory;
  store one immutable `ResolvedAttemptRef` in the terminal run.
- [ ] Add `AttemptJournalRef` and metric-verification files to `RunAttempt`.
- [ ] Add attempt purpose; keep ordinary attempts in `ResolvedRun` and bind the
  independent confirmation directly to `BenchmarkResult`.
- [ ] Map `SIGINT` to cancellation, map `SIGTERM` to preemption, and reconcile
  an abandoned journal as `coordinator_lost`; journal each observed event.
- [ ] Reconcile an abandoned nonterminal journal as `coordinator_lost` after
  acquiring its released lock.
- [ ] Add `retry()` and `viper retry`; each retry uses the same frozen plan and
  the next attempt ID.
- [ ] Verify attempt ordering, terminal status, failure identity, attempt files,
  and retry plan identity.
- [ ] Exercise a failed first attempt, a successful retry, stale ownership,
  cancellation, preemption, and tampered prior evidence.

**Focused gate**

```bash
python -m pytest tests/test_attempt_execution.py tests/test_worker.py \
  tests/test_runner_acceptance.py tests/test_verifier_acceptance.py -q
```

**Commit boundaries**

1. `Allocate and journal durable run attempts`
2. `Publish terminal failure evidence`
3. `Retry frozen runs with preserved history`

## Phase 6. Implement benchmark execution

**Contract:** [Benchmark execution](contracts/BENCHMARK_EXECUTION.md).

- [ ] Add `ExecuteBenchmarkRequest`, `ExecuteBenchmarkSuccess`, and the
  `execute_benchmark()` application operation.
- [ ] Replace `BenchmarkSpec.confirmation_count` with
  `execution_count: Literal[2]`; the count covers one candidate and one
  confirmation.
- [ ] Add typed artifact-comparison and metric-criterion receipts to
  `BenchmarkResult`.
- [ ] Add the `viper execute-benchmark` command with human and JSON output.
- [ ] Verify the candidate run before allocating confirmation attempts.
- [ ] Execute the same frozen plan for the one confirmation required by
  `BenchmarkSpec.execution_count`.
- [ ] Preserve distinct stage snapshots and attempt-file snapshots for each
  confirmation.
- [ ] Recompute every benchmark metric through its Phase 4 dependency contract.
- [ ] Compare complete `parameters` and `predictions` artifact descriptions.
- [ ] Apply every metric threshold after recomputation and parity checks.
- [ ] Construct, publish, and verify `BenchmarkResult` before returning success.
- [ ] Exercise passing confirmation, threshold failure, metric mismatch,
  parameter mismatch, prediction mismatch, source mismatch, and reused-attempt
  rejection.

**Focused gate**

```bash
python -m pytest tests/test_benchmark_execution.py \
  tests/test_verifier_acceptance.py tests/test_application.py tests/test_cli.py -q
```

**Commit boundaries**

1. `Execute independent benchmark confirmations`
2. `Publish and verify benchmark results`

## Phase 7. Generalize execution across local and GCE hosts

**Contract:** [Cloud execution](contracts/CLOUD_EXECUTION.md).

### Protocol and runtime

- [ ] Replace `GCEMachineImageRef` with immutable `GCEBootImageRef` containing
  project, image name, and server-defined image ID.
- [ ] Replace `machine_image` fields with `boot_image` on requested and resolved
  GCE environments.
- [ ] Add `PythonEnvironmentSpec` with the exact Python version and normalized,
  sorted installed-distribution mapping.
- [ ] Resolve the boot-image ID during plan freezing.
- [ ] Generalize preflight from the local-only check to the effective
  environment selected for each stage.
- [ ] Add GCE project, boot-image, machine-type, zone, guest OS, kernel, CPU,
  CUDA, driver, and numerical-runtime observation.
- [ ] Compare the realized environment with the stage environment override or
  shared run environment selected by the plan.
- [ ] Publish the same workspace, snapshots, journal, and terminal run files on
  local and GCE hosts.

### Acceptance

- [ ] Exercise deterministic local CPU, local CUDA, GCE CPU, and GCE CUDA
  fixtures.
- [ ] Reject boot-image, machine-type, accelerator, lockfile, Python
  environment, and numerical-control mismatches.
- [ ] Build and install the Phase 7 wheel on the designated L4 VM.
- [ ] Execute the maintained acceptance project from the existing SSH terminal with
  `python train.py` and `viper run`.
- [ ] Verify the completed GCE run through a clean installed-wheel process.

**Focused gate**

```bash
python -m pytest tests/test_runtime.py tests/test_cloud_execution.py \
  tests/test_preflight.py tests/test_runner_acceptance.py -q
```

**Commit boundaries**

1. `Model immutable GCE boot environments`
2. `Observe and verify GCE runtimes`
3. `Verify in-place GCE execution`

## Phase 8. Freeze the public interface and project scaffold

**Contract:** [Package release](contracts/PACKAGE_RELEASE.md).

### Application and CLI

- [ ] Freeze stable error codes for request, retrieval, conflict, execution,
  verification, publication, cancellation, and internal failures.
- [ ] Apply the approved redaction policy to serialized failures.
- [ ] Canonicalize paths, UTC datetimes, bytes, sets, and mappings in JSON
  results.
- [ ] Add golden JSON fixtures for every public success and failure family.
- [ ] Route warnings into JSON result models.
- [ ] Capture output and exit status for every CLI command in acceptance tests.
- [ ] Freeze one `PreflightCheckCode` for every release-gated preflight rule.
- [ ] Freeze the operation, schema, capability, decorator, context, and helper
  imports listed in `PUBLIC_API.md`.
- [ ] Include `retry`, `execute_benchmark`, and `init_project` in application
  dispatch, CLI dispatch, schema discovery, and capability discovery.

### Project scaffold and guides

- [ ] Implement `viper init PATH --package PROJECT_PACKAGE` for an absent or
  empty target directory.
- [ ] Generate one five-stage example whose repository-relative spec paths
  work with any project package name and directory layout:

  ```text
  download -> build -> embed -> train -> evaluate
  ```

  The example includes project parameter models, one evaluation metric,
  artifact loaders, one experiment, one benchmark, and focused project tests.
- [ ] Make the generated project freeze, preflight, run, benchmark, and verify
  immediately after creation.
- [ ] Add concise guides for stage callables, parameter models, HTTP downloads,
  metrics, artifact loaders, retries, benchmarks, and GCE execution.
- [ ] Reconcile README, protocol, application API, public API, contract index,
  examples, and this checklist.

**Focused gate**

```bash
python -m pytest tests/test_application.py tests/test_application_json.py \
  tests/test_cli.py tests/test_public_api.py tests/test_project_init.py -q
```

**Commit boundaries**

1. `Freeze VIPER application results and public imports`
2. `Generate a complete VIPER starter project`
3. `Document the installed user path`

## Phase 9. Build and validate the release candidate

### Package metadata

- [ ] **Owner input:** select and add the package license.
- [ ] **Owner input:** confirm author names and contact metadata.
- [ ] Confirm the repository and documentation project URLs.
- [ ] Set the distribution version to `0.1.0a1`.
- [ ] Confirm classifiers and supported Python versions against the tested CI
  matrix.

### Deterministic release gate

- [ ] Run the repository gate from a clean checkout.
- [ ] Build the source distribution and wheel.
- [ ] Run `twine check` on both distributions.
- [ ] Install the wheel into clean Python 3.11, 3.12, 3.13, and 3.14
  environments.
- [ ] Run every public import, schema, capability, CLI help, and JSON smoke test
  from the installed wheel.
- [ ] Create the scaffold outside the VIPER checkout and execute its complete
  local run and benchmark.
- [ ] Complete the live GCE acceptance case from the same wheel.
- [ ] Require successful remote CI for the exact candidate commit.
- [ ] Record every command, result, environment, and distribution digest in the
  release-candidate report.

**Release-candidate gate**

```bash
python -m build
python -m twine check dist/*
```

The release report supplies the clean-environment and GCE commands because
those checks execute outside this repository environment.

**Commit:** `Prepare VIPER 0.1.0a1 release candidate`

## Phase 10. Publish VIPER 0.1.0a1

- [ ] **Owner input:** provide TestPyPI credentials through the configured
  credential provider.
- [ ] Publish the validated source distribution and wheel to TestPyPI.
- [ ] Install `viper-provenance==0.1.0a1` from TestPyPI in a clean environment.
- [ ] Repeat the scaffold, local execution, benchmark, verification, and public
  API smoke tests against the TestPyPI installation.
- [ ] Confirm that the TestPyPI file digests equal the release-candidate
  digests.
- [ ] **Owner input:** authorize publication of the validated files to PyPI.
- [ ] **Owner input:** provide the release-tag signing identity and signing
  configuration.
- [ ] Publish those exact files to PyPI.
- [ ] Install `viper-provenance==0.1.0a1` from PyPI in a clean environment.
- [ ] Repeat the installed-package smoke and complete example tests.
- [ ] Create the signed tag `v0.1.0a1`, verify its signature, and push the tag.
- [ ] Publish the final release report with local, CI, GCE, TestPyPI, and PyPI
  results.
- [ ] Verify that `main`, `origin/main`, and the release tag identify the
  validated release commit.

## Deferred work

The following workstreams begin after `0.1.0a1`:

- OCI mounts, network confinement, secret mounts, resource limits, and
  adversarial execution tests.
- Crash adoption across hosts, partial-publication recovery, and durable remote
  object-store publication.
- Multi-GPU distributed execution: assign one child process and CUDA device to
  each rank, initialize the process group, persist rank-local runtime and replay
  state, and verify collective membership.
- Epoch-completion receipts and `OversightPolicy` capability requirements.
- Agent mutation dry-runs and downstream-lineage indexing.
- Internal splits of `protocol.py` and `verifier.py` after their public
  boundaries stabilize.
- Additional built-in metrics, loaders, retrieval strategies, and graphical
  interfaces.
