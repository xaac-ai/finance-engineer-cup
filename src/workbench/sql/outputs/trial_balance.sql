-- Trial balance per customer x account at period end. Signed = debit - credit (debit positive).
-- recorded: Opening Balances + Recorded Entries posted in the period.
-- with_proposed: the same plus Proposed Entries for the period. Never nets across customers.
SELECT
    j.customer_id,
    j.account_number,
    a.name AS account_name,
    sum(CASE WHEN j.status = 'recorded' THEN j.debit - j.credit ELSE 0 END) AS recorded_balance,
    sum(j.debit - j.credit) AS with_proposed_balance,
    sum(CASE WHEN j.status = 'proposed' THEN j.debit - j.credit ELSE 0 END) AS proposed_change
FROM journal_lines j
JOIN accounts a USING (account_number)
WHERE j.entry_kind = 'opening' OR j.posting_period = getvariable('period_label')
GROUP BY ALL
ORDER BY j.customer_id, j.account_number
