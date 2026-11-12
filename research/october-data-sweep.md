# What does the October data actually contain?

Research for issue #11 (child of map #10). **This file states facts only.** It does not classify anything as Error, Valid Explanation or Needs Info. Each item names the Billing Message (MSG) or START_HERE section that may bear on it, without drawing a conclusion.

**Sources (all primary, in-repo, on `main` @ `b93ede8`):**
- `data/raw/2026-10/*.csv`;
- `START_HERE.pdf`, `billing_followups.pdf` and `contracts/*.pdf`, read as the text that `make run` extracts to `out/2026-10/extracted/*.txt`;
- `out/2026-10/contract_terms.csv`;
- the `raw_*` tables in `out/2026-10/workbench.duckdb`.

**Citation format:** `file:N` is the physical CSV line, with the header as line 1. All files are in `data/raw/2026-10/` unless stated. Stripe amounts are in integer cents in the source and shown here as USD. Usage is deduplicated on `record_id` (the first occurrence is kept). Rounding is half up, as START_HERE "USAGE" requires.

## Top anomalies at a glance

| # | Customer (NS id) | Fact | Amount |
|---|---|---|---|
| 1 | Cedar Harbor Labs (639373) | The Nov 1 usage invoice applies the pre-Amendment 30,000 allowance. The Amendment-weighted allowance is 37,742. | billed $11,388.00 vs naive $8,291.20 (**+$3,096.80**) |
| 2 | Juniper Signal Works (437384) | The Nov 1 usage line is priced at $0.05 per run. The Order Form says $0.16, and the September line used $0.16 on the **same `price_id`**. | billed $1,425.10 vs naive $4,560.32 (**−$3,135.22**) |
| 3 | Yarrow Ridge (188999) | There is no Nov 1 usage invoice and no October usage accrual, yet October usage is 25,619 runs over the allowance. | naive **$3,074.28** missing |
| 4 | Meridian Process Systems (335780) | The Amendment's $526.03 October catch-up was never invoiced. The Nov 1 platform invoice is $4,000, not $5,000. Revenue plan and October GL recognition are base-only. | **$526.03** Oct; Nov invoice −$1,000 (follow-up) |
| 5 | Beacon Marsh (810234) | The Oct 31 usage record (1,000 runs) was ingested Nov 3, after the Nov 1 invoice. The accrual includes it; the invoice does not. | billed $1,344.30 vs $1,444.30 (**−$100.00**); $100 residual in 1150 |
| 6 | Unverified workspace `pa_676b6b455e0887` | 49,762 October runs with no owner. Willow Passage is the only customer with no mapped product account. | conditional only (see §2) |
| 7 | Westhaven Metrics (240793) | One `record_id` is exported twice (1,730 runs). Billing and accrual already use the deduplicated count. | a raw sum would overstate by $86.50 |
| 8 | Zephyr Grove (148565) | The $100 concession was credited (issued credit note, GL posted), and the October accrual is already net of it. | $100.00 |
| 9 | Alder Fieldworks (186097) | A $50 credit note is void and has no GL entry. | $50.00 (no effect) |

Every Stripe invoice and issued credit note has exactly one matching GL entry (§5). The October revenue plan ties to GL 4000 row for row (§6).

---

## 1. Usage (`product_usage.csv`, `usage_batch_controls.csv`)

**Row count vs unique records.**
- The file has 1,925 data rows but 1,924 distinct `record_id`s over 61 service dates (2026-09-01 to 2026-10-31). This matches START_HERE "RECONCILIATION POPULATION": "1,924 unique source daily usage records across 61 dates. Physical export row count can differ and must be reconciled."
- The only repeat is `ur_7352010ec2e04c` (Westhaven Metrics, `pa_0f28aff4fcff87`, 2026-10-14, 1,730 units). It appears at `product_usage.csv:1448` and `:1449`, and the two rows are identical in every field, including `ingested_at` 2026-10-15T02:00 and `batch-2026-10-14`. START_HERE file dictionary: "Exact repeated source IDs are not new activity."

**Status and replacement.**
- All 1,925 rows have `record_status = active`, `sku = WORKFLOW_RUN` and a blank `replaces_record_id`.
- START_HERE "USAGE": "there are no superseded versions in this release."

**Zero-unit days.**
- There are 16 zero-unit records, all on the unverified workspace `pa_676b6b455e0887`, for 2026-09-15 to 2026-09-30 (`product_usage.csv:1880`–`:1895`).
- No other product account has a zero day.
- START_HERE "USAGE": "Explicit zero-use days remain records."

