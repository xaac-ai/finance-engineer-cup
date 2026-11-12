-- Physical export rows -> countable unique records, tied to usage_batch_controls per service date.
SELECT * FROM usage_batch_tieout ORDER BY service_date
