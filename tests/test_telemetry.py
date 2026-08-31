"""Behavior tests for the telemetry stores and drift detectors (Chapter 15.3)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from day2ops.config import REPO_ROOT, Settings
from day2ops.telemetry.drift import (
    OccRetryDriftDetector,
    SimilarityDriftDetector,
    TelemetryWindow,
)
from day2ops.telemetry.store import JsonlStore, OpikStore, default_store


def _script_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    parts = [p for p in existing.split(os.pathsep) if p]
    src = str(REPO_ROOT / "src")
    if src not in parts:
        parts.append(src)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def test_jsonl_store_roundtrip(tmp_path: Path) -> None:
    store = JsonlStore(tmp_path / "telemetry.jsonl")
    assert store.is_active
    store.record({"event": "gate_decision", "decision": "ANSWER"})
    store.record({"event": "gate_decision", "decision": "ABSTAIN"})
    lines = (tmp_path / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["decision"] == "ANSWER"


def test_opik_store_inactive_without_opt_in() -> None:
    store = OpikStore(Settings())
    assert not store.is_active
    store.record({"anything": 1})  # must be a silent no-op


def test_opik_store_inactive_without_api_key() -> None:
    store = OpikStore(Settings(opik_enabled=True, opik_api_key=None))
    assert not store.is_active


def test_default_store_is_offline_jsonl(tmp_path: Path) -> None:
    store = default_store(tmp_path / "telemetry.jsonl")
    assert isinstance(store, JsonlStore)


def test_occ_drift_detected_on_spike_windows() -> None:
    windows = [
        TelemetryWindow(window=f"hour-{i:02d}", value=2 + (i % 3))
        for i in range(24)
    ]
    for hour in (14, 15, 16):
        windows[hour] = TelemetryWindow(window=f"hour-{hour:02d}", value=27 + hour - 14, label="drift")
    alerts = OccRetryDriftDetector().detect(windows)
    assert [a.window for a in alerts] == ["hour-14", "hour-15", "hour-16"]
    assert all(a.value >= 25 for a in alerts)


def test_similarity_drift_detected_on_band_drop() -> None:
    windows = [
        TelemetryWindow(window=f"hour-{i:02d}", value=0.80)
        for i in range(24)
    ]
    for hour in (14, 15, 16, 17):
        windows[hour] = TelemetryWindow(
            window=f"hour-{hour:02d}", value=0.61 + 0.01 * (hour - 14), label="drift"
        )
    alerts = SimilarityDriftDetector().detect(windows)
    assert [a.window for a in alerts] == ["hour-14", "hour-15", "hour-16", "hour-17"]
    assert all(a.value < 0.78 for a in alerts)


def test_stable_series_produces_no_alerts() -> None:
    occ = [TelemetryWindow(window=f"h{i}", value=3.0) for i in range(24)]
    assert OccRetryDriftDetector().detect(occ) == []
    sim = [TelemetryWindow(window=f"h{i}", value=0.80) for i in range(24)]
    assert SimilarityDriftDetector().detect(sim) == []


def test_detect_drift_script_occ_exits_nonzero() -> None:
    result = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "scripts/detect_drift.py"),
            "--source", "data/telemetry/fixtures/occ_retries.jsonl",
            "--detector", "occ",
        ],
        capture_output=True, text=True, timeout=120, env=_script_env(),
    )
    assert result.returncode != 0
    assert "DRIFT hour-14" in result.stdout
    assert "DRIFT DETECTED" in result.stderr


def test_detect_drift_script_similarity_exits_nonzero() -> None:
    result = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "scripts/detect_drift.py"),
            "--source", "data/telemetry/fixtures/retrieval_similarity.jsonl",
            "--detector", "similarity",
        ],
        capture_output=True, text=True, timeout=120, env=_script_env(),
    )
    assert result.returncode != 0
    assert "DRIFT hour-14" in result.stdout


def test_prometheus_export_builds_registry() -> None:
    pytest_importorskip = __import__("pytest").importorskip
    pytest_importorskip("prometheus_client")
    from day2ops.telemetry.prometheus_export import build_registry

    registry = build_registry()
    assert registry is not None
