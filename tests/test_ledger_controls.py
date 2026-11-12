from workbench import db, inputs, ledger
from workbench.period import load_period


def _con(root):
    period = load_period("2026-10", root)
    con = db.connect(period)
    inputs.load_raw(con, period)
    ledger.build_journal(con, period)
    return con


def status(results, name):
    return next(r for r in results if r.name.endswith(name))


def test_real_books_pass(repo_copy):
    results = ledger.run_ledger_controls(_con(repo_copy))
    assert [r.title for r in results if r.status != "pass"] == []


def test_unbalanced_entry_and_unknown_account_fail(repo_copy):
    con = _con(repo_copy)
    con.execute("UPDATE journal_lines SET credit = credit + 0.01 WHERE entry_id = (SELECT min(entry_id) FROM journal_lines WHERE entry_kind = 'gl') AND credit > 0")
    con.execute("UPDATE journal_lines SET account_number = '9999' WHERE entry_kind = 'opening' AND customer_id = '186097' AND account_number = '1100'")
    results = ledger.run_ledger_controls(con)
    assert status(results, "balanced_entries").status == "fail"
    assert status(results, "known_accounts").status == "fail"
    assert status(results, "opening_completeness").status == "fail"


def test_proposed_entry_without_finding_fails(repo_copy):
    con = _con(repo_copy)
    con.execute("""INSERT INTO journal_lines BY NAME SELECT 'P-1' AS entry_id, 1 AS line_no, 'proposed' AS status,
        'proposed_october_adjustment' AS entry_kind, DATE '2026-10-31' AS date, 'Oct 2026' AS posting_period,
        '4000' AS account_number, '186097' AS customer_id, 0.00 AS debit, 1.00 AS credit""")
    con.execute("""INSERT INTO journal_lines BY NAME SELECT 'P-1' AS entry_id, 2 AS line_no, 'proposed' AS status,
        'proposed_october_adjustment' AS entry_kind, DATE '2026-10-31' AS date, 'Oct 2026' AS posting_period,
        '1160' AS account_number, '186097' AS customer_id, 1.00 AS debit, 0.00 AS credit""")
    results = ledger.run_ledger_controls(con)
    assert status(results, "balanced_entries").status == "pass"
    assert status(results, "proposed_entry_rules").count == 2
