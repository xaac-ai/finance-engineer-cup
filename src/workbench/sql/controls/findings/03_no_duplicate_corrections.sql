-- title: No duplicate corrections (one proposed document per original invoice, stream and amount)
-- severity: fail
SELECT customer_id, original_invoice, stream, doc_type, amount, count(*) AS n,
       string_agg(finding_id, ', ') AS finding_ids
FROM proposed_billing_documents
GROUP BY ALL
HAVING count(*) > 1
