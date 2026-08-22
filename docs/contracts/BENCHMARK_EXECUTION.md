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
    backend: ExecutionBackend
    timeout_seconds: float | None = Field(default=None, gt=0)


class ExecuteBenchmarkSuccess(ProtocolModel):
    result: BenchmarkResult
    result_path: Path
```

The selected `BenchmarkSpec` fixes the evaluation identity, input
selection, metric criteria, and required confirmation count.

## Execution

For each required confirmation, VIPER performs this sequence:

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
new execution evidence.

## Persisted evidence

The benchmark result identifies the candidate run, confirmation attempt,
benchmark specification, compared artifact files, recomputed measurements,
comparator outcomes, and final status.

## Verification

`execute_benchmark()` must return only after `verify_benchmark_result()` accepts
the newly constructed result. Existing benchmark verifier rules remain the
authority for parity and criteria.

## Propagation

| Surface | Required change |
|---|---|
| Application | Add typed execute-benchmark request, success, and failure results. |
| CLI | Add `viper execute-benchmark` with human and JSON output. |
| Runner | Execute the confirmation through the selected backend. |
| Metrics | Recompute every benchmark metric from its declared dependencies. |
| Persistence | Publish the immutable benchmark result and its referenced evidence. |
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
