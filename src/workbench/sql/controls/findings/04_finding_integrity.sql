-- title: Findings are well-formed (evidence cited; Needs Info has no confirmed amounts; zero October effect is explained)
-- severity: fail
SELECT f.finding_id, problem FROM (
    SELECT f.*, CASE
        WHEN NOT EXISTS (SELECT 1 FROM finding_evidence e WHERE e.finding_id = f.finding_id) THEN 'no evidence cited'
        WHEN status = 'needs_info' AND (billing_effect IS NOT NULL OR october_revenue_effect IS NOT NULL)
            THEN 'Needs Info carries a confirmed amount (use exposure)'
        WHEN status <> 'needs_info' AND exposure IS NOT NULL THEN 'exposure on a confirmed finding'
        WHEN status = 'error' AND billing_effect IS NULL AND october_revenue_effect IS NULL THEN 'error without an effect'
        WHEN status = 'error' AND coalesce(october_revenue_effect, 0) = 0 AND no_october_entry_reason IS NULL
            THEN 'zero October effect without a reason'
        WHEN status NOT IN ('error', 'valid_explanation', 'needs_info') THEN 'unknown status'
    END AS problem
    FROM findings f
) f
WHERE problem IS NOT NULL
ORDER BY f.finding_id
