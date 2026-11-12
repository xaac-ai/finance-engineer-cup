# What START_HERE prescribes for each treatment: the policy checklist

Research for issue #12 (child of map #10). It turns every accounting and billing policy into a checklist item with a citation, a plain-language reading, a worked example on the October data, and the ambiguities. It is not a findings list: the real-data examples show how each rule applies, and the finding rules for each stream still have to be built and tested.

**Sources (all primary):**

- `data/raw/2026-10/START_HERE.pdf`, cited as **SH · SECTION**. Text from `out/2026-10/extracted/START_HERE.txt`, produced by `make run` at `b93ede8`.
- `data/raw/2026-10/billing_followups.pdf`, cited as **MSG-…**. Text from `out/2026-10/extracted/billing_followups.txt`.
- The Notion brief (page `40839a8f-0567-81e4-ae57-e8e132aeb1da`, fetched 2026-11-11), cited as **Brief · heading**.
- The executed documents in `out/2026-10/extracted/OF-*.txt` and `AM-OF-*.txt`, cited by document ID and section.
- The data comes from `out/2026-10/workbench.duckdb` (`raw_*` tables), queried on 2026-11-11.

All arithmetic uses exact decimals and rounds half up.

---

## 0. Accounting terms used below

| Term / account | Plain-language meaning |
|---|---|
| **Debit (Dr) / Credit (Cr)** | Every entry has two equal sides. Asset accounts (1xxx) grow with debits; liability and revenue accounts (2xxx, 4xxx) grow with credits. Signed movement = Debit minus Credit (**SH · MONEY**). |
| **1100 Accounts receivable (AR)** | Money a customer owes on an invoice we have already sent. |
| **1150 Unbilled usage receivable** | Usage the customer has earned the right to be charged for, but we haven't invoiced yet. October usage is invoiced on Nov 1, so at Oct 31 it sits here. |
| **1160 Platform contract asset** | We have delivered more platform service than we have billed: revenue ran ahead of invoicing. |
| **2200 Deferred platform revenue** | We billed platform fees in advance but haven't delivered the service yet: invoicing ran ahead of revenue. |
| **4000 Platform revenue / 4010 Usage revenue** | Revenue earned in the period. |
| **Recognition** | Moving an amount from "billed but not yet earned" (2200) to "earned" (4000) as service days pass. |
| **Accrual** | Booking revenue that has been earned but not yet invoiced (Dr 1150 / Cr 4010). |
| **Reclass** | A presentation-only entry that moves a balance to the right side of the balance sheet. It never touches revenue. |
| **Posting period vs issue date** | The posting period is the month the books record an entry in. The issue date is the date printed on an invoice or credit note. They can differ. |

---

## 1. Source precedence (applies to every item)

| # | Quote | Plain language |
|---|---|---|
| 1.1 | "Executed order forms and amendments determine commercial terms. An amendment changes only named terms; unchanged terms persist. Register supersedes_document_id denotes partial precedence, not cancellation of the original order. START_HERE defines exercise accounting policy; messages establish approvals and context." (**SH · SOURCE PRECEDENCE**) | Contract PDFs set the prices. START_HERE sets the accounting. Billing Messages set approvals. An amendment overrides only the terms it names. |

**Example.** AM-OF-2026-157 (Cedar Harbor) changes only the allowance. The $0.40 rate and the $4,000 monthly platform invoice still come from OF-2026-157. AM-OF-2026-164 (Meridian) changes the annual rate and adds a catch-up, but "Usage terms are unchanged", so the 30,000-run allowance and the $0.12 rate stay.

**Example.** In the register, AM-OF-2026-164 and AM-OF-2026-157 have a **blank `billing_loaded_at`**. Per the file dictionary, "blank billing load means not recorded as loaded" (**SH · FILE DICTIONARY · contract_register.csv**). Billing may therefore still be running on the original terms. MSG-2026-119 says the same: "an amendment that may not have reached billing".

---

## 2. Usage

### 2.1 Aggregate across verified product accounts, deduplicate, then apply one allowance

> "Aggregate unique active records across a customer's verified product accounts before applying its calendar-month allowance. No rollover or tiers. Daily records are additive across product accounts but versions/duplicates must not be double counted. Explicit zero-use days remain records. record_status and replaces_record_id describe source corrections; there are no superseded versions in this release." (**SH · USAGE**)

> "record_id identifies source activity and is the deduplication key … Exact repeated source IDs are not new activity." (**SH · FILE DICTIONARY · product_usage.csv**)

**Plain language.** Add up a customer's runs across all of its verified workspaces, count each `record_id` once, and compare one monthly total with one monthly allowance. An unused allowance doesn't carry over, and there is no volume pricing. A day with 0 runs is still a real record: it counts in record totals but adds 0 units.

**Worked examples (October 2026).**

- *Multi-account aggregation.* Silver Current (CT-676664) has two verified workspaces, `pa_47b88c661eb874` and `pa_f870ed4e1b3515`. October total: 62 records, 72,266 runs. Overage = (72,266 − 20,000) × $0.06 = 52,266 × 0.06 = **$3,135.96**. The Nov 1 invoice bills 52,266 units, which is right. The wrong method applies the allowance to each workspace separately and gives a different, larger number. Timberline Insights (CT-941670) works the same way: 79,285 − 20,000 = 59,285 × 0.06 = **$3,557.10**.
- *Duplicate.* `ur_7352010ec2e04c` (Westhaven, 2026-10-14, 1,730 units) appears twice, at source lines 1448 and 1449, with identical content. The physical file has 1,925 rows; the unique count is 1,924, which matches "1,924 unique source daily usage records" (**SH · RECONCILIATION POPULATION**). Counting the row once gives Westhaven 61,866 runs, so (61,866 − 30,000) × 0.05 = **$1,593.30**. Counting it twice would overstate that by 1,730 × 0.05 = $86.50. The batch control for 2026-10-14 shows 32 records and 57,912 units. The physical rows show 33 records and 59,642 units; after deduplication they match the control.
- *Zero-use days.* 16 records carry `units = 0`, all for `pa_676b6b455e0887` from 2026-09-15 to 09-30. They stay in the record count. They don't mean "no activity is attributable".
- *Source corrections.* All 1,925 rows have `record_status = active` and a blank `replaces_record_id`, so there are no versions to resolve this month. The logic still has to handle them in future months.

