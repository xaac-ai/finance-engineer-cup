-- The books: Opening Balances + Recorded Entries (NetSuite GL). Proposed Entries are inserted
-- later by the accounting logic with status = 'proposed'. One row per debit/credit line.
-- Decision: wayfinder "How should the ledger layer be laid out?" (docs/adr/0001-no-ledger-engine.md).
CREATE OR REPLACE TABLE journal_lines AS
SELECT
    'OB-' || "Customer Internal ID" || '-' || "Account Number"  AS entry_id,
    1                                                          AS line_no,
    'recorded'                                                 AS status,
    'opening'                                                  AS entry_kind,
    CAST("As Of Date" AS DATE)                                 AS date,
    CAST(NULL AS VARCHAR)                                      AS posting_period,
    "Account Number"                                           AS account_number,
    "Customer Internal ID"                                     AS customer_id,
    CAST("Debit Balance" AS DECIMAL(18, 2))                    AS debit,
    CAST("Credit Balance" AS DECIMAL(18, 2))                   AS credit,
    "Account Name"                                             AS memo,
    "Source Reference"                                         AS document_number,
    CAST(NULL AS VARCHAR)                                      AS transaction_type,
    CAST(NULL AS TIMESTAMPTZ)                                  AS created_at,
    CAST(NULL AS VARCHAR)                                      AS ns_internal_id,
    CAST(NULL AS VARCHAR)                                      AS ns_line_id,
    CAST(NULL AS VARCHAR)                                      AS external_source_id,
    CAST(NULL AS VARCHAR)                                      AS revenue_plan_id,
    CAST(NULL AS VARCHAR)                                      AS finding_id,
    CAST(NULL AS VARCHAR)                                      AS basis,
    source_file,
    source_line
FROM raw_netsuite_opening_balances

UNION ALL BY NAME

SELECT
    "Internal ID"                                              AS entry_id,
    CAST("Line ID" AS INTEGER)                                 AS line_no,
    'recorded'                                                 AS status,
    'gl'                                                       AS entry_kind,
    CAST("Date" AS DATE)                                       AS date,
    "Posting Period"                                           AS posting_period,
    "Account Number"                                           AS account_number,
    "Customer Internal ID"                                     AS customer_id,
    CAST("Debit" AS DECIMAL(18, 2))                            AS debit,
    CAST("Credit" AS DECIMAL(18, 2))                           AS credit,
    "Memo"                                                     AS memo,
    "Document Number"                                          AS document_number,
    "Transaction Type"                                         AS transaction_type,
    CAST("Created At" AS TIMESTAMPTZ)                          AS created_at,
    "Internal ID"                                              AS ns_internal_id,
    "Line ID"                                                  AS ns_line_id,
    "External Source ID"                                       AS external_source_id,
    "Revenue Plan ID"                                          AS revenue_plan_id,
    CAST(NULL AS VARCHAR)                                      AS finding_id,
    CAST(NULL AS VARCHAR)                                      AS basis,
    source_file,
    source_line
FROM raw_netsuite_gl_detail;
