-- title: Each Proposed Entry stays within one customer and one stream (no netting across customers, or platform against usage)
-- severity: fail
SELECT entry_id, count(DISTINCT customer_id) AS customers,
       bool_or(account_number IN ('1150', '4010')) AND bool_or(account_number IN ('1160', '2200', '4000')) AS mixes_streams
FROM journal_lines WHERE status = 'proposed'
GROUP BY entry_id
HAVING count(DISTINCT customer_id) <> 1 OR count(*) FILTER (WHERE customer_id IS NULL) > 0 OR mixes_streams
