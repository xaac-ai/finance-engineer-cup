-- title: After the proposed October entries, 1160 equals each customer's net 2200 debit (reclass recomputed)
-- severity: fail
WITH p AS (
    SELECT customer_id,
           sum(october_after) FILTER (WHERE account_number IN ('2200', '1160')) AS combined_2200,
           sum(october_after) FILTER (WHERE account_number = '1160') AS asset_1160
    FROM customer_effects GROUP BY customer_id
)
SELECT customer_id, combined_2200, asset_1160, greatest(0, combined_2200) AS required_1160
FROM p WHERE asset_1160 <> greatest(0, combined_2200)
