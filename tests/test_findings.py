"""The reconciliation + findings framework, exercised with a toy stream and toy rules."""

from datetime import date
from decimal import Decimal

from workbench import db, findings, inputs, ledger
from workbench.controls import run_controls
from workbench.findings import Claim, Evidence, Finding, ProposedBillingDocument, ProposedEntry, ProposedLine
from workbench.period import load_period

ALDER = "186097"


def toy_usage_stream(ctx):
    """Expected usage billing 100.00 more than actual for Alder; revenue as booked for everyone."""
    ctx.con.execute("INSERT INTO billing_lines VALUES (?, 'usage', 'expected', 'toy', 1675.76, 'toy', NULL, NULL)", [ALDER])
    ctx.con.execute("INSERT INTO billing_lines VALUES (?, 'usage', 'actual', 'toy', 1575.76, 'toy', NULL, NULL)", [ALDER])
    ctx.con.execute("""INSERT INTO revenue_lines SELECT customer_id, 'usage', 'toy', sum(credit - debit), 'as booked'
        FROM journal_lines WHERE account_number = '4010' AND posting_period = 'Oct 2026' GROUP BY customer_id""")


def underbilled_rule(**overrides):
    def detect(ctx):
        f = dict(
            rule="toy", key="TOY", customer_id=ALDER, stream="usage", service_period="2026-10", status="error",
            title="Toy underbilling", summary="toy", action="Issue a supplemental invoice.",
            billing_effect=Decimal("100.00"), october_revenue_effect=Decimal("0.00"),
            no_october_entry_reason="The accrual is already correct.",
            evidence=(Evidence("csv_row", "data/raw/2026-10/stripe_invoices.csv", 2, "row", "invoice billed"),),
            claims=(Claim("billing", "usage", Decimal("100.00")),),
            documents=(ProposedBillingDocument("supplemental_invoice", date(2026, 11, 12), "usage", Decimal("100.00"),
                                               date(2026, 10, 1), date(2026, 11, 1), "in_x", "toy"),),
            entries=(ProposedEntry("proposed_november_billing", date(2026, 11, 12), "Nov 2026",
                                   (ProposedLine("1100", debit=Decimal("100.00")), ProposedLine("1150", credit=Decimal("100.00"))),
                                   "toy"),),
        )
        f.update(overrides)
        return [Finding(**f)]
    return detect


def _run(root, rules):
    period = load_period("2026-10", root)
    con = db.connect(period)
    inputs.load_raw(con, period)
    ledger.build_journal(con, period)
    findings.run(con, period, builders=[("usage", toy_usage_stream)], rules=rules)
    results = {r.name: r for r in run_controls(con, "findings") + ledger.run_ledger_controls(con)}
    return con, results


def status(results, suffix):
    return next(r for n, r in results.items() if n.endswith(suffix)).status


def test_every_customer_is_reconciled_and_unexplained_difference_fails(repo_copy):
    con, results = _run(repo_copy, rules=[])
    assert con.execute("SELECT count(*) FROM billing_reconciliation").fetchone()[0] == 30
    assert status(results, "claims_balance") == "fail"


def test_claimed_difference_passes_and_writes_details(repo_copy):
    con, results = _run(repo_copy, rules=[("toy", underbilled_rule())])
    assert {n: r.status for n, r in results.items() if r.status != "pass"} == {}
    fid = con.execute("SELECT finding_id FROM findings").fetchone()[0]
    assert fid == "F-186097-TOY-2026-10"
    assert con.execute("SELECT count(*) FROM journal_lines WHERE finding_id = ?", [fid]).fetchone()[0] == 2


def test_over_claim_fails(repo_copy):
    _, results = _run(repo_copy, rules=[("toy", underbilled_rule(claims=(Claim("billing", "usage", Decimal("150.00")),)))])
    assert status(results, "claims_balance") == "fail"


def test_duplicate_correction_fails(repo_copy):
    twin = underbilled_rule(key="TOY2", claims=())
    _, results = _run(repo_copy, rules=[("toy", underbilled_rule()), ("twin", twin)])
    assert status(results, "no_duplicate_corrections") == "fail"


def test_needs_info_cannot_carry_confirmed_amounts(repo_copy):
    _, results = _run(repo_copy, rules=[("toy", underbilled_rule(status="needs_info"))])
    assert status(results, "finding_integrity") == "fail"


def test_unbalanced_proposed_entry_fails_ledger_control(repo_copy):
    bad = (ProposedEntry("proposed_november_billing", date(2026, 11, 12), "Nov 2026",
                         (ProposedLine("1100", debit=Decimal("100.00")),), "toy"),)
    _, results = _run(repo_copy, rules=[("toy", underbilled_rule(entries=bad))])
    assert status(results, "balanced_entries") == "fail"
