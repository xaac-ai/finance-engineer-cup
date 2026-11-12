-- title: Countable usage records and units tie to usage_batch_controls for every service date
-- severity: fail
SELECT * FROM usage_batch_tieout
WHERE records IS DISTINCT FROM control_records OR units IS DISTINCT FROM control_units
