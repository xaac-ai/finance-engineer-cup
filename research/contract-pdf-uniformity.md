# How uniform are the contract and policy PDFs?

Research for issue #2 (child of map #1). Facts only. Feeds the parse-vs-curate decision.

**Sources (all primary, in-repo):** `data/raw/contracts/*.pdf` (30 order forms `OF-2026-*`, 2 amendments `AM-OF-2026-*`), `data/raw/START_HERE.pdf`, `data/raw/billing_followups.pdf`, `data/raw/contract_register.csv`. Extracted with `pypdf` and `pdfplumber` (latest from PyPI via `uv run --with ...`, 2026-11-11).

## Answer in brief

- **One template, generated programmatically.** All 30 order forms are 1-page, US Letter (612x792), born-digital (standard Helvetica fonts, 0 images, no scanned pages, no producer metadata). A line diff against `OF-2026-118` shows the *only* varying lines are: doc/contract IDs, customer name/address/AP email, signatory name/title, and (for non-annual contracts) the term row, the two fee rows, the commitment line, and the first sentence of section 04. All other wording is byte-identical.
- **Text extraction is reliable with both libraries.** Every field is present in both outputs; no garbling, no OCR needed. The only non-ASCII character in any document is the right single quote U+2019 (62 occurrences, e.g. "customer’s"). `START_HERE` and `billing_followups` extract **identically** under pypdf and pdfplumber.
- **Differences between the libraries are layout-only** (see below). A regex over pypdf text recovered every key field from all 30 order forms with zero misses, and every `Contract CT-*` matched `contract_register.csv`.
- **Only 4 fee/allowance tiers exist across 30 order forms**, plus per-contract overage-rate variation within the $4,000/month tier. The two amendments share a common shell but have different section-03 rows and free-text semantics, so they are the only documents where curation clearly matters.

## Template structure (order forms)

Header: `RelayCloud EXECUTED ORDER FORM` / `OF-2026-NNN` / `Platform subscription and usage services` / `Contract CT-NNNNNN | Executed August 25, 2026`.

| Section | Content |
|---|---|
| 01 CUSTOMER AND BILLING DETAILS | Two columns: Customer/Bill-to (name, address, `Billing contact: Accounts Payable`, `ap@<slug>.example`) and Supplier (RelayCloud, Inc., 1800 Market St, Denver; `billing@relaycloud.example`). |
| 02 SUBSCRIPTION TERM AND PAYMENT | One 4-column row: SERVICE START, SERVICE END (inclusive), BILLING (`Annual in advance` or `Monthly in advance`), PAYMENT / CURRENCY (`Net 30 days / USD` everywhere). |
| 03 SERVICES AND FEES | Two product rows: `RelayCloud Platform` ("One annual platform subscription" — this label appears even on monthly-billed contracts) with billing basis + fee; `Workflow runs` with "N included runs per calendar month", `Monthly, in arrears`, `$X / excess run`. Footer line `ANNUAL PLATFORM COMMITMENT $N + usage overages`. |
| 04 BILLING AND COMMERCIAL TERMS | Prose. Sentence 1 varies by billing anchor (see below). Rest is identical everywhere: usage invoiced on first day of following month; aggregate across verified product accounts before one calendar-month allowance; no tiers/rollover; first partial month allowance prorated by active calendar days, rounded once to whole run half up; fees are negotiated net, no extra discounts; "An executed amendment prevails only for the terms it expressly changes. All other terms of this Order Form remain in effect." |
| 05 ACCEPTANCE | `/s/` typed signatures, name \| title, `Date signed: August 25, 2026` both sides. Supplier signatory is always Morgan Lee, Sales Director. |
| Footer | `Fictional commercial document for Finance Engineer Cup. No legal effect. OF-2026-NNN \| 1 / 1` |

