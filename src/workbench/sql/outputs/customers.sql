-- One row per customer for the report's Customers view: identity across systems + terms in force
-- at period start. Expected/actual billing columns are filled by the accounting logic later.
WITH terms AS (
    SELECT contract_id, term, value FROM contract_terms
    WHERE effective_from <= getvariable('period_start') AND effective_to_exclusive > getvariable('period_start')
)
SELECT
    s."NetSuiteCustomerInternalId__c" AS customer_id,
    s."AccountName" AS customer_name,
    s."AccountId" AS salesforce_account_id,
    s."StripeCustomerId__c" AS stripe_customer_id,
    r.contract_id,
    max(CASE WHEN t.term = 'billing_frequency' THEN t.value END) AS billing_frequency,
    max(CASE WHEN t.term = 'platform_invoice_amount' THEN t.value END) AS platform_invoice_amount,
    max(CASE WHEN t.term = 'platform_annual_rate' THEN t.value END) AS platform_annual_rate,
    max(CASE WHEN t.term = 'included_runs_per_month' THEN t.value END) AS included_runs_per_month,
    max(CASE WHEN t.term = 'overage_rate' THEN t.value END) AS overage_rate,
    string_agg(DISTINCT r2.document_id, ', ' ORDER BY r2.document_id) AS documents,
    s.source_file, s.source_line
FROM raw_salesforce_accounts s
LEFT JOIN raw_contract_register r ON r.salesforce_account_id = s."AccountId" AND r.document_type = 'order_form'
LEFT JOIN raw_contract_register r2 ON r2.salesforce_account_id = s."AccountId"
LEFT JOIN terms t ON t.contract_id = r.contract_id
GROUP BY ALL
ORDER BY customer_name
