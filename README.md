# RelayCloud billing review workbench

Finance Engineer Cup II: Billing Battle, Round 1. The brief is in [`docs/CHALLENGE.md`](docs/CHALLENGE.md) and the domain vocabulary in [`GLOSSARY.md`](GLOSSARY.md).

## For judges

**See the report without installing anything:** [the October report](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html). It's a single offline HTML file, also at `out/2026-10/report.html`.

**Or rerun it** (needs [`uv`](https://docs.astral.sh/uv/) and `make`; no API keys):

```sh
git clone https://github.com/xaac-ai/finance-engineer-cup && cd finance-engineer-cup
make run                          # a few seconds; writes out/2026-10/report.html and CSV workpapers
make scenario NAME=extra-usage    # a deliberate change to October's inputs, caught on the rerun
```

### The answer to Priya

- **What should we have billed?** Expected and actual billing for every customer, with platform and usage shown separately. Confirmed Errors come to **$6,835.53 underbilled** and **$3,096.80 overbilled**, never netted against each other.
- **Which differences need action?** 12 Findings: 7 Errors (one of them a follow-up for November service, kept out of the October totals), 2 Needs Info and 3 Valid Explanations. Each has its customer, period, amount, evidence and a recommended action.
- **Does October's accounting change?** October revenue is **understated $6,735.53** and **overstated $3,096.80**. The Proposed Entries post to the October period and the billing documents are dated in November. Where a billing correction needs no October entry, the Finding says why.
- **How do we catch this next month?** `make run PERIOD=<YYYY-MM>`, with 31 controls (30 pass, 0 fail in October; the 1 warning is the unverified workspace). Nine Scenarios show that the review catches deliberate changes and ignores harmless ones.

### Where each score is shown

| Stat | Where to look |
|---|---|
| **Accounting intel** (25) | [Findings](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#findings): each Finding has a Billing Effect and an October Revenue Effect, kept separate, with its calculation. [Effects](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#effects): each customer's balances before and after the proposals. [Brief](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#brief): the Controller summary, follow-ups and Exposure. Judgment calls are listed below. |
| **Build** (25) | `make run` (exit codes 0 / 1 / 2), `make run PERIOD=<YYYY-MM>` for a new month, `make scenario`, and CI that reruns everything from a clean clone and fails if the committed outputs are stale. |
| **Data** (20) | [Customers](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#customers): contract terms with their effective dates and quotes, and verified product-account mappings. Usage validation: duplicates removed, replaced records dropped, batch tie-out (`usage_batch_tieout.csv`). Source reconciliations: `billing_reconciliation.csv` and `revenue_reconciliation.csv`. |
| **Controls** (15) | [Controls & assumptions](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#controls): completeness, every difference claimed by exactly one Finding, no duplicate or netted corrections. [Evidence index](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#evidence): every cited source row. Needs Info amounts appear only as Exposure. The Scenarios are in `tests/test_scenarios.py`. |
| **Stack** (15) | Python, DuckDB SQL and `make`; one control per SQL file; no ledger engine ([ADR 0001](docs/adr/0001-no-ledger-engine.md)). Agent steps run outside `make run`, each with a pinned model and committed answers: an Amendment-term drafter (Claude), a term check against the Amendment text (Jev), and an Independent Review. |

### Judgment calls

Each links to its Finding and to the ticket where it was decided.

1. **Cedar Harbor's mid-month upgrade.** The allowance is weighted by days and rounded once: 30,000 × 15/31 + 45,000 × 16/31 = **37,742** runs. Billing on the old 30,000 overbilled **$3,096.80**. [Finding](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#F-639373-USAGE-ALLOWANCE-2026-10) · [decision](https://github.com/xaac-ai/finance-engineer-cup/issues/12)
2. **Approved compared with requested concessions.** Zephyr Grove's $100 was approved by the Controller in a Billing Message, so it's a Valid Explanation, reflected once. Willow Passage's $250 was only requested, so it's Needs Info and no credit is proposed. [Zephyr](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#F-148565-CREDIT-APPROVED-CONCESSION-2026-10) · [Willow](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#F-839653-CREDIT-REQUEST-MSG-2026-132-2026-10) · [decision](https://github.com/xaac-ai/finance-engineer-cup/issues/20)
3. **Unverified usage.** 49,762 runs on a workspace with no verified owner are reported as Needs Info, unpriced, and never assigned to a customer by elimination. [Finding](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#F-UNATTRIBUTED-USAGE-UNVERIFIED-pa_676b6b455e0887-2026-10) · [decision](https://github.com/xaac-ai/finance-engineer-cup/issues/16)
4. **Meridian's upgrade, billing and revenue kept apart.** The missing $526.03 catch-up invoice is a billing Error with no October revenue effect. The October revenue that omits the increment is a separate Error, so nothing is counted twice. [Billing](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#F-335780-PLATFORM-MISSING-CATCH-UP-2026-10) · [Revenue](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#F-335780-PLATFORM-UPGRADE-INCREMENT-2026-10) · [decision](https://github.com/xaac-ai/finance-engineer-cup/issues/15)
5. **Beacon Marsh's late record.** 1,000 runs arrived after the invoice was issued: a $100.00 supplemental invoice, but no October entry, because the accrual already included them. [Finding](https://xaac-ai.github.io/finance-engineer-cup/out/2026-10/report.html#F-810234-USAGE-LATE-RECORD-2026-10) · [decision](https://github.com/xaac-ai/finance-engineer-cup/issues/19)
6. **Platform presentation.** Invoice by invoice for the billing periods covering October (the brief's first approach), with October revenue computed separately as days ÷ 365. A full invoice that crosses into October is never treated as October revenue. [decision](https://github.com/xaac-ai/finance-engineer-cup/issues/15)

### Known limits

- Only October's data was supplied. The evidence that the review generalises is the nine Scenarios, not a second real month.
- If Stripe is missing an invoice that NetSuite has posted, the missing-invoice Error is raised, but nothing flags the Stripe-to-NetSuite mismatch directly.
- The Jev term check and the Independent Review replay committed answers, so changed data needs `make jev-check` and `make review-findings` rerun. Until then the run warns.
- The Independent Review agrees on 59 of 60 customer-streams. The one Disagreement (Willow Passage, usage) was resolved by a person, with a reason, in `reviewer_resolutions.yaml`.

## Run it

You need [`uv`](https://docs.astral.sh/uv/) and `make`. `uv` fetches Python 3.11+ and every dependency itself.

```sh
make run                 # review October 2026 -> out/2026-10/
make run PERIOD=2026-11  # review another month (see "New month" below)
make test                # code tests
```

Open `out/<period>/report.html` in a browser. It is a single file with no network access, and its views are Findings, Customers, Effects (before/after balances for each customer with a proposal), Brief, Controls & assumptions, and Evidence index. The CSV workpapers sit next to it.

Exit codes:
- `0`: every control passed or warned.
- `1`: a control failed. Outputs are still written so the failure can be reviewed.
- `2`: an input can't be trusted. Nothing is written, and the message says what to fix.

## New month

1. Put the extracts in `data/raw/<YYYY-MM>/`: the same CSVs, `START_HERE.pdf`, `billing_followups.pdf` and `contracts/*.pdf`.
2. Add `data/curated/<YYYY-MM>/period.yaml` (cutoff and expected row counts) and `amendment_terms.yaml`. Every Amendment's changed terms go in that YAML, each with an exact quote from the PDF.
3. Run `make run PERIOD=<YYYY-MM>`.

The run stops with a clear message if anything is missing, if an Order Form doesn't match the template, or if a curated quote isn't in its PDF.

## Scenarios: does it catch next month's problems?

A **Scenario** is October's inputs with one deliberate change, plus the results that change should produce. Each one runs the real pipeline and is compared with the untouched October run: Findings, totals by stream, and the status of every control.

- **Catch** Scenarios must produce exactly the expected difference, and nothing else may change. Examples: 5,000 extra runs that weren't invoiced (+$400.00 usage Error), a missing platform invoice (+$3,000.00), late usage, an unmapped product account (Needs Info), and an extract that no longer ties to its batch totals (a failed control).
- **Ignore** Scenarios must produce no difference: an exactly duplicated usage row, every CSV reordered, and a record restated with the same units.

```bash
make scenario                      # list them
make scenario NAME=extra-usage     # run one; report in out/scenarios/extra-usage/, difference printed
make test                          # runs them all (tests/test_scenarios.py)
```

Expected amounts are worked out by hand in `src/workbench/scenarios.py`. The suite has already paid for itself: `extra-usage` showed the review had no cause for "invoice billed fewer runs than were known", so the `usage_quantity` rule was added.

## Agent steps

These run outside `make run`. Each pins its model, and its answers are committed, so the review and CI never need an API key. `make run` checks the committed results.

| Target | What it does |
|---|---|
| `make draft-terms` | Claude drafts each Amendment's term changes, without seeing the curated terms. The draft is scored against them and never replaces them. |
| `make jev-check` | Jev (TypeSafe) judges whether the Amendment text supports each curated and drafted term. `make run` fails if a curated term is unchecked. |
| `make review-findings` | Independent Review: a second agent classifies every customer and stream from the source files alone. `make run` warns until each Disagreement with the Findings is resolved in `reviewer_resolutions.yaml`. |

The Independent Review applies the standard four-eyes (maker-checker) control to the review itself. An independent second reviewer was also part of a Finance Engineer Cup I entry; the design here is our own.

Keys, if you rerun the agents yourself, go in a gitignored `.env` as `ANTHROPIC_API_KEY` and `TYPESAFE_API_KEY`.

## Layout

| Path | What |
|---|---|
| `data/raw/<period>/` | Source extracts, as supplied |
| `data/curated/<period>/` | Hand-curated inputs, each citing its source |
| `data/reference/accounts.csv` | Chart of accounts |
| `src/workbench/` | Pipeline: inputs → contract terms → Billing Messages → books → controls → outputs |
| `src/workbench/sql/` | The books (`ledger/`), controls (`controls/<group>/`, one file each; empty result = pass), workpapers (`outputs/`) |
| `out/<period>/` | Generated report, workpapers and extracted PDF text |
| `docs/adr/` | Architecture decisions |

## Licence

The code is MIT-licensed (see `LICENSE`). `data/raw/` is Numeric's fictional Finance Engineer Cup II challenge data, included as supplied for the Cup; it isn't covered by the licence.
