# `viper.application`

`viper.application` is VIPER's public operation layer. Python callers pass a
typed request model to a function. The `viper` command validates a mapping,
calls the same function, and renders its result.

## Operations

| Python | CLI | Result |
| --- | --- | --- |
| `validate_stage(request)` | `viper validate-stage` | Validated stage kind |
| `validate_resolved_stage(request)` | `viper validate-resolved-stage` | Validated resolved-stage kind |
| `validate_run_spec(request)` | `viper validate-run` | Run ID and ordered stage IDs |
| `freeze_run(request)` | `viper freeze-run` | Canonical stage and run specification paths |
| `preflight(request)` | `viper preflight` | Every applicable check and one readiness value |
| `execute_stage(request)` | `viper execute-stage` | Command, artifacts, standard output, and standard error |
| `run_local(request)` | `viper run-local` | Verified terminal run and attempt journal paths |
| `plan_diff(request)` | `viper plan-diff` | Ordered leaf differences between two complete frozen plans |
| `lineage(request)` | `viper lineage` | Verified stages, inputs, artifacts, and their directed relationships |
| `status(request)` | `viper status` | Latest durable attempt state and permitted successor states |
| `compare_runs(request)` | `viper compare-runs` | Ordered differences between two verified terminal runs |
| `verify_run(request)` | `viper verify-run` | Verified run, attempt, stage, and measurement summary |
| `verify_benchmark(request)` | `viper verify-benchmark` | Verified benchmark and confirmation summary |
| `verify_pointer(request)` | `viper verify-pointer` | Verified artifact file count |
| `get_schema(request)` | `viper schema` | JSON Schema for one registered public type |
| `get_capabilities(request)` | `viper capabilities` | Operations and execution backends in this installation |

Every success contains `status="ok"` and the function's `operation` name.

## Validate documents

```python
validate_stage(request: ValidateStageRequest) -> ValidateStageSuccess
validate_resolved_stage(
    request: ValidateResolvedStageRequest,
) -> ValidateResolvedStageSuccess
validate_run_spec(request: ValidateRunSpecRequest) -> ValidateRunSpecSuccess
```

Each request supplies `path: Path`. The stage operations return `path` and
`stage_kind`. Run validation returns `path`, `run_id`, and the ordered
`stage_ids`.

Expected errors: `invalid_document`, `not_found`, `io_failed`.

## Freeze a run plan

```python
freeze_run(request: FreezeRunRequest) -> FreezeRunSuccess
```

| Request field | Type | Meaning |
| --- | --- | --- |
| `draft` | `Path` | `RunPlanDraft` YAML document |
| `repository_root` | `Path` | Root for source paths and canonical run paths |

The operation validates each stage draft, writes its canonical `spec.yaml`,
records its SHA-256 and byte count in `RunSpec.stages`, and writes the run
`spec.yaml`. The result contains `run_id` and every written path.

Expected errors: `invalid_document`, `not_found`, `write_conflict`, `io_failed`.

## Preflight a local plan

```python
preflight(request: PreflightRequest) -> PreflightSuccess
```

| Request field | Type | Meaning |
| --- | --- | --- |
| `run_spec` | `Path` | Frozen run `spec.yaml` |
| `repository_root` | `Path` | Local repository root |

The result contains `run_id`, `ready`, and every `PreflightCheck`. Each check
contains a stable `code`, `status`, `target`, and `message`. `ready` is true
when the report contains zero failures.

## Execute one stage

```python
execute_stage(request: ExecuteStageRequest) -> ExecuteStageSuccess
```

| Request field | Type | Meaning |
| --- | --- | --- |
| `run_spec` | `Path` | Frozen run `spec.yaml` |
| `stage_id` | `StageId` | Stage selected from `RunSpec.stages` |
| `repository_root` | `Path` | Local repository root |
| `timeout_seconds` | positive `float` or `None` | Process deadline |

VIPER verifies the stage-spec bytes, applies the run controls through
`viper.stage_worker`, invokes the project entrypoint, and hashes every declared
artifact file. The result contains `stage_id`, `command`, `artifacts`, `stdout`,
and `stderr`.

Expected errors: `invalid_document`, `not_found`, `io_failed`,
`execution_failed`.

## Execute a complete local run

```python
run_local(request: RunLocalRequest) -> RunLocalSuccess
```

| Request field | Type | Meaning |
| --- | --- | --- |
| `run_spec` | `Path` | Frozen run `spec.yaml` present in the current Git commit |
| `repository_root` | `Path` | Local Git repository root |
| `timeout_seconds` | positive `float` or `None` | Per-stage process deadline |

The trusted-local runner performs these operations in order:

```text
preflight plan
-> acquire run lock
-> materialize verified inputs
-> execute stages in RunSpec order
-> invoke after-stage metrics
-> publish immutable local snapshots
-> write attempt logs and measurements
-> write resolved.yaml
-> verify the complete terminal run
```

The result contains `run_id`, `resolved_run`, and `journal`. Output snapshots
live under `.viper/store/<content digest>/`. Attempt control files live under
`.viper/workspaces/<run ID>/attempt-<attempt ID>/`.

