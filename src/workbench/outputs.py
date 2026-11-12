"""Write a period's reviewable outputs: CSV workpapers and the self-contained report.html.

Decision (wayfinder: "What should the review report look like?"): one static HTML file per run,
data embedded as JSON, plain JavaScript, no CDN, works from file://. Findings workbench is the
default view; Customers, Brief, Controls & assumptions and Evidence index are the other views.
"""

from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import asdict
from decimal import Decimal
from importlib.resources import files

import duckdb

from workbench.controls import SQL_ROOT, ControlResult
from workbench.period import Period

# Workpaper name -> SQL file in sql/outputs. Order matters: by_account reads out_trial_balance.
WORKPAPERS = [
    "trial_balance",
    "trial_balance_by_account",
    "proposed_journal_entries",
    "journal_lines",
    "contract_terms",
    "billing_messages",
    "customers",
]

# Policies applied by the workbench, each cited to its source (START_HERE.pdf section).
ASSUMPTIONS = [
    ("Money is exact decimal USD; every rounding step is half up; Stripe cents convert by x 0.01.", "START_HERE · MONEY"),
    ("Timestamps are interpreted in America/Denver; the cutoff is fixed per period in data/curated/<period>/period.yaml.", "START_HERE · FORMATS, REQUIRED SCOPE"),
    ("An Amendment changes only the terms it names, from its effective date; unchanged terms persist.", "START_HERE · SOURCE PRECEDENCE"),
    ("Blank CSV fields mean missing / not applicable, never zero.", "START_HERE · FORMATS"),
    ("Balances are kept per customer x account; customers are never netted against each other.", "START_HERE · ACCOUNTING"),
]


def _git_commit(period: Period) -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=period.root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=period.root, capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _jsonable(v):
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def write_workpapers(con: duckdb.DuckDBPyConnection, period: Period, controls: list[ControlResult]) -> list[str]:
    period.out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in WORKPAPERS:
        sql = (SQL_ROOT / "outputs" / f"{name}.sql").read_text().strip().rstrip(";")
        con.execute(f"CREATE OR REPLACE VIEW out_{name} AS {sql}")
        path = period.out_dir / f"{name}.csv"
        con.execute(f"COPY (SELECT * FROM out_{name}) TO '{path}' (HEADER, DELIMITER ',')")
        written.append(path.name)
    with open(period.out_dir / "controls.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(asdict(controls[0]).keys()))
        w.writeheader()
        for c in controls:
            w.writerow(asdict(c))
    written.append("controls.csv")
    return written


def write_report(con: duckdb.DuckDBPyConnection, period: Period, controls: list[ControlResult], stats: dict, workpapers: list[str]) -> str:
    customers = [{k: _jsonable(v) for k, v in r.items()} for r in _rows(con, "SELECT * FROM out_customers")]
    tb = [{k: _jsonable(v) for k, v in r.items()} for r in _rows(con, "SELECT * FROM out_trial_balance_by_account")]
    data = {
        "run": {"period": period.key, "label": period.label, "cutoff": period.cutoff,
                "command": f"make run PERIOD={period.key}", "commit": _git_commit(period)},
        "stats": stats,
        "controls": [asdict(c) for c in controls],
        "customers": customers,
        "findings": [],  # filled by the accounting logic (separate map)
        "evidence": [],  # every cited source row, derived from findings
        "trial_balance_by_account": tb,
        "assumptions": [{"text": t, "source": s} for t, s in ASSUMPTIONS],
        "workpapers": workpapers,
    }
    blob = json.dumps(data, indent=1, sort_keys=True).replace("</", "<\\/")
    template = (files("workbench") / "templates" / "report.html").read_text(encoding="utf-8")
    html = template.replace("/*__REPORT_DATA__*/null", blob)
    path = period.out_dir / "report.html"
    path.write_text(html, encoding="utf-8")
    return path.name
