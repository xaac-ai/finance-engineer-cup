"""Error: usage ingested after the usage invoice was created is missing from the invoice.

The accrual (prepared later) may already include it; then there is no October entry and the residual
in 1150 is cleared by a November supplemental invoice.
"""

from workbench.findings import CalcStep, Evidence
from workbench.streams import usage as u

KEY = u.LATE


def detect(ctx):
    out = []
    for m in u.analyse(ctx):
        if KEY not in m.effects:
            continue
        ln, known = m.lines[0], m.units_known_at_invoice
        late_units = sum(int(r["units"]) for r in m.late_records)
        billing, _ = m.effects[KEY]
        late_ev = [Evidence("csv_row", r["source_file"], r["source_line"],
                            f"{r['record_id']} {r['product_account_id']} {r['service_date']}: {r['units']:,} runs, "
                            f"ingested {r['ingested_at']:%Y-%m-%d %H:%M}", "late record") for r in m.late_records]
        out.append(u.error_finding(
            ctx, m, KEY, "usage_late_record",
            title=f"{late_units:,} October runs ingested after the usage invoice was issued",
            summary=(f"{ln.invoice_number} was created {ln.invoice_created:%Y-%m-%d %H:%M} and billed the {known:,} runs known "
                     f"then. {len(m.late_records)} October record(s) with {late_units:,} runs arrived later but before cutoff, "
                     f"so the invoice is short."),
            action=f"Issue a supplemental invoice of ${billing:,} for the late October usage.",
            calculations=(
                CalcStep("Runs known when invoiced", f"records ingested by {ln.invoice_created:%Y-%m-%d %H:%M}", f"{known:,}"),
                CalcStep("Late runs (before cutoff)", "records ingested after the invoice", f"{late_units:,}"),
                CalcStep("Expected charge", f"max(0, {m.units:,} − {m.allowance:,}) × ${m.rate}", f"{m.expected_billing:,}"),
                CalcStep("Charge on runs known at invoicing", f"max(0, {known:,} − {m.allowance:,}) × ${m.rate}",
                         f"{u.charge(known, m.allowance, m.rate):,}"),
                CalcStep("Billing Effect", "expected − charge on known runs", f"{billing:,}"),
            ),
            evidence=u.evidence(ctx, m) + late_ev + [u.start_here(
                ctx, "TIMING", "Source activity, ingestion timestamp, invoice issue date, service period, GL posting period "
                "and GL Created At are distinct.", "policy")],
        ))
    return out
