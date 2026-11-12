"""Needs Info: a concession request with no Controller approval. No credit, no revenue reduction.

START_HERE · UNVERIFIED USAGE: "An unapproved concession request alone does not authorize a credit
or revenue reduction."
"""

from workbench.approvals import message_evidence
from workbench.findings import Finding
from workbench.streams import usage as u


def detect(ctx):
    out = []
    for r in ctx.rows("""SELECT q.* FROM concession_requests q WHERE q.service_period = ? AND NOT EXISTS (
            SELECT 1 FROM approved_concessions a WHERE a.customer_id = q.customer_id AND a.stream = q.stream
              AND a.service_period = q.service_period)""", [ctx.period.key]):
        out.append(Finding(
            rule="credits_concession_request", key=f"CREDIT-REQUEST-{r['message_id']}", customer_id=r["customer_id"],
            stream=r["stream"], service_period=r["service_period"], status="needs_info",
            title=f"Unapproved ${r['amount']:,} {r['stream']} concession request",
            summary=(f"{r['message_id']} records a request for ${r['amount']:,} off {r['stream']} with no Controller approval. "
                     f"No credit has been issued and none is proposed; the request does not establish ownership of "
                     f"any unverified workspace."),
            action="Controller to approve or decline. If approved, issue a credit note against the service month and "
                   "reduce that month's consideration once.",
            exposure=f"${r['amount']:,} reduction of {r['service_period']} {r['stream']} consideration, only if approved.",
            evidence=(message_evidence(ctx, r["message_id"], "request (no approval)"),
                      u.start_here(ctx, "UNVERIFIED USAGE", "An unapproved concession request alone does not authorize a "
                                   "credit or revenue reduction.", "policy")),
        ))
    return out