**Tie to batch controls.**
- After deduplication, all 61 dates tie on both `distinct_active_record_count` and `active_units_total`. Totals are 1,924 records and 3,138,816 units, both sides.
- Before deduplication, only 2026-10-14 breaks: the raw export has 33 rows and 59,642 units, against a control of 32 records and 57,912 units (`usage_batch_controls.csv:45`). The difference of 1 row and 1,730 units is exactly the Westhaven duplicate.
- Batch sizes are 30 records a day for Sep 1–14 and 32 a day for Sep 15–Oct 31, as START_HERE "CONTROLS" states.

**Late ingestion.**
- Every record is ingested the day after its service date at 02:00 local, with one exception.
- `ur_19d11e47355517` (Beacon Marsh, `pa_fbb2b8766f4fac`, 2026-10-31, **1,000 units**, a round number) was ingested **2026-11-03T08:30-07:00** (`product_usage.csv:1832`). That is after the Nov 1 09:00 usage invoice was created. See §3, row Beacon Marsh.
- Bears on: START_HERE "TIMING" (ingestion timestamp vs invoice issue date) and "BILLING".

**October totals (deduplicated):**
- 1,600,946 runs in all;
- 1,551,184 runs on mapped accounts;
- 49,762 runs on the unverified workspace;
- 1,602,676 runs on the raw, not-deduplicated rows.

## 2. Mapping (`product_account_mapping.csv`, `salesforce_accounts.csv`)

- **32 product accounts cover 29 of the 30 customers, and one account is unassigned.**
  - Silver Current has two (`/ East` and `/ West`, `product_account_mapping.csv:20`–`:21`).
  - Timberline Insights has two (`:22`–`:23`).
  - The unverified workspace has a blank `salesforce_account_id` (`:33`).
- **Willow Passage (`00174337ea6baeeAAA`, NS 839653) has no product account at all.** Its Salesforce record is `salesforce_accounts.csv:31`.
- **Effective dates.** Every mapping has a blank `effective_to`. All start 2026-09-01, except Crescent Shore `pa_c38895c66dfafd` (`:32`) and the unverified workspace (`:33`), which both start **2026-09-15**. Their `mapping_updated_at` values are 2026-09-15T08:00. Willow Passage's service also starts 2026-09-15 (OF-2026-430: "SERVICE START September 15, 2026").
- **Unverified workspace activity.**
  - September 15–30: 16 zero records.
  - October: 31 records, the first non-zero being 2026-10-01. The October total is **49,762 runs**: 23,022 on Oct 1–15 and 26,740 on Oct 16–31 (`product_usage.csv:1896`–`:1926`).
  - MSG-2026-130 (Willow onboarding): "No metered production runs are expected during September onboarding."
  - MSG-2026-131: "Do not identify it by elimination from the customer list. … Account names and one-to-one assumptions are not evidence."
  - MSG-2026-132: Willow's $250 request "does not establish ownership of any unverified workspace."
  - START_HERE "UNVERIFIED USAGE" requires documenting the conditional exposure. The arithmetic below is shown only as an example: under Willow's terms (40,000 allowance, $0.04), it would be (49,762 − 40,000) × $0.04 = **$390.48**.
- **Labels.** Two customers share the stem "Juniper": Juniper Bay Analytics (`:11`) and Juniper Signal Works (`:24`). START_HERE "PRODUCTS": "Product-account labels are display text, not a substitute for verified mappings."

## 3. Per-customer October service

**Terms.**
- The terms are the Order Form values in `contract_terms.csv`, cross-checked against the extracted PDF text, for example `OF-2026-331.txt:26` "$0.16 / excess run".
- Annual customers bill $24,000 on Sep 1 for the period 2026-09-01 to 2027-09-01.
- Monthly customers bill on the 1st. The exceptions are Crescent Shore and Willow Passage, which bill on the 15th.

**Allowance.**
- The October allowance is the full monthly figure for everyone except Cedar Harbor, where AM-OF-2026-157 sets it as `30,000×15/31 + 45,000×16/31 = 1,170,000/31 = 37,741.94 → 37,742`.
- Crescent Shore's first partial month was September. Its September allowance is 40,000 × 16/30 = 21,333.33, which rounds to 21,333. The September invoice charged 3,200 = 24,533 − 21,333, which agrees.

