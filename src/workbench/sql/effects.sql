-- Combined October effects (wayfinder: "Build the combined October effects view").
-- Per customer × account, signed debit − credit:
--   october_recorded  Opening Balances + Recorded Entries posted in the review period
--   october_proposed  Proposed October adjustments
--   october_after     the two together: the corrected period-end balance
--   next_recorded     Recorded Entries posted in the following period that are in the extract (e.g. Nov 1 invoices)
--   next_proposed     Proposed billing documents' entries (November)
--   next_after        october_after + next_recorded + next_proposed
CREATE OR REPLACE VIEW customer_effects AS
WITH lines AS (
    SELECT j.customer_id, j.account_number, j.debit - j.credit AS amt,
           CASE WHEN j.entry_kind = 'opening' OR j.posting_period = getvariable('period_label') THEN 'oct' ELSE 'next' END AS slot,
           j.status
    FROM journal_lines j
    WHERE j.entry_kind = 'opening' OR j.date >= getvariable('period_start')
), grid AS (
    SELECT s."NetSuiteCustomerInternalId__c" AS customer_id, s."AccountName" AS customer_name, a.account_number, a.name AS account_name
    FROM raw_salesforce_accounts s CROSS JOIN accounts a
)
SELECT g.customer_id, g.customer_name, g.account_number, g.account_name,
       coalesce(sum(amt) FILTER (WHERE slot = 'oct' AND status = 'recorded'), 0)::DECIMAL(18,2) AS october_recorded,
       coalesce(sum(amt) FILTER (WHERE slot = 'oct' AND status = 'proposed'), 0)::DECIMAL(18,2) AS october_proposed,
       coalesce(sum(amt) FILTER (WHERE slot = 'oct'), 0)::DECIMAL(18,2) AS october_after,
       coalesce(sum(amt) FILTER (WHERE slot = 'next' AND status = 'recorded'), 0)::DECIMAL(18,2) AS next_recorded,
       coalesce(sum(amt) FILTER (WHERE slot = 'next' AND status = 'proposed'), 0)::DECIMAL(18,2) AS next_proposed,
       coalesce(sum(amt), 0)::DECIMAL(18,2) AS next_after
FROM grid g LEFT JOIN lines l USING (customer_id, account_number)
GROUP BY ALL
ORDER BY g.customer_name, g.account_number;

-- Population coverage: every customer × implemented stream, with the worst status that explains it.
CREATE OR REPLACE VIEW coverage AS
WITH f AS (
    SELECT customer_id, stream,
           max(CASE status WHEN 'error' THEN 3 WHEN 'needs_info' THEN 2 WHEN 'valid_explanation' THEN 1 END) AS rank,
           string_agg(finding_id, ', ' ORDER BY finding_id) AS finding_ids
    FROM findings WHERE customer_id IS NOT NULL AND NOT follow_up GROUP BY ALL
), fu AS (
    SELECT customer_id, stream, string_agg(finding_id, ', ' ORDER BY finding_id) AS follow_up_ids
    FROM findings WHERE follow_up AND customer_id IS NOT NULL GROUP BY ALL
)
SELECT b.customer_id, b.customer_name, b.stream,
       b.difference AS billing_difference, r.difference AS revenue_difference,
       CASE f.rank WHEN 3 THEN 'error' WHEN 2 THEN 'needs_info' WHEN 1 THEN 'valid_explanation' ELSE 'clean' END AS status,
       f.finding_ids, fu.follow_up_ids
FROM billing_reconciliation b
JOIN revenue_reconciliation r USING (customer_id, stream)
LEFT JOIN f USING (customer_id, stream)
LEFT JOIN fu USING (customer_id, stream)
ORDER BY b.customer_name, b.stream;

-- Totals by stream, confirmed Errors only (follow-ups excluded); exposure and follow-ups are listed separately.
CREATE OR REPLACE VIEW totals_by_stream AS
SELECT i.stream,
       coalesce(sum(billing_effect) FILTER (WHERE status = 'error' AND NOT follow_up AND billing_effect > 0), 0)::DECIMAL(18,2) AS underbilled,
       coalesce(sum(billing_effect) FILTER (WHERE status = 'error' AND NOT follow_up AND billing_effect < 0), 0)::DECIMAL(18,2) AS overbilled,
       coalesce(sum(october_revenue_effect) FILTER (WHERE status = 'error' AND NOT follow_up AND october_revenue_effect > 0), 0)::DECIMAL(18,2) AS october_understated,
       coalesce(sum(october_revenue_effect) FILTER (WHERE status = 'error' AND NOT follow_up AND october_revenue_effect < 0), 0)::DECIMAL(18,2) AS october_overstated,
       count(f.finding_id) FILTER (WHERE status = 'error' AND NOT follow_up) AS errors,
       count(f.finding_id) FILTER (WHERE status = 'valid_explanation') AS valid_explanations,
       count(f.finding_id) FILTER (WHERE status = 'needs_info') AS needs_info,
       count(f.finding_id) FILTER (WHERE follow_up) AS follow_ups
FROM implemented_streams i LEFT JOIN findings f USING (stream)
GROUP BY ALL ORDER BY i.stream;
