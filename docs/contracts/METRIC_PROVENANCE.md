# Metric provenance

## Status

Metric decorators, measurement writing, floating-point comparators, and
post-stage recomputation are implemented. Exact dependency binding and complete
implementation identity are approved for VIPER 0.1.

## Required claim

VIPER verifies that one metric value came from the frozen metric implementation,
its declared dependencies, its frozen parameters, and its effective execution
environment.

## Current gap

`MetricSpec` stores an implementation path and symbol. `RunSpec.source` supplies
the repository and commit. During execution and recomputation,
[`MetricContext`](../../viper/metrics.py) receives every input and artifact of
the stage that selected the metric.

The current path identifies the implementation. It leaves the metric's actual
dependency set implicit. Determining the authorized stage values requires
inspection of project code.

## Contract models

```python
class MetricImplementationRef(ProtocolModel):
    path: PythonRepoRelPath
    symbol: PythonSymbol
    sha256: SHA256
    bytes: int = Field(gt=0)


class MetricDependency(ProtocolModel):
    source: Literal["input", "artifact"]
    name: InputName | ArtifactName
    data_role: DataRole


class MetricSpec(ProtocolModel):
    metric_id: MetricId
    kind: MetricKind
    implementation: MetricImplementationRef
    dependencies: tuple[MetricDependency, ...]
    params: MetricParams
    production: MetricProduction
    verification: MetricVerification
    comparator: FloatComparator
```

Each stage that selects a metric must contain every named dependency with the
declared data role.

## Execution

The runner verifies the implementation bytes, resolves only the declared
dependencies, constructs `MetricContext`, invokes the top-level symbol, and
writes the returned scalar through `MeasurementSink`.

During recomputation, the verifier repeats the same operation from immutable
source and artifact bytes inside the selected execution backend.

## Persisted evidence

The frozen `MetricSpec`, resolved dependency files, `Measurement`, stage
invocation receipt, and attempt-file snapshot form the metric evidence. A
benchmark result also stores the recomputation result and comparator outcome.

## Verification

| Check | Rule |
|---|---|
| `metric.implementation` | Source commit and implementation reference identify the retrieved bytes and symbol. |
| `metric.dependencies` | Every context entry matches one declared stage input or artifact and data role. |
| `metric.parameters` | The invoked mapping equals `MetricSpec.params`. |
| `metric.measurement` | The measurement identifies the active run, attempt, stage, and metric. |
| `metric.recompute` | The recomputed value satisfies the declared comparator against the recorded value. |

## Propagation

| Surface | Required change |
|---|---|
| Protocol | Add `MetricImplementationRef` and `MetricDependency`. |
| Authoring | Resolve decorator metadata, dependency names, and implementation bytes. |
| Preflight | Validate each dependency against every selecting stage. |
| Runtime | Construct `MetricContext` from the declared dependency set. |
| Persistence | Store measurement and recomputation evidence. |
| Verification | Apply implementation, dependency, parameter, identity, and value checks. |
| Tests | Exercise one evaluation metric and one during-stage metric with a rejected undeclared dependency. |

## Acceptance case

An evaluation metric declares the `predictions` artifact and `targets` input.
VIPER supplies those two paths, recomputes the metric, and accepts equal values.

The rejection case adds an undeclared `holdout_labels` path to the metric
context. `metric.dependencies` fails before invocation.

## Implementation order

1. Add implementation and dependency models.
2. Freeze decorator metadata into `MetricSpec`.
3. Restrict execution and recomputation contexts.
4. Add recomputation evidence and verifier rules.
5. Migrate examples and acceptance fixtures.
