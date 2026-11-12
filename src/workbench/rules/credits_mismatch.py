"""Error: issued usage credits for the month differ from the approved concessions
(a credit without approval, or an approval never credited). None this month."""

from workbench.findings import CalcStep, Claim, Evidence, Finding
from workbench.streams import usage as u


def detect(ctx):
    out = []
    for r in ctx.rows("""
        WITH a AS (SELECT customer_id, sum(amount) AS approved, string_agg(message_id, ', ') AS messages
                   FROM approved_concessions WHERE stream = 'usage' AND service_period = ? GROUP BY ALL),
             c AS (SELECT customer_id, sum(amount) AS credited, string_agg(number, ', ') AS notes,
                          min(source_file) AS source_file, min(source_line) AS source_line
                   FROM usage_credit_notes WHERE effective GROUP BY ALL)
        SELECT coalesce(a.customer_id, c.customer_id) AS customer_id, coalesce(approved, 0) AS approved,
               coalesce(credited, 0) AS credited, messages, notes, source_file, source_line
        FROM a FULL JOIN c USING (customer_id) WHERE coalesce(approved, 0) <> coalesce(credited, 0)""", [ctx.period.key]):
        effect = r["credited"] - r["approved"]  # expected − actual
        if effect > 0:
            title, action = f"${r['credited']:,} usage credit issued without a matching approval", \
                "Obtain and cite the Controller approval, or reverse the unapproved credit with a supplemental invoice."
        else:
            title, action = f"Approved ${r['approved']:,} usage concession not credited", \
                f"Issue the approved credit note (${-effect:,}) against the October usage invoice."
        ev = [Evidence("csv_row", r["source_file"], r["source_line"], f"credit notes: {r['notes']}", "credit note")] \
            if r["notes"] else [Evidence("billing_message", f"data/raw/{ctx.period.key}/billing_followups.pdf", None,
                                         f"approved in {r['messages']}", "approval")]
        out.append(Finding(
            rule="credits_mismatch", key="CREDIT-MISMATCH", customer_id=r["customer_id"], stream="usage",
            service_period=ctx.period.key, status="error", title=title,
            summary=f"Approved concessions {r['approved']:,} ({r['messages'] or 'none'}); issued credits {r['credited']:,} ({r['notes'] or 'none'}).",
            action=action, billing_effect=effect, october_revenue_effect=u.ZERO,
            no_october_entry_reason="Billing-only: the October accrual follows the approval, not the credit note.",
            calculations=(CalcStep("Approved", r["messages"] or "none", f"{r['approved']:,}"),
                          CalcStep("Credited", r["notes"] or "none", f"{r['credited']:,}"),
                          CalcStep("Billing Effect", "credited − approved", f"{effect:,}")),
            evidence=tuple(ev), claims=(Claim("billing", "usage", effect),),
        ))
    return out
