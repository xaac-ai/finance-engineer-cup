"""The books as one DuckDB table, checked by SQL ledger controls (docs/adr/0001-no-ledger-engine.md)."""

from __future__ import annotations

import duckdb

from workbench.controls import SQL_ROOT, ControlResult, run_controls
from workbench.inputs import load_csv
from workbench.period import Period


def build_journal(con: duckdb.DuckDBPyConnection, period: Period) -> int:
    """Load the chart of accounts and build `journal_lines` (Opening Balances + Recorded Entries)."""
    load_csv(con, "accounts", period.reference_dir / "accounts.csv", "data/reference/accounts.csv")
    con.execute((SQL_ROOT / "ledger" / "journal_lines.sql").read_text())
    return con.execute("SELECT count(*) FROM journal_lines").fetchone()[0]


def run_ledger_controls(con: duckdb.DuckDBPyConnection) -> list[ControlResult]:
    return run_controls(con, "ledger")
