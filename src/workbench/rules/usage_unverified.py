"""Needs Info: October usage on a product account with no verified billing owner.

Decision (wayfinder: "How is usage validated and attributed?"): reported as unpriced runs, not
attached to any customer and not priced at any candidate's terms; Product Operations must verify
the owner first. Never assigned by elimination.
"""

from workbench.findings import CalcStep, Evidence, Finding
from workbench.streams import usage as u


def detect(ctx):
    out = []
    accounts = ctx.rows("""SELECT product_account_id, count(*) AS records, sum(units) AS units,
            min(service_date) AS first_day, max(service_date) AS last_day, min(source_line) AS first_line,
            max(source_line) AS last_line, any_value(source_file) AS source_file
        FROM usage_unattributed GROUP BY ALL ORDER BY product_account_id""")
    for a in accounts:
        pa = a["product_account_id"]
        messages = ctx.rows("SELECT message_id, body FROM billing_messages WHERE body LIKE '%' || ? || '%' "
                            "OR body ILIKE '%unverified workspace%' ORDER BY message_id", [pa])
        mapping = ctx.rows("SELECT source_file, source_line, account_label, salesforce_account_id FROM raw_product_account_mapping "
                           "WHERE product_account_id = ?", [pa])
        ev = [Evidence("csv_row", a["source_file"], a["first_line"],
                       f"{pa}: {a['records']} October records, {int(a['units']):,} runs, {a['first_day']} to {a['last_day']} "
                       f"(lines {a['first_line']}–{a['last_line']})", "unattributed usage")]
        ev += [Evidence("csv_row", r["source_file"], r["source_line"],
                        f"{pa} mapping: label {r['account_label']!r}, Salesforce account blank", "no verified owner")
               for r in mapping]
        ev += [Evidence("billing_message", "data/raw/{}/billing_followups.pdf".format(ctx.period.key), None,
                        f"{r['message_id']}: {r['body']}", "instruction") for r in messages]
        ev.append(u.start_here(ctx, "UNVERIFIED USAGE", "Do not force a mapping, assume the remaining customer owns a "
                               "workspace, or treat missing attribution as zero usage. Document conditional exposure and "
                               "request Product Operations evidence.", "policy"))
        out.append(Finding(
            rule="usage_unverified", key=f"USAGE-UNVERIFIED-{pa}", customer_id=None, stream="usage",
            service_period=ctx.period.key, status="needs_info",
            title=f"{int(a['units']):,} October runs on unverified workspace {pa}",
            summary=(f"{pa} metered {int(a['units']):,} runs in October but has no verified billing owner. They are kept out "
                     f"of every customer's usage and are not priced: assigning them to the only customer without a mapped "
                     f"account would be identification by elimination, which Product Operations forbids."),
            action="Product Operations to verify the owner. Then bill the runs under that customer's executed terms "
                   "(or confirm the workspace is internal) and accrue October accordingly.",
            exposure=(f"Unpriced: {int(a['units']):,} runs. $0 if the workspace is internal; otherwise the owner's overage "
                      f"on its combined October runs under its executed contract."),
            calculations=(CalcStep("Unattributed October runs", "unique active records with no verified mapping",
                                   f"{int(a['units']):,}"),),
            evidence=tuple(ev),
        ))
    return out