Expected errors: `execution_failed`, `verification_failed`, `invalid_document`,
`not_found`, `io_failed`.

## Compare frozen plans

```python
plan_diff(request: PlanDiffRequest) -> PlanDiffSuccess
```

| Request field | Type | Meaning |
| --- | --- | --- |
| `left_run_spec` | `Path` | First frozen run `spec.yaml` |
| `left_repository_root` | `Path` | Repository containing the first plan |
| `right_run_spec` | `Path` | Second frozen run `spec.yaml` |
| `right_repository_root` | `Path` | Repository containing the second plan |

VIPER verifies every referenced stage file against its `RunStageRef`, then
compares the run specs and stage-spec contents. Each `PlanChange` contains a
stable dotted `path`, a `kind` of `added`, `removed`, or `changed`, and the
applicable values from each plan.

Expected errors: `invalid_document`.

## Read attempt status

```python
status(request: StatusRequest) -> StatusSuccess
```

`StatusRequest.path` selects one durable attempt journal. The result returns
the entry count, latest state, event, timestamp, event details, terminal flag,
and the states accepted by the next journal append. VIPER validates transition
order when each entry is written.

Expected errors: `invalid_document`, `not_found`, `io_failed`.

## Inspect run lineage

```python
lineage(
    request: LineageRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> LineageSuccess
```

The request supplies a terminal run path and the source repositories permitted
to execute frozen metric and loader code. VIPER verifies the complete run
before constructing the graph.

Each node identifies a stage, input, artifact, or promoted input selection.
Each directed edge has one relation:

- `produces`: stage to artifact;
- `selects`: artifact or promoted selection to stage input;
- `consumes`: stage input to consuming stage.

Expected errors: `invalid_document`, `verification_failed`.

## Compare verified runs

```python
compare_runs(
    request: CompareRunsRequest,
    *,
    left_fetcher: StorageFetcher | None = None,
    right_fetcher: StorageFetcher | None = None,
) -> CompareRunsSuccess
```

The request supplies two terminal run paths and the source repositories
permitted to execute their frozen metric and loader code. VIPER verifies each
run before comparison. The comparison covers:

- terminal run and attempt fields;
- run, experiment, variant, and benchmark specifications;
- ordered stage specifications;
- resolved stage results and artifact identities; and
- recorded measurements.

Each `RunChange` contains a stable dotted `path`, a `kind` of `added`,
`removed`, or `changed`, and the applicable value from each run.

Expected errors: `invalid_document`, `verification_failed`.

## Verify published evidence

```python
verify_run(
    request: VerifyRunRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyRunSuccess

verify_benchmark(
    request: VerifyBenchmarkRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyBenchmarkSuccess

verify_pointer(
    request: VerifyPointerRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyPointerSuccess
```

Each request supplies `path` and `trusted_loader_repositories`. A supplied
`fetcher` retrieves exact bytes for Git, Hugging Face, or local storage
references. Verification checks the connected plan, stage results, inputs,
artifacts, measurements, logs, runtime controls, and terminal selection.
Metrics with `verification="recompute"` run again from frozen implementation
code, verified dependencies, and frozen parameters. VIPER applies the metric's
declared comparator to the recorded and recomputed values.

Expected errors: `invalid_document`, `not_found`, `io_failed`,
`verification_failed`.

## Discover schemas and capabilities

```python
get_schema(request: SchemaRequest) -> SchemaSuccess
get_capabilities(request: CapabilitiesRequest) -> CapabilitiesSuccess
```

`SchemaRequest.name` selects one key in `SCHEMA_REGISTRY`. `SchemaSuccess`
returns `name` and `json_schema`.

`CapabilitiesRequest` has zero fields. `CapabilitiesSuccess` returns the
protocol version, callable operations, and installed execution backends.

## Failures

Expected application failures raise `ViperError`. Its `failure` field is a
`ViperFailure`:

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | `"error"` | Result status |
| `operation` | `OperationName` or `None` | Selected operation |
| `origin` | `request`, `application`, `cli`, or `internal` | Layer that produced the failure |
| `code` | `ErrorCode` | Stable machine-readable category |
| `message` | `str` | Public explanation |
| `details` | `dict[str, object]` | Structured public evidence |

`dispatch(operation, payload)` returns `ViperFailure` for invalid mappings and
expected operation failures. Direct function calls receive Pydantic validation
errors during request construction and `ViperError` during execution.

## JSON CLI

Place `--json` before the command:

```bash
viper --json capabilities
viper --json preflight experiments/example/runs/baseline/<run_id>/spec.yaml
viper --json run-local experiments/example/runs/baseline/<run_id>/spec.yaml
viper --json plan-diff <left-spec.yaml> <right-spec.yaml>
viper --json lineage <resolved.yaml> --trust-loader-source <repository>
viper --json status <journal.jsonl>
viper --json compare-runs <left-resolved.yaml> <right-resolved.yaml> \
  --trust-loader-source <repository>
```

JSON mode writes one UTF-8 document with one trailing newline. Completed
operations use exit status `0`. Application failures and a preflight result
with `ready=false` use exit status `1`.