**Columns in the table.**
- **Naive** = max(0, units − allowance) × rate.
- **Billed** = the Nov 1 `prod_workflow_run` line with period 2026-10-01 to 2026-11-01. The `stripe_invoice_lines.csv` line number is given.
- **Accrual** = the October GL 1150 debit with memo "October usage accrual".
- **Platform covering Oct** lists the invoice(s) whose period overlaps October.

| NS | Customer | Terms (allow / rate; platform) | Oct units | Allow. | Over units | Naive $ | Billed (line) | Δ billed − naive | Oct accrual | Platform covering Oct |
|---|---|---|---|---|---|---|---|---|---|---|
| 186097 | Alder Fieldworks | 10k / .08; $24k annual | 29,697 | 10,000 | 19,697 | 1,575.76 | 1,575.76 (:4) | 0 | 1,575.76 | Sep 1 $24,000 (:2) |
| 866587 | Brookstone Data | 10k / .08; annual | 35,513 | 10,000 | 25,513 | 2,041.04 | 2,041.04 (:7) | 0 | 2,041.04 | Sep 1 $24,000 (:5) |
| 477694 | Copper Finch | 10k / .08; annual | 25,344 | 10,000 | 15,344 | 1,227.52 | 1,227.52 (:10) | 0 | 1,227.52 | Sep 1 $24,000 (:8) |
| 731059 | Driftwood Research | 10k / .08; annual | 26,767 | 10,000 | 16,767 | 1,341.36 | 1,341.36 (:13) | 0 | 1,341.36 | Sep 1 $24,000 (:11) |
| 436791 | Evergreen Dispatch | 10k / .08; annual | 42,808 | 10,000 | 32,808 | 2,624.64 | 2,624.64 (:16) | 0 | 2,624.64 | Sep 1 $24,000 (:14) |
| 286595 | Falcon Ridge | 10k / .08; annual | 83,856 | 10,000 | 73,856 | 5,908.48 | 5,908.48 (:19) | 0 | 5,908.48 | Sep 1 $24,000 (:17) |
| 963044 | Granite Orchard | 10k / .08; annual | 56,401 | 10,000 | 46,401 | 3,712.08 | 3,712.08 (:22) | 0 | 3,712.08 | Sep 1 $24,000 (:20) |
| 142182 | Highwater Studio | 10k / .08; annual | 83,216 | 10,000 | 73,216 | 5,857.28 | 5,857.28 (:25) | 0 | 5,857.28 | Sep 1 $24,000 (:23) |
| 620310 | Indigo Trail | 10k / .08; annual | 46,454 | 10,000 | 36,454 | 2,916.32 | 2,916.32 (:28) | 0 | 2,916.32 | Sep 1 $24,000 (:26) |
| 879513 | Juniper Bay Analytics | 10k / .08; annual | 37,033 | 10,000 | 27,033 | 2,162.64 | 2,162.64 (:31) | 0 | 2,162.64 | Sep 1 $24,000 (:29) |
| 654552 | Kestrel Bridge | 20k / .06; $3k/mo | 65,837 | 20,000 | 45,837 | 2,750.22 | 2,750.22 (:36) | 0 | 2,750.22 | Oct 1 $3,000 (:33) |
| 232251 | Larch Point | 20k / .06; $3k/mo | 37,816 | 20,000 | 17,816 | 1,068.96 | 1,068.96 (:41) | 0 | 1,068.96 | Oct 1 $3,000 (:38) |
| 507826 | Maple Lantern | 20k / .06; $3k/mo | 102,799 | 20,000 | 82,799 | 4,967.94 | 4,967.94 (:46) | 0 | 4,967.94 | Oct 1 $3,000 (:43) |
| 553102 | Northbank Design | 20k / .06; $3k/mo | 46,740 | 20,000 | 26,740 | 1,604.40 | 1,604.40 (:51) | 0 | 1,604.40 | Oct 1 $3,000 (:48) |
| 300468 | Oak Harbor Digital | 20k / .06; $3k/mo | 53,077 | 20,000 | 33,077 | 1,984.62 | 1,984.62 (:56) | 0 | 1,984.62 | Oct 1 $3,000 (:53) |
| 561562 | Pine Summit | 20k / .06; $3k/mo | 69,804 | 20,000 | 49,804 | 2,988.24 | 2,988.24 (:61) | 0 | 2,988.24 | Oct 1 $3,000 (:58) |
| 730965 | Quartz Meadow | 20k / .06; $3k/mo | 84,819 | 20,000 | 64,819 | 3,889.14 | 3,889.14 (:66) | 0 | 3,889.14 | Oct 1 $3,000 (:63) |
| 856042 | Riverbend Operations | 20k / .06; $3k/mo | 25,761 | 20,000 | 5,761 | 345.66 | 345.66 (:71) | 0 | 345.66 | Oct 1 $3,000 (:68) |
| 676664 | Silver Current (2 PAs: 38,404 + 33,862) | 20k / .06; $3k/mo | 72,266 | 20,000 | 52,266 | 3,135.96 | 3,135.96 (:76) | 0 | 3,135.96 | Oct 1 $3,000 (:73) |
| 941670 | Timberline (2 PAs: 44,145 + 35,140) | 20k / .06; $3k/mo | 79,285 | 20,000 | 59,285 | 3,557.10 | 3,557.10 (:81) | 0 | 3,557.10 | Oct 1 $3,000 (:78) |
| 437384 | **Juniper Signal Works** | 30k / **.16**; $4k/mo | 58,502 | 30,000 | 28,502 | **4,560.32** | **1,425.10 @ $0.05** (:86) | **−3,135.22** | **1,425.10** | Oct 1 $4,000 (:83) |
| 240793 | Westhaven Metrics | 30k / .05; $4k/mo | 61,866 (dedup.) | 30,000 | 31,866 | 1,593.30 | 1,593.30 (:91) | 0 | 1,593.30 | Oct 1 $4,000 (:88) |
| 639373 | **Cedar Harbor Labs** | 30k → 45k from Oct 16 / .40; $4k/mo | 58,470 | **37,742** | 20,728 | **8,291.20** | **11,388.00** (28,470 runs) (:96) | **+3,096.80** | **11,388.00** | Oct 1 $4,000 (:93) |
| 335780 | **Meridian Process** | 30k / .12; $48k → $60k/yr from Oct 16 | 49,396 | 30,000 | 19,396 | 2,327.52 | 2,327.52 (:101) | 0 | 2,327.52 | Oct 1 $4,000 (:98); **no $526.03 catch-up** |
| 188999 | **Yarrow Ridge** | 30k / .12; $4k/mo | 55,619 | 30,000 | 25,619 | **3,074.28** | **none** | **−3,074.28** | **none** | Oct 1 $4,000 (:103) |
| 148565 | Zephyr Grove | 30k / .05; $4k/mo | 49,052 | 30,000 | 19,052 | 952.60 | 952.60 (:110); credit −100.00 | 0 (before credit) | **852.60** | Oct 1 $4,000 (:107) |
| 314334 | Aspen Vale | 30k / .05; $4k/mo | 25,000 | 30,000 | 0 | 0.00 | none | 0 | none | Oct 1 $4,000 (:112) |
| 810234 | **Beacon Marsh** | 30k / .10; $4k/mo | 44,443 | 30,000 | 14,443 | **1,444.30** | **1,344.30** (13,443 runs) (:119) | **−100.00** | 1,444.30 | Oct 1 $4,000 (:116) |
| 260381 | Crescent Shore | 40k / .04; $5k/mo on the 15th | 43,543 | 40,000 | 3,543 | 141.72 | 141.72 (:123) | 0 | 141.72 | Sep 15 $5,000 (Sep 15–Oct 15, :120) and Oct 15 $5,000 (Oct 15–Nov 15, :121) |
| 839653 | **Willow Passage** | 40k / .04; $5k/mo on the 15th | **0 (no mapped PA)** | 40,000 | 0 | 0.00 | none | 0 | none | Sep 15 $5,000 (:124) and Oct 15 $5,000 (:125) |

