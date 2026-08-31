#!/usr/bin/env python3
"""Chapter 15.3: detect live drift from a telemetry fixture or export.

Reads per-window telemetry records, runs the chosen detector, prints drifted
windows, and exits nonzero when drift is found, zero otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from day2ops.config import REPO_ROOT  # noqa: E402
from day2ops.schemas import DriftAlert  # noqa: E402
from day2ops.telemetry.drift import (  # noqa: E402
    OccRetryDriftDetector,
    SimilarityDriftDetector,
    TelemetryWindow,
)

DETECTORS = {
    "occ": OccRetryDriftDetector,
    "similarity": SimilarityDriftDetector,
}
VALUE_KEYS = {
    "occ": ("conflicts", "value", "count"),
    "similarity": ("mean_top5_similarity", "similarity", "value"),
}


def load_windows(path: Path, detector: str) -> list[TelemetryWindow]:
    windows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        value = None
        for key in VALUE_KEYS[detector]:
            if key in raw:
                value = float(raw[key])
                break
        if value is None:
            raise SystemExit(f"record has no value for detector '{detector}': {line[:80]}")
        windows.append(TelemetryWindow(
            window=str(raw.get("window", raw.get("hour", ""))),
            value=value,
            label=str(raw.get("label", "stable")),
        ))
    return windows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="telemetry JSONL file")
    parser.add_argument("--detector", choices=["occ", "similarity"], required=True)
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_absolute():
        source = REPO_ROOT / source

    windows = load_windows(source, args.detector)
    detector = DETECTORS[args.detector]()
    alerts: list[DriftAlert] = detector.detect(windows)

    print(f"detector: {args.detector}, windows: {len(windows)}, alerts: {len(alerts)}")
    if alerts:
        for alert in alerts:
            print(f"  DRIFT {alert.window}: value={alert.value:.3f} ({alert.reason})")
        print("DRIFT DETECTED", file=sys.stderr)
        return 1
    print("no drift detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
