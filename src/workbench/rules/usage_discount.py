"""Error: a discount on a usage invoice line (START_HERE: prices are net, no additional invoice discounts)."""

from workbench.findings import CalcStep
from workbench.streams import usage as u

KEY = "USAGE-DISCOUNT"


def detect(ctx):
    out = []
    for m in u.analyse(ctx):
        if KEY not in m.effects:
            continue
        ln = m.lines[0]
        billing, _ = m.effects[KEY]
        out.append(u.error_finding(
            ctx, m, KEY, "usage_discount",
            title=f"Unsupported ${billing:,} discount on October usage",
            summary=f"{ln.invoice_number} carries a ${ln.discount:,} discount on the usage line with no approval cited.",
            action=f"Issue a supplemental invoice of ${billing:,}, or cite the approval that supports the discount.",
            calculations=(CalcStep("Discount on usage line", "discount_amount / 100", f"{ln.discount:,}"),),
            evidence=u.evidence(ctx, m) + [u.start_here(
                ctx, "USAGE", "Prices are negotiated net prices, with no additional invoice discounts.", "policy")],
        ))
    return out
