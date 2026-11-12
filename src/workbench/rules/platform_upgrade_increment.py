"""Error: October platform recognition omits an Amendment's upgrade increment.

START_HERE · ACCOUNTING: preserve the base schedule, add the increment as its own component; then
recompute the customer's 2200 net debit and propose only the incremental 1160 reclass.
"""

from workbench.findings import CalcStep, Claim, Evidence, Finding, ProposedEntry, ProposedLine
from workbench.streams import platform as p


def detect(ctx):
    out = []
    recon = {r["customer_id"]: r for r in ctx.rows(
        "SELECT * FROM revenue_reconciliation WHERE stream = 'platform'")}
    position = {r["customer_id"]: r for r in ctx.rows("SELECT * FROM platform_contract_position")}
    for k in p.contracts(ctx):
        incs = [c for c in k.components if c.name.startswith("increment") and c.amount]
        r = recon[k.customer_id]
        missing = sum((c.amount for c in incs), p.ZERO)
        if not incs or r["difference"] != missing:
            continue
        base = next(c for c in k.components if c.name == "base")
        pos = position[k.customer_id]
        pre = pos["pre_reclass_2200_credit"] - missing
        required = max(p.ZERO, -pre)
        reclass = required - pos["booked_1160"]
        day = p.period_end(ctx)
        entries = [ProposedEntry("proposed_october_adjustment", day, ctx.period.label, (
            ProposedLine("2200", debit=missing, memo="Recognise October upgrade increment"),
            ProposedLine("4000", credit=missing, memo="October platform revenue, upgrade increment")),
            "START_HERE · ACCOUNTING: Recognition Dr 2200 / Cr 4000; increment as its own component")]
        if reclass:
            dr, cr = ("1160", "2200") if reclass > 0 else ("2200", "1160")
            entries.append(ProposedEntry("proposed_october_adjustment", day, ctx.period.label, (
                ProposedLine(dr, debit=abs(reclass), memo="Incremental platform contract asset reclass"),
                ProposedLine(cr, credit=abs(reclass), memo="Incremental platform contract asset reclass")),
                "START_HERE · ACCOUNTING: reverse prior reclass, recalculate, propose only incremental changes"))
        calcs = [CalcStep(f"Base schedule ({base.source.document})", base.formula, p.money(base.amount))]
        calcs += [CalcStep(f"Upgrade increment ({c.source.document}, from {c.start})", c.formula, p.money(c.amount)) for c in incs]
        calcs += [
            CalcStep("Expected October platform revenue", "base + increments", p.money(r["expected"])),
            CalcStep("Booked to 4000", "GL, October", p.money(r["booked"])),
            CalcStep("October Revenue Effect", "expected − booked", p.money(missing)),
            CalcStep("2200 before reclass, as booked", "opening 2200 + 1160 and October 2200 + 1160 movements (credit +)",
                     p.money(pos["pre_reclass_2200_credit"])),
            CalcStep("2200 before reclass, corrected", f"{p.money(pos['pre_reclass_2200_credit'])} − {p.money(missing)}", p.money(pre)),
            CalcStep("Required 1160", "net debit in 2200, else 0", p.money(required)),
            CalcStep("1160 already booked", "opening + October reclass", p.money(pos["booked_1160"])),
            CalcStep("Incremental reclass", "required − booked", p.money(reclass)),
        ]
        ev = [c.source.evidence(ctx.period.key, "annual rate") for c in [base, *incs]]
        ev += [Evidence("contract_term", f"data/raw/{ctx.period.key}/contracts/{t['source_document']}.pdf", None,
                        f"{t['source_section']}: {t['source_quote']}", "increment basis")
               for t in ctx.rows("""SELECT * FROM contract_terms WHERE contract_id = ? AND term IN
                   ('catch_up_amount', 'incremental_consideration') ORDER BY term""", [k.contract_id])]
        ev += [Evidence("csv_row", g["source_file"], g["source_line"], f"GL 4000 {g['memo']}: credit {g['credit']}",
                        "October recognition booked")
               for g in ctx.rows("""SELECT source_file, source_line, memo, credit FROM journal_lines WHERE status = 'recorded' AND entry_kind = 'gl'
                   AND account_number = '4000' AND customer_id = ? AND posting_period = getvariable('period_label')""",
                   [k.customer_id])]
        ev += [Evidence("csv_row", q["source_file"], q["source_line"],
                        f"Revenue plan {q['Revenue Plan ID']} {q['Posting Period']}: {q['Recognized Amount']}, "
                        f"plan updated {q['Plan Updated At']}", "revenue plan (base only)")
               for q in ctx.rows("""SELECT * FROM raw_netsuite_revenue_plan_detail WHERE "Customer Internal ID" = ?
                   AND "Posting Period" = getvariable('period_label')""", [k.customer_id])]
        ev.append(p.start_here(ctx, "ACCOUNTING", "Preserve the original base schedule when adding an upgrade increment."))
        ev.append(p.start_here(ctx, "ACCOUNTING", "Reverse any prior reclass before recalculating. The supplied October GL "
                               "ALREADY contains its baseline reclass. Propose only incremental changes after correcting recognition."))
        out.append(Finding(
            rule="platform_upgrade_increment", key="PLATFORM-UPGRADE-INCREMENT", customer_id=k.customer_id,
            stream="platform", service_period=ctx.period.key, status="error",
            title=f"October platform revenue omits the ${p.money(missing)} upgrade increment",
            summary=(f"October recognition booked only the base schedule (${p.money(base.amount)}). "
                     + "; ".join(f"{c.source.document} adds ${c.annual_rate:,}/yr from {c.start}" for c in incs)
                     + f", so October also earns ${p.money(missing)}. The revenue plan was not updated. Recomputing 2200 "
                     f"after the correction leaves a net debit of ${p.money(required)}, ${p.money(reclass)} more than "
                     f"the baseline reclass."),
            action="Add the increment as a separate revenue-plan component (base schedule unchanged); post the October "
                   "recognition and the incremental 1160 reclass.",
            billing_effect=p.ZERO, october_revenue_effect=missing,
            calculations=tuple(calcs), evidence=tuple(ev),
            claims=(Claim("revenue", "platform", missing),), entries=tuple(entries),
        ))
    return out
