#!/usr/bin/env python3
"""Chapter 15.5: convert reviewer overrides into golden cases and twins."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from day2ops.config import REPO_ROOT  # noqa: E402
from day2ops.hitl.capture import capture_overrides  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overrides", default="data/hitl/overrides/overrides_seed.jsonl")
    parser.add_argument("--golden", default="data/golden/golden_v1.jsonl")
    parser.add_argument("--retired", default="data/golden/retired_ids.json")
    parser.add_argument("--adversarial", default="data/adversarial/adversarial_hitl.jsonl")
    args = parser.parse_args()

    result = capture_overrides(
        overrides_path=REPO_ROOT / args.overrides,
        golden_path=REPO_ROOT / args.golden,
        retired_ids_path=REPO_ROOT / args.retired,
        adversarial_path=REPO_ROOT / args.adversarial,
    )
    print(json.dumps(result, indent=2))
    if result["rejected"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
