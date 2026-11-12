# What can rledger 0.24 do for the workbench?

Research for issue #4 (child of map #1). Facts only. It feeds the ledger-layout decision.

- **Binary tested:** `rledger 0.24.0` (Homebrew, `/opt/homebrew/bin/rledger`, macOS arm64), released 2026-09-06 ([release v0.24.0](https://github.com/rustledger/rustledger/releases/tag/v0.24.0)).
- **Sources:** `rledger <cmd> --help` for every subcommand; the [rustledger repo](https://github.com/rustledger/rustledger) (GPL-3.0) docs under `docs/`; hands-on experiments with throwaway `.beancount` files. **[exp]** marks a claim I checked by running it. **[docs]** marks a claim taken from the repo docs on `main`. Those docs are partly *ahead* of 0.24: `CHANGELOG.md` on `main` lists unreleased breaking changes, so where docs and binary disagree, the binary wins (noted inline).

## TL;DR for the workbench

1. **Drive it by subprocess.** There is no Python package. `rustledger`, `rledger` and similar names all 404 on PyPI **[exp]**. The supported embedding paths are Rust crates, a WASM npm package, and a WASI component (WIT) **[docs: guides/integration.md]**. `check -f json` and `query -f json|csv` are machine-readable and stable enough to parse.
2. **`rledger check -f json` makes a good control gate.** Exit code 0 means clean, or warnings only. 1 means any error (parse, validate or plugin). 2 means usage or IO trouble, such as a missing root file **[exp]**. The JSON lists each diagnostic with `file`, `line`, `column`, `end_line`, `end_column`, `severity`, `phase`, `code` and `message`, plus summary counts.
3. **NetSuite-numbered accounts work**, as long as each segment starts with an uppercase letter or a digit and uses only letters, digits and `-`. `Assets:1100-AR`, `Assets:1160` and `Liabilities:2200-Deferred-Revenue` are valid. `_`, `.`, spaces and a lowercase first letter are not **[exp]**.
4. **Tracing back to source IDs works well.** Links (`^INV-1001`), tags (`#adj`), transaction metadata and posting metadata are all queryable: `'INV-1001' IN links`, `'adj' IN tags`, `entry_meta('source_id')`, `meta('line_id')`, `any_meta(...)`, `open_meta(account, key)`. `doctor linked FILE ^INV-1001` finds every entry with a given link **[exp]**.
5. **Multi-file `include` works, including globs** (`include "oct/*.beancount"`). A missing file or a glob with no matches is a hard error (exit 1) **[exp]**.
6. **It is fast.** A 50k-transaction, 300k-line ledger checks in about 0.3 s cold and about 0.08 s from cache. A grouped query takes about 0.16 s **[exp]**.
7. **Gotcha: the parse cache.** `check` and `query` write a hidden `.<name>.beancount.cache` file *next to the root file*. It was about 30 MB for the 50k ledger. Gitignore `.*.beancount.cache`, or pass `-C`/`--no-cache` (`check`) or `--no-cache` (`query`/`report`), or set `BEANCOUNT_DISABLE_LOAD_CACHE` **[exp, check --help]**. The cache invalidated correctly when an included file changed **[exp]**.

## 1. `rledger check`

Usage: `rledger check [-v] [-q] [-C] [-a] [--native-plugin NAME]... [--plugin WASM]... [-f text|json] [--lint transfers] [FILE]` **[check --help]**

### Exit codes [exp]

| Situation | Exit |
|---|---|
| Clean | 0 |
| Warnings only (e.g. E3004 single-posting transaction) | **0** |
| Any error: parse (`P0012`), validate (`E3001`, `E1001`, `E2001`, ...), plugin (`PLUGIN`, `E8001`) | 1 |
| Missing include / no glob match (`E0001`, `E0005`) | 1 |
| Root file not found; `-` (stdin is **not** supported) | 2 (`error: file not found: ...`) |
| `-q` | prints nothing; exit code as above |

### Output

- Text mode prints miette-style code frames with the code (e.g. `E3001`), `x` for an error and `!` for a warning, then a summary line: `✗ 4 errors, 1 warning` or `✓ No errors found`. All of it goes to **stdout** **[exp]**.
- JSON mode (`-f json`), verified shape **[exp]**:

```json
{"diagnostics":[{"file":"/abs/path/bad.beancount","line":3,"column":1,"end_line":6,"end_column":1,
  "severity":"error","phase":"validate","code":"E3001",
  "message":"Transaction does not balance: residual 10.00 USD"}],
 "error_count":4,"warning_count":1,"parse_error_count":1,"validate_error_count":3}
```

  `phase` is `parse`, `validate` or `plugin`. Some diagnostics carry an optional `hint` (seen on E0005).
- **Plugin diagnostics have no real location.** A `noduplicates` hit came back as `file: "dup.beancount", line: 1`, `code: "PLUGIN"` (text mode: `<unknown>: error[PLUGIN]: Duplicate transaction: ...`) **[exp]**. To trace a plugin finding, rely on the message plus your own metadata.
- One run reports every error, so it does not stop at the first one. A parse error does not hide later validation errors **[exp]**.
- `rledger explain` lists every code with its severity, and `rledger explain E2001` explains one **[exp]**. The relevant codes: E1001 account not opened, E1003 used after close, E1004 closed with non-zero balance (warning), E1005 invalid account name, E2001 balance assertion failed, E2003/E2004 pad problems, E3001 does not balance, E3002 multiple elided postings, E3004 single posting (warning), E5001/E5002 currency constraints, E7001–E7003 options, E10002 future-dated directive (warning).

### Balancing and tolerance [exp]

- Tolerance is inferred from precision, as in Beancount. With 2-decimal amounts, a residual of 0.004 passes and a residual of 0.01 fails (E3001).
- Balance assertions also infer tolerance from the asserted amount's precision. `balance ... 5100.004 USD` fails against 5100.00, while `5100.00 USD` passes. An explicit `balance A 5100.00 ~ 0.01 USD` is supported.
- `balance` asserts the balance at the **start** of its date, so it excludes that day's transactions. That is Beancount semantics. For example, an assertion on `2025-11-01` checks the October close.
- `pad` + `balance` works. The pad becomes a `P`-flagged transaction that `#postings` returns.

## 2. Accounts and naming [exp]

- The roots must be `Assets`, `Liabilities`, `Equity`, `Income` and `Expenses`. Anything else fails with E1005, and the message suggests renaming a root with `option "name_income" "Revenue"`. The `name_*` options are listed by `doctor list-options`.
- Valid: `Assets:1100`, `Assets:1100-AR`, `Assets:1100:Sub`, `Assets:Ünbilled` (Unicode is OK).
- Invalid (parse errors, P0012): `Assets:1100_AR` (underscore), `Assets:ar-1100` (lowercase first letter), `Assets:AR.1100` (dot), `Assets:1100 AR` (space).
- **Suggested shape:** `Assets:1100-AR`, `Assets:1150-Unbilled-Usage-Receivable`, `Assets:1160-...`, `Liabilities:2200-Deferred-Revenue`, `Income:4000-...`, `Income:4010-...`. To map an account back to its NetSuite number explicitly, put the number in `open` metadata (`netsuite_id: "1100"`) and read it with `open_meta(account, 'netsuite_id')` **[exp]**. `account_meta()` does **not** exist **[exp]**.
- Every account must be opened unless you use `auto_accounts` (see §5). An unopened account is E1001.

## 3. Query (BQL)

Usage: `rledger query [-F QUERY_FILE] [-o OUT] [-f text|csv|json|beancount] [-m] [-q] [--no-cache] FILE [QUERY...]` **[query --help]**. With no query it enters interactive mode.

- **Put flags before FILE.** QUERY is variadic and swallows anything after it **[docs: guides/integration.md]**.
- **Output formats [exp]:**
  - `csv`: a header row and RFC-style quoting. Set columns (`links`, `tags`) render as `"INV-1001, JE-77"`.
  - `json`: `{"columns":[...],"row_count":N,"rows":[[...],...]}`. Rows are **positional arrays**, because column names can repeat. **Numbers come out as strings** (`"1200.00"`), which suits `Decimal`. A position is `{"units":{"number":"100.00","currency":"USD"},"cost":null}`, an inventory is `{"positions":[...]}`, a set column is a JSON array, metadata is an object, and a boolean is a JSON bool.
  - `-m` (numberify) strips currencies, so `sum(position)` becomes `1200.00` in CSV.
  - `beancount`: used with `PRINT`.
- **Exit codes [exp]:** 0 on success. 1 on a query syntax error (`error: failed to parse query: ...`) or an unknown function. 1 on a ledger with **parse** errors: it refuses with `refusing to report on a file that did not parse`, and `-q` does not override this. A ledger with **validation** errors still answers with exit 0. The errors go to **stderr** (`E3001: ...`) and stdout stays clean CSV/JSON. `-q` suppresses them.
- **Tables:** the default is postings. System tables are `#accounts`, `#balances`, `#commodities`, `#documents`, `#entries`, `#events`, `#notes`, `#postings`, `#prices` and `#transactions`. The error message lists them **[exp]**. The `.tables` and `.functions` dot-commands do not work non-interactively **[exp]**.
- **Posting columns** (from `SELECT * FROM postings`) **[exp]**: `type id date year month day filename lineno location flag payee narration description tags links posting_flag account other_accounts number currency cost_number cost_currency cost_date cost_label position price weight balance account_balance meta accounts`. `filename`/`lineno` give each row's source location.
- **Clauses verified [exp]:** `WHERE`, `GROUP BY` (by name or ordinal), `HAVING`, `ORDER BY`, `LIMIT`, `DISTINCT`, subqueries in `FROM`, `FROM OPEN ON <date> CLOSE ON <date>`, `FROM <posting filter>`, `BALANCES`, `JOURNAL '<regex>'`, `PRINT`. `PIVOT BY` and window functions (`row_number() OVER (PARTITION BY ...)`, a rustledger extension) are documented **[docs: reference/bql.md]**.
- **Functions** **[docs: reference/bql.md; spot-checked exp]**:
  - Aggregates: `sum count first last min max avg`.
  - Dates: `year month day quarter weekday today yearmonth`.
  - Amounts: `cost units currency commodity number neg abs possign filter_currency`.
  - Strings and accounts: `length upper lower root leaf parent findfirst grep grepn subst has_account str coalesce`.
  - Metadata: `meta entry_meta any_meta getitem commodity_meta open_meta` (`open_meta` was verified only by experiment).
  - Prices: `convert value getprice`.
  - Regex match: `~`. Membership: `'x' IN links`, `'k' IN meta`.
- **Known divergences:**
  - **`PRINT FROM <filter>` in 0.24 filters only transactions.** Every `open` and `balance` directive was printed regardless of `has_account(...)` or `'JE-77' IN links` **[exp]**. The docs on `main` describe the filter applying to all entry types, so this has probably changed since 0.24.
  - **`PRINT` drops transaction and posting metadata** (`source_id` was not printed) **[exp]**. Do not use `PRINT` to round-trip generated files.
  - In text format, `PRINT` renders as a padded table, so use `-f beancount`.
  - The full list of bean-query differences is in [compatibility.md](https://github.com/rustledger/rustledger/blob/main/docs/reference/compatibility.md) (19 items). Most concern multi-currency, cost and lot edge cases that don't apply to a single-currency USD GL.

### Recipes verified for the workbench [exp]

```sql
-- trial balance
SELECT account, sum(number) AS bal GROUP BY account ORDER BY account
-- everything tied to one source document
SELECT date, account, number, entry_meta('source_id'), meta('line_id') WHERE 'INV-1001' IN links
-- adjusting JEs only
SELECT date, account, position, links WHERE 'adj' IN tags
-- AR subledger by customer (customer_id in txn meta)
SELECT str(entry_meta('customer_id')) AS c, sum(number) WHERE account = 'Assets:1100-AR' GROUP BY c
-- period activity vs balance
SELECT account, sum(number) FROM OPEN ON 2025-10-01 CLOSE ON 2025-11-01 GROUP BY account
SELECT account, sum(number) WHERE date >= 2025-10-01 AND date < 2025-11-01 GROUP BY account
-- transaction-level view with links
SELECT DISTINCT id, date, narration, links FROM #entries WHERE 'INV-1001' IN links
SELECT * FROM #transactions
```

## 4. Metadata, links and tags [exp]

- Transaction-level metadata goes on the lines under the header. Posting-level metadata is indented under the posting.
  - `meta()` reads posting metadata only.
  - `entry_meta()` reads transaction metadata only.
  - `any_meta()` reads posting metadata first, then transaction metadata.
  - A key at the wrong level returns NULL, which silently drops rows in a `WHERE` **[docs + exp]**.
- Metadata values keep their types. Strings, numbers (returned as strings in JSON), dates, booleans (`TRUE` → JSON `true`), accounts and amounts (`{"number","currency"}`) all came back typed in JSON **[exp]**.
- Every entry's metadata also carries `filename` and `lineno` **[exp]**.
- Links and tags go on the header line, and a transaction can carry several: `#adj ^INV-1001 ^JE-77` **[exp]**.
- `rledger doctor linked FILE ^LINK` (or `#tag`, or a line number) prints every linked entry **[exp]**.
- Link and tag syntax follows Beancount. I verified `INV-1001` and `JE-77`. I did not exhaustively test other characters, so stick to `[A-Za-z0-9-_/.]`.

## 5. Plugins and options

- **Built-in native plugins.** 33 native plugins are documented **[docs: reference/plugins.md, compatibility.md]**. You enable one in the file with `plugin "beancount.plugins.<name>"`, which resolves to the native version, or on the command line with `--native-plugin <name>`. Both were verified **[exp]**. The ones relevant here:
  - `auto_accounts`: synthesizes `open` directives. `check -a` turns on the auto-plugins implicitly **[exp]**. For a control gate, keep explicit `open`s so typos fail.
  - `noduplicates`: flags directives that are identical apart from metadata **[exp]**. This guards against double-generating the same JE.
  - `leafonly`: blocks postings to parent accounts.
  - `check_closing`, `check_drained`: zero-balance assertions on close.
  - `nounused`: warns about unused accounts.
  - `onecommodity`: limits an account to one commodity.
  - `check_commodity`: requires `commodity` declarations.
  - `pedantic`: enables all of the above.
- An unknown name fails: `--native-plugin nonsense` gives E8001 with exit 1. `plugin "beancount.plugins.nonsense"` gives E8004, because Python plugins must be referenced by file path **[exp]**.
- **Python and WASM plugins are not practical with this build.** The docs say release and Homebrew binaries leave out the plugin runtimes **[docs]**. In practice, `plugin "./myplug.py"` downloaded a CPython-WASI runtime of about 14 MB into `~/Library/Caches/rustledger/python-wasi` and then **failed** with a wasm backtrace (E8002) on a trivial plugin **[exp]**. Do the custom logic in Python *before* writing the Beancount files, not as rledger plugins.
- **Options** (`doctor list-options`) **[exp]**: `title`, `operating_currency`, `name_*`, `account_previous_*`/`account_current_*`, `account_rounding`, `inferred_tolerance_default`, `inferred_tolerance_multiplier`, `infer_tolerance_from_cost`, `booking_method`, `documents`, `render_commas`, and others. An unknown option is E7001.

## 6. Multi-file `include` [exp]

- Relative includes resolve against the including file. Globs work: `include "oct/*.beancount"` loaded every file it matched.
- A missing file gives `E0001 failed to read file`. A glob with no matches gives `E0005 include pattern ... does not match any files`. Both exit 1.
- Diagnostics and `filename` columns carry the **absolute path of the included file** they came from, which helps when tracing errors back to generated files.
- Ordering differs from Python Beancount. Same-date directives across includes keep **include order**, where Beancount compares line numbers across files. This only matters for lot or booking tie-breaks **[docs: compatibility.md §7]**.
- `doctor missing-open` prints the `open` directives a file is missing **[doctor --help]**. That is handy when generating account files.

## 7. Other subcommands [help + exp]

- `format [-i] [--check [--diff]] FILE...`: canonical alignment. `--check` exits 1 when a file is unformatted **[exp]**. Use it to normalise generated files, or skip it and keep the generator's output deterministic.
- `report [-f text|csv|json] FILE <balances|balsheet|income|journal|accounts|stats|...>`:
  - `balances -f json` gives `[{"account","amount","currency","cost"}]` **[exp]**.
  - `balsheet -f csv` gives `section,account,amount,currency,cost` with a `Net Worth,TOTAL` row. It does *not* close Income into equity **[exp]**.
  - `journal -f csv` gives `date,flag,payee,narration,account,amount,currency` **[exp]**.
  - Note the different argument order: `report [OPTIONS] FILE SUBCOMMAND`.
- `doctor`: `lex`, `parse`, `context`, `linked`, `missing-open`, `list-options`, `print-options`, `stats`, `display-context`, `roundtrip`, `region` (transactions in a line range, with balances), `directories`, `generate-synthetic`.
- `lint transfers` and `lint closed-nonempty` are advisory. `explain`, `add`, `extract` (CSV/OFX importer), `price`, `config` and `compat install` (bean-* wrappers) are not needed for the workbench.
- There is an LSP (`rledger-lsp`) and a VS Code extension **[docs]**, which help with hand inspection.

## 8. Driving it from Python

- **No Python bindings.** There is no PyPI package **[exp: pypi 404 for rustledger, rledger, rustledger-py, pyrustledger]**. The documented options are subprocess (CLI + JSON), Rust crates, `@rustledger/wasm` (npm), and the WASI Preview 2 component (`rustledger-ffi-component-v0.24.0.wasm` is a release asset; you would call it via wasmtime-py, which is untested and heavier than it is worth). The old JSON-RPC WASI FFI was removed **[docs: guides/integration.md; release assets]**.
- **Subprocess pattern:**

```python
r = subprocess.run(["rledger", "check", "-C", "-f", "json", root], capture_output=True, text=True)
report = json.loads(r.stdout)          # also valid when exit == 1
if r.returncode == 2: raise RuntimeError(r.stderr)   # usage/IO
ok = r.returncode == 0                 # warnings-only still 0; inspect report["warning_count"]

q = subprocess.run(["rledger", "query", "--no-cache", "-q", "-f", "json", root, bql], capture_output=True, text=True)
res = json.loads(q.stdout); rows = [dict(zip(res["columns"], row)) for row in res["rows"]]
# numbers are strings -> Decimal(row["sum(number)"])
```

  Alternatively, `-f csv` loads straight into DuckDB: `read_csv` on the `-o` output file.
- **Pitfalls:**
  - Always pass options before FILE and QUERY.
  - `query` exits 0 over validation errors, so gate on `check` first. `query` refuses only on parse errors.
  - Stdin is not accepted, so write files first.
  - Disable the cache or gitignore it.
  - Name result columns with `AS` so the JSON column keys are friendly (`sum(number)` otherwise).
- **Python Beancount as an alternative library:** `beancount` 3.2.3 and `beanquery` 0.2.0 are on PyPI **[exp]**. rustledger claims 100% check, BQL and AST match on a 792-file corpus **[docs: compatibility.md]**, so files generated for rledger should also load in Python Beancount if in-process parsing is ever wanted. I did not test this.

## 9. Deviations from Beancount relevant here

- **Flagless transactions are accepted in 0.24.** `2025-01-02 "x"` loads clean as `*` **[exp]**. `main` has made it a parse error, as in Beancount **[docs: CHANGELOG.md]**. **Always emit `*` (or `!`).**
- `option "booking_method"` is being made case-sensitive on `main` **[docs: CHANGELOG]**. Write `FIFO`/`STRICT` in capitals, or omit the option. It is irrelevant for a cash-only USD GL.
- Multi-currency transactions without a price are rejected, where Beancount allows them **[docs: compatibility.md §1]**. Not relevant for USD.
- Custom Python plugins must be referenced by file path, and in practice they failed (see §5).
- `PRINT` filter and metadata behaviour: see §3.

## 10. Performance [exp]

Synthetic ledger: 50,000 two-posting transactions with links, tags and metadata. That is 300k lines (`/usr/bin/time -p`, M-series Mac):

| Command | Wall time |
|---|---|
| `check -C` (no cache) | 0.30 s |
| `check` cold (writes cache) | 0.33 s |
| `check` warm (from cache) | 0.08 s |
| `query ... GROUP BY account` | 0.16 s |
| `query -f json` all 100k postings with links + meta | 0.37 s |

The challenge's data volumes are far below this, so performance is a non-issue. Running `check` on every pipeline step is fine.
