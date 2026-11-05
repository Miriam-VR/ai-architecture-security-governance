"""Run the evaluation suite and gate on thresholds (used by CI). Exit code 1 if a gate fails."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.runner import run_all, scorecard_markdown  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-golden", type=float, default=1.0)
    ap.add_argument("--min-adversarial", type=float, default=1.0)
    ap.add_argument("--out", default="evaluation_report.json")
    a = ap.parse_args()
    s = run_all()
    Path(a.out).write_text(json.dumps(s, indent=2, default=str))
    print(scorecard_markdown(s))
    ok = s["golden_pass_rate"] >= a.min_golden and s["adversarial_blocked"] / s["adversarial_total"] >= a.min_adversarial
    print("\nGATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