**Ambiguity.** The text doesn't say what to do if a repeated `record_id` carries different content (units, date or account). It answers only for "exact repeated source IDs". This month has no such case. The pipeline should stop or raise a Needs Info finding rather than pick one.

### 2.2 First-partial-month proration of the allowance

> "Partial first-month allowance: monthly allowance x active calendar days / days in month, rounded once to whole runs half up." (**SH · USAGE**)
> OF text: "For the first partial calendar month, prorate the included allowance by active calendar days and round once to a whole run, half up. Full later months receive the entire allowance." (**OF-2026-\* · 04**)

**Plain language.** A customer who starts mid-month gets only that month's share of the allowance, counted by calendar days and rounded once to a whole run.

**Worked example (September, the only partial month in the data).** Crescent Shore (CT-260381) started on Sept 15, so Sept 15–30 is 16 active days out of 30.
Allowance = 40,000 × 16 / 30 = 21,333.33… → **21,333 runs**.
September usage was 24,533 runs, so the overage is (24,533 − 21,333) × $0.04 = 3,200 × 0.04 = **$128.00**. That matches invoice `RC-261001-260381-U` (3,200 units, $128.00) and the Sept 30 opening 1150 balance of $128.00.
In October Crescent Shore gets the full 40,000, so (43,543 − 40,000) × 0.04 = **$141.72**, which matches what was billed.

**Ambiguity.** "Days in month" means the calendar month, and the OF wording confirms it. The service intervals are end-exclusive, so Sept 15 00:00 to Oct 1 00:00 is 16 days. Nothing in October is a first partial month.

### 2.3 Amendment allowance weighting

> "For an allowance amendment, weight each allowance by applicable calendar days and round once." (**SH · USAGE**)
> "For October, weight the prior allowance for October 1-15 and the amended allowance for October 16-31 by calendar days. Round the resulting allowance once to a whole run, half up." (**AM-OF-2026-157 · 04**)

**Worked example.** Cedar Harbor Labs (CT-639373), October:
Allowance = 30,000 × 15/31 + 45,000 × 16/31 = 14,516.129… + 23,225.806… = 37,741.935… → **37,742 runs**. Round once, at the end, never each piece.
October usage was 58,470 runs, so the overage is (58,470 − 37,742) × $0.40 = 20,728 × 0.40 = **$8,291.20**.
Billed (`RC-261101-639373-U`): 28,470 units × $0.40 = $11,388.00, which is the old 30,000 allowance applied to the whole month. The difference is **$3,096.80 overbilled**. This is consistent with the amendment's blank `billing_loaded_at`.

**Ambiguity.** "Round once" could also be read as rounding each weighted piece. The amendment text rules that out ("Round the resulting allowance once"). The two readings give the same answer here: 14,516 + 23,226 = 37,742. In other months they could differ.

### 2.4 Overage formula, rounding and pricing

> "Charges equal max(0, eligible units minus allowance) x signed overage rate, rounded once to USD cents half up. Prices are negotiated net prices, with no additional invoice discounts." (**SH · USAGE**)
> "unit_amount_decimal is decimal cents per unit." (**SH · MONEY**)

**Plain language.** Overage = runs above the allowance (never negative) × the contract rate, rounded once to the cent. Discounts aren't allowed, so any `discount_amount` on a usage line is itself a finding.

**Worked examples.**

- Meridian: (49,396 − 30,000) × 0.12 = 19,396 × 0.12 = **$2,327.52**. That matches what was billed. The amendment didn't change usage.
- Zero overage: Aspen Vale has 25,000 runs against a 30,000 allowance, so max(0, −5,000) × 0.05 = **$0.00**. No Nov 1 usage invoice exists, which is valid (see 3.2).
- Units check: Juniper Signal Works (CT-437384) contracts at "$0.16 / excess run" (OF-2026-331 · 03). Its Nov 1 line bills 28,502 units at `unit_amount_decimal = 5.00` (5 cents) = $1,425.10. The September line under the same `price_id` used 16.00. Expected = 28,502 × 0.16 = **$4,560.32**. In the reading of `unit_amount_decimal`, "16.00" means 16 cents, not $16.

**Ambiguity.** "Signed overage rate" isn't defined. Every rate in the data is positive. The most likely reading is "the rate in the signed (executed) contract", not "a rate that can be negative". Read it that way and note it.

### 2.5 Unverified usage

> "Reconcile known mapped activity separately and isolate unverified usage. Do not force a mapping, assume the remaining customer owns a workspace, or treat missing attribution as zero usage. Document conditional exposure and request Product Operations evidence. An unapproved concession request alone does not authorize a credit or revenue reduction." (**SH · UNVERIFIED USAGE**)
> "Workspace pa_676b6b455e0887 has October metering but no verified billing owner … Do not identify it by elimination from the customer list. Product Operations must verify ownership before Billing assigns usage." (**MSG-2026-131**)
> "Willow Passage has requested USD 250 off October usage. This is a request only … The request does not establish ownership of any unverified workspace." (**MSG-2026-132**)

