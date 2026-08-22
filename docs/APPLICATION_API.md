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
| `timeout_seconds` | `float | None` | Process deadline |

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
| `timeout_seconds` | `float | None` | Per-stage process deadline |

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
| `operation` | `OperationName | None` | Selected operation |
| `origin` | `request | application | cli | internal` | Layer that produced the failure |
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
```

JSON mode writes one UTF-8 document with one trailing newline. Successes use
exit status `0`. Failures use exit status `1`.
