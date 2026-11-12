"""Error: October usage over the allowance with no usage invoice issued by cutoff."""

from workbench.findings import CalcStep
from workbench.streams import usage as u

KEY = "USAGE-MISSING-INVOICE"


def detect(ctx):
    out = []
    for m in u.analyse(ctx):
        if KEY not in m.effects:
            continue
        billing, revenue = m.effects[KEY]
        accrual = "and no October accrual was booked" if m.booked == 0 else f"and the October accrual is ${m.booked:,}"
        out.append(u.error_finding(
            ctx, m, KEY, "usage_missing_invoice",
            title=f"October usage of {m.overage_units:,} overage runs never invoiced",
            summary=(f"{m.units:,} validated October runs exceed the {m.allowance:,} allowance by {m.overage_units:,}. "
                     f"No usage invoice for October was issued by cutoff {accrual}."),
            action=f"Issue the October usage invoice (${billing:,}) with a November date; book the October accrual.",
            calculations=(
                CalcStep("Validated October runs", "sum of unique active records on verified accounts", f"{m.units:,}"),
                CalcStep("October allowance", m.allowance_formula, f"{m.allowance:,}"),
                CalcStep("Expected charge", f"max(0, {m.units:,} − {m.allowance:,}) × ${m.rate}", f"{m.expected_billing:,}"),
                CalcStep("Billed", "no usage invoice for 2026-10-01 to 2026-11-01", "0.00"),
            ),
            evidence=u.evidence(ctx, m) + [u.usage_quote(ctx), u.start_here(
                ctx, "BILLING", "An absent usage invoice can be valid when no overage exists.", "policy (overage exists here)")],
        ))
    return out