**Plain language.** One workspace has usage but no confirmed owner. Keep it in its own bucket. Don't bill it, accrue it, or assign it to anyone, and don't treat it as zero either. Report what it *could* be worth and who has to confirm the owner. A customer's discount request is not a credit until the Controller approves it.

**Worked example.** `pa_676b6b455e0887` ("Workspace pending identity verification"):

- It has a blank `salesforce_account_id` and is effective from 2026-09-15.
- It shows 16 zero-unit days in September and 31 records with **49,762 runs** in October.
- Willow Passage (CT-839653, started Sept 15) is the only customer with **no** mapped product account, and MSG-2026-130 says "No metered production runs are expected during September onboarding". The pattern is suggestive, and it is exactly the inference by elimination that the rules forbid.
- Conditional exposure, *if* Product Operations confirmed Willow as the owner: (49,762 − 40,000) × $0.04 = **$390.48** of October usage. If it is an internal workspace, the exposure is **$0**. This is Needs Info and is never added to underbilling totals ("Don't combine confirmed corrections with hypothetical exposure", **Brief · FAQ**).
- Willow's $250 request (MSG-2026-132) has no approval, so there is **no credit and no revenue reduction**.

**Ambiguity.** "Document conditional exposure" doesn't say which contract's terms to price it at. The exposure depends on the owner. Present it as a range per candidate owner, or as "unpriced units", rather than a single number.

---

## 3. Billing

### 3.1 Billing anchors (1st, 15th, annual)

> "Platform invoices are issued in advance on contract billing anchors, either monthly or annually." (**SH · BILLING**)
> Order-form variants (**OF · 04**): annual "invoiced in full on September 1, 2026"; monthly "invoiced on the 1st of each month"; 15th anchor "invoiced on the 15th of each month, beginning September 15, 2026 … ends at 00:00 America/Denver on September 15, 2027".

**In the data:**

- 10 annual contracts at $24,000, all invoiced on Sept 1 for 2026-09-01 to 2027-09-01.
- 18 monthly contracts with a 1st anchor, at $3,000 or $4,000.
- 2 monthly contracts with a 15th anchor at $5,000: Crescent Shore (CT-260381) and Willow Passage (CT-839653).

Stripe matches this pattern: 18 platform invoices on Oct 1 ($62,000), 2 on Oct 15 ($10,000), and 18 on Nov 1 ($62,000).

**Plain language.** Annual customers were billed once in September and get **no** October platform invoice, yet October revenue still exists (**SH · page 1**: "An annual prepaid platform fee is not billed again in October, but October earned revenue still exists"). Monthly 1st-anchor customers get one invoice covering exactly October. 15th-anchor customers have two invoices that each cover part of October.

### 3.2 Usage invoicing and when an absent invoice is fine

> "Usage is always calendar-month based and separately invoiced on the first day of the next month. An absent usage invoice can be valid when no overage exists." (**SH · BILLING**)

**Example.** October usage is billed on the Nov 1 invoices: 27 usage invoices totalling $74,831.90. Two of the three missing invoices are valid: Aspen Vale has no overage, and Willow Passage has no mapped usage. The third, **Yarrow Ridge** (CT-188999), has 55,619 runs against 30,000, so expected = 25,619 × 0.12 = **$3,074.28**. It has no Nov 1 usage invoice and no October accrual. An absent invoice is valid *only* when the expected overage is zero.

### 3.3 What counts as an "additional October-service charge"

> "For advance subscriptions, reconcile the invoice billing periods covering October and identify any additional October-service charges." (**SH · page 1**)
> "October upgrade catch-up: USD 526.03 … This additional October-service charge may be invoiced separately." (**AM-OF-2026-164 · 04**)

**Plain language.** It means any platform charge for October service beyond the regular anchor invoices. In this data the only contractual example is Meridian's $526.03 upgrade catch-up for Oct 16–31. There is no such invoice in Stripe through cutoff, so it is underbilled and needs a supplemental invoice dated in November.

**Ambiguity.** It is unclear whether the phrase also covers usage invoices for October service, which are issued Nov 1. The sentence is scoped to "advance subscriptions", meaning platform, and usage is reconciled separately (**SH · page 1**: "platform fees and usage shown separately"). Read it as platform-only.

### 3.4 Invoices issued by cutoff

> "Include invoices issued by cutoff; November 15 invoices have not yet been issued. September platform invoices are settled; October/November invoices remain unpaid." (**SH · BILLING**)
> "Close cutoff: 2026-11-11T18:00:00-07:00." (**SH · page 1**)
> "unpaid invoices alone do not imply a required adjustment." (**SH · PAYMENT AND DATE DISPLAY**)

**Example.** The latest Stripe invoice is dated 2026-11-01T09:00-07:00. There are no Nov 15 invoices for Crescent Shore or Willow, which is expected and not a finding. Crescent Shore's Oct 15 invoice (Oct 15–Nov 15) is `open`, which is not a finding either.

**Ambiguity.** "Issued" could mean `created` or `finalized_at`. They are equal on every invoice checked, so the question doesn't matter this month. Use `finalized_at`, since a draft isn't issued.

---

## 4. The two accepted platform presentation approaches

> "For advance subscriptions, reconcile the invoice billing periods covering October and identify any additional October-service charges. You may instead show explicit day-based allocations to October, provided your basis is clear. Neither a full crossing-period invoice nor its billing allocation automatically equals October recognized revenue. Both well-supported presentation approaches are accepted." (**SH · page 1**)
> "For subscriptions billed in advance, reconcile the billing periods covering October or show an explicit day-based allocation to October. State your basis. An invoice amount does not automatically equal October's revenue." (**Brief · Data and Scope**)

