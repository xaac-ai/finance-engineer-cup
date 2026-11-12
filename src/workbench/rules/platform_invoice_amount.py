"""Error: a platform invoice's amount differs from the contract amount in force at its service start.

For documents covering the review period the difference is claimed. Invoices for later service are
follow-ups (MSG-2026-119: "later-service issues are follow-ups"), kept out of the period's totals.
"""

from datetime import date
from decimal import Decimal

from workbench.findings import CalcStep, Claim, Evidence, Finding
from workbench.streams import platform as p


def _contract_amount(ctx, customer_id: str, on: date):
    rows = ctx.rows("""SELECT t.value, t.source_document, t.source_quote FROM contract_terms t
        JOIN raw_contract_register r ON r.contract_id = t.contract_id AND r.document_type = 'order_form'
        JOIN raw_salesforce_accounts s ON s."AccountId" = r.salesforce_account_id
        WHERE s."NetSuiteCustomerInternalId__c" = ? AND t.term = 'platform_invoice_amount'
          AND t.effective_from <= ? AND t.effective_to_exclusive > ?""", [customer_id, on, on])
    return rows[0] if rows else None


def _finding(ctx, line, expected, term, *, follow_up):
    diff = expected - line["actual"]
    service = f"{line['service_start']:%Y-%m}"
    ev = (Evidence("csv_row", line["source_file"], line["source_line"],
                   f"{line['invoice_number']} {line['line_id']}: ${p.money(line['actual'])} for {line['doc_key']}", "invoice billed"),
          Evidence("contract_term", f"data/raw/{ctx.period.key}/contracts/{term['source_document']}.pdf", None,
                   term["source_quote"], "contract amount"),
          *p.register_evidence(ctx, term["source_document"]))
    common = dict(rule="platform_invoice_amount", key="PLATFORM-INVOICE-AMOUNT", customer_id=line["customer_id"],
                  stream="platform", service_period=service, status="error", billing_effect=diff,
                  october_revenue_effect=p.ZERO, evidence=ev,
                  calculations=(CalcStep("Contract amount", f"per {term['source_document']}", p.money(expected)),
                                CalcStep("Invoiced", line["invoice_number"], p.money(line["actual"])),
                                CalcStep("Difference", "contract − invoiced", p.money(diff))))
    if follow_up:
        return Finding(**common, follow_up=True,
                       title=f"Later-service platform invoice {line['invoice_number']} is ${p.money(line['actual'])}, "
                             f"contract says ${p.money(expected)}",
                       summary=(f"{line['invoice_number']} bills {line['doc_key']} at ${p.money(line['actual'])}; the executed "
                                f"terms in force from {line['service_start']} give ${p.money(expected)}. This is later service: "
                                f"flagged as a follow-up, not part of the {ctx.period.label} totals."),
                       action=f"Follow up: issue a supplemental invoice or credit note for {p.money(diff)} and load the "
                              f"Amendment's billing terms before the next invoice.",
                       no_october_entry_reason=f"Later-service billing ({service}); no {ctx.period.label} effect.")
    doc, entry = p.november_billing(ctx, diff, line["service_start"], line["service_end_exclusive"], line["invoice_number"],
                                    f"Correct platform billing on {line['invoice_number']}")
    return Finding(**common, claims=(Claim("billing", "platform", diff),), documents=(doc,), entries=(entry,),
                   title=f"Platform invoice {line['invoice_number']} is ${p.money(line['actual'])}, contract says ${p.money(expected)}",
                   summary=f"{line['invoice_number']} bills {line['doc_key']} at ${p.money(line['actual'])} instead of ${p.money(expected)}.",
                   action=f"Issue a {'supplemental invoice' if diff > 0 else 'credit note'} for {p.money(abs(diff))}.",
                   no_october_entry_reason="Platform revenue is recognised by service days / 365, independent of invoicing.")


def detect(ctx):
    out = []
    for d in p.documents(ctx):
        if d["expected"] is not None and d["actual"] is not None and d["difference"]:
            term = _contract_amount(ctx, d["customer_id"], d["service_start"])
            out.append(_finding(ctx, d, d["expected"], term, follow_up=False))
    for ln in ctx.rows("""SELECT customer_id, invoice_number, line_id, service_start, service_end_exclusive,
            service_start || '..' || service_end_exclusive AS doc_key, (amount_cents * 0.01)::DECIMAL(18,2) AS actual,
            source_file, source_line
        FROM platform_invoice_lines WHERE service_start >= getvariable('period_end') ORDER BY source_line"""):
        term = _contract_amount(ctx, ln["customer_id"], ln["service_start"])
        if term and Decimal(term["value"]) != ln["actual"]:
            out.append(_finding(ctx, ln, Decimal(term["value"]), term, follow_up=True))
    return out