**Notes on the flagged rows.**

- **Cedar Harbor.**
  - Billed 28,470 = 58,470 − 30,000, which is the pre-Amendment allowance. Rate $0.40 (`stripe_invoice_lines.csv:96`).
  - `contract_register.csv:25` (AM-OF-2026-157) has a blank `billing_loaded_at` and `approval_reference` MSG-2026-104.
  - AM-OF-2026-157: "For October, weight the prior allowance for October 1-15 and the amended allowance for October 16-31 by calendar days. Round the resulting allowance once to a whole run, half up."
  - Bears on: MSG-104 ("please use the executed documents"), MSG-119 ("an amendment that may not have reached billing").
- **Juniper Signal Works.**
  - The Oct 1 invoice (September usage) is 27,000 × $0.16 = $4,320.00 (`stripe_invoice_lines.csv:85`).
  - The Nov 1 invoice (October usage) is 28,502 × $0.05 = $1,425.10 (`:86`).
  - Both lines carry `price_9163e0b6ff40e5`. OF-2026-331 says "$0.16 / excess run".
  - No Amendment or message mentions a price change. START_HERE: "Prices are negotiated net prices, with no additional invoice discounts." Possibly MSG-119.
- **Yarrow Ridge.**
  - The Stripe invoices for `cus_46ee9e5b5a2782` are at `stripe_invoices.csv:102`–`:105`. There is no `RC-261101-188999-U`.
  - The September usage invoice exists (`:105`, $3,161.64 for 26,347 runs at $0.12), and October usage is 55,619 runs on `pa_64b090ce98d42f` (`product_usage.csv:1589`–`:1649`).
  - START_HERE "BILLING": "An absent usage invoice can be valid when no overage exists". Here an overage exists.
