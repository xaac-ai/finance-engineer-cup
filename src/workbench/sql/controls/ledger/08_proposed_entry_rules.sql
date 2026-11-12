-- title: Proposed Entries cite a finding and sit in their allowed period
-- severity: fail
SELECT entry_id, line_no, entry_kind, date, posting_period, finding_id,
       CASE
         WHEN finding_id IS NULL THEN 'no finding_id'
         WHEN entry_kind = 'proposed_october_adjustment' AND posting_period <> getvariable('period_label')
           THEN 'adjustment not in the review period'
         WHEN entry_kind = 'proposed_november_billing'
              AND NOT (date >= getvariable('period_end') AND date < getvariable('period_end') + INTERVAL 1 MONTH)
           THEN 'billing document not dated in the following month'
         WHEN entry_kind NOT IN ('proposed_october_adjustment', 'proposed_november_billing')
           THEN 'unknown proposed entry kind'
       END AS problem
FROM journal_lines
WHERE status = 'proposed' AND problem IS NOT NULL
ORDER BY entry_id, line_no
