-- Platform billing actually issued by cutoff: Stripe platform lines with their service periods.
CREATE OR REPLACE VIEW platform_invoice_lines AS
SELECT s."NetSuiteCustomerInternalId__c" AS customer_id, i.id AS invoice_id, i.number AS invoice_number, l.id AS line_id,
       CAST(CAST(l.period_start AS TIMESTAMPTZ) AS DATE) AS service_start,
       CAST(CAST(l.period_end AS TIMESTAMPTZ) AS DATE) AS service_end_exclusive,
       CAST(l.amount AS BIGINT) - CAST(l.discount_amount AS BIGINT) AS amount_cents,
       l.source_file, l.source_line
FROM raw_stripe_invoice_lines l
JOIN raw_stripe_invoices i ON i.id = l.invoice_id
JOIN raw_salesforce_accounts s ON s."StripeCustomerId__c" = i.customer_id
WHERE l.product_id = 'prod_platform'
  AND CAST(i.finalized_at AS TIMESTAMPTZ) <= CAST(getvariable('cutoff') AS TIMESTAMPTZ);

-- Issued credit notes against platform lines (none expected; each one is Needs Info).
CREATE OR REPLACE VIEW platform_credit_notes AS
SELECT s."NetSuiteCustomerInternalId__c" AS customer_id, n.id AS credit_note_id, n.number, n.status,
       CAST(nl.amount AS BIGINT) AS amount_cents, nl.service_start, nl.service_end_exclusive, nl.description,
       il.id AS invoice_line_id, nl.source_file, nl.source_line
FROM raw_stripe_credit_note_lines nl
JOIN raw_stripe_credit_notes n ON n.id = nl.credit_note_id
JOIN raw_stripe_invoice_lines il ON il.id = nl.invoice_line_item_id
JOIN raw_salesforce_accounts s ON s."StripeCustomerId__c" = n.customer_id
WHERE il.product_id = 'prod_platform' AND n.status = 'issued'
  AND CAST(n.created AS TIMESTAMPTZ) <= CAST(getvariable('cutoff') AS TIMESTAMPTZ);

-- Per customer: platform 2200/1160 position at period end (recorded only, through the review period).
-- combined = 2200 credit balance + 1160 credit balance: the 2200 balance before any reclass.
CREATE OR REPLACE VIEW platform_contract_position AS
SELECT customer_id,
       sum(CASE WHEN account_number IN ('2200', '1160') THEN credit - debit ELSE 0 END) AS pre_reclass_2200_credit,
       sum(CASE WHEN account_number = '1160' THEN debit - credit ELSE 0 END) AS booked_1160
FROM journal_lines
WHERE status = 'recorded'
  AND (entry_kind = 'opening' OR posting_period = getvariable('period_label'))
GROUP BY customer_id;