- **Beacon Marsh.**
  - The 1,000-unit difference equals the late-ingested record `product_usage.csv:1832`.
  - Bears on: START_HERE "TIMING" and "BILLING".
- **Aspen Vale.** October is exactly 25,000 runs, below the 30,000 allowance, so no usage invoice is expected. START_HERE "BILLING": "An absent usage invoice can be valid when no overage exists."
- **Platform amounts.**
  - All Oct-1 platform invoices match the Order Form monthly amounts ($3,000, $4,000 or $5,000). There are no prorations (`proration=false` on all 124 lines) and no discounts (`discount_amount = 0` everywhere).
  - Annual customers are not billed again in October, per START_HERE: "An annual prepaid platform fee is not billed again in October."
  - Day-based allocation to October:
    - annual: $24,000 × 31/365 = $2,038.36;
    - monthly-on-1st: the full $3,000 or $4,000;
    - Crescent Shore and Willow Passage: $5,000 × 14/30 + $5,000 × 17/31 = $2,333.33 + $2,741.94 = $5,075.27, against recognition of $60,000 × 31/365 = $5,095.89.

## 4. Invoices: completeness and correctness

- **Counts tie.** There are 124 invoices with 124 lines, one line each (`stripe_invoices.csv` and `stripe_invoice_lines.csv` both have 125 lines including the header), as START_HERE "EXTRACT COMPLETENESS" states.
  - 10 annual customers × 3 = 30.
  - 18 monthly-on-1st customers × 5 (Sep P, Oct P, Oct U, Nov P, Nov U) = 90, less Yarrow Nov U and Aspen Nov U = 88.
  - Crescent Shore: 4.
  - Willow Passage: 2.
- **Integrity checks pass.**
  - No line is orphaned. Each line's amount equals quantity × `unit_amount_decimal`, and each subtotal equals its lines. Total = subtotal for every invoice. Status is `paid` for September invoices and `open` for later ones. `created` = `finalized_at`, and `source_system = stripe` throughout.
  - There are no duplicate invoices for any customer, product or period.
- **Missing.**
  - Yarrow Ridge October usage ($3,074.28 naive).
  - Meridian $526.03 October catch-up. AM-OF-2026-164: "October upgrade catch-up: USD 526.03, using USD 12,000 x 16 / 365, rounded half up. This additional October-service charge may be invoiced separately." Check: 12,000 × 16/365 = 526.027, which rounds to 526.03.
  - Willow Passage: no usage invoice for either month, and no mapped usage (§2).
- **Wrong amounts.** Cedar Harbor and Juniper Signal Works October usage (§3).
- **Short billing.** Beacon Marsh October usage is short by 1,000 runs (§3).
- **November follow-up (later service).**
  - Meridian's Nov 1 platform invoice `RC-261101-335780-P` is $4,000 for 2026-11-01 to 2026-12-01 (`stripe_invoice_lines.csv:99`). The Amendment says: "Monthly platform invoices are USD 5,000.00 from November 2026 through August 2027."
  - `contract_register.csv:27` (AM-OF-2026-164) has a blank `billing_loaded_at`.
  - Cedar Harbor's Nov 1 platform invoice is $4,000 (`:94`), which agrees with the Amendment: "The monthly platform invoice remains USD 4,000.00."

## 5. Credit notes, and Stripe ↔ NetSuite GL

