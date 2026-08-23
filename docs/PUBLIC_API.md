# Public Python API

This document defines the approved VIPER 0.1 Python surface. Installed-wheel
tests exercise each path before release. The current pre-release package still
uses the local-only execution names; the stage-invocation increment adds
`viper.stages`, the root stage interface, and the host-neutral `run` operation.

## Modules

| Module | Public responsibility |
| --- | --- |
| `viper.application` | Typed operations, requests, successes, failures, schema discovery, and capability discovery |
| `viper.authoring` | Canonical experiment, variant, benchmark, stage, and run-plan documents |
| `viper.http` | Built-in HTTPX retrieval, project transport decorators, typed transport contexts, and conformance helpers |
| `viper.ids` | Validated identifier types |
| `viper.inspection` | Deterministic attempt status, plan comparison, verified-run comparison, and lineage construction |
| `viper.journal` | Synchronized attempt-state journals |
| `viper.local_store` | Immutable repository-local files and stage snapshots |
| `viper.materialization` | Verified stored-input and same-run input materialization |
| `viper.metrics` | Decorated functions, stateful metrics, comparison, and measurement output |
| `viper.parameter_models` | Project parameter-class loading, identity checks, and validation |
| `viper.preflight` | Complete-plan checks for the active single-host environment |
| `viper.protocol` | Authored and resolved protocol models |
| `viper.resume` | Training resume-state capture, persistence, and restoration |
| `viper.runner` | Complete trusted single-host run execution and publication |
| `viper.serialization` | Duplicate-key-safe parsing and canonical document encoding |
| `viper.stage_execution` | One controlled stage-process invocation on the active host |
| `viper.stages` | Stage decorators, typed contexts, and direct Python execution |
| `viper.verifier` | Run, benchmark, and promoted-artifact verification |
| `viper.worker` | Project command execution through the selected backend |
| `viper.workspace` | Bounded attempt directories and exclusive run ownership |

## Root package

`import viper` exposes these modules:

```python
viper.application
viper.authoring
viper.http
viper.ids
viper.inspection
viper.journal
viper.local_store
viper.materialization
viper.metrics
viper.parameter_models
viper.preflight
viper.protocol
viper.resume
viper.runner
viper.stage_execution
viper.stages
viper.worker
viper.workspace
```

The root package also exposes the project-facing stage interface:

```python
viper.download_stage
viper.build_stage
viper.embed_stage
viper.train_stage
viper.evaluate_stage
viper.http_transport
viper.StageContext
viper.DownloadContext
viper.HttpTransportContext
viper.HttpTransportParams
viper.HttpTransportResult
viper.run
```

`viper.run(stage_callable)` is the ordinary Python adapter. The complete-plan
application operation remains `viper.application.run(request)`.

`viper.StageContext.numpy_generators` exposes the named NumPy generator objects
configured by the frozen run controls. The mapping keys match the names stored
in the stage invocation binding and process-startup receipts.

The release application surface also includes:

```python
viper.application.retry
viper.application.execute_benchmark
viper.application.init_project
```

Import concrete classes and functions from their owning module. For example:

```python
from viper.application import ValidateStageRequest, validate_stage
from viper.protocol import RunSpec
```

## Project parameter models

`viper.protocol.ParameterModelRef` identifies one project-owned Pydantic class
by repository-relative path, top-level symbol, SHA-256 digest, and byte count.
Every `ParameterizedSpec` requires this reference. Download, build, embed,
train, and evaluate specs inherit that contract.

`viper.parameter_models` exposes:

| Function | Result |
| --- | --- |
| `verify_parameter_model_bytes(reference, raw)` | Confirms the frozen byte identity |
| `load_parameter_model(path, symbol, expected_base)` | Loads the selected class and checks its stage-specific base |
| `validate_parameters(path, reference, params, expected_base)` | Returns the class-validated JSON mapping |
| `validate_stage_parameters(repository_root, stage_spec_path, stage)` | Runs stage validation in a dedicated trusted-local worker |
| `validate_loaded_stage_parameters(repository_root, stage_spec_path)` | Loads a parameterized stage and runs the same worker validation |

See [Project parameter models](contracts/PARAMETER_MODELS.md) for the authoring
contract.

## HTTP transports

`viper.http` exposes:

| Name | Responsibility |
| --- | --- |
| `http_transport()` | Decorate one project transport callable and bind its transport ID and parameter class. |
| `HttpTransportContext` | Deliver one frozen request, a runtime credential, a dedicated retrieval workspace, the assigned destination, the retrieval policy, validated transport parameters, and preflight-verified executable paths. |
| `HttpTransportResult` | Return the completed body path and terminal HTTP response. |
| `HttpTransportParams` | Base class for project-defined transport parameters. |
| `run_transport_conformance()` | Exercise a selected transport against the VIPER retrieval contract. |

The built-in transport ID is `httpx`. A `ProjectHttpTransportSpec` freezes a
decorated callable through its repository-relative path, symbol, SHA-256, byte
count, parameter model, complete parameter mapping, and external executable
requirements.

## Serialization compatibility

`viper.serialization.serialize_document()` is the canonical encoder.
`serialize_record()` remains available through the 0.1 release and emits a
`DeprecationWarning`.
