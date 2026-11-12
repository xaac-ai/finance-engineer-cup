-- title: Every recognised revenue-plan row for the period joins an included GL posting
-- severity: warn
SELECT p."Revenue Plan ID", p."Customer Internal ID", p."Posting Period", p."Recognized Amount",
       p."Journal Internal ID", p.source_file, p.source_line
FROM raw_netsuite_revenue_plan_detail p
LEFT JOIN (SELECT DISTINCT ns_internal_id FROM journal_lines WHERE entry_kind = 'gl') g
  ON g.ns_internal_id = p."Journal Internal ID"
WHERE p."Posting Period" = getvariable('period_label')
  AND CAST(p."Recognized Amount" AS DECIMAL(18, 2)) <> 0
  AND g.ns_internal_id IS NULL
ORDER BY p.source_line
