-- title: Extract completeness: physical row counts match START_HERE expected counts
-- severity: fail
SELECT file, actual, expected
FROM input_row_counts
WHERE expected IS NOT NULL AND actual IS DISTINCT FROM expected
ORDER BY file