**Plain language.** This is about how to show *billing* for October; it is not about revenue.

- **Approach A (billing-period reconciliation).** List each invoice whose service period overlaps October at its full amount, check it against the contract, and add any extra October charges.
- **Approach B (day-based allocation).** Take each overlapping invoice and keep only the share for October days.

Either way, **October revenue is a separate number**: actual days / 365 × annual consideration (see 5.1).

**Side by side (real contracts):**

| Contract | Approach A: invoices covering October (full amounts) | Approach B: billing allocated to October by days | October recognized revenue (days/365) |
|---|---|---|---|
| **Annual prepaid**, Highwater Studio CT-142182, $24,000/yr | `RC-260901-142182-P` $24,000.00 for 2026-09-01 to 2027-09-01, issued in September. No October invoice is expected. | $24,000 × 31/365 = **$2,038.36** (the billing period is the 365-day term) | 24,000 × 31/365 = **$2,038.36** |
| **Monthly, 1st anchor**, Meridian CT-335780, $4,000/mo before the upgrade | `RC-261001-335780-P` $4,000.00 for Oct 1–Nov 1. Additional October-service charge expected: the $526.03 catch-up, **missing**. | $4,000 × 31/31 = $4,000.00, plus the catch-up $526.03 = **$4,526.03** | Base 48,000 × 31/365 = $4,076.71, plus increment 12,000 × 16/365 = $526.03, so **$4,602.74** |
| **Monthly, 15th anchor**, Crescent Shore CT-260381, $5,000/mo | `RC-260915-260381-P` $5,000.00 (Sep 15–Oct 15) and `RC-261015-260381-P` $5,000.00 (Oct 15–Nov 15) | $5,000 × 14/30 = $2,333.33 (Oct 1–14 of a 30-day period), plus $5,000 × 17/31 = $2,741.94 (Oct 15–31 of a 31-day period), = **$5,075.27** | 60,000 × 31/365 = **$5,095.89** |

The 15th-anchor row shows why "neither … automatically equals October recognized revenue": the allocation gives $5,075.27 and revenue is $5,095.89. Monthly invoices are equal amounts over unequal months; revenue is per day over 365. The same gap appears for 1st-anchor contracts ($4,000.00 billed vs $4,076.71 revenue), and that gap is what feeds the 2200 → 1160 reclass (see 6.3).

**Ambiguities.**

- (a) For Approach B, the day basis could be days in the invoice's own billing period (30 or 31), as shown above, or 365. With 365, the 15th-anchor allocation would equal revenue, and the distinction the brief draws would disappear. Billing-period days is the reading consistent with "nor its billing allocation automatically equals … revenue". **State the basis explicitly** whichever you choose.
- (b) For Approach A on a 15th anchor, what is "expected October billing"? Both invoices (total $10,000), or only the one issued in October ($5,000)? The text says "invoice billing periods covering October", so both, with their periods shown.
- (c) START_HERE says "Both well-supported presentation approaches are accepted", so this is a presentation choice, not a correctness one. Pick one, apply it to all 30 customers, and document it.

---

## 5. Platform recognition

### 5.1 Actual days / 365, independent of invoice frequency

> "Recognize platform consideration by actual service days / 365, independent of invoice frequency." (**SH · ACCOUNTING**)

**Example.** October has 31 days.

- $48,000/yr: 48,000 × 31/365 = 4,076.712… → **$4,076.71**.
- $36,000/yr: 3,057.53.
- $24,000/yr: 2,038.36.
- $60,000/yr: 5,095.89.

These match the October `REV-OCT-*` journals, for example `JE-f9723c1c618a30` for Meridian at $4,076.71. September (30 days): 48,000 → 3,945.21, which matches plan row `RP-26645e070609bc`.

**Ambiguity.** Leap years aren't addressed: the term Sept 2026–Aug 2027 contains no Feb 29. "/ 365" is literal.

### 5.2 Round each monthly component once; final-period rounding goes to the last period

> "Round each monthly recognition component once to cents, with final-period rounding allocated to the last period." (**SH · ACCOUNTING**)

**Plain language.** Each month's amount for each component (the base schedule and, separately, each upgrade increment) is rounded to cents once. The last month absorbs whatever is needed so the total equals the contract consideration exactly.

**Example, base schedule** (Meridian plan `RP-26645e070609bc`, $48,000):

- 7 months of 31 days × 4,076.71 = 28,536.97
- 4 months of 30 days × 3,945.21 = 15,780.84
- 1 month of 28 days (Feb) × 3,682.19 = 3,682.19
- Total = **48,000.00**

The final period (Aug 2027) needs no adjustment, and the supplied plan shows 4,076.71 there. For the increment, see 5.3.

### 5.3 Preserve the original base schedule when adding an upgrade increment (Meridian)

> "Preserve the original base schedule when adding an upgrade increment. … The signed amendment defines incremental consideration and billing conventions." (**SH · ACCOUNTING**)
> "Annual platform subscription rate increases from USD 48,000 to USD 60,000 effective October 16, 2026 at 00:00 America/Denver … No service before that date is repriced … October upgrade catch-up: USD 526.03, using USD 12,000 x 16 / 365, rounded half up … Incremental consideration for 320 remaining service days is USD 10,520.55. The final platform invoice includes a USD 5.48 credit to reconcile the monthly billing convention to that amount. Original base consideration remains unchanged." (**AM-OF-2026-164 · 04**)

