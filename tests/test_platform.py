"""Platform stream: expected billing documents (Approach A), October revenue by component, findings.

Pinned to hand-checked values (wayfinder: "What exactly does START_HERE prescribe for each treatment?").
"""

import json
import shutil
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import duckdb
import pytest

from workbench.pipeline import run
from workbench.streams.platform import component_amount

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("platform")
    shutil.copytree(REPO / "data", root / "data")
    assert run("2026-10", root).failed == []
    con = duckdb.connect(str(root / "out" / "2026-10" / "workbench.duckdb"), read_only=True)
    yield con, root / "out" / "2026-10"
    con.close()


@pytest.mark.parametrize("name, expected", [
    ("Highwater", "2038.36"),       # annual $24,000 × 31/365
    ("Crescent Shore", "5095.89"),  # 15th anchor, $60,000 × 31/365
    ("Meridian", "4602.74"),        # base 4,076.71 + increment 526.03
])
def test_october_platform_revenue(built, name, expected):
    con, _ = built
    total, = con.execute("""SELECT sum(c.amount) FROM platform_revenue_components c WHERE c.customer_name LIKE ?""",
                         [name + "%"]).fetchone()
    assert total == D(expected)


def test_expected_documents_cover_october(built):
    con, _ = built
    docs = con.execute("""SELECT doc_key, kind, amount FROM platform_expected_documents e
        JOIN raw_salesforce_accounts s ON s."NetSuiteCustomerInternalId__c" = e.customer_id
        WHERE s."AccountName" LIKE ? ORDER BY doc_key""", ["Crescent Shore%"]).fetchall()
    assert docs == [("2026-09-15..2026-10-15", "anchor", D("5000.00")), ("2026-10-15..2026-11-15", "anchor", D("5000.00"))]
    annual, = con.execute("""SELECT doc_key FROM platform_expected_documents e JOIN raw_salesforce_accounts s
        ON s."NetSuiteCustomerInternalId__c" = e.customer_id WHERE s."AccountName" LIKE 'Highwater%'""").fetchone()
    assert annual == "2026-09-01..2027-09-01"  # issued in September, covers October


def test_meridian_findings(built):
    con, _ = built
    rows = con.execute("""SELECT finding_id, billing_effect, october_revenue_effect, follow_up FROM findings
        WHERE stream = 'platform' ORDER BY finding_id""").fetchall()
    assert rows == [
        ("F-335780-PLATFORM-INVOICE-AMOUNT-2026-11", D("1000.00"), D("0.00"), True),
        ("F-335780-PLATFORM-MISSING-CATCH-UP-2026-10", D("526.03"), D("0.00"), False),
        ("F-335780-PLATFORM-UPGRADE-INCREMENT-2026-10", D("0.00"), D("526.03"), False),
    ]
    net = dict(con.execute("""SELECT account_number, sum(debit - credit) FROM journal_lines
        WHERE status = 'proposed' AND entry_kind = 'proposed_october_adjustment' AND customer_id = '335780'
        GROUP BY ALL""").fetchall())
    assert net == {"1160": D("526.03"), "2200": D("0.00"), "4000": D("-526.03")}  # net: Dr 1160 / Cr 4000


def test_follow_up_kept_out_of_totals(built):
    _, out = built
    html = (out / "report.html").read_text()
    data = json.loads(html.split('<script id="report-data" type="application/json">')[1].split("</script>")[0])
    # usage 3,074.28 + 3,135.22 + 100.00, platform 526.03; Meridian's Nov $1,000 is a follow-up
    assert D(data["totals"]["underbilled"]) == D("6835.53")
    assert data["totals"]["follow_ups"] >= 1


def test_increment_final_period_takes_the_residual():
    start, end = date(2026, 10, 16), date(2027, 9, 1)
    assert component_amount(D("12000"), start, end, date(2026, 10, 1), date(2026, 11, 1))[0] == D("526.03")
    assert component_amount(D("12000"), start, end, date(2027, 7, 1), date(2027, 8, 1))[0] == D("1019.18")
    assert component_amount(D("12000"), start, end, date(2027, 8, 1), date(2027, 9, 1))[0] == D("1019.17")


def test_wrong_october_invoice_amount_is_claimed(repo_copy):
    path = repo_copy / "data" / "raw" / "2026-10" / "stripe_invoice_lines.csv"
    lines = path.read_text().splitlines(keepends=True)
    assert lines[32].startswith("il_0eec5a23bafa10,")  # Kestrel Bridge Oct 1 platform line, $3,000.00
    lines[32] = lines[32].replace(",300000,300000,", ",310000,310000,")
    path.write_text("".join(lines))
    result = run("2026-10", repo_copy)
    assert result.failed == []
    con = duckdb.connect(str(repo_copy / "out" / "2026-10" / "workbench.duckdb"), read_only=True)
    row = con.execute("SELECT billing_effect FROM findings WHERE finding_id = 'F-654552-PLATFORM-INVOICE-AMOUNT-2026-10'").fetchone()
    assert row == (D("-100.00"),)
