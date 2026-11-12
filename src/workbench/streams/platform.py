"""Platform stream: expected billing documents covering the period, and expected platform revenue.

Decision (wayfinder: "Which platform billing approach do we present?"):
- Billing, Approach A: every anchor invoice whose service period overlaps the review month (an annual
  prepaid invoice issued in September counts as covering October), plus additional October-service
  platform charges (an Amendment's catch-up). Each is matched to the Stripe line with the same
  customer and service period; differences are per document.
- Revenue: each schedule component at actual days / 365, rounded once per month, half up, with the
  final-period residual in the component's last month. The original base schedule is preserved; an
  Amendment rate change adds a separate increment component from its effective date.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from importlib.resources import files

from workbench.findings import Context, Evidence
from workbench.money import CENT, day_share

SQL = files("workbench") / "sql" / "streams" / "platform.sql"
ZERO = Decimal("0.00")


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, d.day)


def _months(start: date, end: date):
    """Calendar months [m, next) intersecting [start, end)."""
    m = date(start.year, start.month, 1)
    while m < end:
        nxt = _add_months(m, 1)
        yield m, nxt
        m = nxt


def _overlap(a0: date, a1: date, b0: date, b1: date) -> int:
    return max(0, (min(a1, b1) - max(a0, b0)).days)


@dataclass
class Source:
    document: str
    section: str
    quote: str

    def evidence(self, key: str, role: str) -> Evidence:
        return Evidence("contract_term", f"data/raw/{key}/contracts/{self.document}.pdf", None,
                        f"{self.section}: {self.quote}", role)


@dataclass
class ExpectedDocument:
    kind: str  # anchor | catch_up
    service_start: date
    service_end_exclusive: date
    amount: Decimal
    source: Source

    @property
    def key(self) -> str:
        return f"{self.service_start}..{self.service_end_exclusive}"


@dataclass
class Component:
    name: str  # base | increment <document>
    annual_rate: Decimal
    start: date
    end_exclusive: date
    amount: Decimal  # recognised in the review period
    formula: str
    source: Source


@dataclass
class Contract:
    customer_id: str
    customer_name: str
    contract_id: str
    frequency: str
    service_start: date
    service_end_exclusive: date
    documents: list[ExpectedDocument] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)

    @property
    def expected_revenue(self) -> Decimal:
        return sum((c.amount for c in self.components), ZERO)


def _terms(ctx: Context, contract_id: str, term: str) -> list[dict]:
    return ctx.rows("""SELECT value, effective_from, effective_to_exclusive, source_document, source_section, source_quote
        FROM contract_terms WHERE contract_id = ? AND term = ? ORDER BY effective_from""", [contract_id, term])


def _src(t: dict) -> Source:
    return Source(t["source_document"], t["source_section"], t["source_quote"])


def _in_force(terms: list[dict], d: date) -> dict:
    return next(t for t in terms if t["effective_from"] <= d < t["effective_to_exclusive"])


def component_amount(rate: Decimal, start: date, end: date, p0: date, p1: date) -> tuple[Decimal, str]:
    """Recognition for one component in month [p0, p1): days/365 rounded once; the final month takes
    the residual so the component totals rate × all days / 365 exactly."""
    days = _overlap(start, end, p0, p1)
    if days == 0:
        return ZERO, "no service days"
    if p1 < end:
        return day_share(rate, days), f"{rate:,} × {days} / 365"
    total_days = (end - start).days
    total = day_share(rate, total_days)
    prior = sum((day_share(rate, _overlap(start, end, m0, m1)) for m0, m1 in _months(start, p0)), ZERO)
    return total - prior, f"final period: {rate:,} × {total_days} / 365 = {total:,} less {prior:,} recognised before"


def contracts(ctx: Context) -> list[Contract]:
    p0, p1 = ctx.period.start, ctx.period.end_exclusive
    out = []
    for c in ctx.rows("""SELECT s."NetSuiteCustomerInternalId__c" AS customer_id, s."AccountName" AS customer_name, r.contract_id
            FROM raw_salesforce_accounts s
            JOIN raw_contract_register r ON r.salesforce_account_id = s."AccountId" AND r.document_type = 'order_form'
            ORDER BY customer_name"""):
        cid = c["contract_id"]
        one = lambda term: _terms(ctx, cid, term)[0]["value"]  # noqa: E731 - terms never amended
        k = Contract(c["customer_id"], c["customer_name"], cid, one("billing_frequency"),
                     date.fromisoformat(one("service_start")), date.fromisoformat(one("service_end_exclusive")))
        # Billing documents: anchor periods from the service start, stepping by the billing frequency.
        step = 12 if k.frequency == "annual" else 1
        amounts = _terms(ctx, cid, "platform_invoice_amount")
        s = k.service_start
        while s < min(p1, k.service_end_exclusive):
            e = min(_add_months(s, step), k.service_end_exclusive)
            if _overlap(s, e, p0, p1):
                t = _in_force(amounts, s)
                k.documents.append(ExpectedDocument("anchor", s, e, Decimal(t["value"]), _src(t)))
            s = e
        for t in _terms(ctx, cid, "catch_up_amount"):
            if p0 <= t["effective_from"] < p1:
                k.documents.append(ExpectedDocument("catch_up", t["effective_from"], p1, Decimal(t["value"]), _src(t)))
        # Revenue components: base schedule plus one increment per rate change.
        prev = None
        for t in _terms(ctx, cid, "platform_annual_rate"):
            rate = Decimal(t["value"])
            if prev is None:
                name, delta, start = "base", rate, k.service_start
            else:
                name, delta, start = f"increment {t['source_document']}", rate - prev, t["effective_from"]
            amount, formula = component_amount(delta, start, k.service_end_exclusive, p0, p1)
            k.components.append(Component(name, delta, start, k.service_end_exclusive, amount, formula, _src(t)))
            prev = rate
        out.append(k)
    return out


def build(ctx: Context) -> None:
    ctx.con.execute(SQL.read_text())
    ks = contracts(ctx)
    ctx.con.execute("""CREATE OR REPLACE TABLE platform_expected_documents (customer_id VARCHAR, doc_key VARCHAR,
        kind VARCHAR, service_start DATE, service_end_exclusive DATE, amount DECIMAL(18,2), source_document VARCHAR,
        source_quote VARCHAR)""")
    ctx.con.execute("""CREATE OR REPLACE TABLE platform_revenue_components (customer_id VARCHAR, customer_name VARCHAR,
        contract_id VARCHAR, component VARCHAR, annual_rate DECIMAL(18,2), component_start DATE,
        component_end_exclusive DATE, amount DECIMAL(18,2), formula VARCHAR, source_document VARCHAR)""")
    for k in ks:
        for d in k.documents:
            ctx.con.execute("INSERT INTO platform_expected_documents VALUES (?,?,?,?,?,?,?,?)", [
                k.customer_id, d.key, d.kind, d.service_start, d.service_end_exclusive, d.amount, d.source.document, d.source.quote])
            ctx.con.execute("INSERT INTO billing_lines VALUES (?, 'platform', 'expected', ?, ?, ?, NULL, NULL)", [
                k.customer_id, d.key, d.amount, f"{d.kind.replace('_', '-')} {d.key} per {d.source.document}"])
        for c in k.components:
            ctx.con.execute("INSERT INTO platform_revenue_components VALUES (?,?,?,?,?,?,?,?,?,?)", [
                k.customer_id, k.customer_name, k.contract_id, c.name, c.annual_rate, c.start, c.end_exclusive,
                c.amount, c.formula, c.source.document])
            ctx.con.execute("INSERT INTO revenue_lines VALUES (?, 'platform', ?, ?, ?)", [
                k.customer_id, c.name, c.amount, c.formula])
    # Actual: Stripe platform lines whose service period overlaps the review month.
    ctx.con.execute("""INSERT INTO billing_lines
        SELECT customer_id, 'platform', 'actual', service_start || '..' || service_end_exclusive,
               amount_cents * 0.01, invoice_number || ' ' || line_id, source_file, source_line
        FROM platform_invoice_lines
        WHERE service_start < getvariable('period_end') AND service_end_exclusive > getvariable('period_start')""")
    ctx.con.execute("""CREATE OR REPLACE VIEW platform_documents AS
        WITH e AS (SELECT * FROM platform_expected_documents),
             a AS (SELECT customer_id, service_start || '..' || service_end_exclusive AS doc_key, service_start,
                          service_end_exclusive, invoice_number, line_id, (amount_cents * 0.01)::DECIMAL(18,2) AS actual,
                          source_file, source_line
                   FROM platform_invoice_lines
                   WHERE service_start < getvariable('period_end') AND service_end_exclusive > getvariable('period_start'))
        SELECT coalesce(e.customer_id, a.customer_id) AS customer_id, coalesce(e.doc_key, a.doc_key) AS doc_key, e.kind,
               coalesce(e.service_start, a.service_start) AS service_start,
               coalesce(e.service_end_exclusive, a.service_end_exclusive) AS service_end_exclusive,
               e.amount AS expected, a.actual, (coalesce(e.amount, 0) - coalesce(a.actual, 0))::DECIMAL(18,2) AS difference,
               a.invoice_number, a.line_id, e.source_document, a.source_file, a.source_line
        FROM e FULL JOIN a ON a.customer_id = e.customer_id AND a.doc_key = e.doc_key""")


def documents(ctx: Context) -> list[dict]:
    return ctx.rows("""SELECT d.*, s."AccountName" AS customer_name FROM platform_documents d
        JOIN raw_salesforce_accounts s ON s."NetSuiteCustomerInternalId__c" = d.customer_id
        ORDER BY customer_name, service_start""")


def period_end(ctx: Context) -> date:
    return ctx.period.end_exclusive - timedelta(days=1)


def money(x: Decimal) -> str:
    return f"{x.quantize(CENT):,}"


def register_evidence(ctx: Context, document_id: str) -> list[Evidence]:
    return [Evidence("csv_row", r["source_file"], r["source_line"],
                     f"{document_id}: effective {r['effective_from']}, billing_loaded_at "
                     f"{r['billing_loaded_at'] or 'blank (not recorded as loaded)'}, approval {r['approval_reference'] or 'none'}",
                     "contract register")
            for r in ctx.rows("SELECT * FROM raw_contract_register WHERE document_id = ?", [document_id])]


def start_here(ctx: Context, section: str, quote: str, role: str = "policy") -> Evidence:
    return Evidence("pdf_quote", f"data/raw/{ctx.period.key}/START_HERE.pdf", None, f"{section}: {quote}", role)


def november_billing(ctx: Context, amount: Decimal, d_start: date, d_end: date, original: str | None, what: str):
    """A November supplemental invoice (amount > 0) or linked credit note (< 0) for platform billing,
    with its Proposed Entry: Dr 1100 / Cr 2200 (START_HERE · ACCOUNTING platform invoice pattern) or reverse."""
    from workbench.findings import ProposedBillingDocument, ProposedEntry, ProposedLine
    issue = ctx.period.billing_issue_date
    if amount > 0:
        doc = ProposedBillingDocument("supplemental_invoice", issue, "platform", amount, d_start, d_end, original, what)
        lines = (ProposedLine("1100", debit=amount, memo=what), ProposedLine("2200", credit=amount, memo="Deferred platform revenue"))
    else:
        doc = ProposedBillingDocument("credit_note", issue, "platform", -amount, d_start, d_end, original, what)
        lines = (ProposedLine("2200", debit=-amount, memo="Deferred platform revenue"), ProposedLine("1100", credit=-amount, memo=what))
    entry = ProposedEntry("proposed_november_billing", issue, issue.strftime("%b %Y"), lines,
                          "START_HERE · APPROVAL AND DATES: finalized invoices are not edited; November billing document")
    return doc, entry
