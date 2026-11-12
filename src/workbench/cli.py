"""Command line: `workbench run --period 2026-10` (wrapped by `make run`).

Exit codes: 0 = all controls pass or warn; 1 = a control failed (outputs are still written so the
failure can be reviewed); 2 = inputs could not be trusted (nothing written; the message says what to fix).
"""

from __future__ import annotations

import argparse
import sys

from workbench.errors import WorkbenchError
from workbench.pipeline import run

MARK = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workbench", description="RelayCloud billing review workbench")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="run the review for a period")
    p_run.add_argument("--period", required=True, help="review period as YYYY-MM, e.g. 2026-10")
    args = parser.parse_args(argv)

    try:
        result = run(args.period)
    except WorkbenchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"Review {result.period.key} (cutoff {result.period.cutoff})")
    for c in result.controls:
        extra = f"  [{c.count} rows in {c.view}]" if c.count else (f"  ({c.detail})" if c.detail else "")
        print(f"  {MARK[c.status]}  {c.title}{extra}")
    rel = result.period.out_dir.relative_to(result.period.root)
    print(f"Outputs in {rel}/: {', '.join(result.outputs)}")
    if result.failed:
        print(f"{len(result.failed)} control(s) FAILED — see {rel}/report.html#controls", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
