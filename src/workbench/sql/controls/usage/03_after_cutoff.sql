-- title: Usage records for the period ingested after the cutoff (excluded from October)
-- severity: warn
SELECT record_id, product_account_id, service_date, units, ingested_at::VARCHAR AS ingested_at, source_file, source_line FROM usage_after_cutoff
