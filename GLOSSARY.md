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

### Evidence

**Billing Message**:
A dated sales or billing communication (e.g. an approval, a request, a status note) identified by its message ID and cited as evidence.
_Avoid_: Email, follow-up, ticket
