-- Approach A: each expected platform billing document covering the period vs the Stripe line for the same service period.
SELECT d.*, s."AccountName" AS customer_name FROM platform_documents d
JOIN raw_salesforce_accounts s ON s."NetSuiteCustomerInternalId__c" = d.customer_id
ORDER BY customer_name, service_start
