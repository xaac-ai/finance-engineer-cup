"""Reconciliations and Findings.

Decision (wayfinder: "How should findings be structured?"):
1. Stream builders (`workbench/streams/*.py`, each with `build(ctx)`) write expected and actual
   amounts per customer × stream into `billing_lines` and `revenue_lines`.
2. Reconciliations compare them for every customer × implemented stream:
   - billing: expected vs actual (Stripe);
   - October revenue: expected vs booked (GL 4000 platform / 4010 usage, recorded, the period).
   difference = expected − actual, so positive means underbilled / understated.
3. Finding rules (`workbench/rules/*.py`, each with `detect(ctx) -> list[Finding]`) explain the
   differences. Each Finding claims the amounts it explains; controls require claims to equal the
   differences exactly (nothing unexplained, nothing double-counted).

A Finding is one root cause for one customer and service period, with a Billing Effect and an
October Revenue Effect. Needs Info amounts go only in `exposure`, never in confirmed totals.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Literal

import duckdb

from workbench.period import Period

Status = Literal["error", "valid_explanation", "needs_info"]
Stream = Literal["platform", "usage"]
STREAMS: tuple[str, ...] = ("platform", "usage")


@dataclass(frozen=True)
class CalcStep:
    description: str
    formula: str
    value: str


@dataclass(frozen=True)
class Evidence:
    kind: Literal["csv_row", "pdf_quote", "billing_message", "contract_term"]
    file: str
    line: int | None
    text: str
    role: str  # why this evidence matters, e.g. "contract rate", "invoice billed"


@dataclass(frozen=True)
class Claim:
    """The part of a reconciliation difference this Finding explains."""
    recon: Literal["billing", "revenue"]
    stream: Stream
    amount: Decimal  # same sign convention as the difference (expected − actual)


@dataclass(frozen=True)
class ProposedLine:
    account_number: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    memo: str = ""


@dataclass(frozen=True)
class ProposedEntry:
    kind: Literal["proposed_october_adjustment", "proposed_november_billing"]
    date: date
    posting_period: str
    lines: tuple[ProposedLine, ...]
    basis: str


@dataclass(frozen=True)
class ProposedBillingDocument:
    doc_type: Literal["supplemental_invoice", "credit_note"]
    issue_date: date
    stream: Stream
    amount: Decimal
    service_start: date
    service_end_exclusive: date
    original_invoice: str | None
    description: str


@dataclass(frozen=True)
class Finding:
    rule: str
    key: str  # short root-cause key, e.g. "USAGE-ALLOWANCE"
    customer_id: str | None  # None for findings not attributable to a customer
    stream: Stream
    service_period: str  # e.g. "2026-10"
    status: Status
    title: str
    summary: str
    action: str
    billing_effect: Decimal | None = None
    october_revenue_effect: Decimal | None = None
    exposure: str | None = None  # Needs Info only: described, possibly unpriced
    no_october_entry_reason: str | None = None
    follow_up: bool = False
    calculations: tuple[CalcStep, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    claims: tuple[Claim, ...] = ()
    entries: tuple[ProposedEntry, ...] = ()
    documents: tuple[ProposedBillingDocument, ...] = ()

    @property
    def finding_id(self) -> str:
        return f"F-{self.customer_id or 'UNATTRIBUTED'}-{self.key}-{self.service_period}"


@dataclass
class Context:
    con: duckdb.DuckDBPyConnection
    period: Period
    streams: list[str] = field(default_factory=list)  # streams with a builder this run

    def rows(self, sql: str, params: list | None = None) -> list[dict]:
        cur = self.con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _discover(package: str, attr: str) -> list[tuple[str, Callable]]:
    pkg = importlib.import_module(package)
    found = []
    for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        mod = importlib.import_module(f"{package}.{m.name}")
        if hasattr(mod, attr):
            found.append((m.name, getattr(mod, attr)))
    return found


def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE OR REPLACE TABLE billing_lines (customer_id VARCHAR, stream VARCHAR, side VARCHAR,
            doc_key VARCHAR, amount DECIMAL(18,2), description VARCHAR, source_file VARCHAR, source_line INTEGER);
        CREATE OR REPLACE TABLE revenue_lines (customer_id VARCHAR, stream VARCHAR, component VARCHAR,
            amount DECIMAL(18,2), description VARCHAR);
        CREATE OR REPLACE TABLE implemented_streams (stream VARCHAR);
        CREATE OR REPLACE TABLE findings (finding_id VARCHAR, rule VARCHAR, customer_id VARCHAR, stream VARCHAR,
            service_period VARCHAR, status VARCHAR, title VARCHAR, summary VARCHAR, action VARCHAR,
            billing_effect DECIMAL(18,2), october_revenue_effect DECIMAL(18,2), exposure VARCHAR,
            no_october_entry_reason VARCHAR, follow_up BOOLEAN);
        CREATE OR REPLACE TABLE finding_calculations (finding_id VARCHAR, step INTEGER, description VARCHAR,
            formula VARCHAR, value VARCHAR);
        CREATE OR REPLACE TABLE finding_evidence (finding_id VARCHAR, seq INTEGER, kind VARCHAR, file VARCHAR,
            line INTEGER, text VARCHAR, role VARCHAR);
        CREATE OR REPLACE TABLE finding_claims (finding_id VARCHAR, recon VARCHAR, customer_id VARCHAR,
            stream VARCHAR, amount DECIMAL(18,2));
        CREATE OR REPLACE TABLE proposed_billing_documents (document_id VARCHAR, finding_id VARCHAR,
            customer_id VARCHAR, doc_type VARCHAR, issue_date DATE, stream VARCHAR, amount DECIMAL(18,2),
            service_start DATE, service_end_exclusive DATE, original_invoice VARCHAR, description VARCHAR);
    """)


