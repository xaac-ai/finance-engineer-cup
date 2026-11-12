"""DuckDB connection with the session settings every run depends on."""

from __future__ import annotations

from pathlib import Path

import duckdb

from workbench.period import Period

TIMEZONE = "America/Denver"  # START_HERE · FORMATS: normalized timestamps carry America/Denver offsets


def connect(period: Period, path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open a fresh database and pin the session so results don't depend on the machine.

    - TimeZone is pinned: casting an offset timestamp to a date otherwise uses the laptop's zone.
    - Period parameters are exposed as SQL variables for control and output queries:
      getvariable('cutoff'), getvariable('period_label'), getvariable('period_start'),
      getvariable('period_end').
    """
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        for p in (path, path.with_suffix(path.suffix + ".wal")):
            p.unlink(missing_ok=True)
    con = duckdb.connect(str(path) if path else ":memory:")
    con.execute(f"SET TimeZone = '{TIMEZONE}'")
    con.execute("SET VARIABLE cutoff = CAST(? AS TIMESTAMPTZ)", [period.cutoff])
    con.execute("SET VARIABLE period_label = ?", [period.label])
    con.execute("SET VARIABLE period_start = CAST(? AS DATE)", [period.start.isoformat()])
    con.execute("SET VARIABLE period_end = CAST(? AS DATE)", [period.end_exclusive.isoformat()])
    return con
