# Jev term-check spike (jev-1.14.0)

- Cases: 22 × 3 repeats. Majority verdict correct: **21/22**.
- Wrong claims not marked `supports` (first run): **14/14**.
- Cases whose verdict changed across repeats: **0/22**.
- Input tokens total: 38,688 (≈ $0.0016). Median latency: 0.17 s.

| Case | Expected | Answers | Min confidence | Gate (≥0.8) | Majority right |
|---|---|---|---|---|---|
| `157_runs_ok` | supports | supports/supports/supports | 0.50 | review | ✅ |
| `157_runs_wrong_value` | contradicts | contradicts/contradicts/contradicts | 0.16 | review | ✅ |
| `157_runs_ok_s0304` | supports | supports/supports/supports | 0.98 | auto | ✅ |
| `157_runs_wrong_value_s0304` | contradicts | contradicts/contradicts/contradicts | 0.96 | auto | ✅ |
| `157_runs_wrong_date` | contradicts | contradicts/contradicts/contradicts | 1.00 | auto | ✅ |
| `157_weighting_ok` | supports | supports/supports/supports | 0.97 | auto | ✅ |
| `157_weighting_wrong` | contradicts | contradicts/contradicts/contradicts | 1.00 | auto | ✅ |
| `157_overage_decoy` | contradicts | contradicts/contradicts/contradicts | 1.00 | auto | ✅ |
| `164_rate_ok` | supports | supports/supports/supports | 1.00 | auto | ✅ |
| `164_rate_wrong_value` | contradicts | contradicts/contradicts/contradicts | 0.96 | auto | ✅ |
| `164_rate_wrong_date` | contradicts | contradicts/contradicts/contradicts | 0.98 | auto | ✅ |
| `164_invoice_ok` | supports | supports/supports/supports | 1.00 | auto | ✅ |
| `164_invoice_wrong_value` | contradicts | contradicts/contradicts/contradicts | 1.00 | auto | ✅ |
| `164_catchup_ok` | supports | supports/supports/supports | 1.00 | auto | ✅ |
| `164_catchup_wrong_value` | contradicts | contradicts/contradicts/contradicts | 1.00 | auto | ✅ |
| `164_catchup_wrong_basis` | contradicts | contradicts/contradicts/contradicts | 1.00 | auto | ✅ |
| `164_incremental_ok` | supports | supports/supports/supports | 1.00 | auto | ✅ |
| `164_incremental_wrong` | contradicts | contradicts/contradicts/contradicts | 1.00 | auto | ✅ |
| `164_credit_ok` | supports | supports/supports/supports | 1.00 | auto | ✅ |
| `164_credit_wrong_sign` | contradicts | contradicts/contradicts/contradicts | 0.89 | auto | ✅ |
| `164_usage_decoy` | contradicts | says_nothing/says_nothing/says_nothing | 0.88 | auto | ❌ |
| `164_says_nothing` | says_nothing | says_nothing/says_nothing/says_nothing | 1.00 | auto | ✅ |

## Verdict (wayfinder: "Can Jev tell a supported Amendment term from an unsupported one?")

**Yes. Adopt Jev as the post-quote-gate term check.**

- **No wrong claim was marked `supports`: 14 of 14.** That covers wrong values, dates, bases and signs, and decoys.
- **Every correct claim was marked `supports`: 8 of 8.**
- **Zero verdict flips** across 3 repeats of each case.
- **Cost:** about $0.002 for the whole run, with a median latency of 0.17 s.
- **The one "miss" is defensible.** For `164_usage_decoy`, AM-164 says only "Usage terms are unchanged", so `says_nothing` (0.93) about "$0.10 per run" is reasonable, and it is still not `supports`.
- **Context matters.** Section 03 alone is a table without the effective date, so `157_runs_*` scored low confidence (0.50 / 0.16). Given sections 03 and 04 together, confidence rose to 0.98 / 0.96.

**Design for the workbench:**
- Send each term with the Amendment's terms text: sections 03 **and** 04, not the single quoted section.
- Auto-accept only `supports` with confidence ≥ 0.8. Anything else goes to human review.
- Pin `jev-1.14.0` and commit the answer cache.
