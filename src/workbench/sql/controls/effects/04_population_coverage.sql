-- title: Every customer is reviewed for every implemented stream (coverage = customers × streams)
-- severity: fail
SELECT (SELECT count(*) FROM raw_salesforce_accounts) * (SELECT count(*) FROM implemented_streams) AS expected_rows,
       (SELECT count(*) FROM coverage) AS coverage_rows
WHERE expected_rows <> coverage_rows
