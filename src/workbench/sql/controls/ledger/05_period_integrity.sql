-- title: Each GL line's date falls inside its posting period
-- severity: fail
SELECT entry_id, line_no, date, posting_period, source_file, source_line
FROM journal_lines
WHERE entry_kind <> 'opening' AND strftime(date, '%b %Y') <> posting_period
ORDER BY entry_id, line_no