**Plain language.** Leave the existing $48,000 schedule alone. Add a second, separate schedule for the extra $12,000/yr from Oct 16. Don't re-spread a blended $60,000 over the rest of the term, and don't touch Sept 1–Oct 15.

**Worked example.**

- Remaining days, Oct 16 2026 to Sept 1 2027 (end-exclusive): 16 + 30 + 31 + 31 + 28 + 31 + 30 + 31 + 30 + 31 + 31 = **320**.
- Incremental consideration: 12,000 × 320/365 = 10,520.5479… → **$10,520.55**, which matches the amendment.
- Incremental schedule, each month rounded once:

| Period | Days | Exact | Rounded |
|---|---|---|---|
| Oct 2026 | 16 | 526.0274 | **526.03** |
| Nov 2026 | 30 | 986.3014 | 986.30 |
| Dec 2026 – Jan 2027 | 31 each | 1,019.1781 | 1,019.18 each |
| Feb 2027 | 28 | 920.5479 | 920.55 |
| Mar, May, Jul 2027 | 31 each | 1,019.1781 | 1,019.18 each |
| Apr, Jun 2027 | 30 each | 986.3014 | 986.30 each |
| **Aug 2027 (final)** | 31 | 1,019.1781 | **1,019.17**, which is 10,520.55 minus the sum of the prior 10 months (9,501.38). Final-period rounding of −0.01 lands here. |

- October total for Meridian: base 4,076.71 (unchanged), plus increment **526.03**, = 4,602.74.
- Billing convention (from the amendment, not a recognition rule):
  - catch-up 526.03, plus 10 monthly increments of $1,000 (Nov–Aug, as part of $5,000 invoices), = 10,526.03;
  - minus the final-invoice credit **5.48**, = **10,520.55**.
  - Billing and revenue agree in total over the term but not month by month.
- October booked: only the base $4,076.71 (`JE-f9723c1c618a30`). The increment of **$526.03** is unrecognized, and the catch-up invoice was never issued. The amendment's `billing_loaded_at` is blank.

**Ambiguity.** The final-period rounding of −$0.01 goes to "the last period" of the *increment* component, which is Aug 2027. The amendment's $5.48 billing credit also falls in the final invoice. These are two different reconciling amounts (one revenue, one billing), and they shouldn't be confused.

---

## 6. Journal patterns

### 6.1 Platform invoice: Dr 1100 / Cr 2200. Recognition: Dr 2200 / Cr 4000

> "Platform invoice: Dr 1100 AR / Cr 2200 deferred platform revenue. Recognition: Dr 2200 / Cr 4000 platform revenue." (**SH · ACCOUNTING**)

**Example.** Meridian's October platform invoice `JE-7767a3aee3cd1d` is Dr 1100 4,000.00 / Cr 2200 4,000.00. Its October recognition `JE-f9723c1c618a30` is Dr 2200 4,076.71 / Cr 4000 4,076.71. October GL totals: platform billing credits to 2200 of $72,000.00 ($62,000 on Oct 1 plus $10,000 on Oct 15), and recognition of $93,764.36 across 30 customers.

### 6.2 Usage accrual and release: Dr 1150 / Cr 4010, then Dr 1100 / Cr 1150

> "Usage accounting: Dr 1150 unbilled usage receivable / Cr 4010 usage revenue in the service month. The next-month invoice is Dr 1100 / Cr 1150, not revenue again. September 30 unbilled balances are released by October 1 invoices; November 1 invoices release October accruals only to the amounts actually billed. Residuals may remain until supported billing corrections." (**SH · ACCOUNTING**)

**Plain language.** Usage revenue is booked in the month the runs happen, through an accrual. Next month's invoice only turns "unbilled" into "billed"; it never creates revenue again. If the invoice is smaller or larger than the accrual, the difference stays in 1150 (a residual) until a supplemental invoice or credit note clears it.

**Worked examples.**

- *Clean release.* Highwater Studio: Sept 30 opening 1150 of $5,741.36 is released by `RC-261001-142182-U` (Dr 1100 / Cr 1150 5,741.36). The October accrual `USG-OCT-142182` is Dr 1150 / Cr 4010 5,857.28, and `RC-261101-142182-U` releases exactly 5,857.28. The Sept 30 1150 total of $82,170.97 equals the Oct 1 usage releases of $82,170.97 for every customer.
- *Residual, billing short but accrual correct.* Beacon Marsh (CT-810234): October accrual $1,444.30 = (44,443 − 30,000) × 0.10, which is correct. The Nov 1 invoice bills 13,443 units = $1,344.30, so the release is $1,344.30 and **$100.00 stays in 1150**. Fix: a supplemental November invoice for $100.00, Dr 1100 / Cr 1150. October revenue is already right, so **no October revenue entry** is needed.
- *Accrual wrong.* Cedar Harbor's accrual is $11,388.00 vs the correct $8,291.20, so October usage revenue is overstated by $3,096.80. Juniper Signal Works' accrual is $1,425.10 vs $4,560.32, understated by $3,135.22. Yarrow Ridge has no accrual vs $3,074.28, understated by $3,074.28. These need October entries (Dr 4010 / Cr 1150, or Dr 1150 / Cr 4010), *plus* a November billing document that clears 1150.
- *Pattern observed.* The supplied October accruals equal the Nov 1 invoice amounts for every customer except Zephyr (−$100, approved concession) and Beacon Marsh (+$100). So the accrual mostly copied billing errors rather than the contract.

