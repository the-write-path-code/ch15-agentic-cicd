#!/usr/bin/env python3
"""Chapter 15.5: promote a golden case to PRODUCTION-FROZEN (one-way ratchet)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from day2ops.config import REPO_ROOT  # noqa: E402
from day2ops.hitl.promote import demote_case, promote_case  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--evidence", required=True, help="URL or reference justifying promotion")
    parser.add_argument("--demote", action="store_true",
                        help="attempt demotion; always refused (ratchet)")
    args = parser.parse_args()

    golden_path = REPO_ROOT / "data/golden/golden_v1.jsonl"
    audit_path = REPO_ROOT / "data/golden/audit_log.jsonl"

    if args.demote:
        try:
            demote_case(args.case_id, golden_path)
        except ValueError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        return 0

    try:
        promoted = promote_case(args.case_id, args.reviewer, args.evidence, golden_path, audit_path)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"promoted {promoted.case_id} to {promoted.status.value} by {args.reviewer}")
    print(f"audit entry appended to {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
