-- Validated usage (wayfinder: "How is usage validated and attributed?").
-- Typed source rows; one row per physical export line.
CREATE OR REPLACE VIEW usage_source AS
SELECT record_id, product_account_id, sku, CAST(service_date AS DATE) AS service_date, CAST(units AS BIGINT) AS units,
       CAST(ingested_at AS TIMESTAMPTZ) AS ingested_at, record_status, replaces_record_id, batch_id,
       source_file, source_line
FROM raw_product_usage;

-- The same record_id exported with different content is not a duplicate we can resolve: control fails.
CREATE OR REPLACE VIEW usage_conflicting_duplicates AS
SELECT record_id, count(*) AS physical_rows,
       count(DISTINCT (product_account_id, sku, service_date, units, ingested_at, record_status, replaces_record_id, batch_id)) AS versions,
       string_agg(source_line::VARCHAR, ', ' ORDER BY source_line) AS source_lines
FROM usage_source GROUP BY record_id
HAVING versions > 1;

-- Unique records: exact repeats of a record_id count once (the first physical line is cited).
CREATE OR REPLACE VIEW usage_unique AS
SELECT * EXCLUDE (rn) FROM (
    SELECT *, row_number() OVER (PARTITION BY record_id ORDER BY source_line) AS rn,
              count(*) OVER (PARTITION BY record_id) AS physical_rows
    FROM usage_source
) WHERE rn = 1;

-- Countable records: active and not replaced by another active record (START_HERE · USAGE).
CREATE OR REPLACE VIEW usage_records AS
SELECT u.* FROM usage_unique u
WHERE u.record_status = 'active'
  AND NOT EXISTS (SELECT 1 FROM usage_unique r WHERE r.record_status = 'active' AND r.replaces_record_id = u.record_id);

-- Per service date: countable records vs the independent batch controls.
CREATE OR REPLACE VIEW usage_batch_tieout AS
WITH src AS (
    SELECT service_date, count(*) AS records, sum(units) AS units FROM usage_records GROUP BY ALL
), phys AS (
    SELECT service_date, count(*) AS physical_rows FROM usage_source GROUP BY ALL
), ctl AS (
    SELECT CAST(service_date AS DATE) AS service_date, CAST(distinct_active_record_count AS BIGINT) AS control_records,
           CAST(active_units_total AS BIGINT) AS control_units, source_line
    FROM raw_usage_batch_controls
)
SELECT coalesce(c.service_date, s.service_date) AS service_date, p.physical_rows, s.records, c.control_records,
       s.units, c.control_units, c.source_line AS control_source_line
FROM ctl c FULL JOIN src s USING (service_date) LEFT JOIN phys p ON p.service_date = coalesce(c.service_date, s.service_date)
ORDER BY 1;

-- Attribution: only through a mapping with a Salesforce account that is effective on the service date
-- (intervals are start-inclusive / end-exclusive, START_HERE · FORMATS).
CREATE OR REPLACE VIEW usage_mapped AS
SELECT r.*, m.salesforce_account_id, m.account_label, m.source_line AS mapping_source_line,
       s."NetSuiteCustomerInternalId__c" AS customer_id
FROM usage_records r
LEFT JOIN raw_product_account_mapping m
  ON m.product_account_id = r.product_account_id
 AND m.salesforce_account_id IS NOT NULL
 AND CAST(m.effective_from AS DATE) <= r.service_date
 AND (m.effective_to IS NULL OR r.service_date < CAST(m.effective_to AS DATE))
LEFT JOIN raw_salesforce_accounts s ON s."AccountId" = m.salesforce_account_id;

-- Eligible for the period: service date in the period and known by the cutoff.
CREATE OR REPLACE VIEW usage_period AS
SELECT *, ingested_at <= CAST(getvariable('cutoff') AS TIMESTAMPTZ) AS known_by_cutoff
FROM usage_mapped
WHERE service_date >= getvariable('period_start') AND service_date < getvariable('period_end');

CREATE OR REPLACE VIEW usage_attributed AS
SELECT * FROM usage_period WHERE known_by_cutoff AND customer_id IS NOT NULL;

CREATE OR REPLACE VIEW usage_unattributed AS
SELECT * FROM usage_period WHERE known_by_cutoff AND customer_id IS NULL;

CREATE OR REPLACE VIEW usage_after_cutoff AS
SELECT * FROM usage_period WHERE NOT known_by_cutoff;

-- Actual usage billing for the period: Stripe workflow-run lines for this service month, issued by cutoff.
CREATE OR REPLACE VIEW usage_invoice_lines AS
SELECT s."NetSuiteCustomerInternalId__c" AS customer_id, i.id AS invoice_id, i.number AS invoice_number,
       CAST(CAST(i.created AS TIMESTAMPTZ) AS TIMESTAMP) AS invoice_created_local, l.id AS line_id,
       CAST(l.quantity AS BIGINT) AS quantity, CAST(l.unit_amount_decimal AS DECIMAL(18, 6)) AS unit_cents,
       CAST(l.amount AS BIGINT) AS amount_cents, CAST(l.discount_amount AS BIGINT) AS discount_cents,
       l.price_id, l.source_file, l.source_line
FROM raw_stripe_invoice_lines l
JOIN raw_stripe_invoices i ON i.id = l.invoice_id
JOIN raw_salesforce_accounts s ON s."StripeCustomerId__c" = i.customer_id
WHERE l.product_id = 'prod_workflow_run'
  AND CAST(CAST(l.period_start AS TIMESTAMPTZ) AS DATE) = getvariable('period_start')
  AND CAST(CAST(l.period_end AS TIMESTAMPTZ) AS DATE) = getvariable('period_end')
  AND CAST(i.finalized_at AS TIMESTAMPTZ) <= CAST(getvariable('cutoff') AS TIMESTAMPTZ);
