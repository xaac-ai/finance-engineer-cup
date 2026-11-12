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
