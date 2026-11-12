-- title: No Recorded Entry was created after the close cutoff
-- severity: fail
SELECT entry_id, line_no, created_at, getvariable('cutoff') AS cutoff, source_file, source_line
FROM journal_lines
WHERE status = 'recorded' AND created_at > getvariable('cutoff')
ORDER BY entry_id, line_no
