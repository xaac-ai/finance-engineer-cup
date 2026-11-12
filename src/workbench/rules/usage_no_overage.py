"""Valid Explanation: no October usage invoice because verified usage stayed within the allowance."""

from workbench.findings import CalcStep, Finding
from workbench.streams import usage as u

KEY = "USAGE-NO-OVERAGE"


def detect(ctx):
    out = []
    for m in u.analyse(ctx):
        if m.lines or m.expected_billing or not m.product_accounts:
            continue  # only customers with verified usage, no overage and no invoice
        out.append(Finding(
            rule="usage_no_overage", key=KEY, customer_id=m.customer_id, stream="usage", service_period=ctx.period.key,
            status="valid_explanation",
            title="No October usage invoice: usage within the allowance",
            summary=f"{m.units:,} validated October runs are within the {m.allowance:,}-run allowance, so no usage charge arises.",
            action="None.", billing_effect=u.ZERO, october_revenue_effect=u.ZERO,
            no_october_entry_reason="Nothing was billed or accrued, and nothing was owed.",
            calculations=(
                CalcStep("Validated October runs", "sum of unique active records on verified accounts", f"{m.units:,}"),
                CalcStep("October allowance", m.allowance_formula, f"{m.allowance:,}"),
                CalcStep("Expected charge", f"max(0, {m.units:,} − {m.allowance:,}) × ${m.rate}", "0.00"),
            ),
            evidence=tuple(u.evidence(ctx, m, invoice=False, accrual=False) + [u.start_here(
                ctx, "BILLING", "An absent usage invoice can be valid when no overage exists.", "policy")]),
        ))
    return out
