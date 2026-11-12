"""Credits and approvals: issued vs void notes, approved concessions reflected once, unapproved requests."""

import shutil
from decimal import Decimal as D
from pathlib import Path

import duckdb
import pytest

from workbench.pipeline import run

REPO = Path(__file__).resolve().parents[1]


def _db(root):
    return duckdb.connect(str(root / "out" / "2026-10" / "workbench.duckdb"), read_only=True)


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    root = tmp_path_factory.mktemp("credits")
    shutil.copytree(REPO / "data", root / "data")
    assert run("2026-10", root).failed == []
    con = _db(root)
    yield con
    con.close()


def test_credit_findings(db):
    rows = db.execute("""SELECT finding_id, status, billing_effect, exposure IS NOT NULL FROM findings
        WHERE rule LIKE 'credits%' ORDER BY finding_id""").fetchall()
    assert rows == [
        ("F-148565-CREDIT-APPROVED-CONCESSION-2026-10", "valid_explanation", D("0.00"), False),   # Zephyr, MSG-109
        ("F-186097-CREDIT-VOID-CN-186097-20261102-2026-10", "valid_explanation", D("0.00"), False),  # Alder, MSG-116
        ("F-839653-CREDIT-REQUEST-MSG-2026-132-2026-10", "needs_info", None, True),               # Willow, MSG-132
    ]


def test_zephyr_billing_is_net_of_credit_and_concession(db):
    row = db.execute("""SELECT expected, actual, difference FROM billing_reconciliation
        WHERE customer_id = '148565' AND stream = 'usage'""").fetchone()
    assert row == (D("852.60"), D("852.60"), D("0.00"))  # 952.60 − 100 both sides


def test_void_note_and_request_have_no_effect(db):
    alder = db.execute("SELECT actual FROM billing_reconciliation WHERE customer_id = '186097' AND stream = 'usage'").fetchone()
    assert alder == (D("1575.76"),)  # void $50 note ignored
    willow = db.execute("SELECT count(*) FROM journal_lines WHERE status = 'proposed' AND customer_id = '839653'").fetchone()
    assert willow == (0,)  # no credit proposed for an unapproved request


def test_approved_concession_never_credited_is_an_error(repo_copy):
    path = repo_copy / "data" / "raw" / "2026-10" / "stripe_credit_notes.csv"
    path.write_text(path.read_text().replace("cn_85bf669490fd97,CN-148565-20261104,in_6cf692b3e9f58a,cus_499cb732fd7b9c,issued",
                                             "cn_85bf669490fd97,CN-148565-20261104,in_6cf692b3e9f58a,cus_499cb732fd7b9c,draft"))
    assert run("2026-10", repo_copy).failed == []
    con = _db(repo_copy)
    assert con.execute("SELECT billing_effect FROM findings WHERE finding_id = 'F-148565-CREDIT-MISMATCH-2026-10'").fetchone() \
        == (D("-100.00"),)


def test_request_quote_must_be_in_message(repo_copy):
    from workbench.errors import InputError
    path = repo_copy / "data" / "curated" / "2026-10" / "approvals.yaml"
    path.write_text(path.read_text().replace("requested USD 250", "requested USD 25"))
    with pytest.raises(InputError, match="MSG-2026-132"):
        run("2026-10", repo_copy)
