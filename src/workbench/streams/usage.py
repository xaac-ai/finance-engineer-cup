"""Usage stream: validated usage -> expected Nov 1 usage invoice and expected October accrual.

Decision (wayfinder: "How is usage validated and attributed?"):
- Exact repeats of a record_id count once; only active, unreplaced records count; the same
  record_id with different content fails a control. Countable records tie to usage_batch_controls.
- A record belongs to a customer only through a mapping with a Salesforce account, effective on
  its service date. Everything else is isolated as unverified usage, never assigned by elimination.
- Per customer and calendar month: units across all verified accounts, one allowance (weighted by
  calendar days when it changes, or prorated in a partial month, rounded once to whole runs),
  expected invoice = max(0, units − allowance) × contract rate, rounded once to cents half up.
- Expected October accrual = expected invoice less approved concessions (approvals.py).

`build(ctx)` fills billing_lines / revenue_lines. `analyse(ctx)` (used by the usage finding rules,
after reconciliation) splits each customer's billing difference into root-cause effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib.resources import files

from workbench.errors import ContractError
from workbench.findings import (CalcStep, Claim, Context, Evidence, Finding, ProposedBillingDocument, ProposedEntry,
                                ProposedLine)
from workbench.money import CENT, round_cents, round_whole

SQL = files("workbench") / "sql" / "streams" / "usage.sql"
START_HERE = "data/raw/{key}/START_HERE.pdf"
ZERO = Decimal("0.00")


@dataclass
class InvoiceLine:
    invoice_id: str
    invoice_number: str
    invoice_created: datetime
    line_id: str
    quantity: int
    unit_price: Decimal  # USD per run
    gross: Decimal
    discount: Decimal
    source_file: str
    source_line: int

    @property
    def net(self) -> Decimal:
        return self.gross - self.discount


@dataclass
class UsageMonth:
    customer_id: str
    customer_name: str
    contract_id: str
    units: int
    records: int
    product_accounts: list[str]
    allowance: int
    allowance_formula: str
    allowance_values: set[int]  # every allowance in force during the month
    allowance_sources: list[tuple[str, str, str]]  # (document, section, quote)
    rate: Decimal
    rate_source: tuple[str, str, str]
    overage_units: int
    expected_billing: Decimal
    concession: Decimal
    concession_message: str | None
    concession_quote: str | None
    lines: list[InvoiceLine] = field(default_factory=list)
    units_known_at_invoice: int | None = None
    late_records: list[dict] = field(default_factory=list)
    # filled by analyse()
    billing_diff: Decimal = ZERO
    revenue_diff: Decimal = ZERO
    booked: Decimal = ZERO
    effects: dict[str, tuple[Decimal, Decimal | None]] = field(default_factory=dict)  # key -> (billing, revenue)

    @property
    def expected_revenue(self) -> Decimal:
        return self.expected_billing - self.concession

    @property
    def billed(self) -> Decimal:
        return sum((ln.net for ln in self.lines), ZERO)


def price(x: Decimal) -> str:
    """A per-run price with at least two decimals: 0.4 -> '0.40', 0.045 -> '0.045'."""
    places = max(2, -x.normalize().as_tuple().exponent)
    return f"{x:.{places}f}"


def charge(units: int, allowance: int, rate: Decimal) -> Decimal:
    """START_HERE · USAGE: max(0, eligible units − allowance) × rate, rounded once to cents half up."""
    return round_cents(Decimal(max(0, units - allowance)) * rate)


def _terms(ctx: Context, contract_id: str, term: str, start: date, end: date) -> list[dict]:
    return ctx.rows("""SELECT value, effective_from, effective_to_exclusive, source_document, source_section, source_quote
        FROM contract_terms WHERE contract_id = ? AND term = ? AND effective_from < ? AND effective_to_exclusive > ?
        ORDER BY effective_from""", [contract_id, term, end, start])


def _allowance(ctx: Context, contract_id: str) -> tuple[int, str, set[int], list[tuple[str, str, str]]]:
    """Weight each allowance by the calendar days it applies (0 outside the service term), round once."""
    start, end = ctx.period.start, ctx.period.end_exclusive
    days_in_month = (end - start).days
    terms = _terms(ctx, contract_id, "included_runs_per_month", start, end)
    parts: list[tuple[int, int]] = []
    for t in terms:
        days = (min(end, t["effective_to_exclusive"]) - max(start, t["effective_from"])).days
        parts.append((int(t["value"]), days))
    weighted = sum(Decimal(v * d) for v, d in parts) / days_in_month
    allowance = round_whole(weighted)
    if len(parts) == 1 and parts[0][1] == days_in_month:
        formula = f"{parts[0][0]:,} (full month)"
    else:
        formula = " + ".join(f"{v:,} × {d}/{days_in_month}" for v, d in parts) + \
            f" = {weighted.quantize(CENT):,}, rounded once half up to {allowance:,}"
    sources = [(t["source_document"], t["source_section"], t["source_quote"]) for t in terms]
    weighting = _terms(ctx, contract_id, "allowance_weighting_rule", start, end)
    sources += [(t["source_document"], t["source_section"], t["source_quote"]) for t in weighting]
    return allowance, formula, {v for v, _ in parts}, sources


def _rate(ctx: Context, contract_id: str) -> tuple[Decimal, tuple[str, str, str]]:
    terms = _terms(ctx, contract_id, "overage_rate", ctx.period.start, ctx.period.end_exclusive)
    if len({t["value"] for t in terms}) != 1:
        raise ContractError(f"{contract_id}: expected one overage rate for {ctx.period.key}, found "
                            f"{[t['value'] for t in terms]}. A mid-month rate change needs an explicit rule.")
    t = terms[0]
    return Decimal(t["value"]), (t["source_document"], t["source_section"], t["source_quote"])


def customer_months(ctx: Context) -> list[UsageMonth]:
    """Expected usage for every customer with an Order Form, plus its actual invoice lines."""
    concessions = {r["customer_id"]: r for r in ctx.rows(
        "SELECT * FROM approved_concessions WHERE stream = 'usage' AND service_period = ?", [ctx.period.key])} \
        if ctx.con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'approved_concessions'").fetchone()[0] else {}
    customers = ctx.rows("""
        SELECT s."NetSuiteCustomerInternalId__c" AS customer_id, s."AccountName" AS customer_name, r.contract_id,
               coalesce(u.units, 0) AS units, coalesce(u.records, 0) AS records, u.product_accounts
        FROM raw_salesforce_accounts s
        JOIN raw_contract_register r ON r.salesforce_account_id = s."AccountId" AND r.document_type = 'order_form'
        LEFT JOIN (SELECT customer_id, sum(units) AS units, count(*) AS records,
                          string_agg(DISTINCT product_account_id, ', ' ORDER BY product_account_id) AS product_accounts
                   FROM usage_attributed GROUP BY ALL) u ON u.customer_id = s."NetSuiteCustomerInternalId__c"
        ORDER BY customer_name""")
    lines: dict[str, list[InvoiceLine]] = {}
    for ln in ctx.rows("SELECT * FROM usage_invoice_lines ORDER BY customer_id, source_line"):
        lines.setdefault(ln["customer_id"], []).append(InvoiceLine(
            ln["invoice_id"], ln["invoice_number"], ln["invoice_created_local"], ln["line_id"], ln["quantity"],
            Decimal(ln["unit_cents"]) / 100, Decimal(ln["amount_cents"]) * CENT, Decimal(ln["discount_cents"]) * CENT,
            ln["source_file"], ln["source_line"]))
    out = []
    for c in customers:
        allowance, formula, values, sources = _allowance(ctx, c["contract_id"])
        rate, rate_source = _rate(ctx, c["contract_id"])
        units = int(c["units"])
        con = concessions.get(c["customer_id"])
        m = UsageMonth(
            customer_id=c["customer_id"], customer_name=c["customer_name"], contract_id=c["contract_id"],
            units=units, records=int(c["records"]),
            product_accounts=(c["product_accounts"] or "").split(", ") if c["product_accounts"] else [],
            allowance=allowance, allowance_formula=formula, allowance_values=values, allowance_sources=sources,
            rate=rate, rate_source=rate_source, overage_units=max(0, units - allowance),
            expected_billing=charge(units, allowance, rate),
            concession=Decimal(con["amount"]) if con else ZERO,
            concession_message=con["message_id"] if con else None, concession_quote=con["quote"] if con else None,
            lines=lines.get(c["customer_id"], []),
        )
        if len(m.lines) == 1:
            created = m.lines[0].invoice_created
            m.units_known_at_invoice = int(ctx.con.execute(
                "SELECT coalesce(sum(units), 0) FROM usage_attributed WHERE customer_id = ? AND ingested_at::TIMESTAMP <= ?",
                [m.customer_id, created]).fetchone()[0])
            m.late_records = ctx.rows("""SELECT record_id, product_account_id, service_date, units, ingested_at::TIMESTAMP AS ingested_at,
                       source_file, source_line FROM usage_attributed WHERE customer_id = ? AND ingested_at::TIMESTAMP > ? ORDER BY source_line""", [m.customer_id, created])
        out.append(m)
    return out


def build(ctx: Context) -> None:
    ctx.con.execute(SQL.read_text())
    months = customer_months(ctx)
    ctx.con.execute("""CREATE OR REPLACE TABLE usage_by_customer (customer_id VARCHAR, customer_name VARCHAR,
        contract_id VARCHAR, product_accounts VARCHAR, records INTEGER, units BIGINT, allowance BIGINT,
        allowance_formula VARCHAR, overage_units BIGINT, rate DECIMAL(18,4), expected_billing DECIMAL(18,2),
        approved_concession DECIMAL(18,2), concession_message VARCHAR, expected_accrual DECIMAL(18,2),
        billed DECIMAL(18,2), billed_invoices VARCHAR, credited DECIMAL(18,2), credit_notes VARCHAR)""")
    doc = f"usage-{ctx.period.key}"
    credits: dict[str, list[dict]] = {}
    for n in ctx.rows("""SELECT customer_id, number, amount, invoice_number, line_source_file, line_source_line
            FROM usage_credit_notes WHERE effective ORDER BY line_source_line"""):
        credits.setdefault(n["customer_id"], []).append(n)
    for m in months:
        cns = credits.get(m.customer_id, [])
        ctx.con.execute("INSERT INTO usage_by_customer VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            m.customer_id, m.customer_name, m.contract_id, ", ".join(m.product_accounts), m.records, m.units,
            m.allowance, m.allowance_formula, m.overage_units, m.rate, m.expected_billing, m.concession,
            m.concession_message, m.expected_revenue, m.billed, ", ".join(ln.invoice_number for ln in m.lines) or None,
            sum((n["amount"] for n in cns), ZERO), ", ".join(n["number"] for n in cns) or None])
        # Billing is what the customer owes for the month's service: issued credit notes reduce actual,
        # approved concessions reduce expected (decision: "Build the credits and approvals stream").
        for n in cns:
            ctx.con.execute("INSERT INTO billing_lines VALUES (?, 'usage', 'actual', ?, ?, ?, ?, ?)", [
                m.customer_id, n["number"], -n["amount"], f"{n['number']}: issued credit against {n['invoice_number']}",
                n["line_source_file"], n["line_source_line"]])
        if m.concession:
            ctx.con.execute("INSERT INTO billing_lines VALUES (?, 'usage', 'expected', ?, ?, ?, NULL, NULL)", [
                m.customer_id, m.concession_message, -m.concession, f"approved concession, {m.concession_message}"])
        ctx.con.execute("INSERT INTO billing_lines VALUES (?, 'usage', 'expected', ?, ?, ?, NULL, NULL)", [
            m.customer_id, doc, m.expected_billing,
            f"{m.units:,} runs − allowance {m.allowance:,} = {m.overage_units:,} × ${m.rate}"])
        for ln in m.lines:
            ctx.con.execute("INSERT INTO billing_lines VALUES (?, 'usage', 'actual', ?, ?, ?, ?, ?)", [
                m.customer_id, ln.invoice_number, ln.net,
                f"{ln.invoice_number}: {ln.quantity:,} runs × ${price(ln.unit_price)}"
                + (f" less discount ${ln.discount}" if ln.discount else ""), ln.source_file, ln.source_line])
        ctx.con.execute("INSERT INTO revenue_lines VALUES (?, 'usage', 'usage_overage', ?, ?)", [
            m.customer_id, m.expected_billing, "expected October usage consideration"])
        if m.concession:
            ctx.con.execute("INSERT INTO revenue_lines VALUES (?, 'usage', 'approved_concession', ?, ?)", [
                m.customer_id, -m.concession, f"approved concession, {m.concession_message}"])


# ---- analysis used by the usage finding rules ---------------------------------------------------

LATE = "USAGE-LATE-RECORD"


def _allocate_revenue(effects: dict[str, Decimal], revenue_diff: Decimal) -> dict[str, Decimal | None]:
    """Which effects did the booked accrual repeat? Try: all of them, none, all but the late record
    (an accrual prepared after late ingestion includes it). Unexplainable -> None (left unclaimed)."""
    keys = list(effects)
    for repeated in (set(keys), set(), set(keys) - {LATE}):
        if sum((effects[k] for k in repeated), ZERO) == revenue_diff:
            return {k: (effects[k] if k in repeated else ZERO) for k in keys}
    return {k: None for k in keys}


def analyse(ctx: Context) -> list[UsageMonth]:
    """Customer months with their reconciliation differences split into root-cause effects."""
    diffs = {(r["customer_id"], r["recon"]): r for r in ctx.rows("""
        SELECT customer_id, 'billing' AS recon, difference, actual AS other FROM billing_reconciliation WHERE stream = 'usage'
        UNION ALL
        SELECT customer_id, 'revenue', difference, booked FROM revenue_reconciliation WHERE stream = 'usage'""")}
    months = customer_months(ctx)
    for m in months:
        m.billing_diff = diffs[(m.customer_id, "billing")]["difference"]
        m.revenue_diff = diffs[(m.customer_id, "revenue")]["difference"]
        m.booked = diffs[(m.customer_id, "revenue")]["other"]
        billing: dict[str, Decimal] = {}
        if not m.lines and m.expected_billing:
            billing["USAGE-MISSING-INVOICE"] = m.expected_billing
        elif len(m.lines) == 1:
            ln = m.lines[0]
            if ln.unit_price != m.rate:
                billing["USAGE-RATE"] = round_cents(ln.quantity * m.rate) - ln.gross
            if ln.discount:
                billing["USAGE-DISCOUNT"] = ln.discount
            known = m.units_known_at_invoice or 0
            implied_allowance = known - ln.quantity
            if implied_allowance != m.allowance and implied_allowance in m.allowance_values:
                billing["USAGE-ALLOWANCE"] = charge(known, m.allowance, m.rate) - round_cents(ln.quantity * m.rate)
            if m.late_records:
                billing[LATE] = m.expected_billing - charge(known, m.allowance, m.rate)
        billing = {k: v for k, v in billing.items() if v}
        revenue = _allocate_revenue(billing, m.revenue_diff)
        m.effects = {k: (billing[k], revenue[k]) for k in billing}
    return months


def correction(ctx: Context, m: UsageMonth, key: str) -> dict:
    """Claims, Proposed Entries and billing documents for one usage effect (Finding kwargs)."""
    billing, revenue = m.effects[key]
    period_end = ctx.period.end_exclusive - timedelta(days=1)
    issue = ctx.period.billing_issue_date
    nov_label = issue.strftime("%b %Y")
    claims = [Claim("billing", "usage", billing)]
    entries, documents = [], []
    if revenue:
        claims.append(Claim("revenue", "usage", revenue))
        dr, cr = ("1150", "4010") if revenue > 0 else ("4010", "1150")
        entries.append(ProposedEntry("proposed_october_adjustment", period_end, ctx.period.label, (
            ProposedLine(dr, debit=abs(revenue), memo=f"October usage {'understated' if revenue > 0 else 'overstated'}"),
            ProposedLine(cr, credit=abs(revenue), memo=f"{m.customer_name} October usage accrual correction")),
            "START_HERE · APPROVAL AND DATES: supported October-service corrections use the October posting period"))
    original = m.lines[0].invoice_number if m.lines else None
    if billing > 0:
        documents.append(ProposedBillingDocument(
            "supplemental_invoice", issue, "usage", billing, ctx.period.start, ctx.period.end_exclusive, original,
            f"October workflow-run overage {'not invoiced' if not original else 'under-billed on ' + original}"))
        lines = (ProposedLine("1100", debit=billing, memo="Supplemental October usage invoice"),
                 ProposedLine("1150", credit=billing, memo="Release unbilled October usage"))
    else:
        documents.append(ProposedBillingDocument(
            "credit_note", issue, "usage", -billing, ctx.period.start, ctx.period.end_exclusive, original,
            f"Credit for October workflow-run overage over-billed on {original}"))
        lines = (ProposedLine("1150", debit=-billing, memo="Reverse over-released unbilled October usage"),
                 ProposedLine("1100", credit=-billing, memo="Credit note against " + str(original)))
    entries.append(ProposedEntry("proposed_november_billing", issue, nov_label, lines,
                                 "START_HERE · APPROVAL AND DATES: finalized invoices are not edited; November billing document"))
    return {"claims": tuple(claims), "entries": tuple(entries), "documents": tuple(documents),
            "billing_effect": billing, "october_revenue_effect": revenue}


def evidence(ctx: Context, m: UsageMonth, *, terms: bool = True, invoice: bool = True, accrual: bool = True) -> list[Evidence]:
    """The standard evidence for a customer's October usage."""
    ev: list[Evidence] = []
    if terms:
        for doc, sec, quote in m.allowance_sources:
            ev.append(Evidence("contract_term", f"data/raw/{ctx.period.key}/contracts/{doc}.pdf", None,
                               f"{sec}: {quote}", "allowance"))
        doc, sec, quote = m.rate_source
        ev.append(Evidence("contract_term", f"data/raw/{ctx.period.key}/contracts/{doc}.pdf", None, f"{sec}: {quote}", "overage rate"))
    ev.append(Evidence("csv_row", f"data/raw/{ctx.period.key}/product_usage.csv", None,
                       f"{m.records} October records, {m.units:,} runs on {', '.join(m.product_accounts) or 'no verified account'} "
                       f"(deduplicated, active, verified mapping)", "validated usage"))
    if invoice:
        for ln in m.lines:
            ev.append(Evidence("csv_row", ln.source_file, ln.source_line,
                               f"{ln.invoice_number} {ln.line_id}: {ln.quantity:,} × ${price(ln.unit_price)} = ${ln.gross:,}",
                               "invoice billed"))
    if accrual:
        for r in ctx.rows("""SELECT source_file, source_line, debit, credit, memo FROM journal_lines
                WHERE status = 'recorded' AND entry_kind = 'gl' AND account_number = '4010' AND customer_id = ?
                  AND posting_period = getvariable('period_label') ORDER BY source_line""", [m.customer_id]):
            ev.append(Evidence("csv_row", r["source_file"], r["source_line"],
                               f"GL 4010 {r['memo']}: credit {r['credit']}", "October accrual booked"))
    return ev


