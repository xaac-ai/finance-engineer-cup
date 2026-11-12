"""Check a period's input files are present and load every raw CSV into DuckDB as text.

Each raw table is `raw_<file stem>` with every source column as VARCHAR (blank -> NULL, per
START_HERE · FORMATS) plus `source_file` and `source_line` (1-based physical line in the CSV),
so any downstream row can be traced back to the exact line an auditor can open.
"""

from __future__ import annotations

import csv

import duckdb

from workbench.errors import InputError
from workbench.period import Period

RAW_CSVS = [
    "contract_register.csv",
    "netsuite_gl_detail.csv",
    "netsuite_opening_balances.csv",
    "netsuite_revenue_plan_detail.csv",
    "product_account_mapping.csv",
    "product_usage.csv",
    "salesforce_accounts.csv",
    "stripe_credit_note_lines.csv",
    "stripe_credit_notes.csv",
    "stripe_invoice_lines.csv",
    "stripe_invoices.csv",
    "usage_batch_controls.csv",
]
RAW_PDFS = ["START_HERE.pdf", "billing_followups.pdf"]
CURATED = ["period.yaml", "amendment_terms.yaml"]


def check_inputs(period: Period) -> None:
    """Fail with one message listing every missing input, so a new month's drop is fixed in one pass."""
    missing = [period.raw_dir / f for f in RAW_CSVS + RAW_PDFS if not (period.raw_dir / f).exists()]
    if not (period.raw_dir / "contracts").is_dir():
        missing.append(period.raw_dir / "contracts")
    missing += [period.curated_dir / f for f in CURATED if not (period.curated_dir / f).exists()]
    if not (period.reference_dir / "accounts.csv").exists():
        missing.append(period.reference_dir / "accounts.csv")
    if missing:
        listing = "\n  ".join(str(p.relative_to(period.root)) for p in missing)
        raise InputError(f"Missing inputs for period {period.key}:\n  {listing}")


def load_csv(con: duckdb.DuckDBPyConnection, table: str, path, source_file: str) -> int:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = []
        for rec in reader:
            if not rec:
                continue
            if len(rec) != len(header):
                raise InputError(f"{source_file} line {reader.line_num}: expected {len(header)} fields, got {len(rec)}.")
            rows.append([v if v != "" else None for v in rec] + [source_file, reader.line_num])
    cols = ", ".join(f'"{h}" VARCHAR' for h in header)
    con.execute(f'CREATE OR REPLACE TABLE "{table}" ({cols}, source_file VARCHAR, source_line INTEGER)')
    if rows:
        con.executemany(f'INSERT INTO "{table}" VALUES ({", ".join("?" * (len(header) + 2))})', rows)
    return len(rows)


def load_raw(con: duckdb.DuckDBPyConnection, period: Period) -> dict[str, int]:
    """Load every raw CSV and the curated expected counts. Returns physical row counts per file."""
    counts = {}
    for name in RAW_CSVS:
        rel = f"data/raw/{period.key}/{name}"
        counts[name] = load_csv(con, f"raw_{name.removesuffix('.csv')}", period.raw_dir / name, rel)
    con.execute("CREATE OR REPLACE TABLE input_row_counts (file VARCHAR, actual INTEGER, expected INTEGER)")
    con.executemany(
        "INSERT INTO input_row_counts VALUES (?, ?, ?)",
        [[f, counts.get(f), period.expected_counts.get(f)] for f in sorted(set(counts) | set(period.expected_counts))],
    )
    return counts
