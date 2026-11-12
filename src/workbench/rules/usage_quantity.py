"""Error: the usage invoice billed a different overage quantity than the validated usage known when it was issued.

Not seen in October's supplied data; surfaced by the `extra-usage` Scenario (records known at invoice time
but left off the invoice). Over-billed quantity gives a negative Billing Effect and a credit note.
"""

from workbench.findings import CalcStep
from workbench.streams import usage as u

KEY = u.QUANTITY


def detect(ctx):
    out = []
    for m in u.analyse(ctx):
        if KEY not in m.effects:
            continue
        ln, known = m.lines[0], m.units_known_at_invoice or 0
        should = max(0, known - m.allowance)
        billing, _ = m.effects[KEY]
        under = billing > 0
        out.append(u.error_finding(
            ctx, m, KEY, "usage_quantity",
            title=f"October usage invoice bills {ln.quantity:,} overage runs; validated usage gives {should:,}",
            summary=(f"{ln.invoice_number} was created {ln.invoice_created:%Y-%m-%d %H:%M} and bills {ln.quantity:,} overage runs. "
                     f"Validated usage known by then was {known:,} runs against a {m.allowance:,} allowance, so "
                     f"{should:,} overage runs. No allowance, approval or late record explains the "
                     f"{abs(should - ln.quantity):,}-run difference."),
            action=(f"Issue a supplemental invoice of ${billing:,} for the unbilled October runs" if under else
                    f"Issue a credit note of ${-billing:,} for the over-billed October runs")
                   + "; correct the October accrual if it repeated the invoice; find why the invoice run missed records.",
            calculations=(
                CalcStep("Validated runs known at invoice", "deduplicated, active, mapped, ingested before the invoice", f"{known:,}"),
                CalcStep("Overage runs", f"max(0, {known:,} − {m.allowance:,})", f"{should:,}"),
                CalcStep("Billed overage runs", "invoice quantity", f"{ln.quantity:,}"),
                CalcStep("Billing Effect", f"({should:,} − {ln.quantity:,}) × ${m.rate}, rounded once half up", f"{billing:,}"),
            ),
            evidence=u.evidence(ctx, m),
        ))
    return out
