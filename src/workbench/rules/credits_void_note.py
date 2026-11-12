"""Valid Explanation: a void credit note has no current credit effect (START_HERE · CREDITS)."""

from workbench.approvals import message_evidence
from workbench.findings import Evidence, Finding
from workbench.streams import usage as u


def detect(ctx):
    out = []
    for n in ctx.rows("""SELECT n.id, n.number, n.status, n.created, n.voided_at, (CAST(n.amount AS BIGINT) * 0.01)::DECIMAL(18,2) AS amount,
            n.invoice_id, s."NetSuiteCustomerInternalId__c" AS customer_id, n.source_file, n.source_line,
            nl.description, nl.service_start, nl.source_file AS line_file, nl.source_line AS line_line,
            (SELECT count(*) FROM journal_lines j WHERE j.status = 'recorded' AND j.external_source_id = n.id) AS gl_lines
        FROM raw_stripe_credit_notes n JOIN raw_salesforce_accounts s ON s."StripeCustomerId__c" = n.customer_id
        LEFT JOIN raw_stripe_credit_note_lines nl ON nl.credit_note_id = n.id
        WHERE n.status = 'void' ORDER BY n.source_line"""):
        if n["gl_lines"]:
            continue  # a posted void note is not explained by its void status; reconciliation will show it
        msgs = ctx.rows("SELECT message_id FROM billing_messages WHERE body LIKE '%' || ? || '%' ORDER BY message_id", [n["id"]])
        out.append(Finding(
            rule="credits_void_note", key=f"CREDIT-VOID-{n['number']}", customer_id=n["customer_id"], stream="usage",
            service_period=str(n["service_start"])[:7] if n["service_start"] else ctx.period.key,
            status="valid_explanation",
            title=f"Void credit note {n['number']} (${n['amount']:,}) has no effect",
            summary=(f"{n['number']} was created {n['created'][:16]} and voided {n['voided_at'][:16]}. Void notes have no "
                     f"current credit effect, and nothing was posted to NetSuite."),
            action="None.", billing_effect=u.ZERO, october_revenue_effect=u.ZERO,
            no_october_entry_reason="Void notes have no current credit effect.",
            evidence=(Evidence("csv_row", n["source_file"], n["source_line"],
                               f"{n['number']} status {n['status']}, voided {n['voided_at']}, ${n['amount']:,}", "credit note"),
                      Evidence("csv_row", n["line_file"], n["line_line"], f"{n['description']}", "credit note line"),
                      Evidence("csv_row", f"data/raw/{ctx.period.key}/netsuite_gl_detail.csv", None,
                               f"No GL line has External Source ID {n['id']}", "not posted"),
                      *[message_evidence(ctx, m["message_id"], "explanation") for m in msgs],
                      u.start_here(ctx, "CREDITS", "Use issued notes only; void notes have no current credit effect.", "policy")),
        ))
    return out
