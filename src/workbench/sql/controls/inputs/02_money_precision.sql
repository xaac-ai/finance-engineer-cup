-- title: NetSuite amounts have at most two decimals (no silent rounding on load)
-- severity: fail
SELECT source_file, source_line, 'Debit/Credit' AS field, "Debit" || ' / ' || "Credit" AS value
FROM raw_netsuite_gl_detail
WHERE NOT regexp_full_match("Debit", '\d+(\.\d{1,2})?') OR NOT regexp_full_match("Credit", '\d+(\.\d{1,2})?')
UNION ALL
SELECT source_file, source_line, 'Debit/Credit Balance', "Debit Balance" || ' / ' || "Credit Balance"
FROM raw_netsuite_opening_balances
WHERE NOT regexp_full_match("Debit Balance", '\d+(\.\d{1,2})?') OR NOT regexp_full_match("Credit Balance", '\d+(\.\d{1,2})?')
ORDER BY 1, 2
