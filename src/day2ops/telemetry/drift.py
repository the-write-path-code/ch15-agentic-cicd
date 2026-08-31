"""Drift detectors over live telemetry windows (Chapter 15.3).

Single responsibility: detect operational drift from per-window telemetry.
The OCC detector consumes hourly optimistic-concurrency conflict counts, the
Chapter 13 signal: version-based OCC rejects stale writes, the agent
re-fetches and re-evaluates, and a rising retry rate means contention or a
stale-read pattern is getting worse. The similarity detector consumes the
rolling mean top-5 retrieval similarity and alerts when it falls below the
baseline band, signaling corpus or embedding drift. Constraints: pure
functions over committed records; alert thresholds are constants, not
configuration guesswork.
"""
from __future__ import annotations

from pydantic import BaseModel

from day2ops.schemas import DriftAlert


class TelemetryWindow(BaseModel):
    window: str
    value: float
    label: str = "stable"


class OccRetryDriftDetector(BaseModel):
    """Alerts when OCC conflict counts exceed the rolling baseline."""

    z_threshold: float = 3.0
    absolute_threshold: float = 25.0

    def detect(self, windows: list[TelemetryWindow]) -> list[DriftAlert]:
        stable = [w.value for w in windows if w.label != "drift"]
        if not stable:
            return []
        mean = sum(stable) / len(stable)
        variance = sum((v - mean) ** 2 for v in stable) / len(stable)
        std = variance ** 0.5 or 1.0
        alerts: list[DriftAlert] = []
        for w in windows:
            z_score = (w.value - mean) / std
            if z_score >= self.z_threshold or w.value >= self.absolute_threshold:
                alerts.append(DriftAlert(
                    window=w.window,
                    value=w.value,
                    reason=(
                        f"occ conflict z-score {z_score:.2f} at or beyond "
                        f"{self.z_threshold} (baseline mean {mean:.2f})"
                        if z_score >= self.z_threshold
                        else f"occ conflicts {w.value:.0f} at or beyond the absolute "
                        f"threshold {self.absolute_threshold}"
                    ),
                ))
        return alerts


class SimilarityDriftDetector(BaseModel):
    """Alerts when mean top-5 retrieval similarity drops below the band."""

    band_low: float = 0.78
    band_high: float = 0.84
    margin: float = 0.0

    def detect(self, windows: list[TelemetryWindow]) -> list[DriftAlert]:
        stable = [w.value for w in windows if w.label != "drift"]
        if not stable:
            return []
        baseline_mean = sum(stable) / len(stable)
        alerts: list[DriftAlert] = []
        floor = min(self.band_low, baseline_mean - self.margin)
        for w in windows:
            if w.value < floor:
                alerts.append(DriftAlert(
                    window=w.window,
                    value=w.value,
                    reason=(
                        f"mean top-5 similarity {w.value:.3f} below the baseline band "
                        f"floor {floor:.3f} (baseline mean {baseline_mean:.3f})"
                    ),
                ))
        return alerts
