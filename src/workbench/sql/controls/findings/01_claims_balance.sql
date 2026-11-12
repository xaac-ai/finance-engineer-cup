-- title: Every reconciliation difference is explained exactly once (claims = difference)
-- severity: fail
SELECT 'billing' AS recon, customer_id, customer_name, stream, difference, claimed, finding_ids
FROM billing_reconciliation WHERE difference <> claimed
UNION ALL
SELECT 'revenue', customer_id, customer_name, stream, difference, claimed, finding_ids
FROM revenue_reconciliation WHERE difference <> claimed
ORDER BY 1, 3, 4
