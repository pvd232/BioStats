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