**Ambiguity.** "Residuals may remain until supported billing corrections" could mean "leave them in 1150 at Oct 31", the reading taken here: the residual is a November balance, since the release happened Nov 1. It could also mean "propose an October reversal". The first reading avoids touching October revenue that is already correct.

### 6.3 Reclass a customer's net debit in 2200 to 1160

> "Any customer platform net debit in 2200 is reclassified Dr 1160 platform contract asset / Cr 2200. Reverse any prior reclass before recalculating. The supplied October GL ALREADY contains its baseline reclass. Propose only incremental changes after correcting recognition. Do not net different customers or platform assets against usage." (**SH · ACCOUNTING**)

**Plain language.** For each customer separately, look at their 2200 balance. If recognition has run ahead of billing, the "deferred revenue" balance has gone negative (a debit). Show it as an asset (1160) instead. Recompute after any recognition correction:

1. Take 2200 *before* any reclass (add back the existing reclass).
2. Add the corrected recognition.
3. The new net debit, if any, is the required 1160 amount.
4. Propose only the difference from the reclass already booked.

Never offset one customer against another, or platform against usage (1150).

**Worked examples.**

- *Baseline, monthly 1st anchor at $48k.* Sept 30 opening 2200 = credit 54.79 (4,000 − 3,945.21). In October, invoice Cr 4,000.00 and recognition Dr 4,076.71 give 54.79 + 4,000.00 − 4,076.71 = **−21.92, a net debit**. The baseline reclass `RECLASS-OCT-335780` Dr 1160 / Cr 2200 is 21.92, which is correct. The $36k contracts give 41.10 + 3,000 − 3,057.53 = −16.43, matching the 16.43 reclasses. The 18 baseline reclasses total $339.66.
- *Meridian after the upgrade correction.*
  - The October recognition correction adds Dr 2200 / Cr 4000 526.03.
  - Pre-reclass 2200 = 54.79 + 4,000.00 − 4,076.71 − 526.03 = −547.95, so the required 1160 is 547.95.
  - Already booked: 21.92. **Incremental reclass: Dr 1160 / Cr 2200 526.03.**
  - The combined October effect of the two entries is Dr 1160 526.03 / Cr 4000 526.03. The catch-up invoice, when issued in November (Dr 1100 / Cr 2200), unwinds the asset in November.
- *No reclass, 15th anchor and annual.* Crescent Shore: 2,369.86 + 5,000.00 − 5,095.89 = 2,273.97, a credit, so no reclass. Highwater (annual): 22,027.40 − 2,038.36 = 19,989.04, a credit, so no reclass.

**Ambiguity.** "Reverse any prior reclass before recalculating" could mean posting an explicit reversal entry plus a new full reclass (gross presentation), or just computing the difference (net). The next sentence, "Propose only incremental changes", favors one net incremental entry. Show the calculation in gross form so a reviewer can check it, and propose the net entry.

### 6.4 Residuals rule (summary)

Residuals in 1150 after a Nov 1 release are expected whenever billing ≠ accrual. They clear only with a *supported* billing correction: a supplemental invoice (Dr 1100 / Cr 1150) or a linked credit note (Dr 1150 / Cr 1100). They are never written off to revenue. See 6.2 for Beacon Marsh.

---

## 7. Credits

> "Use issued notes only; void notes have no current credit effect. Retain original service-period allocation. Approved reductions of October consideration affect October where not already reflected. A November credit can reduce AR and reverse the corresponding release of unbilled usage without reducing revenue a second time." (**SH · CREDITS**)
> "status issued/void determines effect" (**SH · FILE DICTIONARY · stripe_credit_notes.csv**). "Service dates are internal enrichment, with service_period_source identifying provenance." (**· stripe_credit_note_lines.csv**)

**Plain language.**

- Count only `issued` credit notes; a void one never happened.
- A credit belongs to the service month of the line it credits, not the month it was issued.
- If a reduction to October's price was approved, October revenue must reflect it once.
- When the credit note goes out in November, it reduces what the customer owes (1100) and puts back the 1150 amount that the Nov 1 invoice over-released. It does **not** hit revenue again.

**Worked examples.**

- *Void.* `cn_82a7ddd6e88e69` (Alder, $50.00, status `void`, voided 2026-11-03) has no effect. MSG-2026-116 confirms it was voided before import, and the GL has no Alder credit posting. Alder's usage, (29,697 − 10,000) × 0.08 = $1,575.76, matches both the bill and the accrual.
- *Issued, approved, already reflected (Zephyr Grove, CT-148565).*
  - MSG-2026-109 (Controller): "reduce Zephyr Grove October usage consideration by USD 100 … ensure the October accrual is already net of this approved concession. Do not apply a second concession."
  - Contract overage = (49,052 − 30,000) × 0.05 = 952.60. Approved consideration = 952.60 − 100.00 = **852.60**.
  - October accrual `USG-OCT-148565` = **852.60**, so the concession is already reflected and there is **no October entry**.
  - Nov 1 invoice of 952.60 releases 952.60 from 1150, leaving 1150 at −100.00.
  - Credit note `cn_85bf669490fd97` (issued Nov 4, line service period 2026-10-01 to 2026-11-01, `service_period_source = original invoice line`) posts `CM-148565` as **Dr 1150 100.00 / Cr 1100 100.00**.
  - Result: 1150 is back to 0, AR is $852.60, and revenue was reduced once, in October.
  - This is the exact pattern in the quote.

**Ambiguities.**

- (a) The text doesn't give the posting pattern for a *platform* credit note. By analogy it would be Dr 2200 / Cr 1100, plus a recognition correction if consideration changed. There is no case in the data.
- (b) The text doesn't say whether a concession is a revenue reduction (Dr 4010) or a contra-revenue account. Only 4000 and 4010 exist, so a revenue reduction it is.
- (c) MSG-2026-109 says "issue a credit … once finalized". The note was issued Nov 4, after finalization on Nov 1, so it complies.