def start_here(ctx: Context, section: str, quote: str, role: str) -> Evidence:
    return Evidence("pdf_quote", START_HERE.format(key=ctx.period.key), None, f"{section}: {quote}", role)


def usage_quote(ctx: Context) -> Evidence:
    return start_here(ctx, "USAGE", "Charges equal max(0, eligible units minus allowance) x signed overage rate, "
                      "rounded once to USD cents half up.", "policy")


def error_finding(ctx: Context, m: UsageMonth, key: str, rule: str, *, title: str, summary: str, action: str,
                  calculations: tuple[CalcStep, ...], evidence: list[Evidence]) -> Finding:
    """An Error for one usage effect, with its claims, Proposed Entries and billing document."""
    fix = correction(ctx, m, key)
    reason = None
    if fix["october_revenue_effect"] == 0:
        reason = (f"The October accrual booked (${m.booked:,}) already equals expected October usage "
                  f"(${m.expected_revenue:,}); only billing is wrong. The difference stays in 1150 until the "
                  f"November billing document clears it.")
    return Finding(rule=rule, key=key, customer_id=m.customer_id, stream="usage", service_period=ctx.period.key,
                   status="error", title=title, summary=summary, action=action, no_october_entry_reason=reason,
                   calculations=calculations, evidence=tuple(evidence), **fix)
