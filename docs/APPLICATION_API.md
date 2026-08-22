# VIPER application API

**Status:** Specified. Implementation is tracked in the
[publication checklist](PUBLICATION_TODO.md).

`viper.application` is the public application boundary for Python callers, the
CLI, and agent integrations. Each function accepts one validated request model,
delegates to the owning VIPER operation, and returns one validated success
model.

```text
request model
    │
    ▼
viper.application function
    ├── record validation
    ├── plan authoring
    ├── stage execution
    ├── provenance verification
    └── discovery
    │
    ▼
success model or ViperError
```

## Common records

All application records are frozen Pydantic models.

```python
class ApplicationModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        ser_json_bytes="base64",
        val_json_bytes="base64",
    )


OperationName = Literal[
    "validate_stage",
    "validate_resolved_stage",
    "validate_run",
    "freeze_run",
    "execute_stage",
    "verify_run",
    "verify_benchmark",
    "verify_pointer",
    "get_schema",
    "get_capabilities",
]

StageKind = Literal["download", "build", "embed", "train", "evaluate"]
EnvironmentKind = Literal["gce"]
StorageKind = Literal["git", "huggingface"]
ProtocolSchemaVersion = Literal[1]

ErrorCode = Literal[
    "invalid_request",
    "invalid_record",
    "not_found",
    "write_conflict",
    "io_failed",
    "execution_failed",
    "verification_failed",
    "internal_error",
]


class ApplicationSuccess(ApplicationModel):
    status: Literal["ok"] = "ok"
    operation: OperationName


class ApplicationFailure(ApplicationModel):
    status: Literal["error"] = "error"
    operation: OperationName
    code: ErrorCode
    target: str
    cause: str


class CliFailure(ApplicationModel):
    status: Literal["error"] = "error"
    operation: Literal["cli"] = "cli"
    code: Literal["invalid_request", "internal_error"]
    target: None = None
    cause: str
```

`target` identifies the local path or protocol record associated with the
failure. `CliFailure` covers command parsing and faults caught before an
application operation supplies a target. `cause` states the failed condition.
Callers branch on `code`.

`ViperError` is the public exception for an expected application failure:

```python
class ViperError(Exception):
    failure: ApplicationFailure
```

Application functions translate expected validation, filesystem, execution,
and verification failures into `ViperError`. Unexpected implementation faults
propagate as their original Python exceptions.

## Request records

| Model | Fields |
|---|---|
| `ValidateStageRequest` | `path: Path` |
| `ValidateResolvedStageRequest` | `path: Path` |
| `ValidateRunRequest` | `path: Path` |
| `FreezeRunRequest` | `draft: Path`, `repository_root: Path` |
| `ExecuteStageRequest` | `run_spec: Path`, `stage_id: StageId`, `repository_root: Path`, `timeout_seconds: float | None = None` |
| `VerifyRunRequest` | `path: Path`, `trusted_loader_repositories: frozenset[str]` |
| `VerifyBenchmarkRequest` | `path: Path`, `trusted_loader_repositories: frozenset[str]` |
| `VerifyPointerRequest` | `path: Path`, `trusted_loader_repositories: frozenset[str]`, `expected_data_role: DataRole | None = None`, `materialization_path: RepoRelPath | None = None` |
| `SchemaRequest` | `record_type: RecordTypeName` |
| `CapabilitiesRequest` | No fields. |

## Success records

Every success record extends `ApplicationSuccess` and fixes `operation` to the
corresponding operation name.

| Model | Operation-specific fields |
|---|---|
| `ValidateStageSuccess` | `path: Path`, `stage_kind: StageKind` |
| `ValidateResolvedStageSuccess` | `path: Path`, `stage_kind: StageKind` |
| `ValidateRunSuccess` | `path: Path`, `run_id: RunId`, `stage_ids: tuple[StageId, ...]` |
| `FreezeRunSuccess` | `run_id: RunId`, `files: tuple[Path, ...]` |
| `ExecuteStageSuccess` | `stage_id: StageId`, `command: tuple[str, ...]`, `started_at: AwareDatetime`, `completed_at: AwareDatetime`, `artifacts: dict[ArtifactName, ResolvedArtifact]`, `stdout: bytes`, `stderr: bytes` |
| `VerifyRunSuccess` | `run_id: RunId`, `run_status: Literal["succeeded", "failed", "cancelled"]`, `successful_attempt_id: int | None`, `stage_ids: tuple[StageId, ...]`, `measurement_count: int` |
| `VerifyBenchmarkSuccess` | `benchmark_id: BenchmarkId`, `run_id: RunId`, `benchmark_status: Literal["passed", "failed"]`, `confirmation_attempt_id: int` |
| `VerifyPointerSuccess` | `run: ResolvedRunRef`, `stage_id: StageId`, `artifact_name: ArtifactName`, `data_role: DataRole`, `snapshot: StageResultSnapshotRef`, `files: tuple[SnapshotFileRef, ...]` |
| `SchemaSuccess` | `record_type: RecordTypeName`, `dialect: Literal["https://json-schema.org/draft/2020-12/schema"]`, `schema: dict[str, JsonValue]` |
| `CapabilitiesSuccess` | `package_version: str`, `protocol_schema_versions: tuple[ProtocolSchemaVersion, ...]`, `operations: tuple[OperationName, ...]`, `record_types: tuple[RecordTypeName, ...]`, `stage_kinds: tuple[StageKind, ...]`, `environment_kinds: tuple[EnvironmentKind, ...]`, `storage_kinds: tuple[StorageKind, ...]` |

