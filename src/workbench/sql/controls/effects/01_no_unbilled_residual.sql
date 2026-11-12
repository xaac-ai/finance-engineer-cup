-- title: After the proposed billing documents, no customer has an unexplained 1150 residual
-- severity: fail
SELECT customer_id, customer_name, october_after, next_recorded, next_proposed, next_after
FROM customer_effects WHERE account_number = '1150' AND next_after <> 0