Section 04 sentence 1, three variants:
- Annual: "Platform fees are invoiced in full on September 1, 2026. The initial service term runs through August 31, 2027, inclusive, and ends at 00:00 America/Denver on September 1, 2027."
- Monthly, 1st anchor: "Platform fees are invoiced on the 1st of each month, beginning September 1, 2026. ..." (same term sentence)
- Monthly, 15th anchor (OF-419, OF-430): "Platform fees are invoiced on the 15th of each month, beginning September 15, 2026. The initial service term runs through September 14, 2027, inclusive, and ends at 00:00 America/Denver on September 15, 2027."

**Fields that do not appear in any order form:** renewal / auto-renewal, termination, price escalators, discounts, tiers, minimums beyond the platform fee, tax. (Grep for `renew|terminat` across all extracted text: no hits in contracts.) Every document is signed 2026-08-25; payment terms are Net 30 / USD in all 30.

## Per-document key fields (order forms)

Extracted by regex from pypdf text; register columns from `contract_register.csv`. Service end is the inclusive date shown on the PDF; the register's `effective_to` is the end-exclusive date (matches the "ends at 00:00 ... on" sentence).

| doc | contract | customer | start | end (incl.) | billing | platform fee | annual commit | incl. runs/mo | overage $/run | terms | register eff_from | register eff_to | CT match |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OF-2026-118 | CT-186097 | Alder Fieldworks | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-122 | CT-866587 | Brookstone Data | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-133 | CT-477694 | Copper Finch Systems | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-144 | CT-731059 | Driftwood Research | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-155 | CT-436791 | Evergreen Dispatch | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-157 | CT-639373 | Cedar Harbor Labs | September 1, 2026 | August 31, 2027 | Monthly | $4,000.00 / month | $48,000.00 | 30,000 | 0.40 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-164 | CT-335780 | Meridian Process Systems | September 1, 2026 | August 31, 2027 | Monthly | $4,000.00 / month | $48,000.00 | 30,000 | 0.12 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-166 | CT-286595 | Falcon Ridge Software | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-177 | CT-963044 | Granite Orchard | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-188 | CT-142182 | Highwater Studio | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-199 | CT-620310 | Indigo Trail Networks | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-210 | CT-879513 | Juniper Bay Analytics | September 1, 2026 | August 31, 2027 | Annual | $24,000.00 / year | $24,000.00 | 10,000 | 0.08 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-221 | CT-654552 | Kestrel Bridge | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-232 | CT-232251 | Larch Point Services | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-243 | CT-507826 | Maple Lantern | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-254 | CT-553102 | Northbank Design | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-265 | CT-300468 | Oak Harbor Digital | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-276 | CT-561562 | Pine Summit Logistics | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-287 | CT-730965 | Quartz Meadow | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-298 | CT-856042 | Riverbend Operations | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-309 | CT-676664 | Silver Current | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-320 | CT-941670 | Timberline Insights | September 1, 2026 | August 31, 2027 | Monthly | $3,000.00 / month | $36,000.00 | 20,000 | 0.06 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-331 | CT-437384 | Juniper Signal Works | September 1, 2026 | August 31, 2027 | Monthly | $4,000.00 / month | $48,000.00 | 30,000 | 0.16 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-342 | CT-240793 | Westhaven Metrics | September 1, 2026 | August 31, 2027 | Monthly | $4,000.00 / month | $48,000.00 | 30,000 | 0.05 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-375 | CT-188999 | Yarrow Ridge | September 1, 2026 | August 31, 2027 | Monthly | $4,000.00 / month | $48,000.00 | 30,000 | 0.12 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-386 | CT-148565 | Zephyr Grove | September 1, 2026 | August 31, 2027 | Monthly | $4,000.00 / month | $48,000.00 | 30,000 | 0.05 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-397 | CT-314334 | Aspen Vale | September 1, 2026 | August 31, 2027 | Monthly | $4,000.00 / month | $48,000.00 | 30,000 | 0.05 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-408 | CT-810234 | Beacon Marsh | September 1, 2026 | August 31, 2027 | Monthly | $4,000.00 / month | $48,000.00 | 30,000 | 0.10 | Net 30 days | 2026-09-01 | 2027-09-01 | ok |
| OF-2026-419 | CT-260381 | Crescent Shore | September 15, 2026 | September 14, 2027 | Monthly | $5,000.00 / month | $60,000.00 | 40,000 | 0.04 | Net 30 days | 2026-09-15 | 2027-09-15 | ok |
| OF-2026-430 | CT-839653 | Willow Passage | September 15, 2026 | September 14, 2027 | Monthly | $5,000.00 / month | $60,000.00 | 40,000 | 0.04 | Net 30 days | 2026-09-15 | 2027-09-15 | ok |

