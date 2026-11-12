-- title: Every journal line posts to an account in the chart of accounts
-- severity: fail
SELECT j.entry_id, j.line_no, j.account_number, j.source_file, j.source_line
FROM journal_lines j
LEFT JOIN accounts a USING (account_number)
WHERE a.account_number IS NULL
ORDER BY j.entry_id, j.line_no
