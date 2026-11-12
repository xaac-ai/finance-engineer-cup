"""Combined October effects: coverage, totals by stream, and the cross-stream controls."""

import shutil
from decimal import Decimal as D
from pathlib import Path

import duckdb
import pytest

from workbench.controls import SQL_ROOT, run_controls
from workbench.period import load_period
from workbench.pipeline import run

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    root = tmp_path_factory.mktemp("effects")
    shutil.copytree(REPO / "data", root / "data")
    assert run("2026-10", root).failed == []
    return root


def _open(root):
    """Reopen the run's database with the session variables the views read."""
    period = load_period("2026-10", root)
    con = duckdb.connect(str(period.out_dir / "workbench.duckdb"))
    con.execute("SET TimeZone = 'America/Denver'")
    con.execute("SET VARIABLE cutoff = CAST(? AS TIMESTAMPTZ)", [period.cutoff])
    con.execute("SET VARIABLE period_label = ?", [period.label])
    con.execute("SET VARIABLE period_start = CAST(? AS DATE)", [period.start.isoformat()])
    con.execute("SET VARIABLE period_end = CAST(? AS DATE)", [period.end_exclusive.isoformat()])
    return con


def test_coverage_is_every_customer_and_stream(root):
    con = _open(root)
    counts = dict(con.execute("SELECT status, count(*) FROM coverage GROUP BY ALL").fetchall())
    assert sum(counts.values()) == 60
    assert counts == {"clean": 51, "error": 5, "valid_explanation": 3, "needs_info": 1}


def test_totals_by_stream(root):
    con = _open(root)
    rows = con.execute("SELECT stream, underbilled, overbilled, october_understated, october_overstated "
                       "FROM totals_by_stream ORDER BY stream").fetchall()
    assert rows == [("platform", D("526.03"), D("0.00"), D("526.03"), D("0.00")),
                    ("usage", D("6309.50"), D("-3096.80"), D("6209.50"), D("-3096.80"))]


def test_every_customer_ends_with_no_unbilled_residual(root):
    con = _open(root)
    assert con.execute("SELECT count(*) FROM customer_effects WHERE account_number = '1150' AND next_after <> 0").fetchone() == (0,)


def _add_proposed(con, entry_id, lines):
    for n, (customer, account, dr, cr) in enumerate(lines, 1):
        con.execute("""INSERT INTO journal_lines BY NAME SELECT ? AS entry_id, ? AS line_no, 'proposed' AS status,
            'proposed_october_adjustment' AS entry_kind, DATE '2026-10-31' AS date, 'Oct 2026' AS posting_period,
            ? AS account_number, ? AS customer_id, ?::DECIMAL(18,2) AS debit, ?::DECIMAL(18,2) AS credit, 'F-TEST' AS finding_id""",
                    [entry_id, n, account, customer, dr, cr])


@pytest.mark.parametrize("lines, control", [
    ([("186097", "1150", 10, 0), ("186097", "4010", 0, 10)], "01_no_unbilled_residual"),           # accrual never billed
    ([("335780", "2200", 10, 0), ("335780", "4000", 0, 10)], "02_contract_asset_after_corrections"),  # reclass not recomputed
    ([("186097", "1150", 10, 0), ("866587", "4010", 0, 10)], "03_no_netting"),                      # two customers
    ([("186097", "1150", 10, 0), ("186097", "4000", 0, 10)], "03_no_netting"),                      # usage against platform
])
def test_effects_controls_catch_bad_proposals(root, lines, control):
    con = _open(root)
    _add_proposed(con, "P-TEST", lines)
    con.execute((SQL_ROOT / "effects.sql").read_text())
    failed = {r.name for r in run_controls(con, "effects") if r.status == "fail"}
    con.execute("DELETE FROM journal_lines WHERE entry_id = 'P-TEST'")
    assert control in failed
