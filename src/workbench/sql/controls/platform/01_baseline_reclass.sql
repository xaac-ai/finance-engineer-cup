-- title: Recorded 1160 equals each customer's net debit in 2200 before reclass (baseline reclass is right)
-- severity: fail
SELECT customer_id, pre_reclass_2200_credit, booked_1160,
       greatest(0, -pre_reclass_2200_credit) AS required_1160
FROM platform_contract_position
WHERE booked_1160 <> greatest(0, -pre_reclass_2200_credit)
ORDER BY customer_id
