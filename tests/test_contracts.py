from datetime import date

import pytest
import yaml

from workbench import contracts, db, inputs
from workbench.contracts import ContractTerm, apply_amendment, parse_order_form
from workbench.errors import ContractError
from workbench.pdf import extract_text
from workbench.period import load_period

from conftest import REPO

RAW = REPO / "data" / "raw" / "2026-10" / "contracts"


def terms_by_name(terms):
    return {t.term: t for t in terms}


def test_parse_annual_order_form():
    cid, terms = parse_order_form("OF-2026-118", extract_text(RAW / "OF-2026-118.pdf"))
    t = terms_by_name(terms)
    assert cid == "CT-186097"
    assert t["billing_frequency"].value == "annual"
    assert t["platform_invoice_amount"].value == "24000.00"
    assert t["included_runs_per_month"].value == "10000"
    assert t["overage_rate"].value == "0.08"
    assert t["service_end_exclusive"].value == "2027-09-01"
    assert t["overage_rate"].source_quote == "Monthly, in arrears $0.08 / excess run"


def test_parse_mid_month_anchor():
    _, terms = parse_order_form("OF-2026-419", extract_text(RAW / "OF-2026-419.pdf"))
    t = terms_by_name(terms)
    assert t["billing_anchor_day"].value == "15"
    assert t["service_start"].value == "2026-09-15"


def test_unrecognised_template_fails_loudly():
    with pytest.raises(ContractError, match="OF-X.*overage rate"):
        parse_order_form("OF-X", extract_text(RAW / "OF-2026-118.pdf").replace("excess run", "extra run").replace("OF-2026-118", "OF-X"))


def test_amendment_cuts_only_the_named_term():
    base = [
        ContractTerm("CT-1", "included_runs_per_month", "30000", date(2026, 9, 1), date(2027, 9, 1), "OF-1", "03", "q"),
        ContractTerm("CT-1", "overage_rate", "0.40", date(2026, 9, 1), date(2027, 9, 1), "OF-1", "03", "q"),
    ]
    change = ContractTerm("CT-1", "included_runs_per_month", "45000", date(2026, 10, 16), date(2027, 9, 1), "AM-1", "03", "q")
    out = apply_amendment(base, change)
    runs = sorted((t for t in out if t.term == "included_runs_per_month"), key=lambda t: t.effective_from)
    assert [(r.value, r.effective_from, r.effective_to_exclusive) for r in runs] == [
        ("30000", date(2026, 9, 1), date(2026, 10, 16)),
        ("45000", date(2026, 10, 16), date(2027, 9, 1)),
    ]
    assert [t for t in out if t.term == "overage_rate"] == [base[1]]


def _build(root):
    period = load_period("2026-10", root)
    con = db.connect(period)
    inputs.load_raw(con, period)
    return contracts.build_contract_terms(con, period)


def test_curated_quote_must_appear_verbatim(repo_copy):
    path = repo_copy / "data" / "curated" / "2026-10" / "amendment_terms.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["amendments"][1]["changes"][2]["quote"] = "October upgrade catch-up: USD 562.03"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ContractError, match="not in the document text"):
        _build(repo_copy)


def test_uncurated_amendment_fails(repo_copy):
    path = repo_copy / "data" / "curated" / "2026-10" / "amendment_terms.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["amendments"] = doc["amendments"][:1]
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ContractError, match="AM-OF-2026-164"):
        _build(repo_copy)
