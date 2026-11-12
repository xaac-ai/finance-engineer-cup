"""Controls: SQL files that return offending rows. An empty result is a pass.

Each file in sql/controls/<group>/ starts with two header comments:
    -- title: <what the control checks>
    -- severity: fail | warn
The rows are kept as a view `ctl_<group>_<stem>` so the report and reviewers can inspect them.
Adding a control = adding one SQL file; callers never change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.resources import files

import duckdb

SQL_ROOT = files("workbench") / "sql"


@dataclass(frozen=True)
class ControlResult:
    group: str
    name: str
    title: str
    status: str  # pass | warn | fail
    count: int  # offending rows
    view: str | None  # view holding the offending rows, or None for Python-side checks
    detail: str = ""


def _header(sql: str, key: str, default: str) -> str:
    m = re.search(rf"^--\s*{key}:\s*(.+)$", sql, re.MULTILINE)
    return m.group(1).strip() if m else default


def run_controls(con: duckdb.DuckDBPyConnection, group: str) -> list[ControlResult]:
    results = []
    for f in sorted((SQL_ROOT / "controls" / group).iterdir(), key=lambda p: p.name):
        if not f.name.endswith(".sql"):
            continue
        sql = f.read_text()
        stem = f.name.removesuffix(".sql")
        short = re.sub(r"^\d+_", "", stem)
        view = f"ctl_{group}_{short}"
        con.execute(f"CREATE OR REPLACE VIEW {view} AS {sql.strip().rstrip(';')}")
        n = con.execute(f"SELECT count(*) FROM {view}").fetchone()[0]
        severity = _header(sql, "severity", "fail")
        results.append(ControlResult(
            group=group, name=stem, title=_header(sql, "title", stem),
            status="pass" if n == 0 else severity, count=n, view=view,
        ))
    return results


def passed(group: str, name: str, title: str, detail: str) -> ControlResult:
    """Record a check enforced in Python (which raises on failure) so it appears in the report."""
    return ControlResult(group=group, name=name, title=title, status="pass", count=0, view=None, detail=detail)
