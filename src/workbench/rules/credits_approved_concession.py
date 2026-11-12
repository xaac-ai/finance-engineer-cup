"""Valid Explanation: an approved concession already reflected once (accrual net of it, credit note issued).

START_HERE · CREDITS: "Approved reductions of October consideration affect October where not already
reflected. A November credit can reduce AR and reverse the corresponding release of unbilled usage
without reducing revenue a second time."
"""

from workbench.approvals import message_evidence
from workbench.findings import CalcStep, Evidence, Finding
from workbench.streams import usage as u


def detect(ctx):
    out = []
    months = {m.customer_id: m for m in u.customer_months(ctx)}
    for c in ctx.rows("SELECT * FROM approved_concessions WHERE stream = 'usage' AND service_period = ?", [ctx.period.key]):
        notes = ctx.rows("SELECT * EXCLUDE (created_local, voided_local), created_local::VARCHAR AS created "
                         "FROM usage_credit_notes WHERE customer_id = ? AND effective", [c["customer_id"]])
        credited = sum((n["amount"] for n in notes), u.ZERO)
        if credited != c["amount"]:
            continue  # credits_mismatch explains it
        m = months[c["customer_id"]]
        requests = ctx.rows("""SELECT message_id FROM billing_messages WHERE message_id <> ? AND body ILIKE '%' || ? || '%'
            AND body ILIKE '%request%' ORDER BY message_id""", [c["message_id"], m.customer_name.split(",")[0]])
        ev = [message_evidence(ctx, r["message_id"], "request") for r in requests]
        ev.append(message_evidence(ctx, c["message_id"], "Controller approval"))
        for n in notes:
            ev.append(Evidence("csv_row", n["source_file"], n["source_line"],
                               f"{n['number']} issued {n['created'][:16]}: ${n['amount']:,} against {n['invoice_number']}", "credit note"))
            ev.append(Evidence("csv_row", n["line_source_file"], n["line_source_line"],
                               f"{n['description']}; service {n['service_start']} to {n['service_end_exclusive']} "
                               f"({n['service_period_source']})", "credit note line"))
            ev += [Evidence("csv_row", g["source_file"], g["source_line"],
                            f"{g['document_number']} {g['posting_period']} {g['account_number']}: Dr {g['debit']} Cr {g['credit']} {g['memo']}",
                            "credit memo posted")
                   for g in ctx.rows("""SELECT source_file, source_line, document_number, posting_period, account_number,
                       debit, credit, memo FROM journal_lines WHERE status = 'recorded' AND external_source_id = ?
                       ORDER BY source_line""", [n["credit_note_id"]])]
        ev += u.evidence(ctx, m, terms=False)
        out.append(Finding(
            rule="credits_approved_concession", key="CREDIT-APPROVED-CONCESSION", customer_id=c["customer_id"],
            stream="usage", service_period=ctx.period.key, status="valid_explanation",
            title=f"Approved ${c['amount']:,} October usage concession, reflected once",
            summary=(f"The Controller approved a ${c['amount']:,} reduction of October usage consideration ({c['message_id']}). "
                     f"The October accrual (${m.booked:,}) is already net of it, and credit note "
                     f"{', '.join(n['number'] for n in notes)} reduced the November receivable and reversed the over-release "
                     f"of unbilled usage. Revenue was reduced once, in October."),
            action="None. Do not apply a second concession.",
            billing_effect=u.ZERO, october_revenue_effect=u.ZERO,
            no_october_entry_reason="The October accrual is already net of the approved concession.",
            calculations=(
                CalcStep("Contract usage charge", f"max(0, {m.units:,} − {m.allowance:,}) × ${m.rate}", f"{m.expected_billing:,}"),
                CalcStep("Approved concession", c["message_id"], f"{-c['amount']:,}"),
                CalcStep("Expected October consideration", "charge − concession", f"{m.expected_revenue:,}"),
                CalcStep("October accrual booked", "GL 4010", f"{m.booked:,}"),
                CalcStep("Net billed", f"invoice {m.billed:,} − credit {credited:,}", f"{m.billed - credited:,}"),
            ),
            evidence=tuple(ev + [u.start_here(ctx, "CREDITS", "Approved reductions of October consideration affect October "
                                              "where not already reflected.", "policy")]),
        ))
    return out
