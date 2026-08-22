# Public Python API

VIPER 0.1 supports the modules and names listed here. Installed-wheel tests
exercise each path before release.

## Modules

| Module | Public responsibility |
| --- | --- |
| `viper.application` | Typed operations, requests, successes, failures, schema discovery, and capability discovery |
| `viper.authoring` | Canonical experiment, variant, benchmark, stage, and run-plan documents |
| `viper.ids` | Validated identifier types |
| `viper.journal` | Synchronized attempt-state journals |
| `viper.metrics` | Decorated functions, stateful metrics, comparison, and measurement output |
| `viper.protocol` | Authored and resolved protocol models |
| `viper.resume` | Training resume-state capture, persistence, and restoration |
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
viper.journal
viper.metrics
viper.protocol
viper.resume
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
