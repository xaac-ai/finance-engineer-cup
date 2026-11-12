# Finance Engineer Cup II: Billing Battle — Round 1

Source: https://numeric.notion.site/Finance-Engineer-Cup-II-Billing-Battle-Round-1-Challenge-Draft-40839a8f056781e4ae57e8e132aeb1da
Data: https://drive.google.com/drive/folders/1n5SKaQWqQH9k34n35Qbye0UxkWD-oYYw (mirrored in `data/raw/`)
Submit to: nigel@numeric.io — working build, results, run instructions, 3–5 min Loom.

## Scenario
Revenue Accounting Manager at RelayCloud (fictional B2B SaaS). Annual platform subscription
(upfront or monthly billing) + monthly workflow-run usage overage. Salesforce (customers),
Stripe Billing (invoices), NetSuite (books), internal metering (usage). Closing October 2026.

Controller Priya: "Tell me what we should have billed, which differences need action, and
whether anything changes October's accounting. Then show me how we can catch this next month."

## The build must
1. **Reconstruct expected billing** from contract terms + validated usage; compare to actual per
   customer, platform and usage shown separately.
2. **Explain findings & recommend next steps**: error / valid explanation / needs info; customer,
   period, amount, evidence, action.
3. **Explain what changes October's books**: under- and overbilling separately; proposed October
   JEs with calculations; explain when a billing correction needs no extra October revenue entry.
4. **Support review & rerun**: completeness checks, reconciliation totals, assumptions, unresolved
   issues; traceable to source; rerunnable on a new month.

## Scoring (100)
| Stat | Pts | Focus |
|---|---|---|
| ACCT'G INTEL | 25 | Contract interpretation, billing vs revenue effects, prioritization, follow-up |
| BUILD | 25 | Functional, usable, rerunnable workflow |
| DATA | 20 | Customer mappings, effective dates, usage validation, source reconciliation |
| CONTROLS | 15 | Completeness, traceable calcs, visible uncertainty, no duplicate/unsupported corrections |
| STACK | 15 | Tools used well, sensible complexity, maintainable |

## Key rules
- Don't invent terms or force mappings. Don't mix confirmed corrections with hypothetical exposure.
- Proposed billing docs: November issue dates. October-service accounting adjustments: October period.
- Out of scope: tax, FX, collections, cash, fees, marketplace, breakage, multi-PO arrangements.
- Policies live in `data/raw/START_HERE.pdf`; approvals/context in `data/raw/billing_followups.pdf`.
