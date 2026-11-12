"""Usage stream: validated usage, expected billing / accrual, and the usage finding rules.

Pinned to hand-checked values (wayfinder: "What does the October data actually contain?").
"""

import shutil
from decimal import Decimal as D
from pathlib import Path

import duckdb
import pytest

from workbench.errors import InputError
from workbench.pipeline import run
from workbench.streams.usage import LATE, _allocate_revenue

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    root = tmp_path_factory.mktemp("usage")
    shutil.copytree(REPO / "data", root / "data")
    result = run("2026-10", root)
    assert result.failed == []
    con = duckdb.connect(str(root / "out" / "2026-10" / "workbench.duckdb"), read_only=True)
    yield con
    con.close()


def by_customer(db, name):
    cols = ["units", "allowance", "expected_billing", "expected_accrual", "billed"]
    row = db.execute(f"SELECT {', '.join(cols)} FROM usage_by_customer WHERE customer_name LIKE ?", [name + "%"]).fetchone()
    return dict(zip(cols, row))


@pytest.mark.parametrize("name, allowance, expected, billed", [
    ("Cedar Harbor", 37742, "8291.20", "11388.00"),   # AM-OF-2026-157 day-weighted allowance
    ("Juniper Signal", 30000, "4560.32", "1425.10"),  # 28,502 × $0.16 contract rate
    ("Yarrow Ridge", 30000, "3074.28", "0.00"),       # no invoice issued
    ("Silver Current", 20000, "3135.96", "3135.96"),  # two verified product accounts, one allowance
    ("Westhaven", 30000, "1593.30", "1593.30"),       # after removing the exact duplicate
    ("Beacon Marsh", 30000, "1444.30", "1344.30"),    # includes the late Oct 31 record
])
def test_expected_usage_billing(db, name, allowance, expected, billed):
    r = by_customer(db, name)
    assert (r["allowance"], r["expected_billing"], r["billed"]) == (allowance, D(expected), D(billed))


def test_expected_accrual_nets_approved_concession(db):
    assert by_customer(db, "Zephyr")["expected_accrual"] == D("852.60")  # 952.60 − 100.00, MSG-2026-109


def test_population_ties_to_batch_controls(db):
    physical, records, dates = db.execute(
        "SELECT sum(physical_rows), sum(records), count(*) FROM usage_batch_tieout").fetchone()
    assert (physical, records, dates) == (1925, 1924, 61)


def test_findings_and_effects(db):
    rows = db.execute("SELECT finding_id, status, billing_effect, october_revenue_effect FROM findings "
                      "WHERE rule LIKE 'usage%' ORDER BY finding_id").fetchall()
    assert rows == [
        ("F-188999-USAGE-MISSING-INVOICE-2026-10", "error", D("3074.28"), D("3074.28")),
        ("F-314334-USAGE-NO-OVERAGE-2026-10", "valid_explanation", D("0.00"), D("0.00")),
        ("F-437384-USAGE-RATE-2026-10", "error", D("3135.22"), D("3135.22")),
        ("F-639373-USAGE-ALLOWANCE-2026-10", "error", D("-3096.80"), D("-3096.80")),
        ("F-810234-USAGE-LATE-RECORD-2026-10", "error", D("100.00"), D("0.00")),
        ("F-UNATTRIBUTED-USAGE-UNVERIFIED-pa_676b6b455e0887-2026-10", "needs_info", None, None),
    ]


def test_unverified_workspace_is_unpriced_and_unattributed(db):
    attributed, = db.execute("SELECT sum(units) FROM usage_by_customer").fetchone()
    exposure, = db.execute("SELECT exposure FROM findings WHERE customer_id IS NULL").fetchone()
    assert attributed == 1_551_184  # 1,600,946 October runs − 49,762 unverified
    assert "Unpriced: 49,762 runs" in exposure and "390.48" not in exposure  # never priced at Willow's terms


def test_proposed_entries_net_per_customer(db):
    """Cedar: the October correction plus the November credit note leave 1150 at zero once billing is fixed."""
    rows = dict(db.execute("""SELECT account_number, sum(debit - credit) FROM journal_lines
        WHERE status = 'proposed' AND customer_id = '639373' GROUP BY ALL""").fetchall())
    assert rows == {"4010": D("3096.80"), "1150": D("0.00"), "1100": D("-3096.80")}


def test_conflicting_duplicate_fails(repo_copy):
    path = repo_copy / "data" / "raw" / "2026-10" / "product_usage.csv"
    lines = path.read_text().splitlines(keepends=True)
    assert lines[1447].split(",")[0] == lines[1448].split(",")[0] == "ur_7352010ec2e04c"
    lines[1448] = lines[1448].replace(",1730,", ",1731,")
    path.write_text("".join(lines))
    failed = {c.name for c in run("2026-10", repo_copy).failed}
    assert "02_conflicting_duplicates" in failed


def test_unapproved_concession_quote_stops_the_run(repo_copy):
    path = repo_copy / "data" / "curated" / "2026-10" / "approvals.yaml"
    path.write_text(path.read_text().replace("by USD 100.", "by USD 1000."))
    with pytest.raises(InputError, match="MSG-2026-109"):
        run("2026-10", repo_copy)


@pytest.mark.parametrize("effects, revenue_diff, expected", [
    ({"USAGE-RATE": D("10")}, D("10"), {"USAGE-RATE": D("10")}),                 # accrual repeated the invoice
    ({LATE: D("5")}, D("0"), {LATE: D("0")}),                                     # accrual already right
    ({"USAGE-RATE": D("10"), LATE: D("5")}, D("10"), {"USAGE-RATE": D("10"), LATE: D("0")}),
    ({"USAGE-RATE": D("10")}, D("7"), {"USAGE-RATE": None}),                      # unexplained: left unclaimed
])
def test_allocate_revenue(effects, revenue_diff, expected):
    assert _allocate_revenue(effects, revenue_diff) == expected
