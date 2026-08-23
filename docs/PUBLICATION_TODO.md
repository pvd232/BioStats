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
5. [Phase 1: stage invocation and process startup](#phase-1-implement-stage-invocation-and-process-startup)
6. [Phase 2: controlled HTTP retrieval](#phase-2-implement-controlled-http-retrieval)
7. [Phase 3: artifact validation](#phase-3-close-artifact-validation)
8. [Phase 4: metric provenance](#phase-4-close-metric-provenance)
9. [Phase 5: durable attempts and retry](#phase-5-implement-durable-attempts-and-retry)
10. [Phase 6: benchmark execution](#phase-6-implement-benchmark-execution)
11. [Phase 7: local and GCE execution](#phase-7-generalize-execution-across-local-and-gce-hosts)
12. [Phase 8: public interface and project scaffold](#phase-8-freeze-the-public-interface-and-project-scaffold)
13. [Phase 9: release candidate](#phase-9-build-and-validate-the-release-candidate)
14. [Phase 10: publication](#phase-10-publish-viper-010a1)
15. [Deferred work](#deferred-work)

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

Four owner inputs enter at fixed points:

| Owner input | Required by |
|---|---|
| Package license | Phase 9 metadata gate |
| Author names and contact metadata | Phase 9 metadata gate |
| TestPyPI credentials | Phase 10 TestPyPI upload |
| PyPI publication authorization | Phase 10 PyPI upload |

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

Items marked **Owner input** require a licensing, identity, credential, or
publication decision from the package owner.

## Contract coverage

Every implementation contract appears once in the execution sequence.

| Contract | Current status | Execution phase | Completion evidence |
|---|---|---|---|
| [Parameter models](contracts/PARAMETER_MODELS.md) | Implemented | Regression coverage in Phases 1 and 2 | The exact project class validates the frozen mapping received by the stage context. |
| [Stage invocation](contracts/STAGE_INVOCATION.md) | Approved | Phase 1 | The frozen callable receives the typed parameters and declared paths. |
| [Process startup](contracts/PROCESS_STARTUP.md) | Approved | Phase 1 | The controlled child starts with the frozen process controls and writes one invocation receipt. |
| [HTTP retrieval](contracts/HTTP_RETRIEVAL.md) | Approved | Phase 2 | The resolved exchange binds each request to the response bytes delivered to project code. |
| [Artifact validation](contracts/ARTIFACT_VALIDATION.md) | Approved | Phase 3 | The verifier reports representation identity, loadability, or reserved semantic validity at its established level. |
| [Metric provenance](contracts/METRIC_PROVENANCE.md) | Approved | Phase 4 | Each measurement binds the implementation, dependency set, parameters, environment, and comparator. |
| [Attempt execution](contracts/ATTEMPT_EXECUTION.md) | Approved | Phase 5 | Failed attempts persist; retry allocates a greater attempt ID and preserves prior evidence. |
| [Benchmark execution](contracts/BENCHMARK_EXECUTION.md) | Approved | Phase 6 | `execute_benchmark()` produces the independent confirmation accepted by `verify_benchmark()`. |
| [Cloud execution](contracts/CLOUD_EXECUTION.md) | Approved | Phase 7 | The installed wheel executes in place on GCE and verifies the realized host. |
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
- [x] Ruff, Pyright, 129 tests, and 13 subtests at commit `d5580ee`.

## Phase 1. Implement stage invocation and process startup

**Contracts:** [Stage invocation](contracts/STAGE_INVOCATION.md) and
[Process startup](contracts/PROCESS_STARTUP.md).

### Protocol and authoring

- [ ] Add `StageImplementationRef` with repository-relative path, top-level
  symbol, SHA-256, and byte count.
- [ ] Replace each parameterized stage's `script` field with
  `implementation: StageImplementationRef`.
- [ ] Add `StageInvocationReceipt` to the resolved stage contract.
- [ ] Update `ProvenanceS1_v3.md` with the callable, context, receipt, and
  process-startup relationships.
- [ ] Add one public decorator for each stage kind.
- [ ] Resolve decorator metadata into the frozen implementation and parameter
  model references.

### Runtime

- [ ] Add generic `StageContext` with typed parameters, materialized input
  paths, writable artifact paths, run ID, attempt ID, and stage ID.
- [ ] Add `viper.run(stage_callable)` as the ordinary Python adapter.
- [ ] Bind `--stage` to the callable launched by the project module and execute
  every stage in `RunSpec.stages` order.
- [ ] Rename `run_local()` and its request/result models to the host-neutral
  `run()` operation.
- [ ] Rename `viper run-local` to `viper run`.
- [ ] Derive the canonical child-process environment from
  `RunSpec.reproducibility`.
- [ ] Launch each stage in one controlled child carrying
  `VIPER_CONTEXT_PATH`.
- [ ] Apply library controls before importing the frozen callable.
- [ ] Validate parameters into the exact project class and place that object in
  `StageContext.params`.
- [ ] Construct `StageContext.inputs` from the stage's declared,
  role-permitted inputs.
- [ ] Invoke the frozen callable once and persist its invocation receipt.

### Verification and acceptance

- [ ] Verify implementation identity, decorator metadata, parameter identity,
  parameter digest, context digest, and invocation outcome.
- [ ] Replace constant fixture scripts with decorated functions that consume
  their typed parameters and declared paths.
- [ ] Prove that `python train.py --run RUN --stage train` and `viper run RUN`
  produce terminal results accepted by the same verifier.
- [ ] Reject a changed callable, parameter mapping, context binding, and second
  invocation.

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

- [ ] Add `HttpRequestSpec`, `SecretRef`, and `ResolvedHttpExchange`.
- [ ] Replace `RemoteFileRef` inputs on `DownloadSpec` with frozen HTTP request
  specifications.
- [ ] Store the complete ordered exchange sequence on
  `ResolvedDownloadSpec`.
- [ ] Expand URL templates during authoring and freeze the canonical request.
- [ ] Reject literal authorization values and preserve secret references.

### Runtime

- [ ] Implement one controlled HTTP client with scheme, host, port, request
  count, response-size, and timeout limits.
- [ ] Resolve credentials at execution time through `SecretRef`.
- [ ] Store each response body by content digest before project code runs.
- [ ] Add `DownloadContext` as the `StageContext` extension that exposes typed
  `DownloadParams`, verified response handles, and the controlled follow-up
  request interface.
- [ ] Record redirects and project-requested pagination calls in exchange
  order.
- [ ] Deliver only verified response handles through the download context.

### Verification and acceptance

- [ ] Verify the frozen first request, every realized target, HTTP status,
  exchange order, response digest, response byte count, parameter model,
  implementation identity, and published artifacts.
- [ ] Exercise one static request, redirect, paginated source, secret reference,
  request-policy failure, and same-length response tampering.
- [ ] Prove that the acceptance download callable consumes the response selected
  by its frozen request.

**Focused gate**

```bash
python -m pytest tests/test_http_retrieval.py tests/test_stage_invocation.py \
  tests/test_runner_acceptance.py tests/test_verifier.py -q
```

**Commit boundaries**

1. `Define frozen HTTP requests and resolved exchanges`
2. `Execute downloads through the controlled HTTP client`
3. `Verify HTTP response provenance`

## Phase 3. Close artifact validation

**Contract:** [Artifact validation](contracts/ARTIFACT_VALIDATION.md).

- [ ] Add `ArtifactLoaderRef` with path, symbol, SHA-256, and byte count.
- [ ] Replace artifact loader IDs and paths with exact implementation
  references.
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

- [ ] Add `MetricImplementationRef` and `MetricDependency`.
- [ ] Freeze `MetricKind`, `MetricProduction`, and `MetricVerification`.
- [ ] Require one comparator for every recomputed floating-point metric.
- [ ] Freeze decorator metadata, dependencies, parameters, and implementation
  identity into `MetricSpec`.
- [ ] Require benchmark criteria to select evaluation metrics produced after a
  stage and verified by recomputation.

### Runtime and verification

- [ ] Construct each `MetricContext` from its declared inputs and artifacts.
- [ ] Enforce every dependency's data role before invoking metric code.
- [ ] Record during-stage measurements through the runner-owned
  `MeasurementSink`.
- [ ] Invoke after-stage metrics through the trusted worker boundary.
- [ ] Recompute eligible metrics from immutable dependencies and the frozen
  implementation.
- [ ] Persist the recomputed value and comparator result.
- [ ] Verify implementation identity, dependency identity, parameters,
  measurement ownership, and comparator outcome.
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
- [ ] Close and publish attempts with `succeeded`, `failed`, `cancelled`, or
  `preempted` status.
- [ ] Replace `failure_reason` with typed `AttemptFailure`.
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
- [ ] Add the `viper execute-benchmark` command with human and JSON output.
- [ ] Verify the candidate run before allocating confirmation attempts.
- [ ] Execute the same frozen plan for every confirmation required by
  `BenchmarkSpec`.
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
- [ ] Permit the existing `ComputeSpec` CPU/CUDA union on local environments.
- [ ] Resolve the boot-image ID during plan freezing.
- [ ] Generalize preflight from the local-only check to the effective
  environment selected for each stage.
- [ ] Add local CUDA observation.
- [ ] Add GCE project, boot-image, machine-type, zone, guest OS, kernel, CPU,
  CUDA, driver, and numerical-runtime observation.
- [ ] Compare the realized environment with the stage environment override or
  shared run environment selected by the plan.
- [ ] Publish the same workspace, snapshots, journal, and terminal run files on
  local and GCE hosts.

### Acceptance

- [ ] Exercise deterministic local CPU, local CUDA, GCE CPU, and GCE CUDA
  fixtures.
- [ ] Reject boot-image, machine-type, accelerator, lockfile, and numerical
  control mismatches.
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
2. `Observe local CUDA and GCE runtimes`
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
- [ ] Publish those exact files to PyPI.
- [ ] Install `viper-provenance==0.1.0a1` from PyPI in a clean environment.
- [ ] Repeat the installed-package smoke and complete example tests.
- [ ] Tag the release commit as `v0.1.0a1` and push the tag.
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
- Distributed and multi-rank execution.
- Epoch-completion receipts and `OversightPolicy` capability requirements.
- Agent mutation dry-runs and downstream-lineage indexing.
- Internal splits of `protocol.py` and `verifier.py` after their public
  boundaries stabilize.
- Additional built-in metrics, loaders, retrieval strategies, and graphical
  interfaces.