def build_streams(ctx: Context, builders: list[tuple[str, Callable]] | None = None) -> list[str]:
    """Run stream builders; each fills billing_lines / revenue_lines for its stream."""
    for name, build in builders if builders is not None else _discover("workbench.streams", "build"):
        build(ctx)
        ctx.streams.append(name)
        ctx.con.execute("INSERT INTO implemented_streams VALUES (?)", [name])
    return ctx.streams


def run_rules(ctx: Context, rules: list[tuple[str, Callable]] | None = None) -> list[Finding]:
    """Run finding rules and persist Findings, their detail rows, and Proposed Entries."""
    findings: list[Finding] = []
    for _, detect in rules if rules is not None else _discover("workbench.rules", "detect"):
        findings += detect(ctx)
    seen = set()
    for f in sorted(findings, key=lambda f: f.finding_id):
        fid = f.finding_id
        if fid in seen:
            raise ValueError(f"Duplicate finding_id {fid}: two rules claim the same root cause.")
        seen.add(fid)
        c = ctx.con
        c.execute("INSERT INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            fid, f.rule, f.customer_id, f.stream, f.service_period, f.status, f.title, f.summary, f.action,
            f.billing_effect, f.october_revenue_effect, f.exposure, f.no_october_entry_reason, f.follow_up])
        for i, s in enumerate(f.calculations, 1):
            c.execute("INSERT INTO finding_calculations VALUES (?,?,?,?,?)", [fid, i, s.description, s.formula, s.value])
        for i, e in enumerate(f.evidence, 1):
            c.execute("INSERT INTO finding_evidence VALUES (?,?,?,?,?,?,?)", [fid, i, e.kind, e.file, e.line, e.text, e.role])
        for cl in f.claims:
            c.execute("INSERT INTO finding_claims VALUES (?,?,?,?,?)", [fid, cl.recon, f.customer_id, cl.stream, cl.amount])
        for i, d in enumerate(f.documents, 1):
            c.execute("INSERT INTO proposed_billing_documents VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
                f"PD-{fid}-{i}", fid, f.customer_id, d.doc_type, d.issue_date, d.stream, d.amount,
                d.service_start, d.service_end_exclusive, d.original_invoice, d.description])
        for i, e in enumerate(f.entries, 1):
            for n, ln in enumerate(e.lines, 1):
                c.execute("""INSERT INTO journal_lines BY NAME SELECT ? AS entry_id, ? AS line_no, 'proposed' AS status,
                    ? AS entry_kind, ? AS date, ? AS posting_period, ? AS account_number, ? AS customer_id,
                    ?::DECIMAL(18,2) AS debit, ?::DECIMAL(18,2) AS credit, ? AS memo, ? AS finding_id, ? AS basis""",
                    [f"P-{fid}-{i}", n, e.kind, e.date, e.posting_period, ln.account_number, f.customer_id,
                     ln.debit, ln.credit, ln.memo, fid, e.basis])
    return findings


