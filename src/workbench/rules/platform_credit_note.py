"""Needs Info: an issued credit note against a platform line. START_HERE gives no posting pattern for
platform credits (wayfinder: "Which platform billing approach do we present?"), so we ask, not guess."""

from workbench.findings import Evidence, Finding
from workbench.streams import platform as p


def detect(ctx):
    out = []
    for n in ctx.rows("SELECT * FROM platform_credit_notes ORDER BY source_line"):
        amount = p.money(p.Decimal(n["amount_cents"]) * p.CENT)
        out.append(Finding(
            rule="platform_credit_note", key=f"PLATFORM-CREDIT-{n['number']}", customer_id=n["customer_id"],
            stream="platform", service_period=str(n["service_start"])[:7] or ctx.period.key, status="needs_info",
            title=f"Platform credit note {n['number']} (${amount}) needs its basis",
            summary=f"{n['number']} credits ${amount} against platform line {n['invoice_line_id']}: {n['description']}.",
            action="Billing to provide the approval and the service period credited; Revenue to confirm whether "
                   "consideration (and so recognition) changed.",
            exposure=f"Up to ${amount} of platform consideration, depending on the approval and service period.",
            evidence=(Evidence("csv_row", n["source_file"], n["source_line"], f"{n['number']} {n['status']} ${amount}",
                               "credit note"),),
        ))
    return out