JSON serialization encodes byte fields with URL-safe Base64. Python callers
receive the original bytes.

## Functions

Delegated operations remain owned by [serialization](../viper/serialization.py),
[authoring](../viper/authoring.py), [stage execution](../viper/stage_execution.py),
and [verification](../viper/verifier.py).

| Signature | Delegated operation | Effects |
|---|---|---|
| `validate_stage(request: ValidateStageRequest) -> ValidateStageSuccess` | `load_stage_spec()` | Reads one local file. |
| `validate_resolved_stage(request: ValidateResolvedStageRequest) -> ValidateResolvedStageSuccess` | `load_resolved_stage()` | Reads one local file. |
| `validate_run(request: ValidateRunRequest) -> ValidateRunSuccess` | Parse as `RunSpec`. | Reads one local file. |
| `freeze_run(request: FreezeRunRequest) -> FreezeRunSuccess` | `load_run_plan_draft()`, then `freeze_run_plan()`. | Writes canonical stage and run `spec.yaml` files. |
| `execute_stage(request: ExecuteStageRequest) -> ExecuteStageSuccess` | Load the selected `RunStageRef` and stage spec, then call `execute_stage_process()`. | Executes the stage script and hashes every declared artifact file it produces. |
| `verify_run(request: VerifyRunRequest, *, fetcher: StorageFetcher | None = None) -> VerifyRunSuccess` | Parse as `ResolvedRun`, then call `verify_run_result()`. | Retrieves referenced files and may execute loaders from trusted repositories. |
| `verify_benchmark(request: VerifyBenchmarkRequest, *, fetcher: StorageFetcher | None = None) -> VerifyBenchmarkSuccess` | Parse as `BenchmarkResult`, then call `verify_benchmark_result()`. | Retrieves referenced files and may execute loaders from trusted repositories. |
| `verify_pointer(request: VerifyPointerRequest, *, fetcher: StorageFetcher | None = None) -> VerifyPointerSuccess` | Parse as `ArtifactPointer`, then call `verify_promoted_artifact()`. | Retrieves referenced files and may execute loaders from trusted repositories. |
| `get_schema(request: SchemaRequest) -> SchemaSuccess` | Generate the registered model or union schema. | None. |
| `get_capabilities(request: CapabilitiesRequest) -> CapabilitiesSuccess` | Read the installed capability registry. | None. |

The validation operations validate one document internally. They do not retrieve
or compare referenced records. The verification operations retrieve the complete
referenced chain required by their existing verifier functions.

## Error classification

| Code | Condition |
|---|---|
| `invalid_request` | CLI or JSON input cannot construct the request model. |
| `invalid_record` | YAML parsing or Pydantic validation rejects a loaded record. |
| `not_found` | A required local or referenced file is absent. |
| `write_conflict` | Authoring would replace an existing file with different bytes. |
| `io_failed` | A local or remote read or write fails for another reason. |
| `execution_failed` | A stage times out, exits unsuccessfully, or omits a declared artifact. |
| `verification_failed` | A loaded provenance relationship, file identity, loader policy, or recorded benchmark outcome is inconsistent. |
| `internal_error` | The CLI catches an unexpected implementation fault at the process boundary. |

| Operations | Expected `ViperError` codes |
|---|---|
| `validate_stage`, `validate_resolved_stage`, `validate_run` | `invalid_record`, `not_found`, `io_failed` |
| `freeze_run` | `invalid_record`, `not_found`, `write_conflict`, `io_failed` |
| `execute_stage` | `invalid_record`, `not_found`, `io_failed`, `execution_failed` |
| `verify_run`, `verify_benchmark`, `verify_pointer` | `invalid_record`, `not_found`, `io_failed`, `verification_failed` |
| `get_schema`, `get_capabilities` | None. A valid request has no expected application failure. |

The CLI alone constructs `internal_error`; Python callers receive the original
unexpected exception. `operation="cli"` identifies command parsing failures
that occur before an application operation is selected.

## CLI mapping

Every installed command calls the corresponding `viper.application` function.

| CLI command | Application function |
|---|---|
| `viper validate-stage` | `validate_stage()` |
| `viper validate-resolved-stage` | `validate_resolved_stage()` |
| `viper validate-run` | `validate_run()` |
| `viper freeze-run` | `freeze_run()` |
| `viper execute-stage` | `execute_stage()` |
| `viper verify-run` | `verify_run()` |
| `viper verify-benchmark` | `verify_benchmark()` |
| `viper verify-pointer` | `verify_pointer()` |
| `viper schema` | `get_schema()` |
| `viper capabilities` | `get_capabilities()` |

Human output remains the default. `--json` writes exactly one serialized success
record to standard output or one serialized failure record to standard error.
The process exits with `0` for success, `1` for an application failure, and `2`
for invalid command syntax.

## Discovery

`get_schema()` uses [Pydantic schema generation](https://docs.pydantic.dev/latest/concepts/json_schema/)
and returns one [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
document. `dialect` is:

```text
https://json-schema.org/draft/2020-12/schema
```

`RecordTypeName` contains every request, success, failure, authored protocol,
and resolved protocol type accepted by the installed package. The registry is
the sole source for both schema discovery and `get_capabilities().record_types`.
`RecordTypeName` is a closed string enum generated from the registry keys.

`get_capabilities()` reports installed support. It does not inspect a user
project or claim that a project supplies the scripts, metrics, loaders,
credentials, or infrastructure required to execute a run.
