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
    "billing_reconciliation",
    "revenue_reconciliation",
    "findings",
    "finding_calculations",
    "finding_evidence",
    "proposed_billing_documents",
    "usage_by_customer",
    "usage_batch_tieout",
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
    def j(sql):
        return [{k: _jsonable(v) for k, v in r.items()} for r in _rows(con, sql)]

    tb = j("SELECT * FROM out_trial_balance_by_account")
    found = j("SELECT f.*, s.\"AccountName\" AS customer_name FROM out_findings f "
              "LEFT JOIN raw_salesforce_accounts s ON s.\"NetSuiteCustomerInternalId__c\" = f.customer_id")
    calcs, evid = j("SELECT * FROM out_finding_calculations"), j("SELECT * FROM out_finding_evidence")
    docs, entries = j("SELECT * FROM out_proposed_billing_documents"), j("SELECT * FROM out_proposed_journal_entries")
    for f in found:
        fid = f["finding_id"]
        f["calculation"] = [c for c in calcs if c["finding_id"] == fid]
        f["evidence"] = [e for e in evid if e["finding_id"] == fid]
        f["documents"] = [d for d in docs if d["finding_id"] == fid]
        f["entries"] = [e for e in entries if e["finding_id"] == fid]
    index: dict[tuple, dict] = {}
    for e in evid:
        k = (e["file"], e["line"], e["text"])
        index.setdefault(k, {"file": e["file"], "line": e["line"], "kind": e["kind"], "text": e["text"], "cited_by": []})
        if e["finding_id"] not in index[k]["cited_by"]:
            index[k]["cited_by"].append(e["finding_id"])
    totals = j("""SELECT
        coalesce(sum(CASE WHEN status = 'error' AND billing_effect > 0 THEN billing_effect END), 0) AS underbilled,
        coalesce(sum(CASE WHEN status = 'error' AND billing_effect < 0 THEN billing_effect END), 0) AS overbilled,
        coalesce(sum(CASE WHEN status = 'error' AND october_revenue_effect > 0 THEN october_revenue_effect END), 0) AS october_understated,
        coalesce(sum(CASE WHEN status = 'error' AND october_revenue_effect < 0 THEN october_revenue_effect END), 0) AS october_overstated,
        count(*) FILTER (WHERE status = 'needs_info' AND exposure IS NOT NULL) AS exposure_items
        FROM out_findings""")[0]
    data = {
        "run": {"period": period.key, "label": period.label, "cutoff": period.cutoff,
                "command": f"make run PERIOD={period.key}", "commit": _git_commit(period)},
        "stats": stats,
        "controls": [asdict(c) for c in controls],
        "customers": customers,
        "findings": found,
        "evidence": sorted(index.values(), key=lambda e: (e["file"], e["line"] or 0)),
        "totals": totals,
        "billing_reconciliation": j("SELECT * FROM out_billing_reconciliation"),
        "revenue_reconciliation": j("SELECT * FROM out_revenue_reconciliation"),
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
