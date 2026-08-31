"""Prometheus export for the telemetry counters (Chapter 15.3).

Single responsibility: expose evaluation and drift counters through
prometheus_client, installed via the `telemetry` extra. Constraints: this
module is small by design and never imported by the default offline path;
CI never requires it.
"""
from __future__ import annotations

PROMETHEUS_IMPORT_ERROR = (
    "the telemetry extra is not installed; run `uv sync --extra telemetry` "
    "to export Prometheus metrics"
)


def build_registry():
    """Return a registry with the drift counters attached."""
    try:
        from prometheus_client import CollectorRegistry, Counter, Gauge
    except ImportError as exc:
        raise ImportError(PROMETHEUS_IMPORT_ERROR) from exc

    registry = CollectorRegistry()
    Counter(
        "day2ops_gate_decisions_total",
        "Gate decisions by outcome", labelnames=["decision"], registry=registry,
    )
    Counter(
        "day2ops_redteam_blocks_total",
        "Red-team blocks by layer", labelnames=["layer"], registry=registry,
    )
    Gauge(
        "day2ops_drift_alerts",
        "Drift alerts currently active", labelnames=["detector"], registry=registry,
    )
    return registry
