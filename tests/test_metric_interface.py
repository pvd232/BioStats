"""Tests for project metric authoring, execution, and measurement output."""

import json
from pathlib import Path

from viper.metrics import (
    MeasurementSink,
    MetricContext,
    StatefulMetric,
    compare_metric_values,
    load_metric,
    metric,
)
from viper.protocol import FloatComparator, MetricParams


@metric(metric_id="mean_value", kind="evaluation")
def mean_value(context: MetricContext) -> float:
    """Return the frozen scalar supplied through metric parameters."""
    return float(context.params.model_dump()["value"])


@metric(metric_id="running_mean", kind="training")
class RunningMean(StatefulMetric):
    """Accumulate a scalar mean across training updates."""

    def __init__(self) -> None:
        """Initialize an empty accumulator."""
        self.total = 0.0
        self.count = 0

    def update(self, value: float) -> None:
        """Add one scalar observation."""
        self.total += value
        self.count += 1

    def compute(self) -> float:
        """Return the accumulated arithmetic mean."""
        return self.total / self.count


def test_decorators_define_stateless_and_stateful_metrics() -> None:
    """Attach the correct role and invocation timing to both authoring forms."""
    assert mean_value.__viper_metric__.production == "after_stage"  # type: ignore[attr-defined]
    assert mean_value.__viper_metric__.verification == "recompute"  # type: ignore[attr-defined]
    assert RunningMean.__viper_metric__.production == "during_stage"  # type: ignore[attr-defined]
    metric_value = RunningMean()
    metric_value.update(1.0)
    metric_value.update(3.0)
    assert metric_value.compute() == 2.0


def test_metric_loader_invokes_top_level_symbol(tmp_path: Path) -> None:
    """Load and invoke a metric from one selected repository-relative file."""
    implementation = tmp_path / "project_metric.py"
    implementation.write_text(
        "def compute(context):\n    return float(context.params.value)\n",
        encoding="utf-8",
    )
    loaded = load_metric(implementation, "compute")
    context = MetricContext(
        params=MetricParams.model_validate({"schema_version": 1, "value": 4.5})
    )

    assert loaded(context) == 4.5


def test_measurement_sink_writes_verifier_compatible_jsonl(tmp_path: Path) -> None:
    """Write one complete Measurement row and synchronize its bytes."""
    path = tmp_path / "evaluate.mean_value.jsonl"
    sink = MeasurementSink(
        path,
        run_id="01JABCDEFGHJKMNPQRSTVWXYZ0",
        attempt_id=1,
        stage_id="evaluate",
        metric_id="mean_value",
    )

    measurement = sink.append(2.5)
    row = json.loads(path.read_text(encoding="utf-8"))

    assert measurement.value == 2.5
    assert row["metric_id"] == "mean_value"


def test_metric_comparator_applies_declared_tolerance() -> None:
    """Accept recomputed values within the declared absolute tolerance."""
    comparator = FloatComparator(mode="absolute", tolerance=0.01)

    assert compare_metric_values(1.0, 1.005, comparator)
    assert not compare_metric_values(1.0, 1.02, comparator)
