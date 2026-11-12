-- title: Balanced entries (debits = credits per Recorded and Proposed Entry)
-- severity: fail
SELECT entry_id, status, entry_kind, sum(debit) AS debits, sum(credit) AS credits
FROM journal_lines
WHERE entry_kind <> 'opening'
GROUP BY ALL
HAVING sum(debit) <> sum(credit)
ORDER BY entry_id
