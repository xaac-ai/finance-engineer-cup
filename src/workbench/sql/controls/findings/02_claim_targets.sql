-- title: Findings only claim differences that exist (known customer, implemented stream)
-- severity: fail
SELECT c.*
FROM finding_claims c
LEFT JOIN (SELECT 'billing' AS recon, customer_id, stream FROM billing_reconciliation
           UNION ALL SELECT 'revenue', customer_id, stream FROM revenue_reconciliation) r
  USING (recon, customer_id, stream)
WHERE r.customer_id IS NULL
ORDER BY finding_id
