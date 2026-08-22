# Public Python API

VIPER 0.1 supports the modules and names listed here. Installed-wheel tests
exercise each path before release.

## Modules

| Module | Public responsibility |
| --- | --- |
| `viper.application` | Typed operations, requests, successes, failures, schema discovery, and capability discovery |
| `viper.authoring` | Canonical experiment, variant, benchmark, stage, and run-plan documents |
| `viper.ids` | Validated identifier types |
| `viper.inspection` | Deterministic comparison of complete frozen plans |
| `viper.journal` | Synchronized attempt-state journals |
| `viper.local_store` | Immutable repository-local files and stage snapshots |
| `viper.materialization` | Verified stored-input and same-run input materialization |
| `viper.metrics` | Decorated functions, stateful metrics, comparison, and measurement output |
| `viper.preflight` | Complete-plan checks for trusted local execution |
| `viper.protocol` | Authored and resolved protocol models |
| `viper.resume` | Training resume-state capture, persistence, and restoration |
| `viper.runner` | Complete trusted-local run execution and publication |
| `viper.serialization` | Duplicate-key-safe parsing and canonical document encoding |
| `viper.stage_execution` | One local stage-process invocation |
| `viper.verifier` | Run, benchmark, and promoted-artifact verification |
| `viper.worker` | Project command execution through the selected backend |
| `viper.workspace` | Bounded attempt directories and exclusive run ownership |

## Root package

`import viper` exposes these modules:

```python
viper.application
viper.authoring
viper.ids
viper.inspection
viper.journal
viper.local_store
viper.materialization
viper.metrics
viper.preflight
viper.protocol
viper.resume
viper.runner
viper.stage_execution
viper.worker
viper.workspace
```

Import concrete classes and functions from their owning module. For example:

```python
from viper.application import ValidateStageRequest, validate_stage
from viper.protocol import RunSpec
```

## Serialization compatibility

`viper.serialization.serialize_document()` is the canonical encoder.
`serialize_record()` remains available through the 0.1 release and emits a
`DeprecationWarning`.
