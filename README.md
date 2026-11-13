# RelayCloud billing review workbench

Finance Engineer Cup II: Billing Battle, Round 1. The brief is in [`docs/CHALLENGE.md`](docs/CHALLENGE.md) and the domain vocabulary in [`GLOSSARY.md`](GLOSSARY.md).

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
