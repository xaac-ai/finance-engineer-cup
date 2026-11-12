-- title: Opening Balances cover accounts 1100/1150/1160/2200 for every customer, one side only
-- severity: fail
WITH customers AS (
    SELECT DISTINCT "NetSuiteCustomerInternalId__c" AS customer_id FROM raw_salesforce_accounts
), required AS (
    SELECT c.customer_id, a.account_number
    FROM customers c CROSS JOIN (VALUES ('1100'), ('1150'), ('1160'), ('2200')) a(account_number)
)
SELECT r.customer_id, r.account_number, 'missing opening row' AS problem, NULL AS source_line
FROM required r
LEFT JOIN journal_lines j
  ON j.entry_kind = 'opening' AND j.customer_id = r.customer_id AND j.account_number = r.account_number
WHERE j.entry_id IS NULL
UNION ALL
SELECT customer_id, account_number, 'both debit and credit nonzero', source_line
FROM journal_lines
WHERE entry_kind = 'opening' AND debit <> 0 AND credit <> 0
ORDER BY 1, 2
