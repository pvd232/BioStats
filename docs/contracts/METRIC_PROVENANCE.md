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


class FileMetricDependency(ProtocolModel):
    source: Literal["input", "artifact"]
    name: InputName | ArtifactName
    data_role: DataRole


class AfterStageMetricSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    metric_id: MetricId
    kind: MetricKind
    implementation: MetricImplementationRef
    dependencies: tuple[FileMetricDependency, ...] = Field(min_length=1)
    params: MetricParams
    production: Literal["after_stage"] = "after_stage"
    verification: Literal["recompute"] = "recompute"
    comparator: FloatComparator


class DuringStageMetricSpec(ProtocolModel):
    schema_version: Literal[1] = 1
    metric_id: MetricId
    kind: Literal["training", "diagnostic"]
    implementation: MetricImplementationRef
    params: MetricParams
    production: Literal["during_stage"] = "during_stage"
    verification: Literal["execution"] = "execution"


MetricSpec = Annotated[
    AfterStageMetricSpec | DuringStageMetricSpec,
    Field(discriminator="production"),
]
```

Each stage that selects an `AfterStageMetricSpec` must contain every named
dependency with the declared data role. Dependency pairs of `source` and `name`
are unique.

`DuringStageMetricSpec` governs values produced inside a stage callable. VIPER
loads the frozen implementation and parameters and places a metric handle in
`StageContext`. Project code supplies the live values consumed by
`StatefulMetric.update()`. The 0.1 execution claim covers the selected metric
implementation, its parameters, the active stage, and the measurements written
through the runner-owned sink. A stronger claim about each live tensor requires
a future tensor-capture contract.

The runtime handle has one stable surface:

```python
class DuringStageMetricHandle(Protocol):
    def update(self, *args: object, **kwargs: object) -> None:
        ...

    def record(
        self,
        *args: object,
        epoch: int | None = None,
        step: int | None = None,
        **kwargs: object,
    ) -> Measurement:
        ...
```

For a function metric, `record(...)` invokes the frozen function with the
supplied values and writes its scalar result. For a stateful metric,
`update(...)` advances the frozen class instance and `record()` calls its
`compute()` method before writing the result. The handle supplies the active
run, attempt, stage, and metric identities to `MeasurementSink`.

## Execution

For an after-stage metric, the runner verifies the implementation bytes,
resolves the declared file dependencies, constructs `MetricContext`, invokes
the top-level symbol, and writes the returned scalar through `MeasurementSink`.

For a during-stage metric, the child loads the selected function or stateful
class before invoking the stage callable. `StageContext.metrics[metric_id]`
contains the bound metric handle. Every completed value enters
`MeasurementSink` with the active run, attempt, stage, and metric IDs.

During recomputation, the verifier repeats the after-stage operation from
immutable source and dependency bytes through the execution backend selected
by the effective stage environment.

## Persisted evidence

The frozen `MetricSpec`, resolved dependency files, `Measurement`, stage
invocation receipt, and attempt-file snapshot form the metric evidence.

Each recomputation writes:

```python
class MetricVerificationReceipt(ProtocolModel):
    schema_version: Literal[1] = 1
    metric_id: MetricId
    stage_id: StageId
    measurement: Measurement
    dependency_digest: SHA256
    environment_digest: SHA256
    recomputed_value: float = Field(allow_inf_nan=False)
    comparator: FloatComparator
    passed: bool
    completed_at: AwareDatetime
```

`dependency_digest` hashes the canonical ordered mapping from each declared
dependency to its resolved file identities. `environment_digest` hashes the
effective environment and observed execution context used for recomputation.
The attempt publishes each receipt as an immutable verification file. A
benchmark result references the receipts used for its criteria.

```python
dependency_digest = sha256(
    serialize_document(ordered_resolved_dependencies)
).hexdigest()
environment_digest = sha256(
    serialize_document((effective_environment, execution_context))
).hexdigest()
```

The receipt's embedded `measurement` equals one row in the containing
attempt's measurement file for the same stage and metric.

## Verification

| Check | Rule |
|---|---|
| `metric.implementation` | Source commit and implementation reference identify the retrieved bytes and symbol. |
| `metric.dependencies` | Every after-stage context entry matches one declared stage input or artifact and data role. |
| `metric.parameters` | The invoked mapping equals `MetricSpec.params`. |
| `metric.measurement` | The embedded measurement equals the attempt's recorded row and identifies the active run, attempt, stage, and metric. |
| `metric.execution` | A during-stage measurement was written through the metric handle bound to the active invocation. |
| `metric.recompute` | The recomputation receipt binds the dependencies and environment; its recomputed value satisfies the declared comparator against the recorded value. |

## Propagation

| Surface | Required change |
|---|---|
| Protocol | Add `MetricImplementationRef`, `FileMetricDependency`, the production-specific metric models, and `MetricVerificationReceipt`. |
| Authoring | Resolve decorator metadata, dependency names, and implementation bytes. |
| Preflight | Validate each dependency against every selecting stage. |
| Runtime | Construct an after-stage `MetricContext` from declared file dependencies and inject during-stage metric handles into `StageContext`. |
| Persistence | Store measurements and immutable metric-verification receipts. |
| Verification | Apply implementation, dependency, parameter, identity, and value checks. |
| Tests | Exercise one evaluation metric and one during-stage metric with a rejected undeclared dependency. |

## Acceptance case

An evaluation metric declares the `predictions` artifact and `targets` input.
VIPER supplies those two paths, recomputes the metric through the selected
backend, writes `MetricVerificationReceipt`, and accepts equal values.

The rejection case adds an undeclared `holdout_labels` path to the metric
context. `metric.dependencies` fails before invocation.

## Implementation order

1. Add implementation, dependency, production-specific, and receipt models.
2. Freeze decorator metadata into `MetricSpec`.
3. Restrict execution and recomputation contexts.
4. Add recomputation evidence and verifier rules.
5. Migrate examples and acceptance fixtures.
