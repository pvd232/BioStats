# `viper.application`

**Status:** Proposed application contract. Implementation is tracked in the
[publication checklist](PUBLICATION_TODO.md).

`viper.application` is the typed Python interface for plan authoring, stage
execution, provenance verification, and API discovery.

Each function accepts a Pydantic request model, returns a Pydantic result model,
and raises `ViperError` for an expected application failure. The `viper` command
calls the same functions.

Every result model includes `status="ok"` and the function's `operation` name.

## Operations

| Operation | Purpose | CLI command |
|---|---|---|
| [`validate_stage()`](#validate_stage) | Validate an authored stage specification. | `viper validate-stage` |
| [`validate_resolved_stage()`](#validate_resolved_stage) | Validate a resolved stage specification. | `viper validate-resolved-stage` |
| [`validate_run_spec()`](#validate_run_spec) | Validate a frozen run specification. | `viper validate-run` |
| [`freeze_run()`](#freeze_run) | Create a frozen run specification and its stage specifications. | `viper freeze-run` |
| [`execute_stage()`](#execute_stage) | Execute one stage from a frozen run. | `viper execute-stage` |
| [`verify_run()`](#verify_run) | Verify a terminal run and its provenance chain. | `viper verify-run` |
| [`verify_benchmark()`](#verify_benchmark) | Verify benchmark criteria and independent confirmation. | `viper verify-benchmark` |
| [`verify_pointer()`](#verify_pointer) | Resolve and verify a promoted artifact. | `viper verify-pointer` |
| [`get_schema()`](#get_schema) | Return the JSON Schema for a public VIPER type. | `viper schema` |
| [`get_capabilities()`](#get_capabilities) | Return the installed VIPER capabilities. | `viper capabilities` |

## `validate_stage()`

```python
validate_stage(request: ValidateStageRequest) -> ValidateStageSuccess
```

Loads the YAML document at `request.path` and validates it as a `Spec`.

### Parameters

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Local path to an authored stage specification. |

### Returns

`ValidateStageSuccess`

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Validated path. |
| `stage_kind` | `StageKind` | `download`, `build`, `embed`, `train`, or `evaluate`. |

### Errors

`invalid_document`, `not_found`, `io_failed`

## `validate_resolved_stage()`

```python
validate_resolved_stage(
    request: ValidateResolvedStageRequest,
) -> ValidateResolvedStageSuccess
```

Loads the YAML document at `request.path` and validates it as a `ResolvedSpec`.

### Parameters

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Local path to a resolved stage specification. |

### Returns

`ValidateResolvedStageSuccess`

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Validated path. |
| `stage_kind` | `StageKind` | `download`, `build`, `embed`, `train`, or `evaluate`. |

### Errors

`invalid_document`, `not_found`, `io_failed`

## `validate_run_spec()`

```python
validate_run_spec(
    request: ValidateRunSpecRequest,
) -> ValidateRunSpecSuccess
```

Loads the YAML document at `request.path` and validates it as a `RunSpec`.

### Parameters

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Local path to a frozen run specification. |

### Returns

`ValidateRunSpecSuccess`

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Validated path. |
| `run_id` | `RunId` | Run identity. |
| `stage_ids` | `tuple[StageId, ...]` | Stage identities in execution order. |

### Errors

`invalid_document`, `not_found`, `io_failed`

## `freeze_run()`

```python
freeze_run(request: FreezeRunRequest) -> FreezeRunSuccess
```

Loads a `RunPlanDraft`, validates its stage sources, writes each canonical stage
specification, and writes the hash-bound `RunSpec`.

### Parameters

| Field | Type | Description |
|---|---|---|
| `draft` | `Path` | Local path to the `RunPlanDraft`. |
| `repository_root` | `Path` | Root used to resolve source and destination paths. |

### Returns

`FreezeRunSuccess`

| Field | Type | Description |
|---|---|---|
| `run_id` | `RunId` | Frozen run identity. |
| `files` | `tuple[Path, ...]` | Stage and run specification files written by the operation. |

### Errors

`invalid_document`, `not_found`, `write_conflict`, `io_failed`

## `execute_stage()`

```python
execute_stage(request: ExecuteStageRequest) -> ExecuteStageSuccess
```

Loads the selected `RunStageRef`, verifies the referenced stage specification,
executes its script, and hashes every declared artifact file.

### Parameters

| Field | Type | Description |
|---|---|---|
| `run_spec` | `Path` | Local path to the frozen `RunSpec`. |
| `stage_id` | `StageId` | Stage selected from `RunSpec.stages`. |
| `repository_root` | `Path` | Working directory for the stage process. |
| `timeout_seconds` | `float \| None` | Maximum process duration in seconds. `None` leaves process duration unrestricted. |

### Returns

`ExecuteStageSuccess`

| Field | Type | Description |
|---|---|---|
| `stage_id` | `StageId` | Executed stage identity. |
| `command` | `tuple[str, ...]` | Exact process command. |
| `started_at` | `AwareDatetime` | Process start time. |
| `completed_at` | `AwareDatetime` | Process completion time. |
| `artifacts` | `dict[ArtifactName, ResolvedArtifact]` | Declared artifacts and their file identities. |
| `stdout` | `bytes` | Captured standard output. |
| `stderr` | `bytes` | Captured standard error. |

JSON output encodes `stdout` and `stderr` with URL-safe Base64.

### Errors

`invalid_document`, `not_found`, `io_failed`, `execution_failed`

## `verify_run()`

```python
verify_run(
    request: VerifyRunRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyRunSuccess
```

Loads a `ResolvedRun`, retrieves its referenced files, verifies the complete run
plan and every attempt, and reconstructs artifacts with approved loaders.

### Parameters

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Local path to the terminal `ResolvedRun`. |
| `trusted_loader_repositories` | `frozenset[str]` | Source repository URLs approved to supply executable artifact loaders. |
| `fetcher` | `StorageFetcher \| None` | Byte retrieval function. `None` selects `fetch_storage_bytes()`. |

### Returns

`VerifyRunSuccess`

| Field | Type | Description |
|---|---|---|
| `run_id` | `RunId` | Verified run identity. |
| `run_status` | `succeeded \| failed \| cancelled` | Terminal run status. |
| `successful_attempt_id` | `int \| None` | Successful attempt identity. |
| `stage_ids` | `tuple[StageId, ...]` | Verified stage identities. |
| `measurement_count` | `int` | Verified measurement count. |

### Errors

`invalid_document`, `not_found`, `io_failed`, `verification_failed`

## `verify_benchmark()`

```python
verify_benchmark(
    request: VerifyBenchmarkRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyBenchmarkSuccess
```

Loads a `BenchmarkResult`, verifies its selected run, checks the independent
confirmation attempt, compares declared artifacts, and applies every metric
criterion in the `BenchmarkSpec`.

### Parameters

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Local path to the `BenchmarkResult`. |
| `trusted_loader_repositories` | `frozenset[str]` | Source repository URLs approved to supply executable artifact loaders. |
| `fetcher` | `StorageFetcher \| None` | Byte retrieval function. `None` selects `fetch_storage_bytes()`. |

### Returns

`VerifyBenchmarkSuccess`

| Field | Type | Description |
|---|---|---|
| `benchmark_id` | `BenchmarkId` | Verified benchmark identity. |
| `run_id` | `RunId` | Candidate run identity. |
| `benchmark_status` | `passed \| failed` | Recorded benchmark result. |
| `confirmation_attempt_id` | `int` | Independent confirmation attempt identity. |

### Errors

`invalid_document`, `not_found`, `io_failed`, `verification_failed`

## `verify_pointer()`

```python
verify_pointer(
    request: VerifyPointerRequest,
    *,
    fetcher: StorageFetcher | None = None,
) -> VerifyPointerSuccess
```

Loads an `ArtifactPointer`, verifies its producer run, selects the named stage
artifact, verifies its files, and invokes its approved loader.

### Parameters

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Local path to the `ArtifactPointer`. |
| `trusted_loader_repositories` | `frozenset[str]` | Source repository URLs approved to supply executable artifact loaders. |
| `expected_data_role` | `DataRole \| None` | Required artifact data role. |
| `materialization_path` | `RepoRelPath \| None` | Repository-relative loader path for the verified files. |
| `fetcher` | `StorageFetcher \| None` | Byte retrieval function. `None` selects `fetch_storage_bytes()`. |

### Returns

`VerifyPointerSuccess`

| Field | Type | Description |
|---|---|---|
| `run` | `ResolvedRunRef` | Producer run reference. |
| `stage_id` | `StageId` | Producer stage identity. |
| `artifact_name` | `ArtifactName` | Selected artifact name. |
| `data_role` | `DataRole` | Verified artifact data role. |
| `snapshot` | `StageResultSnapshotRef` | Snapshot containing the artifact files. |
| `files` | `tuple[SnapshotFileRef, ...]` | Verified artifact files. |

### Errors

`invalid_document`, `not_found`, `io_failed`, `verification_failed`

## `get_schema()`

```python
get_schema(request: SchemaRequest) -> SchemaSuccess
```

Returns the [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
generated by [Pydantic](https://docs.pydantic.dev/latest/concepts/json_schema/)
for one public VIPER type.

### Parameters

| Field | Type | Description |
|---|---|---|
| `schema_type` | `SchemaTypeName` | Registered request, result, error, authored-document, or resolved-document type. |

### Returns

`SchemaSuccess`

| Field | Type | Description |
|---|---|---|
| `schema_type` | `SchemaTypeName` | Requested type name. |
| `dialect` | `https://json-schema.org/draft/2020-12/schema` | Schema dialect. |
| `schema` | `dict[str, JsonValue]` | Generated schema. |

### Errors

`invalid_request`

## `get_capabilities()`

```python
get_capabilities(request: CapabilitiesRequest) -> CapabilitiesSuccess
```

Returns the operations and protocol types supported by the installed VIPER
package.

### Parameters

`CapabilitiesRequest` is an empty model.

### Returns

`CapabilitiesSuccess`

| Field | Type | Description |
|---|---|---|
| `package_version` | `str` | Installed VIPER package version. |
| `protocol_schema_versions` | `tuple[ProtocolSchemaVersion, ...]` | Supported protocol schema versions. |
| `operations` | `tuple[OperationName, ...]` | Supported application operations. |
| `schema_types` | `tuple[SchemaTypeName, ...]` | Types available through `get_schema()`. |
| `stage_kinds` | `tuple[StageKind, ...]` | Supported stage kinds. |
| `environment_kinds` | `tuple[EnvironmentKind, ...]` | Supported environment kinds. |
| `storage_kinds` | `tuple[StorageKind, ...]` | Supported storage kinds. |

## Errors

Application functions raise `ViperError`. Its `failure` attribute contains:

| Field | Type | Description |
|---|---|---|
| `status` | `Literal["error"]` | Error result marker. |
| `operation` | `OperationName` | Failed operation. |
| `code` | `ErrorCode` | Stable programmatic error code. |
| `target` | `str` | Path or protocol document associated with the failure. |
| `cause` | `str` | Specific failed condition. |

| Code | Meaning |
|---|---|
| `invalid_request` | Request-model validation failed. |
| `invalid_document` | YAML parsing or protocol-model validation failed. |
| `not_found` | A required local or referenced file is absent. |
| `write_conflict` | Authoring selected an existing path containing different bytes. |
| `io_failed` | Local or remote byte transfer failed. |
| `execution_failed` | The stage timed out, exited unsuccessfully, or omitted a declared artifact. |
| `verification_failed` | A provenance relationship, file identity, loader policy, or benchmark result failed verification. |
| `internal_error` | The CLI caught an unexpected implementation fault. |

Python callers receive unexpected exceptions with their original types.

## CLI output

Human-readable output is the default. `--json` writes one result model to
standard output or one error model to standard error.

Command parsing errors use `status="error"`, `operation="cli"`,
`code="invalid_request"`, `target=null`, and a concrete `cause`.

| Exit status | Meaning |
|---|---|
| `0` | Operation succeeded. |
| `1` | VIPER operation failed. |
| `2` | Command syntax or request validation failed. |

## Shared types

Application models are frozen Pydantic models with unknown fields rejected.
JSON serialization encodes byte fields with URL-safe Base64.

| Type | Values |
|---|---|
| `StageKind` | `download`, `build`, `embed`, `train`, `evaluate` |
| `EnvironmentKind` | `gce` |
| `StorageKind` | `git`, `huggingface` |
| `ProtocolSchemaVersion` | `1` |

`SchemaTypeName` is generated from the application schema registry. The same
registry supplies `get_schema()` and `get_capabilities()`.
