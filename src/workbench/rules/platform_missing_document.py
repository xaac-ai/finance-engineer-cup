"""Error: an expected platform billing document covering the period was never issued
(e.g. an Amendment's additional October-service catch-up charge)."""

from workbench.findings import CalcStep, Claim, Evidence, Finding
from workbench.streams import platform as p


def detect(ctx):
    out = []
    for d in p.documents(ctx):
        if d["actual"] is not None or not d["expected"]:
            continue
        catch_up = d["kind"] == "catch_up"
        key = "PLATFORM-MISSING-CATCH-UP" if catch_up else f"PLATFORM-MISSING-INVOICE-{d['service_start']:%Y%m%d}"
        what = (f"{'Upgrade catch-up' if catch_up else 'Platform invoice'} for {d['service_start']} to "
                f"{d['service_end_exclusive']} (end-exclusive)")
        doc, entry = p.november_billing(ctx, d["expected"], d["service_start"], d["service_end_exclusive"], None, what)
        ev = [Evidence("contract_term", f"data/raw/{ctx.period.key}/contracts/{d['source_document']}.pdf", None,
                       next(r["source_quote"] for r in ctx.rows(
                           "SELECT source_quote FROM platform_expected_documents WHERE customer_id = ? AND doc_key = ?", [d["customer_id"], d["doc_key"]])),
                       "expected charge")]
        ev += p.register_evidence(ctx, d["source_document"])
        ev.append(Evidence("csv_row", f"data/raw/{ctx.period.key}/stripe_invoice_lines.csv", None,
                           f"No platform line for {d['customer_name']} with service period {d['doc_key']} issued by cutoff",
                           "absence in Stripe"))
        ev.append(p.start_here(ctx, "REQUIRED SCOPE", "For advance subscriptions, reconcile the invoice billing periods "
                               "covering October and identify any additional October-service charges."))
        out.append(Finding(
            rule="platform_missing_document", key=key, customer_id=d["customer_id"], stream="platform",
            service_period=ctx.period.key, status="error",
            title=f"{'October upgrade catch-up' if catch_up else 'Platform invoice'} of ${p.money(d['expected'])} not invoiced",
            summary=(f"{d['source_document']} requires {what.lower()} of ${p.money(d['expected'])}. No such charge was "
                     f"issued in Stripe by cutoff."),
            action=f"Issue a supplemental invoice of ${p.money(d['expected'])} dated {doc.issue_date}.",
            billing_effect=d["expected"], october_revenue_effect=p.ZERO,
            no_october_entry_reason=("Platform revenue is recognised by service days / 365, independent of invoicing; "
                                     "any October recognition correction is its own Finding."),
            calculations=(CalcStep("Expected charge", f"per {d['source_document']}", p.money(d["expected"])),
                          CalcStep("Issued by cutoff", "Stripe platform lines for this service period", "0.00"),
                          CalcStep("Billing Effect", "expected − issued", p.money(d["expected"]))),
            evidence=tuple(ev), claims=(Claim("billing", "platform", d["expected"]),),
            documents=(doc,), entries=(entry,),
        ))
    return out