---

## 8. Approvals and dates

> "Recommend corrections for Controller approval. Finalized invoices are not silently edited: propose supplemental invoices or linked credit notes. Proposed billing documents use November issue dates; supported October-service accounting corrections use the October posting period. You need not create live records." (**SH · APPROVAL AND DATES**; same in **MSG-2026-133** and **Brief · Rules**)

**Plain language.** We only *recommend*. To fix an invoice, never change it; add a new invoice for an undercharge, or a credit note linked to the original for an overcharge. Every recommended billing document is dated in November. Every accounting correction for October service is posted to October, even though it is prepared in November.

**Worked example (Cedar Harbor overbilling of $3,096.80):**

- Billing: a linked credit note against `RC-261101-639373-U` for $3,096.80, with a November issue date and service period Oct 1–Nov 1. When issued it posts in November: Dr 1150 / Cr 1100 3,096.80.
- Accounting: an October posting-period entry, Dr 4010 / Cr 1150 3,096.80, which corrects the overstated accrual.
- Check: 1150 for Cedar gets accrual 11,388.00, less the October correction 3,096.80, less the Nov 1 release 11,388.00, plus the credit note 3,096.80, = **0**. Revenue is 8,291.20, reduced once.

**Meridian:**

- Billing: a supplemental invoice for $526.03 with a November issue date (October service).
- Accounting: the October entries from 5.3 and 6.3.
- Recommend updating plan `RP-26645e070609bc` with an increment element. "Recommend updating an affected revenue plan; a future schedule or new system record is not required" (**MSG-2026-133**).

---

## 9. Timing and cutoff

> "Source activity, ingestion timestamp, invoice issue date, service period, GL posting period and GL Created At are distinct. October entries can be created during November close. Determine evidence availability using the cutoff, not an assumption that October entries were all created October 31." (**SH · TIMING**)
> "REQUIRED SCOPE: October 1-31, 2026 service and its effect on October books. Close cutoff: 2026-11-11T18:00:00-07:00 … Flag later-service issues as follow-ups; do not reconcile November or rebuild future contract history." (**SH · page 1**)

**Examples.**

- All October `REV-OCT`, `USG-OCT` and `RECLASS-OCT` journals have `Date` 2026-10-31 and `Posting Period` Oct 2026, but `Created At` is 2026-11-05 (10:00, 11:00 and 12:00). They are October entries created before the cutoff, so they are included. MSG-2026-125: "The accrual work was prepared November 5."
- The latest GL `Created At` is 2026-11-05T12:00-07:00, and every message is on or before Nov 7, so all evidence is inside the cutoff.
- *Later-service follow-up.* Meridian's Nov 1 platform invoice is $4,000.00, but the amendment says "$5,000.00 from Nov 1". That is a **November-service** underbilling of $1,000. Flag it as a follow-up; it is not an October correction.

---

## 10. Formats, money, controls and extract completeness

| Item | Quote (section) | What it means / check |
|---|---|---|
| Blank ≠ zero | "blank means missing/not applicable rather than zero. IDs are strings." (**SH · FORMATS**) | Read every column as a string first. A blank `billing_loaded_at` or `salesforce_account_id` carries information. |
| Intervals | "All normalized service intervals are start-inclusive/end-exclusive." (**SH · FORMATS**); "Visible service ends are inclusive" (**SH · PAYMENT AND DATE DISPLAY**) | The PDF says "August 31, 2027"; the register says `2027-09-01`. Day counts use end-exclusive arithmetic. |
| Money | "Stripe amount/subtotal/total/discount fields are integer USD cents; unit_amount_decimal is decimal cents per unit. NetSuite amounts are decimal USD. Use exact decimal arithmetic, round half up." (**SH · MONEY**) | 2,400,000 means $24,000.00. `unit_amount_decimal` "12.00" means $0.12 per run. |
| Population | "30 customers, 32 product accounts, 30 executed order forms, 2 amendments; 1,924 unique source daily usage records across 61 dates … 120 customer opening-account rows; 362 existing plan-period rows." (**SH · RECONCILIATION POPULATION**) | The data confirms 1,924 unique of 1,925 physical rows, 32 mapping rows, 120 opening rows and 362 plan rows. |
| Batch controls | "September 1-14 source batches have 30 records/day; September 15-October 31 have 32." "Reconcile after deduplication, not after dropping unmatched customers." (**SH · CONTROLS**, **FILE DICTIONARY**) | Control totals *include* the unverified workspace. Reconcile before excluding it, and remove only the duplicate. |
| Opening balances | "Opening balances include accounts 1100, 1150, 1160 and 2200 for every customer, including zeros." (**SH · CONTROLS**) | 30 × 4 = 120. Sept 30 1160 is 0 for all. |
| Plan joins | "September recognition journal IDs in plans are historical references outside the GL period; October recognized plan rows must join included postings. Future plan rows are context." (**SH · CONTROLS**) | 30 Oct plan rows carry `Journal Internal ID`s that must exist in the GL. The 30 Sep rows reference `SEP-REV-*` and are not expected in the GL. |
| Extract completeness | "These are all issued invoices and credit notes … Source report row counts: contract_register.csv = 32, netsuite_gl_detail.csv = 340, … stripe_invoices.csv = 124. Compare these counts to the supplied files; they do not establish that a commercially required invoice was actually issued." (**SH · EXTRACT COMPLETENESS**) | Row counts prove the *extract* is complete, not that billing is complete. A missing Meridian catch-up or Yarrow usage invoice is a business finding, not an extract gap. |
| Products | "prod_platform = platform subscription; prod_workflow_run = workflow-run overage. Price IDs are customer-specific. Product-account labels are display text, not a substitute for verified mappings." (**SH · PRODUCTS**) | Don't map workspaces by label text. |
| Out of scope | "Tax, FX, collections, cash settlement, processing fees, marketplace sales, breakage and complex multi-obligation arrangements are excluded." (**SH · COMPANY RULES**) | Unpaid status is never a finding by itself. |

