-- title: No duplicate GL lines, and no source document posted twice for the same purpose
-- severity: fail
SELECT 'repeated NetSuite line' AS problem, ns_internal_id || ':' || ns_line_id AS key, count(*) AS n,
       string_agg(source_line::VARCHAR, ',' ORDER BY source_line) AS source_lines
FROM journal_lines
WHERE ns_internal_id IS NOT NULL
GROUP BY ns_internal_id, ns_line_id
HAVING count(*) > 1
UNION ALL
SELECT 'source document posted in more than one entry', external_source_id || ' / ' || account_number || ' / ' || memo,
       count(DISTINCT entry_id), string_agg(source_line::VARCHAR, ',' ORDER BY source_line)
FROM journal_lines
WHERE external_source_id IS NOT NULL
GROUP BY external_source_id, account_number, memo
HAVING count(DISTINCT entry_id) > 1
ORDER BY 1, 2
