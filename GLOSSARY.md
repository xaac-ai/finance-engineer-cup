# RelayCloud Billing Review

The October 2026 billing-to-contract review for RelayCloud: what should have been billed, what was billed, and what changes the books.

## Language

### Contracts

**Order Form**:
The executed document that establishes a customer's contract: term, billing frequency, platform fee, included runs, and overage rate.
_Avoid_: Contract PDF, OF (in prose)

**Amendment**:
An executed document that changes only the terms it expressly names on an existing Order Form, from its effective date; all other terms persist.
_Avoid_: Superseding contract, replacement order

**Contract Term**:
One commercial term of a contract (e.g. platform fee, included runs per month, overage rate) with the date range it applies to and the document and quote it comes from.
_Avoid_: Contract field, setting

**Drafted Term**:
A Contract Term proposed by the drafter agent from an Amendment's text. It has no effect until a person copies it into the curated terms.
_Avoid_: Extracted term, AI term

### Books

**Recorded Entry**:
A journal entry already posted in RelayCloud's general ledger (NetSuite) as supplied.
_Avoid_: Actual entry, booked JE

**Proposed Entry**:
A journal entry we recommend for Controller approval, tied to a finding; never posted by us.
_Avoid_: Adjustment (alone), correction entry, draft JE

**Opening Balance**:
A customer's balance in one account at the start of the review period, as supplied; a starting point, not an entry.
_Avoid_: Opening entry, beginning JE

### Usage

**Validated Usage**:
Workflow runs that count toward a customer's month: unique, active, unreplaced usage records on product accounts with a verified mapping to that customer, effective on the service date.
_Avoid_: Usage (alone) when meaning the billable count, metered runs

**Unverified Usage**:
Usage on a product account with no verified billing owner. It is isolated, never assigned to a customer by elimination, and reported as Needs Info.
_Avoid_: Orphan usage, unmapped customer usage

**Approved Concession**:
A reduction of a customer's consideration approved by the Controller in a Billing Message; it lowers the expected accrual for its service period exactly once.
_Avoid_: Discount, credit request

### Review

**Finding**:
A difference or issue the review surfaces for one customer and period, classified as an Error, a Valid Explanation, or Needs Info, with its amount (where supportable), evidence, and recommended action.
_Avoid_: Exception, discrepancy, issue (alone)

**Error**:
A Finding where billing departs from the applicable Contract Terms or validated usage with no approval or policy that explains it.
_Avoid_: Mistake, bug

**Valid Explanation**:
A Finding whose difference is accounted for by an approved term, credit, or timing rule, needing no correction.
_Avoid_: False positive, explained variance

**Needs Info**:
A Finding that cannot be resolved or quantified from the evidence supplied; it names what is missing and is never mixed into confirmed corrections.
_Avoid_: Open item (alone), pending, unknown

**Reconciliation**:
The comparison, for every customer and stream (platform, usage), of what was expected against what was billed, and of expected October revenue against what is booked; each nonzero difference must be explained by exactly one Finding.
_Avoid_: Variance report, diff

**Billing Effect**:
The signed amount a Finding says billing is off by: positive when underbilled, negative when overbilled; empty when not supportable.
_Avoid_: Billing variance, correction amount

**October Revenue Effect**:
The signed amount a Finding says October's booked revenue is off by; when zero, the Finding states why no October entry is needed.
_Avoid_: Revenue adjustment (alone), P&L impact

**Exposure**:
A conditional amount attached to a Needs Info Finding: what would be owed if the missing evidence came out one way. Never added to confirmed corrections.
_Avoid_: Potential error, estimate, at-risk amount

**Independent Review**:
A classification of every customer and stream by a second agent that never sees the Findings, compared with them field by field; the four-eyes principle applied to the review itself.
_Avoid_: Second opinion, AI audit

**Disagreement**:
A customer-stream where the Independent Review's status or amounts differ from the Findings. It stays open until a person resolves it with a reason.
_Avoid_: Mismatch, discrepancy

**Scenario**:
A copy of one period's inputs with one named, deliberate change, and the Findings that change should produce: a new or altered Finding for a change the review must catch, or identical results for a change it must ignore.
_Avoid_: Perturbation, fixture, data-change test

### Evidence

**Billing Message**:
A dated sales or billing communication (e.g. an approval, a request, a status note) identified by its message ID and cited as evidence.
_Avoid_: Email, follow-up, ticket
