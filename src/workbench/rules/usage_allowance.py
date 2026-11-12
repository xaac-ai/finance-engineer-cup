"""Error: October usage billed (and accrued) on an allowance that was not in force for the month.

Detected when the invoiced quantity implies an allowance (runs known at invoicing − billed runs) that
is one of the contract's allowances but not the month's day-weighted one (e.g. an Amendment that
never reached billing).
"""

from workbench.findings import CalcStep
from workbench.streams import usage as u

KEY = "USAGE-ALLOWANCE"


def detect(ctx):
    out = []
    for m in u.analyse(ctx):
        if KEY not in m.effects:
            continue
        ln, known = m.lines[0], m.units_known_at_invoice
        used = known - ln.quantity
        billing, _ = m.effects[KEY]
        out.append(u.error_finding(
            ctx, m, KEY, "usage_allowance",
            title=f"October usage billed on the {used:,}-run allowance instead of {m.allowance:,}",
            summary=(f"{ln.invoice_number} charges {ln.quantity:,} runs = {known:,} − {used:,}, the allowance before the "
                     f"Amendment. The executed terms give an October allowance of {m.allowance:,} "
                     f"({m.allowance_formula}). The October accrual repeated the invoice."),
            action=f"Issue a credit note of ${-billing:,} against {ln.invoice_number}; correct the October accrual; "
                   f"load the Amendment's allowance into billing before December 1.",
            calculations=(
                CalcStep("Validated October runs", "sum of unique active records on verified accounts", f"{known:,}"),
                CalcStep("October allowance", m.allowance_formula, f"{m.allowance:,}"),
                CalcStep("Expected charge", f"max(0, {known:,} − {m.allowance:,}) × ${m.rate}", f"{m.expected_billing:,}"),
                CalcStep("Billed", f"{ln.quantity:,} × ${u.price(ln.unit_price)} (implies allowance {used:,})", f"{ln.gross:,}"),
                CalcStep("Billing Effect", "expected − billed", f"{billing:,}"),
            ),
            evidence=u.evidence(ctx, m) + [u.start_here(
                ctx, "USAGE", "For an allowance amendment, weight each allowance by applicable calendar days and round once.", "policy")],
        ))
    return out