---

## 11. When a billing correction does not need another October revenue adjustment

> Brief requirement: "Explain when a billing correction does not require another October revenue adjustment." (**Brief · What Your Build Should Do · 3**)
> Supporting rules: "Recognize platform consideration … independent of invoice frequency" (**SH · ACCOUNTING**); "The next-month invoice is Dr 1100 / Cr 1150, not revenue again" (**SH · ACCOUNTING**); "A November credit can reduce AR and reverse the corresponding release of unbilled usage without reducing revenue a second time" (**SH · CREDITS**); "Approved reductions of October consideration affect October where not already reflected" (**SH · CREDITS**).

**General rule (derived).** Invoices and credit notes never post to revenue in this policy. Platform billing posts to 1100/2200, and usage billing posts to 1100/1150. October revenue is set only by:

- (i) platform recognition = days/365 × the contract consideration in effect;
- (ii) the usage accrual = the contractual overage on validated usage, net of *approved* concessions.

So:

> **A billing correction needs an October revenue adjustment only if October's booked revenue (recognition + accrual) differs from what the contract, validated usage and approvals support. If booked revenue is already right, the correction is purely a balance-sheet movement (1100 ↔ 1150 or 1100 ↔ 2200/1160), posted when the document is issued in November.**

Test, per customer and per stream: compare *booked October revenue* with *supportable October revenue*. Don't compare billed with expected.

| Case (real data) | Billing correction (November date) | October revenue entry? | Why |
|---|---|---|---|
| Beacon Marsh: invoice $100 short, accrual right | Supplemental invoice $100, Dr 1100 / Cr 1150 | **No** | The accrual of $1,444.30 is already correct, and the invoice just clears the 1150 residual. |
| Zephyr Grove: approved $100 concession | Credit note $100 (already issued), Dr 1150 / Cr 1100 | **No** | The October accrual was already net (852.60). "Do not apply a second concession" (MSG-2026-109). |
| Alder: $50 credit note voided | None | **No** | A void note has no effect. |
| Meridian Nov 1 platform invoice $4,000 instead of $5,000 | Supplemental invoice $1,000 (follow-up) | **No** (for October) | November service; recognition is independent of invoicing. |
| Any platform invoice timing difference (e.g. 15th anchor) | None | **No** | Recognition is days/365 regardless of anchor. The gap shows up only in 2200/1160. |
| Cedar Harbor: overbilled $3,096.80, accrual copied the bill | Linked credit note $3,096.80 | **Yes**: Dr 4010 / Cr 1150 3,096.80 (October) | The accrual (revenue) was overstated. |
| Juniper Signal: wrong rate | Supplemental invoice $3,135.22 | **Yes**: Dr 1150 / Cr 4010 3,135.22 | The accrual was understated. |
| Yarrow Ridge: no usage invoice, no accrual | Supplemental invoice $3,074.28 | **Yes**: Dr 1150 / Cr 4010 3,074.28 | No accrual was booked. |
| Meridian: upgrade not loaded | Supplemental catch-up invoice $526.03 | **Yes**: Dr 2200 / Cr 4000 526.03, then incremental reclass Dr 1160 / Cr 2200 526.03 | Recognition omitted the increment. The October revenue change comes from the *contract*, not from the invoice. |
| Willow: $250 request, unapproved | None | **No** | "An unapproved concession request alone does not authorize a credit or revenue reduction." |
| Unverified workspace | None (Needs Info) | **No** | Exposure is conditional; it is not booked. |

Corollary: where a revenue entry *is* needed, it is booked **once**, in October. The later November billing document then only clears 1150 or 2200/1160, which is the meaning of "without reducing revenue a second time".

---

## 12. Open questions (text doesn't settle the treatment)

1. **Approach B day basis.** Does the allocation denominator use the invoice's own billing-period days (30/31) or 365? Recommend billing-period days and stating the basis (§4a).
2. **15th-anchor "expected October billing".** Are both overlapping invoices expected October billing, or only the one issued in October (§4b)?
3. **"Signed overage rate".** Does it mean the contract (executed) rate or a sign convention? Recommend the former (§2.4).
4. **Conflicting duplicate versions.** If a repeated `record_id` carries different content, which wins? There is no rule and no case this month; stop and raise Needs Info (§2.1).
5. **Conditional exposure pricing for unverified usage.** Show it per candidate owner, as a range, or as unpriced runs (§2.5)?
6. **Platform credit-note posting.** What is the pattern? Not specified; Dr 2200 / Cr 1100 by analogy (§7a).
7. **Reclass presentation.** Gross (reverse + rebook) or net incremental? Recommend net, with the gross calculation shown (§6.3).
8. **1150 residuals at Oct 31.** Leave them in November (the reading here), or propose an October entry? The policy's "may remain" suggests leaving them (§6.2).
9. **"Additional October-service charge" scope.** Platform only (the reading here), or also October-service usage invoices (§3.3)?
10. **"Issued by cutoff".** Use `created` or `finalized_at`? They are identical this month (§3.4).
