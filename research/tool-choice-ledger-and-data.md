# Ledger layer and data tooling: facts for the tool choice

Research for issue #5 ("How should the ledger layer be laid out?"). Facts, not a recommendation. Implications are flagged **Implication:**.

- **Options under review:** (A) rustledger (`rledger` 0.24.0) driven by subprocess; (B) no ledger engine, with double-entry and balance checks written as SQL in DuckDB; (C) Python Beancount v3 + beanquery from PyPI.
- **Already decided:** Python 3.11 + uv, and DuckDB transformations as named SQL files.
- **Builds on** [research/rledger-capabilities.md](https://github.com/xaac-ai/finance-engineer-cup/blob/research/rledger-capabilities/research/rledger-capabilities.md) (rledger features, exit codes, JSON shapes). This note does not repeat it.
- **Markers:** **[exp]** means I verified it hands-on on 2026-11-11 (macOS arm64, uv 0.13.6, scratch dir, `uv run --no-project --with ...`). **[2nd]** marks a secondary source. Everything else cites a primary URL.

## TL;DR

1. **rustledger installs as a static binary, not through Python.**
   - It is in **homebrew-core**, but bottles exist only for macOS arm64 and Linux. Intel Macs build it from source with Rust.
   - Prebuilt release archives cover 8 targets, including Windows.
   - There is **no PyPI package**, so `uv sync` alone cannot install it.
   - Homebrew always installs the latest version, and 0.2x releases ship breaking changes, the `query -f json` shape among them.
   - It has one dominant maintainer.
2. **Beancount 3.2.3 installs cleanly through uv** **[exp]**.
   - PyPI has binary wheels for macOS arm64 and x86, Linux x86_64 and aarch64, and Windows, for CPython 3.9–3.14. No compiler is needed.
   - A cold install took under a second, and the package ships `bean-check` and `bean-query`.
   - The in-process API (`loader.load_file`, `beanquery.connect`) worked, and so did a **custom Python plugin** **[exp]**.
   - beanquery is still 0.2.0, released 2025-03-24.
3. **DuckDB 2.0.0 has wheels for every target platform.** Its `DECIMAL` arithmetic is exact for `+`, `-` and `*`, but it has traps:
   - **`ROUND` on DECIMAL rounds half away from zero.** `round_even` is banker's rounding **[exp + docs]**.
   - **Any division involving a DECIMAL returns DOUBLE** **[exp + docs]**.
   - **A TIMESTAMPTZ cast to DATE uses the machine's local time zone**, which can change results between judges **[exp]**.
   - Fetching a TIMESTAMPTZ into Python needs `pytz` installed **[exp]**.
4. **The SQL-only ledger controls fit in about 25 lines of SQL** **[exp]**: balanced transactions, balance assertions, duplicates, and account open/close dates.
   - What you lose is Beancount's standard file format, its precision-inferred tolerance, and a recognised "engine says OK" artefact.
5. **Precedent.** Neither Cup I nor Cup II mentions plain-text accounting.
   - The Cup II rubric says **"Tool count and visual polish alone do not earn points"** and asks for a workflow "another accountant can adopt and rerun".
   - Cup I's rubric said STACK "isn't about using the most tools — it's about using them well".
   - The Cup I entries I could find publicly used Python with pandas and openpyxl, or Node with Postgres. I found no ledger engines.

---

## 1. rustledger distribution

### Install channels (v0.24.0)

| Channel | macOS | Linux | Windows | Pin a version? | Source |
|---|---|---|---|---|---|
| Homebrew **core** (`brew install rustledger`) | arm64 bottles (Sonoma → Golden Gate). **No x86_64 macOS bottle**, so Intel builds from source (`build_dependencies: ["rust"]`) | `arm64_linux`, `x86_64_linux` bottles | – | No. Core carries only the latest stable (0.24.0) or HEAD | [formulae.brew.sh API](https://formulae.brew.sh/api/formula/rustledger.json) |
| GitHub release archives | `aarch64-apple-darwin` (12.8 MB), `x86_64-apple-darwin` (14.2 MB) | gnu and musl, for x86_64 and aarch64 (12.7–14.1 MB) | `x86_64`/`aarch64-pc-windows-msvc` .zip (14.0–14.5 MB) | Yes, by URL. Each asset has a `.sha256` | [release v0.24.0](https://github.com/rustledger/rustledger/releases/tag/v0.24.0) |
| `cargo binstall rustledger` / `cargo install rustledger` | ✓ | ✓ | ✓ | Yes (`@0.24.0`). Needs a Rust toolchain; `cargo install` compiles | [README Install](https://github.com/rustledger/rustledger#install), [crates.io](https://crates.io/crates/rustledger) (0.24.0) |
| Scoop bucket (own bucket, not main) | – | – | ✓ | – | [README](https://github.com/rustledger/rustledger#install) |
| AUR `rustledger-bin`, Fedora COPR `robcohen/rustledger`, Nix flake | – | ✓ | – | Nix yes | [README](https://github.com/rustledger/rustledger#install) |
| Docker `ghcr.io/rustledger/rustledger` | ✓ (with Docker) | ✓ | ✓ | Tag | [README](https://github.com/rustledger/rustledger#install). Manifest for `:latest` resolved **[exp]** |
| npm `@rustledger/wasm` (library, not a CLI), `npx @rustledger/mcp-server` | – | – | – | Yes (58 versions, latest 0.24.0) | [npm registry](https://registry.npmjs.org/@rustledger/wasm) |
| **PyPI** | `rustledger` and `rledger` return **404** | | | | [pypi/rustledger](https://pypi.org/pypi/rustledger/json) **[exp]** |

**Hands-on [exp]:**

- Downloading `rustledger-v0.24.0-aarch64-apple-darwin.tar.gz` with curl took about 1 s, and its sha256 matched the published `.sha256`.
- The archive holds three binaries: `rledger` (10.8 MB), `ag-rledger` (11.2 MB) and `rledger-lsp` (6.5 MB).
- The extracted `rledger --version` printed `rledger 0.24.0`.
- The binary is ad-hoc signed. `spctl -a` reports **"rejected"** (not notarized).
  - A curl download carries no quarantine flag, so it ran.
  - A copy downloaded **through a browser** would be quarantined, and Gatekeeper would block it until the judge clears the flag (`xattr -d com.apple.quarantine`).
- The Homebrew keg on this machine is 29 MB, and its `rledger` is 23.9 MB.
- `rledger check` on a 20-line ledger runs in about 4 ms. For comparison, `uv run ... bean-check` on the same file took about 0.5 s, most of it uv start-up and Python import.

**Implication:**

- For "one command and minimal installs", rledger means a second, non-Python prerequisite.
- The one-command path would be either:
  - `brew install rustledger`, which is unpinned and has no Intel-Mac bottle and no Windows support; or
  - a bootstrap step that downloads the pinned release asset for the host triple and checks its sha256. That step is about 20 lines of Python to maintain.

### Maturity, cadence, maintainers, license

- **Repo:** [rustledger/rustledger](https://github.com/rustledger/rustledger). Created 2026-01-04, so it is about 10 months old. 428 stars, 50 forks, 24 open issues, last push 2026-11-12 ([GitHub API](https://api.github.com/repos/rustledger/rustledger)).
- **License: GPL-3.0-only** ([Homebrew API](https://formulae.brew.sh/api/formula/rustledger.json)). Beancount is GPL-2.0-only ([PyPI](https://pypi.org/pypi/beancount/json)) and DuckDB is MIT ([repo](https://github.com/duckdb/duckdb)). Calling rledger by subprocess does not link it into our code.
- **Bus factor is about 1.**
  - Top contributors: `robcohen` with 3,088 commits, then bots (dependabot 310, rustledger-bot 44, github-actions 23), `claude` 17, and no human above 6 ([contributors API](https://api.github.com/repos/rustledger/rustledger/contributors)).
  - It still shows heavy activity: 100+ commits in the last 30 days ([commits API](https://api.github.com/repos/rustledger/rustledger/commits)).
- **Cadence:**
  - 0.8.0 shipped on 2026-01-29.
  - 0.24.0 shipped on 2026-09-06.
  - In between came about 40 releases, sometimes several a day (0.17.0–0.19.0 between 2026-06-30 and 2026-07-02).
  - There has been no release in the two months since 0.24.0, but `main` has moved a lot ([releases](https://github.com/rustledger/rustledger/releases)).
- **Homebrew installs:** 671 in 365 days and 70 in 90 days ([formulae.brew.sh analytics](https://formulae.brew.sh/api/formula/rustledger.json)). crates.io downloads: 2,454 total and 538 recent ([crates.io API](https://crates.io/api/v1/crates/rustledger)).

### Breaking changes in 0.2x that touch a subprocess consumer

- **v0.23.0:** "`rledger query -f json` now emits positional row arrays instead of objects keyed by column name" (#2241) ([release v0.23.0](https://github.com/rustledger/rustledger/releases/tag/v0.23.0)). Code written against 0.22 breaks on 0.23+.
- **v0.24.0:** two breaking changes, both in `rledger extract` (`importers.toml` rejects unknown keys; unconfigured liability imports are refused). Neither matters to us ([release v0.24.0](https://github.com/rustledger/rustledger/releases/tag/v0.24.0)).
- **Unreleased on `main`:** the `### Breaking` section of [CHANGELOG.md](https://github.com/rustledger/rustledger/blob/main/CHANGELOG.md) runs to about 110 lines. It changes how option values are read (`render_commas`, `infer_tolerance_from_cost`, `tolerance_multiplier`), reports invalid options without applying them, and more.
  - The prior note found that `main` makes **flagless transactions a parse error** and makes `booking_method` case-sensitive.
- **Implication:** an unpinned install (`brew install`) during judging, after a 0.25 release, could change parse results or output shapes. Pinning needs the release-asset or cargo route.

## 2. Python Beancount v3

### Versions and wheels

| Package | Latest | Released | Wheels | Deps | Source |
|---|---|---|---|---|---|
| `beancount` | **3.2.3** | 2026-05-05 | cp39–cp314 (incl. 3.14t) × macOS x86_64 + arm64, manylinux x86_64 + aarch64, win32 + win_amd64. About 0.43 MB each. Plus an sdist | `click`, `python-dateutil`, `regex` | [PyPI JSON](https://pypi.org/pypi/beancount/json) |
| `beanquery` | **0.2.0** | 2025-03-24 | pure `py3-none-any` | `beancount>=2.3.4`, `click`, `python-dateutil`, `tatsu-lts` | [PyPI JSON](https://pypi.org/pypi/beanquery/json) |

- **v3 release history:** 3.0.0 (2024-06-22), 3.1.0 (2025-01), 3.2.0 (2025-09), and 3.2.1–3.2.3 (2026-04-29 to 2026-05-05) ([PyPI JSON](https://pypi.org/pypi/beancount/json)).
- **No compiler or bison is needed** on any mainstream platform, because a binary wheel exists for each one. Only exotic platforms fall back to the sdist.

### Hands-on [exp]

- **Cold install.** `UV_CACHE_DIR=<empty> uv run --python 3.11 --no-project --with beancount==3.2.3 --with beanquery==0.2.0 bean-check --help` installed 7 packages in **0.9 s wall**. The uv cache grew to 19 MB.
- **Console scripts.** The `beancount` wheel alone provides `bean-check`, `bean-format`, `bean-doctor` and `bean-example`. **`bean-query` comes from `beanquery`**: it appears only when that package is also installed **[exp, entry points]**.
- **Behaviour on a test ledger** with a duplicate transaction, an unbalanced transaction, and a wrong balance assertion, plus `plugin "beancount.plugins.noduplicates"`:
  - `bean-check` reported all three and **exited 1**.
  - Its messages carry `file:line` for every error, **including the duplicate** (`t.beancount:10: Duplicate entry: ...`). rledger reports a plugin finding at `line 1`, code `PLUGIN`.
  - rledger 0.24 on the same file found the same three problems (`PLUGIN`, `E3001`, `E2001`) **[exp]**.
- **In-process API (worked):**

```python
from beancount import loader
import beanquery
entries, errors, options = loader.load_file("ledger.beancount")   # errors: list of namedtuples (source, message, entry)
conn = beanquery.connect("beancount:ledger.beancount")
cur  = conn.execute("SELECT account, sum(number) AS bal GROUP BY account ORDER BY account")
cur.description  # [('account',...), ('bal',...)]
cur.fetchall()   # [('Assets:1100-AR', Decimal('2410.00')), ...]  -- real Decimal objects
```

- **A custom Python plugin worked** with a plain `PYTHONPATH=.`:
  - `plugin "plugins.require_source"` loaded a 10-line module (`__plugins__ = ["require_source_id"]`) that returns `(entries, errors)`.
  - Its error appeared in `errors` beside the built-in ones, with a line number.
  - In rledger 0.24, Python plugins fail (prior note §5).
- Account names like `Assets:1100-AR` and `Liabilities:2200-Deferred-Revenue` load in both engines **[exp]**.

### Features compared with rustledger (for our needs)

| Need | Beancount 3.2.3 | rledger 0.24 |
|---|---|---|
| Balanced transactions, tolerance inferred from precision | ✓ (`__tolerances__` meta seen, USD 0.005) **[exp]** | ✓ (prior note) |
| `balance` assertions (start-of-day semantics) | ✓ **[exp]** | ✓ |
| `open`/`close` enforcement | ✓ | ✓ |
| `noduplicates` | ✓, with location **[exp]** | ✓, location is line 1 |
| Custom plugins | **Python modules, in-process** **[exp]** | Python plugins failed; WASM plugins not in the release build |
| BQL | beanquery 0.2.0 (Python DB-API style cursor, returns `Decimal`) | built in; JSON/CSV output; numbers as strings |
| Machine-readable check output | Python objects (no JSON CLI flag) | `check -f json` |
| Speed | about 0.5 s per invocation incl. uv/Python start-up **[exp]** | about 4 ms **[exp]** |

### Maintenance status

- **beancount/beancount:** 6.2k stars, GPL-2.0, 248 open issues, last push 2026-08-23.
  - Recent commits: 2026-08-22 (an external contributor) and 2026-05-17 (Martin Blais).
  - Top contributors: `blais` 5,527 commits and `dnicolodi` 238 ([repo API](https://api.github.com/repos/beancount/beancount), [commits](https://github.com/beancount/beancount/commits)).
  - The project is slow-moving and stable. The bus factor is also small, but the format has had about 15 years of use.
- **beancount/beanquery:** 66 stars, last push 2026-06-11. Recent commits by Daniele Nicolodi add Python 3.14 to CI and fix parsing ([commits](https://github.com/beancount/beanquery/commits)). It has had no PyPI release since 0.2.0 (2025-03).

## 3. DuckDB facts

### Version and wheels

- **`duckdb` 2.0.0** was released to PyPI on 2026-10-21 and **requires Python ≥ 3.11** ([PyPI JSON](https://pypi.org/pypi/duckdb/json)).
- cp311 wheels exist for macOS universal2, x86_64 and arm64 (17.6 MB), manylinux x86_64 and aarch64, win_amd64 and win_arm64.
- It has no required dependencies (pandas, pyarrow and numpy are extras only). Homebrew's `duckdb` CLI is also 2.0.0 ([formulae.brew.sh](https://formulae.brew.sh/api/formula/duckdb.json)).

### DECIMAL semantics [exp on 2.0.0, docs cited]

| Expression | Result | Note |
|---|---|---|
| `ROUND(2.345::DECIMAL(18,3), 2)` | `2.35` | half away from zero |
| `ROUND(2.355::DECIMAL(18,3), 2)` | `2.36` | |
| `ROUND(2.5::DECIMAL(18,1), 0)` / `ROUND(3.5::…,0)` | `3` / `4` | **not** banker's |
| `ROUND(-2.5::DECIMAL(18,1), 0)` | `-3` | away from zero |
| `ROUND_EVEN(2.5::DECIMAL,0)` / `(3.5)` / `ROUND_EVEN(2.345::DECIMAL(18,3),2)` | `2` / `4` / `2.34` | banker's ("rounding half to even rule"; alias `roundbankers`) |
| `'12.345'::DECIMAL(18,2)` | `12.35` | **casting rounds, half-up**, without error |
| `0.1::DECIMAL(18,2)+0.2::DECIMAL(18,2) = 0.3` | `true` (DOUBLE: `false`) | exact |
| `1.10::DECIMAL(18,2) * 1.10::DECIMAL(18,2)` | `1.2100`, `DECIMAL(18,4)` | scales add |
| `sum(DECIMAL(18,2))` | `DECIMAL(38,2)` | |
| `10.00::DECIMAL(18,2) / 3` | `3.3333333333333335`, **DOUBLE** | **division leaves DECIMAL** |
| `(10.00::DECIMAL(18,2) * 7 / 31)::DECIMAL(18,2)` | `2.26` | passes through a double before the cast back |
| `typeof(2.345)` (bare literal) | `DECIMAL(4,3)` | |
| `try_cast('1,200.00' AS DECIMAL(18,2))` | `NULL` | thousands separators are not parsed |

- **Docs:**
  - The [numeric functions](https://duckdb.org/docs/2.0/sql/functions/numeric.html) page lists `round(v, s)` only as "Round to s decimal places" and does not state the tie rule. The table above shows it by experiment. `round_even` and `roundbankers` are documented as "rounding half to even".
  - The [numeric types](https://duckdb.org/docs/2.0/sql/data_types/numeric.html) page says: "DuckDB uses approximate floating-point arithmetic for all divisions that involve fixed-point decimals and accordingly returns floating-point data types." Multiplication returns a decimal "with the required WIDTH and SCALE to contain the exact result" (max width 38).
- **Implication:**
  - Proration (`fee × days / days_in_period`) gives a DOUBLE. Either multiply first and round once, accepting a double intermediate, or prorate in Python `Decimal`.
  - Pick one rounding rule and write it down, then use `ROUND` (half-up) or `ROUND_EVEN` on purpose. Python's default `Decimal` context is `ROUND_HALF_EVEN` ([docs.python.org](https://docs.python.org/3.11/library/decimal.html)), so `round(Decimal('2.345'), 2)` gives `2.34`, while `quantize(..., ROUND_HALF_UP)` gives `2.35` **[exp]**. DuckDB `ROUND` and Python `round()` therefore **disagree on ties**.

### CSV reading

- **`all_varchar=true`:**
  - The docs define it as "Skip type detection and assume all columns are of type VARCHAR", and it is supported only by `read_csv` ([CSV overview](https://duckdb.org/docs/2.0/data/csv/overview.html)).
  - **[exp]** With it, every column is VARCHAR, and leading zeros (`001`, `0042`) and offset timestamps are kept as written.
- **Without `all_varchar` [exp]:**
  - `12.345` was auto-detected as **DOUBLE**, not DECIMAL.
  - `2026-10-01T08:00:00-07:00` was detected as `TIMESTAMP WITH TIME ZONE`.
  - IDs with leading zeros stayed VARCHAR in this sample. Do not rely on that.
- **Timestamps with offsets [exp]:**
  - `'2026-10-01T08:00:00-07:00'::TIMESTAMPTZ` stores the instant correctly.
  - `::TIMESTAMP` (without a time zone) **silently drops the offset** and returns `2026-10-01 08:00:00`.
  - `TIMESTAMPTZ::DATE` uses the session `TimeZone`, which **defaults to the machine's zone**. Here that was `America/Phoenix`. After `SET TimeZone='UTC'`, `'2026-10-31 23:30:00-07:00'::TIMESTAMPTZ::DATE` returned **2026-11-01**.
  - The docs confirm that conversions between the WITH and WITHOUT TIME ZONE types use "the configured time zone" ([timestamp docs](https://duckdb.org/docs/2.0/sql/data_types/timestamp.html)).
  - **Implication:** a cutoff (October vs November) can change with the judge's laptop time zone. Set `SET TimeZone=...` explicitly in the run, or derive dates from the string's own local date with `strptime`/`substr`.
- **Python fetch gotcha [exp]:** `.fetchall()` on a TIMESTAMPTZ column raised `InvalidInputException: Required module 'pytz' failed to import` in a clean env. It works with `--with pytz`. Cast to VARCHAR or DATE before fetching, or add `pytz` as a dependency.
- **COPY TO CSV [exp]:** `COPY (...) TO 'out.csv' (HEADER, DELIMITER ',')` wrote `a,amt,n,s\n1,12.30,,"x,y"\n`. DECIMAL scale is kept (`12.30`), NULL is written as an empty field, and fields that contain commas are quoted.

### Alternatives, briefly

- **sqlite3:**
  - There is no DECIMAL storage class. The storage classes are NULL, INTEGER, REAL (8-byte IEEE float), TEXT and BLOB.
  - A declared `DECIMAL(10,5)` only gets **NUMERIC affinity** ([datatype3](https://www.sqlite.org/datatype3.html)).
  - Exact decimal maths needs the optional `decimal.c` extension, which works on text-stored numbers ([floatingpoint](https://www.sqlite.org/floatingpoint.html)). It is not loaded in Python's stdlib `sqlite3` by default.
- **polars 2.1.0** (2026-10-25, Python ≥ 3.11, [PyPI](https://pypi.org/pypi/polars/json)):
  - `pl.Decimal` is a "128-bit type", and its docstring carries no unstable warning in 2.1.0 **[exp]**.
  - `Series.round(2)` on Decimal rounded **half to even** (`2.345 → 2.34`, `2.5 → 2.0`) **[exp]**.
  - Decimal ÷ int **stays Decimal**, with the scale kept (`10.00/3 → 3.33`) **[exp]**.
  - It is a different rounding rule from DuckDB's `ROUND`.
- **Plain Python `Decimal`:**
  - Exact, and in the stdlib.
  - The default context is 28 digits with `ROUND_HALF_EVEN`, and it can be set per context ([docs](https://docs.python.org/3.11/library/decimal.html)).
  - Beancount and beanquery return `Decimal` natively **[exp]**.

## 4. SQL-only ledger controls (option B)

**Tested in DuckDB 2.0.0 [exp].** This schema plus four queries caught the same three defects as `bean-check`/`rledger check`. It also caught a posting before an account's open date and an unknown account (via a foreign key).

```sql
CREATE TABLE accounts(account VARCHAR PRIMARY KEY, netsuite_id VARCHAR, open_date DATE NOT NULL, close_date DATE);
CREATE TABLE je_lines(je_id VARCHAR NOT NULL, line_no INT NOT NULL, je_date DATE NOT NULL,
  account VARCHAR NOT NULL REFERENCES accounts(account),          -- unknown account -> Constraint Error at INSERT
  amount DECIMAL(18,2) NOT NULL, source_id VARCHAR NOT NULL,       -- traceability enforced by NOT NULL
  PRIMARY KEY (je_id, line_no));
CREATE TABLE balance_assertions(account VARCHAR, as_of DATE, expected DECIMAL(18,2));

-- balanced transactions (exact: DECIMAL sums, tolerance 0)
SELECT je_id, sum(amount) AS residual FROM je_lines GROUP BY je_id HAVING sum(amount) <> 0;
-- balance assertions, Beancount semantics (balance at START of as_of)
SELECT b.account, b.expected, coalesce(sum(l.amount),0) AS actual
FROM balance_assertions b LEFT JOIN je_lines l ON l.account=b.account AND l.je_date < b.as_of
GROUP BY ALL HAVING actual <> b.expected;
-- duplicates: same date + same multiset of (account, amount) -- like noduplicates, ignoring metadata
WITH sig AS (SELECT je_id, any_value(je_date) d,
               string_agg(account||':'||amount::VARCHAR, '|' ORDER BY account, amount) s
             FROM je_lines GROUP BY je_id)
SELECT list(je_id ORDER BY je_id) AS jes, d, s FROM sig GROUP BY d, s HAVING count(*) > 1;
-- account open/close window
SELECT l.je_id, l.account, l.je_date FROM je_lines l JOIN accounts a USING(account)
WHERE l.je_date < a.open_date OR l.je_date > a.close_date;
```

**Notes:**

- Cross-row rules such as "each JE sums to 0" **cannot be a declarative constraint**. They are checks you have to run. That is the same position as running `rledger check`, only you own the check code.
- What Beancount and rledger give that this does not:
  - a standard, human-readable journal format that judges or accountants may recognise;
  - tolerance inferred from precision (moot if everything is `DECIMAL(18,2)`);
  - `pad`, multi-currency and cost booking (not needed here);
  - an existing, independently written validator. With SQL checks, we write both the checks and the code they check.
- What SQL gives:
  - **no extra install**;
  - the checks sit beside the transformations as named `.sql` files;
  - outputs are tables that export straight to CSV.

## 5. Precedent and what Numeric says it values

### Rubric wording (primary: Numeric's Notion briefs)

- **Cup II (Billing Battle)**, from the [challenge page](https://numeric.notion.site/Finance-Engineer-Cup-II-Billing-Battle-Round-1-Challenge-Draft-40839a8f056781e4ae57e8e132aeb1da), via the Notion API:
  - **STACK:** "Tools selected and used well, with sensible complexity and maintainability. **Tool count and visual polish alone do not earn points.**"
  - **BUILD:** "A functional, usable workflow **another accountant can adopt and rerun**."
  - **CONTROLS:** "Completeness checks, traceable calculations, visible uncertainty, and prevention of duplicate or unsupported corrections."
  - The page also says: "Use any tools you want. Excel, Google Sheets, Python, Claude, ChatGPT, Cursor, no-code tools…"
  - And: "Do I need to know how to code? No. A functional spreadsheet, no-code workflow, or AI-assisted build can meet the challenge. What matters is that it works and another accountant can use it."
- **Cup I (Ridgeline Foods freight accruals, May 21 – June 14, 2026)**, from the [brief](https://numeric.notion.site/Finance-Engineer-Cup-Round-1-Challenge-36739a8f056780fc9316f0a5144e8a19):
  - It used the same five stats and weights.
  - **STACK:** "How savvy is your tool selection? Did you connect systems intelligently? This isn't about using the most tools — it's about using them well."
  - **CONTROLS:** "An accountant who automates without controls is just automating errors faster."
  - "Repeatability — could someone else on the team run this next month without rebuilding it?"
  - The rules listed "Python, Claude Code, Cursor, Excel/Google Sheets, Zapier, MCP servers, Lovable, Replit".
- **Implication:** the audience is an *accountant* rerunning the build. A Beancount journal is readable plain text, but it is a niche format, and nothing in either brief mentions plain-text accounting.

### Cup I results

- **Winner:** Alexandria Ramirez (Betterment), with "Four-Eye Check". Two independent AI agents reconcile the same feed, a deterministic layer clears the items they agree on, and humans review the disagreements ([Numeric blog, 2026-07-31](https://www.numeric.io/blog/how-alexandria-ramirez-won-numerics-first-finance-engineer-cup)).
  - That was the **final round**, where finalists could submit any workflow. Claude and a "vibe-coding environment" are mentioned, but no specific stack.
- **Other finalists:** Leslie Cunnane (Jasper), Casey Barry (Pulumi) and Matt Atieh (ClickUp) ([Cup page](https://www.numeric.io/finance-engineer-cup); finals video "[Numeric's Finance Engineer Cup: Live Finals](https://www.youtube.com/watch?v=Y9HQ6ze-DI4)").
- **Entries:** "170+ submissions" (Mike Haylon, LinkedIn, as quoted in search results) **[2nd]**.
- **The Cup page's framing:** "Finance engineers own data pipelines, ship automations, and treat the general ledger as a system to architect rather than a process to execute" ([numeric.io/finance-engineer-cup](https://www.numeric.io/finance-engineer-cup)).
- **Public Cup I Round 1 repos [2nd]:** the authors self-identify these as entries, and their placement is **unknown**.
  - [Winventions/ridgeline-freight-accrual](https://github.com/Winventions/ridgeline-freight-accrual): Python with `pandas`, `openpyxl`, `pillow`. It runs with `python run_accrual.py --data-dir data --output-dir output` and also has a Vercel page.
  - [justinstlouiswood/ridgeline-freight-accrual](https://github.com/justinstlouiswood/ridgeline-freight-accrual): a Python package with a CLI, pytest, a Dockerfile, double-clickable macOS `.command` launchers, xlsx output, and an "idempotency guard".
  - [agenticledger/ridgeline-finance-os](https://github.com/agenticledger/ridgeline-finance-os): Node, Prisma + PostgreSQL, an MCP server, and an append-only `LedgerEvent` table with a human sign-off gate before the JE posts.
  - None used a plain-text ledger engine.

### Plain-text accounting in finance-engineering practice

- I found **no primary-source evidence** of finance teams or Numeric content using Beancount, ledger or hledger.
- Numeric's [Finance Engineer article](https://www.numeric.io/blog/the-finance-engineer-why-accountants-are-the-best-builders-in-the-room) (Nigel Sapp, 2026-07-02) cites "Python scripts", "TypeScript, Python, and no code tools", and Claude skills.
- Plain-text accounting is mostly personal finance. The [plaintextaccounting.org FAQ](https://github.com/plaintextaccounting/plaintextaccounting/blob/master/src/FAQ.md) cites "500–1500 transactions … per year" as typical for individuals **[2nd, via search summary]**.
- There are single-business write-ups, for example [ztoz.blog](https://ztoz.blog/posts/plaintext-accounting-reporting/) (Beancount v3 for a small publisher's books, chosen partly for its Python API) **[2nd]**.
- **Implication:** a ledger engine would stand out as unusual. Whether that reads as "savvy" or as "extra complexity" depends on how visibly it carries the CONTROLS story: balance assertions tied to NetSuite opening balances, and duplicate-JE prevention.

## Open points not verified

- I did not measure the time for rledger `cargo binstall` or for an Intel-Mac Homebrew source build.
- I did not run DuckDB or Beancount on Windows. The claims rest on the wheel listings only.