| Note | Status | Invoice / line | Service period (source) | Amount | GL |
|---|---|---|---|---|---|
| `cn_82a7ddd6e88e69` CN-186097-20261102 (`stripe_credit_notes.csv:2`, line `stripe_credit_note_lines.csv:2`) | **void**: created 2026-11-02, `voided_at` 2026-11-03, reason `order_change` | `RC-261101-186097-U`, `il_3e61bdcb3f3274` (`stripe_invoice_lines.csv:4`) | 2026-10-01 to 2026-11-01 ("original invoice line") | $50.00 | none |
| `cn_85bf669490fd97` CN-148565-20261104 (`:3`, line `:3`) | **issued** 2026-11-04 | `RC-261101-148565-U`, `il_df52e1ad4a7155` (`:110`) | 2026-10-01 to 2026-11-01 | $100.00 | `netsuite_gl_detail.csv:296`–`:297`: Credit Memo CM-148565, Nov 2026, **Dr 1150 100.00 / Cr 1100 100.00** |

- **Alder.** MSG-2026-116: "created in error and voided before the NetSuite import. … No credit or reversal has been posted to NetSuite." START_HERE "CREDITS": "void notes have no current credit effect."
- **Zephyr.**
  - MSG-2026-108 is the request. MSG-2026-109 (Controller, Oct 29) reads: "reduce Zephyr Grove October usage consideration by USD 100 … ensure the October accrual is already net of this approved concession. Do not apply a second concession."
  - The October accrual is $852.60 = $952.60 − $100.00 (`netsuite_gl_detail.csv:300`–`:301`). The Nov 1 invoice released the full $952.60 from 1150 (`:295`), and the credit memo debits 1150 back by $100. Zephyr's net 1150 movement across October and November is therefore 852.60 − 952.60 + 100.00 = 0.
  - START_HERE "CREDITS": "A November credit can reduce AR and reverse the corresponding release of unbilled usage without reducing revenue a second time."
- **Willow.** MSG-2026-132 is the $250 request: "no Controller approval". No credit note exists.

**GL tie-out.**
- Every Stripe invoice issued on or after Oct 1 (Oct 1, Oct 15 and Nov 1; 94 in all) has exactly one NetSuite Invoice journal, joined on `External Source ID` and matching in customer, document number and amount:
  - 1100 debit = invoice total;
  - platform lines credit 2200;
  - usage lines credit 1150 ("Release prior service-month usage accrual").
- Every GL `Date` equals the Stripe `created` date.
- The only issued credit note has its GL entry. The void note has none.
- No document posts twice, and no GL `External Source ID` lacks a matching Stripe document. Every journal balances.
- September invoices are outside the GL extract. Their effects sit in the opening balances, per MSG-2026-125: "Historical September journals are outside this extract".
- Totals by period:
  - Oct-period invoices: 1100 Dr 154,170.97 = 2200 Cr 72,000.00 + 1150 Cr 82,170.97.
  - Nov-period invoices: 1100 Dr 136,831.90 = 2200 Cr 62,000.00 + 1150 Cr 74,831.90.

## 6. Revenue plan vs GL

- **Size.** `netsuite_revenue_plan_detail.csv` has 362 rows: 30 plans, one element per customer. Every plan has `Plan Updated At` 2026-09-01T08:00.
- **October rows tie to GL.** The 30 October rows (Planned = Recognized, $93,764.36 in total) each join a GL journal through `Journal Internal ID` and `Revenue Plan ID`, and the GL 4000 credit equals the recognized amount for every customer.
  - Annual: $2,038.36 = 24,000 × 31/365.
  - $3k/month: $3,057.53 = 36,000 × 31/365.
  - $4k/month: $4,076.71 = 48,000 × 31/365.
  - $5k/month: $5,095.89 = 60,000 × 31/365.
- **September rows** carry `SEP-REV-*` journal IDs that sit outside the GL period. START_HERE "CONTROLS": "September recognition journal IDs in plans are historical references outside the GL period."
- **Meridian.**
  - The plan `RP-26645e070609bc` (`:278`–`:289`) has only the base element from OF-2026-164.
  - October is $4,076.71 (`:279`), matching GL 4000 on JE-f9723c1c618a30.
  - There is no upgrade-increment element. November onward stays at base, for example Nov $3,945.21 (`:280`), and the plan was not updated after the 2026-10-14 signature.
  - Under START_HERE "ACCOUNTING" ("Recognize platform consideration by actual service days / 365 … Preserve the original base schedule when adding an upgrade increment"), the October increment arithmetic is 12,000 × 16/365 = **$526.03**. It is absent from both the plan and the GL.
  - Total increment per AM-OF-2026-164: $10,520.55 over 320 days (12,000 × 320/365 = 10,520.548). Check: 10 × $1,000 + $526.03 − $5.48 final credit = $10,520.55.
