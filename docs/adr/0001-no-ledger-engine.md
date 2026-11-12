# No ledger engine: the books are a DuckDB journal table

We first chose rustledger (a Beancount-compatible ledger engine) for the books, then dropped it. Opening balances, recorded GL entries and proposed entries now live in one DuckDB `journal_lines` table, and the double-entry guarantees (balanced entries, opening-balance completeness, known accounts, no duplicates, period and cutoff integrity) are enforced by SQL ledger controls.

A ledger engine fails the deletion test here:
- **Its checks are structural.** They take about 25 lines of SQL, and in testing that SQL caught the same defects as `rledger check` and `bean-check`.
- **It adds no real independence.** It would validate files generated from the same DuckDB views, so a wrong amount would still balance.
- **It costs judges an install.** rustledger has no PyPI package, has a single maintainer, ships frequent breaking releases, and Homebrew installs it unpinned. That conflicts with our "clean clone, one command" rerun requirement.

## Considered Options

- **rustledger via subprocess.** Rejected for the install and stability reasons above.
- **Python Beancount v3.** It installs through PyPI, so it has no install problem. Rejected because it still only adds structural checks we already have, plus a second representation of the books to keep in sync.
- **SQL-only (chosen).** One tool fewer. Proposed journal entries are shown as tables, which accountants read more easily than Beancount syntax.

Evidence: [rledger capabilities](https://github.com/xaac-ai/finance-engineer-cup/blob/research/rledger-capabilities/research/rledger-capabilities.md), [tool-choice research](https://github.com/xaac-ai/finance-engineer-cup/blob/research/tool-choice-ledger-and-data/research/tool-choice-ledger-and-data.md), and the resolution of [How should the ledger layer be laid out?](https://github.com/xaac-ai/finance-engineer-cup/issues/5).
