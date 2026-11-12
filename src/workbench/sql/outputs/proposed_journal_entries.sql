-- Proposed Entries for Controller approval (empty until the accounting logic exists).
SELECT entry_id, line_no, entry_kind, date, posting_period, account_number, customer_id,
       debit, credit, memo, finding_id, basis
FROM journal_lines
WHERE status = 'proposed'
ORDER BY entry_id, line_no