- **Cedar Harbor.** The plan is unchanged at $4,076.71 for October. AM-OF-2026-157 changes only the allowance: "Platform fee $48,000.00 (unchanged)".

## 7. October GL accounting effects

**Usage accrual (1150 / 4010).**
- There are 27 accrual journals, created 2026-11-05T11:00 and dated 2026-10-31 (Oct 2026), totalling $74,831.90.
- That equals the Nov 1 invoice 1150 release of $74,831.90. Per customer, though, it differs in four places:
  - Zephyr: accrual $852.60 vs release $952.60;
  - Beacon: accrual $1,444.30 vs release $1,344.30;
  - the two differences offset.
- Accrual against what deduplicated, mapped usage implies:
  - **Juniper Signal Works** $1,425.10 (`:232`–`:233`) vs $4,560.32 implied: **−$3,135.22**.
  - **Cedar Harbor** $11,388.00 (`:260`–`:261`) vs $8,291.20 implied: **+$3,096.80**.
  - **Yarrow Ridge**: no accrual vs $3,074.28 implied.
  - **Beacon Marsh** $1,444.30 (`:324`–`:325`) = implied. The Nov 1 release was only $1,344.30 (`:321`), which leaves **$100.00 in 1150**.
  - **Zephyr** $852.60, net of the approved $100 (MSG-109).
  - Aspen Vale and Willow Passage: no accrual, and no mapped overage.
  - The unverified workspace has no accrual.
  - All other 22 customers: accrual = implied = billed.
- MSG-2026-125: "The accrual work was prepared November 5. … completeness and the application of contract terms have not yet been checked."

**September accrual release.**
- The opening 1150 balances (30 rows, `netsuite_opening_balances.csv`, total $82,170.97) are each released exactly by the customer's Oct 1 usage invoice. The 29 Oct-1 usage invoices credit 1150 for $82,170.97 in total; Willow's opening 1150 is $0.00 (`:119`).
- Each opening 1150 equals the September overage that usage implies. Example: Juniper Signal Works $4,320.00 (`:83`) = 27,000 × $0.16.
- Every customer's September usage billing agrees with deduplicated September usage, including Crescent Shore's prorated 21,333 allowance.

**2200 / 1160 reclass.**
- 18 reclass journals (`RECLASS-OCT-*`, created 2026-11-05T12:00) post Dr 1160 / Cr 2200, totalling $339.66:
  - 10 customers at $3k/month × $16.43: −41.10 opening − 3,000.00 billed + 3,057.53 recognized = 16.43 net debit;
  - 8 customers at $4k/month × $21.92: −54.79 − 4,000.00 + 4,076.71 = 21.92.
- These match the opening 2200 balances: annual −22,027.40; $3k −41.10; $4k −54.79; $5k −2,369.86 (= 5,000 − 60,000 × 16/365).
- Annual customers, Crescent Shore and Willow Passage stay in net credit in 2200, so they have no reclass.
- Opening 1100 and 1160 are 0.00 for every customer.
- Fact for Meridian: if the $526.03 increment were recognized without a matching billing correction, its October 2200 net debit would rise from $21.92 to $547.95. START_HERE: "Reverse any prior reclass before recalculating. The supplied October GL ALREADY contains its baseline reclass."

**Timing.**
- All October journals were created between 2026-11-05 10:00 and 12:00, before the cutoff of 2026-11-11T18:00-07:00.
- The Zephyr credit memo was created 2026-11-04T10:05.
- No GL line was created after the cutoff.

## Open points this sweep could not settle from the data

- Who owns `pa_676b6b455e0887`. MSG-131 says Product Operations must verify; the files contain no evidence of ownership.
- Why Juniper Signal Works' price changed on the same `price_id`. No document or message explains it.
- Whether Beacon Marsh's Oct 31 record of exactly 1,000 units is a genuine late record or a placeholder. Its only distinguishing fields are the round value and the Nov 3 `ingested_at`.
