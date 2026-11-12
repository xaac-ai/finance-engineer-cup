"""Error: October usage invoiced at a unit price other than the executed overage rate."""

from workbench.findings import CalcStep
from workbench.streams import usage as u

KEY = "USAGE-RATE"


def detect(ctx):
    out = []
    for m in u.analyse(ctx):
        if KEY not in m.effects:
            continue
        ln = m.lines[0]
        billing, _ = m.effects[KEY]
        out.append(u.error_finding(
            ctx, m, KEY, "usage_rate",
            title=f"October usage priced at ${u.price(ln.unit_price)} per run instead of ${m.rate}",
            summary=(f"{ln.invoice_number} prices {ln.quantity:,} overage runs at ${u.price(ln.unit_price)}; the Order Form "
                     f"rate is ${m.rate} and no Amendment or approval changes it. Prices are net, with no further discounts. "
                     f"The October accrual repeated the invoice."),
            action=f"Issue a supplemental invoice of ${billing:,} for October usage; correct the October accrual; "
                   f"fix the customer's price in billing.",
            calculations=(
                CalcStep("Billed overage runs", "invoice quantity (agrees with validated usage)", f"{ln.quantity:,}"),
                CalcStep("At contract rate", f"{ln.quantity:,} × ${m.rate}", f"{u.round_cents(ln.quantity * m.rate):,}"),
                CalcStep("Billed", f"{ln.quantity:,} × ${u.price(ln.unit_price)}", f"{ln.gross:,}"),
                CalcStep("Billing Effect", "contract − billed", f"{billing:,}"),
            ),
            evidence=u.evidence(ctx, m) + [u.start_here(
                ctx, "USAGE", "Prices are negotiated net prices, with no additional invoice discounts.", "policy")],
        ))
    return out