Distinct tiers (fee / runs / billing): **$24,000/yr annual, 10,000 runs, $0.08** (10 contracts: 118, 122, 133, 144, 155, 166, 177, 188, 199, 210); **$3,000/mo, 20,000 runs, $0.06** (10: 221–320); **$4,000/mo, 30,000 runs** (8: 157, 164, 331, 342, 375, 386, 397, 408) with overage varying $0.05 / $0.10 / $0.12 / $0.16 / **$0.40** (OF-157 — highest rate in the set, 2.5x the next-highest); **$5,000/mo, 40,000 runs, $0.04, 15th-of-month anchor** (2: 419, 430). Annual commitment always equals 12 x monthly fee.

## Amendments

Same shell as order forms (header `EXECUTED AMENDMENT`, subtitle `Subscription amendment`, signed/executed October 14, 2026; same 01 and 05 sections), but sections 02–04 differ:

- **02 AMENDMENT SCOPE**: ORIGINAL ORDER / EFFECTIVE DATE / TERM END (INCLUSIVE) — both `OF-2026-157`/`OF-2026-164`, October 16, 2026, August 31, 2027. Register: `supersedes_document_id` = original OF, `effective_from` 2026-10-16, `effective_to` 2027-09-01, `approval_reference` MSG-2026-104, **`billing_loaded_at` blank for both** (register header documents blank as "not recorded as loaded").
- **03 CHANGES TO COMMERCIAL TERMS**: a 3-column TERM / PREVIOUS / AMENDED table — the **rows differ per amendment**:

| | AM-OF-2026-157 (Cedar Harbor Labs) | AM-OF-2026-164 (Meridian Process Systems) |
|---|---|---|
| Change type | Allowance increase | Platform price upgrade |
| Row 1 | Included workflow runs: 30,000 → 45,000 / calendar month | Annual platform rate: $48,000.00/yr → $60,000.00/yr |
| Row 2 | Overage rate: $0.40 → $0.40 (unchanged) | Monthly platform invoice: $4,000.00/mo → $5,000.00 from Nov 1 |
| Row 3 | Platform fee: $48,000.00/yr (unchanged) | October upgrade catch-up: Not previously billed → $526.03 additional |
| 04 prose | Effective Oct 16 00:00 America/Denver. October allowance = prior allowance weighted Oct 1–15 + amended allowance Oct 16–31 by calendar days, rounded once to whole run half up. No retrospective change. Monthly platform invoice remains USD 4,000.00. | Effective Oct 16 00:00 America/Denver for remainder of term; no prior service repriced; usage terms unchanged. Catch-up USD 526.03 = 12,000 x 16 / 365, half up, "may be invoiced separately". USD 5,000.00 monthly invoices Nov 2026–Aug 2027. Incremental consideration for 320 remaining service days = USD 10,520.55; final platform invoice includes a USD 5.48 credit to reconcile billing convention to that amount. Original base consideration unchanged. |

Amendment semantics (both the OF section 04 and START_HERE "SOURCE PRECEDENCE"): an amendment changes only named terms; unchanged terms persist; `supersedes_document_id` means partial precedence, not cancellation. Note that the amendments embed computed amounts and calendar-weighting rules in prose that is not in any table.

