# VIPER End-of-Day Journal — 2026-08-22

## Outcome

VIPER now executes a complete frozen run on a trusted local host. The path is
usable through the Python application API and the `viper` command:

```text
freeze plan
-> preflight committed evidence
-> execute ordered stages
-> materialize verified inputs
-> invoke frozen metrics
-> publish immutable local results
-> write resolved.yaml
-> verify the terminal run
```

The implementation passed its source checks, complete test suite, distribution
build, metadata inspection, and an installed-wheel smoke test.

## Completed

### Application and command surface

- Added typed requests, successes, failures, stable operation names, schema
  discovery, and capability discovery in
  [`viper.application`](../viper/application.py).
- Routed command parsing and JSON output through the same application
  operations in [`viper.cli`](../viper/cli.py).
- Added `preflight`, `run_local`, `plan_diff`, and `lineage` to the Python and
  command surfaces.
- Made a preflight result with `ready=false` return a failing process status for
  automation.

### Trusted-local execution

- Added bounded attempt workspaces, exclusive run ownership, synchronized
  journals, immutable local snapshots, and verified input materialization.
- Added the VIPER runtime bootstrap. It applies run-wide randomness,
  determinism, precision, and parallelism controls before importing project
  code.
- Implemented ordered multi-stage execution in
  [`viper.runner`](../viper/runner.py).
- Persisted the preflight report in the attempt workspace.
- Recorded every declared successful-attempt state through terminal
  verification.
- Routed Git, Hugging Face, and local immutable references through their
  corresponding retrieval paths.
- Required the local Git origin and committed plan bytes to match the frozen
  run evidence.

### Metrics and verification

- Invoked after-stage metric functions from their frozen source commit.
- Wrote VIPER-owned measurement rows.
- Recomputed metrics that declare `verification="recompute"` from verified
  inputs, verified artifacts, and frozen parameters.
- Applied each metric's declared comparator to the recorded and recomputed
  values.
- Extended benchmark verification to recompute confirmation metrics.

### Agent-first inspection

- Added `plan_diff()` for stable leaf-by-leaf comparison of two complete frozen
  plans, including every stage spec identified by each RunSpec.
- Added `lineage()` for a verified graph of stages, inputs, promoted
  selections, artifacts, roles, paths, and directed relationships.

### Documentation and package surface

- Rewrote the application reference with functions first and exact request,
  result, effect, and failure contracts.
- Updated the root README, public API inventory, release roadmap, and overnight
  charter to reflect the trusted-local implementation.
- Built `viper-provenance` as a source distribution and wheel. The wheel
  contains the `viper` package and installed command.

## Validation

Executed in the `mantra` Conda environment:

```text
Ruff: passed
Pyright: 0 errors, 0 warnings
Pytest: 109 passed, 13 subtests passed
Distribution build: passed
Twine metadata check: passed for wheel and source distribution
Installed-wheel imports: passed
Installed-wheel capabilities: passed
Installed-wheel CLI help for plan-diff and lineage: passed
Git local/upstream equality: passed before this journal commit
```

Two dependency warnings remain visible during tests:

- one deliberate `serialize_record()` deprecation test;
- TorchData's internal call to deprecated `torch.set_vital`.

## Git increments

```text
68b5eef  Implement VIPER application and JSON CLI
774ff5  Add local worker and metric interfaces
c33cfb7  Add local preflight and immutable storage
ce2569b  Implement verified trusted-local runs
67e0677  Recompute frozen metrics during verification
bdb67b1  Expose preflight and local run operations
30c093a  Document trusted local execution
07ea8a7  Add immutable plan and lineage inspection
d953e07  Complete local preflight and publication journal
```

## Remaining release work

The local successful-run path is complete. VIPER 0.1 still requires:

1. crash recovery, retry allocation, cancellation, preemption, and resumed
   publication;
2. hardened OCI execution and live GCE validation;
3. complete project parameter-model binding and isolated validator execution;
4. benchmark confirmation execution and immutable recomputation evidence;
5. metric dependency bindings that name each permitted input and artifact;
6. agent status, run comparison, and controlled mutation dry runs;
7. owner-approved license and author metadata, remote CI, TestPyPI, and PyPI.

## Next action

Add `status()` over the durable attempt journal, then add `compare_runs()` over
two verified terminal runs. Keep both operations read-only and return stable
Pydantic results through the Python API and JSON CLI.

## Autonomous continuation

### Outcome

The read-only agent inspection phase is complete:

- `status()` reads one durable attempt journal and returns its latest event,
  timestamp, details, terminal flag, and permitted successor states.
- `compare_runs()` verifies two terminal runs, then compares their terminal
  records, run plans, experiment and variant specifications, benchmark
  specifications, stage specifications, resolved stages, artifacts, and
  measurements.
- `get_capabilities()` lists callable operations, registered schemas, and
  execution backends.
- `plan_diff()`, `lineage()`, `status()`, and `compare_runs()` are available
  through typed Python functions and JSON commands.

### Checklist audit

Every overnight acceptance gate was traced to an executable test. The audit
made four corrections:

1. Installed-wheel checks now run in isolated interpreter mode, import every
   documented public module, resolve every application export, and exercise
   capability and command discovery.
2. `serialize_record()` has a focused warning-and-byte-equivalence test. Its
   removal is scheduled for `0.2.0` in the versioning policy.
3. Durable journal reads validate the complete attempt transition chain.
   Journal writes reject invalid successor states.
4. Empty mappings and sequences remain visible during plan and run comparison.

The publication roadmap now marks each verified application, CLI,
serialization, CI-configuration, and immutable-inspection item complete. Items
requiring remote CI, coordinator authority, recovery, or stronger isolation
remain open.

### Validation

Executed in the `mantra` Conda environment:

```text
Ruff: passed
Pyright: 0 errors, 0 warnings
Pytest: 119 passed, 13 subtests passed
Known dependency warning: TorchData calls deprecated torch.set_vital
Distribution build: passed
Twine metadata check: passed for wheel and source distribution
Isolated installed-wheel module imports: passed
Installed application export inventory: passed
Installed schema and capability discovery: passed
Installed status and compare-runs command help: passed
Markdown fences and local links: passed
```

### Git increments

```text
ac1cdff  Add attempt status and verified run comparison
77261f1  Document agent inspection and harden wheel smoke tests
03e0968  Harden attempt history and capability discovery
```

### Remaining local priorities

1. Bind project-defined Pydantic parameter models to frozen stage
   implementations and execute their validators through the worker boundary.
2. Bind metric dependencies to exact stage inputs and artifacts.
3. Persist failed attempts and implement retry and publication recovery from
   the durable journal.
4. Execute benchmark confirmations through the runner and publish their
   recomputation evidence.

### Next action

Implement project parameter-model binding. This gives user-defined stages a
typed extension point while preserving the frozen implementation identity,
preflight checks, and verifier guarantees.
