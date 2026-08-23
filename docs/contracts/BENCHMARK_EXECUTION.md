# Benchmark execution

## Status

Benchmark models and verification are implemented. Production of the
independent confirmation is approved for VIPER 0.1.

## Required claim

VIPER can execute the confirmation required by a frozen `BenchmarkSpec`, build
the resulting `BenchmarkResult`, and verify it through the existing benchmark
rules.

## Current gap

[`verify_benchmark_result()`](../../viper/verifier.py) verifies a supplied
confirmation attempt, estimator parity, prediction parity, metric criteria,
and benchmark status. Confirmation execution and result assembly remain outside
the public application surface.

Users currently assemble the confirmation and benchmark result themselves.

## Application operation

```python
class ExecuteBenchmarkRequest(ProtocolModel):
    resolved_run: Path
    benchmark_spec: Path
    repository_root: Path
    timeout_seconds: float | None = Field(default=None, gt=0)


class ExecuteBenchmarkSuccess(ProtocolModel):
    result: BenchmarkResult
    result_path: Path
```

The selected `BenchmarkSpec` fixes the evaluation identity, input
selection, metric criteria, and required execution count. VIPER 0.1 fixes:

```python
class BenchmarkSpec(ProtocolModel):
    execution_count: Literal[2] = 2
```

The count includes the selected candidate execution and one independent
confirmation. The field replaces the current `confirmation_count` name.

## Execution

VIPER performs this sequence for the one required confirmation:

```text
verify the candidate run
-> execute the same frozen run plan as a new attempt
-> preserve distinct resolved stage snapshots
-> recompute the benchmark metrics
-> compare estimator and prediction artifacts
-> apply every benchmark criterion
-> construct BenchmarkResult
-> verify BenchmarkResult
```

The confirmation uses the same frozen plan. It receives a new attempt ID and
new execution evidence. Its `RunAttempt.purpose` is
`benchmark_confirmation`; the candidate run history continues to contain only
ordinary run and retry attempts.

## Persisted evidence

The benchmark result stores these comparison receipts:

```python
class ArtifactComparisonReceipt(ProtocolModel):
    artifact: StageArtifactRef
    candidate_stage: ResolvedStageRef
    confirmation_stage: ResolvedStageRef
    candidate_digest: SHA256
    confirmation_digest: SHA256
    passed: bool


class MetricCriterionReceipt(ProtocolModel):
    metric_id: MetricId
    candidate_verification: ResolvedFileRef
    confirmation_verification: ResolvedFileRef
    comparison: Literal["ge", "le"]
    threshold: float = Field(allow_inf_nan=False)
    passed: bool


class BenchmarkResult(ProtocolModel):
    schema_version: Literal[1] = 1
    benchmark: ResolvedBenchmarkSpecRef
    run: ResolvedRunRef
    confirmation: ResolvedAttemptRef
    artifacts: tuple[ArtifactComparisonReceipt, ...] = Field(min_length=2)
    metrics: tuple[MetricCriterionReceipt, ...] = Field(min_length=1)
    status: Literal["passed", "failed"]
    completed_at: AwareDatetime
```

Each artifact digest hashes the canonical `ResolvedArtifact` description from
the selected stage snapshot. The two required artifact receipts select
`parameters` and `predictions`. Each metric receipt references the immutable
`MetricVerificationReceipt` files produced for the candidate and confirmation
attempts.

`BenchmarkResult.artifacts` contains exactly those two receipts. Its metric IDs
equal the IDs in `BenchmarkSpec.metrics`. Every referenced
`MetricVerificationReceipt.passed` value is true before the threshold is
applied.

## Verification

`execute_benchmark()` returns after `verify_benchmark_result()` accepts the
newly constructed result. The verifier reconstructs every artifact digest,
loads every metric-verification receipt, applies every threshold, and derives
the expected final status. It also requires the confirmation attempt ID to
exceed every candidate run attempt ID and its purpose to equal
`benchmark_confirmation`.

## Propagation

| Surface | Required change |
|---|---|
| Application | Add typed execute-benchmark request, success, and failure results. |
| CLI | Add `viper execute-benchmark` with human and JSON output. |
| Runner | Execute the confirmation through the selected backend. |
| Metrics | Recompute every benchmark metric from its declared dependencies. |
| Persistence | Publish the immutable benchmark result, confirmation attempt, artifact-comparison receipts, and metric-criterion receipts. |
| Tests | Execute one passing confirmation and reject one altered artifact. |

## Acceptance case

The candidate run trains and evaluates one model. `execute_benchmark()` runs the
same frozen plan as attempt `2`, recomputes the declared evaluation metric, and
publishes a passing `BenchmarkResult` after artifact parity and metric criteria
pass.

Replacing one prediction file with different bytes of the same length causes
benchmark verification to fail on its SHA-256 identity.

## Implementation order

1. Add the application operation and result models.
2. Reuse the attempt allocator and selected execution backend.
3. Construct benchmark evidence from the verified candidate and confirmation.
4. Call the existing benchmark verifier before publication.
5. Add installed-wheel CLI and acceptance coverage.