## Extraction comparison: pypdf vs pdfplumber

| Aspect | pypdf `extract_text()` | pdfplumber `extract_text()` |
|---|---|---|
| Completeness | All tokens present | All tokens present |
| Two-column blocks (01, 05) | Emits left column's lines, then right column's (address lines de-interleaved) | Merges both columns onto one line per row ("120 Oak Street, Suite 100 1800 Market Street, Suite 400") |
| Fee table (03) | `RelayCloud Platform` / subtitle / `Annual, in advance $24,000.00 / year` on separate lines | Name, basis and fee on one line, subtitle on next |
| Whitespace | Preserves triple spaces around `|` | Collapses to single spaces |
| Char counts | ~10 chars more per contract (the spaces) | — |
| START_HERE / followups | Identical to pdfplumber | Identical to pypdf |

Tables: the PDFs have no real ruled tables. pdfplumber default `extract_tables()` finds one empty 2x2 grid per contract (decorative rules: 5 rects, 12 lines per page). The `text` strategy splits words mid-token ("Augu" | "st 31,") — unusable. `extract_text(layout=True)` gives a clean fixed-width rendering with columns aligned (SERVICE START / SERVICE END / BILLING / PAYMENT aligned under headers), which is the most faithful for column-based parsing. Fonts: Helvetica / Helvetica-Bold at 7–15pt, standard Type1 — no custom encodings, so no ligature or glyph-mapping garbling.

Implication (fact, not recommendation): because the order forms are machine-generated from one template with label-anchored values, simple regex over either library's plain text is sufficient and was verified 30/30; the two amendments are structurally different in their section 03 rows and carry derived amounts in prose, so a generic parser would not capture them without per-document handling.

## START_HERE.pdf (6 pages, prose only, no tables)

Title "Finance Engineer Cup Challenge Instructions"; footer "RelayCloud | Fictional challenge material | Page N of 6". Text is a sequence of ALL-CAPS-labelled paragraphs, no tables or figures: intro + REQUIRED SCOPE (October 1–31, 2026; cutoff 2026-11-11T18:00:00-07:00), COMPANY RULES, PAYMENT AND DATE DISPLAY, SOURCE PRECEDENCE, USAGE (allowance proration/rounding formula), UNVERIFIED USAGE, BILLING, ACCOUNTING (account numbers 1100/1150/1160/2200/4000/4010 and journal patterns), CREDITS, APPROVAL AND DATES, TIMING, FORMATS, MONEY, EXPORT PROVENANCE, RECONCILIATION POPULATION (30 customers, 32 product accounts, 30 OFs, 2 amendments, 1,924 usage records over 61 dates), CONTROLS, EXTRACT COMPLETENESS (expected row counts per CSV), PRODUCTS (`prod_platform`, `prod_workflow_run`), and FILE DICTIONARY (one paragraph per CSV with its column list, pages 4–6).

## billing_followups.pdf (2 pages, prose only, no tables)

Title "RelayCloud Sales and Billing Messages", snapshot 2026-11-11T18:00:00-07:00. Ten messages, each with a one-line header `MSG-2026-NNN | <date time> America/Denver | <from> -> <to> | <subject>` followed by a short paragraph: 104 (amendments signed, effective Oct 16), 108 (Zephyr Grove USD 100 concession request), 109 (Controller approves Zephyr USD 100), 116 (Alder USD 50 credit note `cn_82a7ddd6e88e69` voided), 119 (review request; amendment may not have reached billing), 125 (extract status), 130 (Willow Passage onboarding Sept 15, subscription chargeable), 131 (unverified workspace `pa_676b6b455e0887`), 132 (Willow Passage USD 250 request, unapproved), 133 (review authority / dating rules). Messages are not in strict chronological order (MSG-130 is dated Sept 15). Header lines are regex-parseable (`MSG-\d{4}-\d{3} \|`), though some wrap onto a second line.
