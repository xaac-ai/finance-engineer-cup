-- title: Usage for the period with no verified owner (isolated; see the unverified-usage Needs Info finding)
-- severity: warn
SELECT product_account_id, count(*) AS records, sum(units) AS units, min(source_line) AS first_line, max(source_line) AS last_line
FROM usage_unattributed GROUP BY ALL
