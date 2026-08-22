# VIPER six-hour execution charter

**Date:** August 22, 2026

**Time budget:** six hours

**Authority:** [VIPER 0.1 release roadmap](PUBLICATION_TODO.md)

This session delivers the first complete local VIPER execution path. The
release roadmap remains the source of truth for the complete 0.1 scope.

## Session outcome

By shutdown, one test project can:

```text
freeze a two-stage run plan
-> inspect schemas and capabilities
-> preflight the complete plan
-> execute both stages through trusted_local
-> materialize a same-run artifact input
-> invoke one frozen evaluation metric
-> publish resolved stage results and a terminal resolved run
-> verify the published run
-> reject one tampered result
```

The same operations are available through the Python application API and the
JSON CLI.

## Budget

| Time | Deliverable | Completion test |
| --- | --- | --- |
| 0:00-0:30 | Freeze the contracts required by this session | Artifact loadability, metric semantics, application errors, the attempt state sequence, and `trusted_local` behavior have named types and focused tests. |
| 0:30-1:05 | Repair the public package surface and CI smoke test | The public import inventory exists; `viper.records` is gone from CI; compatibility for `serialize_record` is explicit; package metadata and wheel imports pass. |
| 1:05-1:40 | Implement the application foundation | Typed application operations return deterministic success or failure models; schema and capability discovery use explicit registries. |
| 1:40-2:10 | Route the CLI through the application layer | Global `--json`, custom parsing failures, stdout and stderr rules, and stable exit statuses pass golden tests. |
| 2:10-3:00 | Implement the workspace and development worker | An immutable run request, exclusive attempt workspace, durable journal, and `trusted_local` worker share the release worker interface. |
| 3:00-3:40 | Implement the metric interface | One decorated stateless metric and one stateful training metric freeze to exact implementation references and write VIPER-owned measurements. |
| 3:40-4:20 | Implement preflight and input materialization | Preflight returns every applicable numbered check; stored and same-run inputs materialize from verified bytes; artifact loaders establish loadability. |
| 4:20-5:15 | Complete the local vertical slice | Two stages execute in order, publish resolved results, write the terminal run, pass verification, and reject altered artifact bytes. |
| 5:15-5:45 | Slack | Absorb implementation or validation overruns. If the core outcome is already complete, begin benchmark recomputation. |
| 5:45-6:00 | Shutdown handoff | Run the final checks, commit each completed boundary, push, verify local and upstream equality, and write the dated journal entry. |

Planned implementation occupies five hours and fifteen minutes. Thirty minutes
remain available for overrun, and fifteen minutes protect the handoff.

## Contract freeze for this session

The first block settles the exact contracts consumed during the remaining
work:

- A generic artifact loader proves that the exact verified file set can be
  loaded.
- VIPER validates the value schema of reserved artifacts such as
  `resume_state`.
- Evaluation metrics use `production = after_stage` and
  `verification = recompute`.
- Recomputed floating-point values use an explicit comparator recorded by the
  metric specification.
- Expected failures carry a stable code, operation, origin, message, and
  structured details.
- One coordinator owns each run and advances its durable attempt journal.
- `trusted_local` executes inside the caller's trust boundary and reports that
  capability through discovery.

Each settled contract receives a focused test before its first consumer is
implemented.

## Acceptance gates

The session outcome requires all of these gates:

1. `test_application_schema_and_capability_discovery`
   verifies explicit registries and deterministic JSON.
2. `test_cli_json_success_and_failure_contract`
   verifies parsing, output channels, and exit statuses.
3. `test_metric_freeze_execute_and_recompute`
   verifies implementation identity, permitted inputs, parameters,
   measurement construction, and recomputation.
4. `test_preflight_reports_all_plan_failures`
   verifies stable check codes and complete multi-result reporting.
5. `test_two_stage_run_publishes_and_verifies`
   verifies same-run input materialization, two resolved stage snapshots,
   measurements, logs, and the terminal resolved run.
6. `test_two_stage_run_rejects_tampered_artifact`
   verifies that altered artifact bytes fail verification.
7. Installed-wheel smoke tests import the public surface and execute schema,
   capability, and CLI help commands.

Test names may change during implementation when the owning module supplies a
clearer namespace. Their stated assertions remain fixed.

## Mid-session replan

At 3:00, compare the observed state with the package, application, CLI, and
worker gates.

If the application, CLI, or worker gates remain open, finish those gates and
the metric interface during the remaining implementation window. Move
preflight and the two-stage runner test to the next session and record each
unmet dependency in the journal.

If those gates pass, preserve the metric, preflight, runner, and verification
outcome as the session priority.

## Stretch order

Use recovered slack in this order:

1. Execute one benchmark confirmation and recompute its threshold metrics.
2. Add immutable plan-diff and upstream-lineage inspection.
3. Add an OCI worker spike behind the frozen execution-policy interface.

## Deferred release work

The [release roadmap](PUBLICATION_TODO.md) retains these release gates for
later sessions:

- hardened OCI execution on a pre-provisioned GCE host;
- the full crash, preemption, cancellation, and publication-recovery matrix;
- benchmark parity and confirmation coverage;
- downstream-lineage indexing and coordinator status;
- internal protocol and verifier module splits;
- complete documentation and installed-wheel examples;
- remote CI, live GCE, TestPyPI, and PyPI validation.

## Shutdown checklist

- [ ] Stop feature work at 5:45.
- [ ] Run the smallest focused checks for each completed boundary.
- [ ] Run Ruff, Pyright, and the complete pytest suite.
- [ ] Build and inspect the wheel when package surfaces changed.
- [ ] Commit completed boundaries with task-scoped messages.
- [ ] Push every commit and verify local `HEAD` equals its upstream.
- [ ] Write a new dated journal entry with results, open gates, and the exact
  next action.

## Observed completion

The trusted-local vertical slice reached the session outcome:

- Typed Python operations and the JSON CLI expose validation, freezing,
  preflight, stage execution, complete local execution, verification, schema
  discovery, and capability discovery.
- The runner executes two ordered stages, materializes a same-run input,
  invokes a frozen metric, publishes immutable snapshots, writes logs and
  measurements, writes the terminal `resolved.yaml`, and verifies the result.
- The verifier recomputes metrics that declare `verification="recompute"` and
  applies their declared comparators.
- The acceptance suite rejects altered artifact bytes.
- Ruff, Pyright, 109 tests, 13 subtests, package builds, metadata checks, and an
  installed-wheel smoke test pass.

## Phase 2: read-only agent operations

Phase 2 uses the verified plan and run evidence through deterministic JSON
operations. These operations inspect immutable inputs and leave execution
state unchanged.

1. `plan_diff()` compares two complete frozen plans, including the exact stage
   specs named by each RunSpec.
2. `lineage()` returns the verified upstream path from each stage input to its
   source artifact and producing stage.
3. `status()` summarizes the latest durable attempt-journal entry and the next
   valid coordinator action.
4. `compare_runs()` compares two verified terminal runs after plan, input,
   artifact, and measurement verification.

Implementation begins with `plan_diff()` and `lineage()`. They have a read-only
authority surface and let an agent explain why two plans differ and where each
run input originated.