RECON_SQL = """
CREATE OR REPLACE VIEW billing_reconciliation AS
WITH grid AS (
    SELECT s."NetSuiteCustomerInternalId__c" AS customer_id, s."AccountName" AS customer_name, i.stream
    FROM raw_salesforce_accounts s CROSS JOIN implemented_streams i
), sums AS (
    SELECT customer_id, stream,
           sum(CASE WHEN side = 'expected' THEN amount ELSE 0 END) AS expected,
           sum(CASE WHEN side = 'actual' THEN amount ELSE 0 END) AS actual
    FROM billing_lines GROUP BY ALL
), claims AS (
    SELECT customer_id, stream, sum(amount) AS claimed, string_agg(DISTINCT finding_id, ', ') AS finding_ids
    FROM finding_claims WHERE recon = 'billing' GROUP BY ALL
)
SELECT g.customer_id, g.customer_name, g.stream,
       coalesce(s.expected, 0)::DECIMAL(18,2) AS expected,
       coalesce(s.actual, 0)::DECIMAL(18,2) AS actual,
       (coalesce(s.expected, 0) - coalesce(s.actual, 0))::DECIMAL(18,2) AS difference,
       coalesce(c.claimed, 0)::DECIMAL(18,2) AS claimed,
       c.finding_ids
FROM grid g LEFT JOIN sums s USING (customer_id, stream) LEFT JOIN claims c USING (customer_id, stream)
ORDER BY g.customer_name, g.stream;

CREATE OR REPLACE VIEW revenue_reconciliation AS
WITH grid AS (
    SELECT s."NetSuiteCustomerInternalId__c" AS customer_id, s."AccountName" AS customer_name, i.stream
    FROM raw_salesforce_accounts s CROSS JOIN implemented_streams i
), expected AS (
    SELECT customer_id, stream, sum(amount) AS expected FROM revenue_lines GROUP BY ALL
), booked AS (
    SELECT customer_id, CASE account_number WHEN '4000' THEN 'platform' WHEN '4010' THEN 'usage' END AS stream,
           sum(credit - debit) AS booked
    FROM journal_lines
    WHERE status = 'recorded' AND entry_kind = 'gl' AND account_number IN ('4000', '4010')
      AND posting_period = getvariable('period_label')
    GROUP BY ALL
), claims AS (
    SELECT customer_id, stream, sum(amount) AS claimed, string_agg(DISTINCT finding_id, ', ') AS finding_ids
    FROM finding_claims WHERE recon = 'revenue' GROUP BY ALL
)
SELECT g.customer_id, g.customer_name, g.stream,
       coalesce(e.expected, 0)::DECIMAL(18,2) AS expected,
       coalesce(b.booked, 0)::DECIMAL(18,2) AS booked,
       (coalesce(e.expected, 0) - coalesce(b.booked, 0))::DECIMAL(18,2) AS difference,
       coalesce(c.claimed, 0)::DECIMAL(18,2) AS claimed,
       c.finding_ids
FROM grid g LEFT JOIN expected e USING (customer_id, stream) LEFT JOIN booked b USING (customer_id, stream)
LEFT JOIN claims c USING (customer_id, stream)
ORDER BY g.customer_name, g.stream;
"""


def create_reconciliations(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(RECON_SQL)


def run(con: duckdb.DuckDBPyConnection, period: Period, builders=None, rules=None) -> Context:
    """Streams -> reconciliations -> rules. Called by the pipeline before ledger controls run."""
    ctx = Context(con=con, period=period)
    create_tables(con)
    build_streams(ctx, builders)
    create_reconciliations(con)
    run_rules(ctx, rules)
    return ctx
