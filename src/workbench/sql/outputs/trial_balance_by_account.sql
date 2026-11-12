-- Trial balance totals by account at period end (sum of the per-customer rows).
SELECT account_number, account_name,
       sum(recorded_balance) AS recorded_balance,
       sum(with_proposed_balance) AS with_proposed_balance,
       sum(proposed_change) AS proposed_change
FROM out_trial_balance
GROUP BY ALL
ORDER BY account_number
