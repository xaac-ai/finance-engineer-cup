"""Turn executed Order Forms and Amendments into date-ranged, cited Contract Terms.

Decision (wayfinder: "Parse or curate contract terms?"):
- Order Forms come from one machine-generated template, so they are parsed at runtime with
  label-anchored regexes. Any field that doesn't match fails the run, naming the document.
- Amendments are bespoke, so their term changes are hand-curated in
  data/curated/<period>/amendment_terms.yaml. Every curated quote must appear verbatim
  (whitespace-normalised) in the Amendment's extracted text, or the run fails.
- An Amendment changes only the terms it names, from its effective date; unchanged terms persist
  (START_HERE · SOURCE PRECEDENCE). So an amended term's prior record is cut at the change date.

Output table `contract_terms`: one row per (contract, term, date range) with its source citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

import duckdb
import yaml

from workbench.errors import ContractError
from workbench.pdf import extract_to, normalize
from workbench.period import Period

DATE = r"[A-Z][a-z]+ \d{1,2}, \d{4}"


@dataclass(frozen=True)
class ContractTerm:
    contract_id: str
    term: str
    value: str
    effective_from: date
    effective_to_exclusive: date
    source_document: str
    source_section: str
    source_quote: str


def _date(s: str) -> date:
    return datetime.strptime(s, "%B %d, %Y").date()


def _money(s: str) -> str:
    return s.replace(",", "")


def _find(doc_id: str, field: str, pattern: str, text: str) -> re.Match:
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        raise ContractError(
            f"{doc_id}: could not find '{field}' in the Order Form text (template changed?). "
            f"Check out/<period>/extracted/{doc_id}.txt; if the layout is genuinely different, "
            f"curate this document's terms instead of guessing."
        )
    return m


def parse_order_form(doc_id: str, text: str) -> tuple[str, list[ContractTerm]]:
    """Parse one Order Form. Returns (contract_id, terms). Raises ContractError on any miss."""
    _find(doc_id, "document header", rf"^RelayCloud EXECUTED ORDER FORM\n({re.escape(doc_id)})$", text)
    contract = _find(doc_id, "contract id", r"^Contract (CT-\d+)\s+\|\s+Executed (" + DATE + r")$", text)
    term_row = _find(
        doc_id, "term row",
        rf"^({DATE}) ({DATE}) (Annual|Monthly) in advance (Net \d+ days / [A-Z]{{3}})$", text)
    fee = _find(doc_id, "platform fee", r"^(Annual|Monthly), in advance \$([\d,]+\.\d{2}) / (year|month)$", text)
    runs = _find(doc_id, "included runs", r"^([\d,]+) included runs per calendar month$", text)
    overage = _find(doc_id, "overage rate", r"^Monthly, in arrears \$(\d+\.\d+) / excess run$", text)
    commit = _find(doc_id, "annual commitment", r"^ANNUAL PLATFORM COMMITMENT \$([\d,]+\.\d{2}) \+ usage overages$", text)
    anchor = _find(
        doc_id, "billing anchor",
        rf"Platform fees are invoiced (?:in full on ({DATE})|on the (\d{{1,2}})(?:st|nd|rd|th) of each month)", text)

    cid = contract.group(1)
    start = _date(term_row.group(1))
    end_excl = _date(term_row.group(2)) + timedelta(days=1)  # PDF shows inclusive end
    frequency = term_row.group(3).lower()
    if fee.group(1).lower() != frequency:
        raise ContractError(f"{doc_id}: billing row says {frequency!r} but fee row says {fee.group(1)!r}.")
    anchor_day = str(_date(anchor.group(1)).day) if anchor.group(1) else anchor.group(2)

    s2, s3, s4 = "02 SUBSCRIPTION TERM AND PAYMENT", "03 SERVICES AND FEES", "04 BILLING AND COMMERCIAL TERMS"
    rows = [
        ("service_start", start.isoformat(), s2, term_row.group(0)),
        ("service_end_exclusive", end_excl.isoformat(), s2, term_row.group(0)),
        ("billing_frequency", frequency, s2, term_row.group(0)),
        ("payment_terms", term_row.group(4), s2, term_row.group(0)),
        ("platform_invoice_amount", _money(fee.group(2)), s3, fee.group(0)),
        ("platform_annual_rate", _money(commit.group(1)), s3, commit.group(0)),
        ("included_runs_per_month", _money(runs.group(1)), s3, runs.group(0)),
        ("overage_rate", overage.group(1), s3, overage.group(0)),
        ("billing_anchor_day", anchor_day, s4, anchor.group(0)),
    ]
    return cid, [ContractTerm(cid, t, v, start, end_excl, doc_id, sec, q) for t, v, sec, q in rows]


def apply_amendment(terms: list[ContractTerm], change: ContractTerm) -> list[ContractTerm]:
    """Apply one curated change: cut the prior record of the same term at the change date, add the new one."""
    out = []
    for t in terms:
        if t.contract_id == change.contract_id and t.term == change.term and t.effective_from < change.effective_from < t.effective_to_exclusive:
            out.append(replace(t, effective_to_exclusive=change.effective_from))
        elif t.contract_id == change.contract_id and t.term == change.term and t.effective_from >= change.effective_from:
            continue  # fully superseded from the change date onward
        else:
            out.append(t)
    out.append(change)
    return out


def build_contract_terms(con: duckdb.DuckDBPyConnection, period: Period) -> dict:
    """Extract, parse, curate, verify and load `contract_terms`. Returns stats for the report."""
    register = con.execute(
        "SELECT document_id, contract_id, document_type, document_filename, effective_from, effective_to, "
        "supersedes_document_id FROM raw_contract_register ORDER BY document_id"
    ).fetchall()
    reg = {r[0]: r for r in register}
    pdf_dir = period.raw_dir / "contracts"
    pdfs = {p.stem: p for p in sorted(pdf_dir.glob("*.pdf"))}

    unregistered = sorted(set(pdfs) - set(reg))
    missing_pdf = sorted(d for d, r in reg.items() if r[3] and r[3].removesuffix(".pdf") not in pdfs)
    if unregistered or missing_pdf:
        raise ContractError(
            f"Contract PDFs and contract_register.csv disagree. PDFs not in register: {unregistered or 'none'}; "
            f"register rows without a PDF: {missing_pdf or 'none'}."
        )

    texts = {d: extract_to(p, period.extracted_dir) for d, p in pdfs.items()}

    terms: list[ContractTerm] = []
    order_forms = [d for d, r in reg.items() if r[2] == "order_form"]
    for doc_id in order_forms:
        cid, parsed = parse_order_form(doc_id, texts[doc_id])
        r = reg[doc_id]
        start = next(t.value for t in parsed if t.term == "service_start")
        end = next(t.value for t in parsed if t.term == "service_end_exclusive")
        problems = []
        if cid != r[1]:
            problems.append(f"contract {cid} vs register {r[1]}")
        if start != r[4]:
            problems.append(f"service start {start} vs register effective_from {r[4]}")
        if end != r[5]:
            problems.append(f"service end (exclusive) {end} vs register effective_to {r[5]}")
        if problems:
            raise ContractError(f"{doc_id} disagrees with contract_register.csv: " + "; ".join(problems))
        terms += parsed

    curated = yaml.safe_load((period.curated_dir / "amendment_terms.yaml").read_text()) or {}
    curated_by_doc = {a["document_id"]: a.get("changes") or [] for a in curated.get("amendments") or []}
    amendments = [d for d, r in reg.items() if r[2] == "amendment"]
    uncurated = [d for d in amendments if not curated_by_doc.get(d)]
    if uncurated:
        raise ContractError(
            f"Amendments in the register with no curated term changes: {uncurated}. Add them to "
            f"data/curated/{period.key}/amendment_terms.yaml with document, section and exact quote."
        )
    unknown = sorted(set(curated_by_doc) - set(amendments))
    if unknown:
        raise ContractError(f"amendment_terms.yaml lists documents that are not amendments in the register: {unknown}")

    quotes_checked = 0
    for doc_id in amendments:
        r = reg[doc_id]
        if r[6] not in order_forms:
            raise ContractError(f"{doc_id} supersedes {r[6]!r}, which is not an Order Form in the register.")
        haystack = normalize(texts[doc_id])
        for ch in curated_by_doc[doc_id]:
            for key in ("term", "value", "section", "quote"):
                if not ch.get(key):
                    raise ContractError(f"{doc_id}: a curated change is missing '{key}'.")
            if normalize(ch["quote"]) not in haystack:
                raise ContractError(
                    f"{doc_id}: curated quote for '{ch['term']}' is not in the document text:\n  {ch['quote']!r}\n"
                    f"Compare with out/{period.key}/extracted/{doc_id}.txt."
                )
            quotes_checked += 1
            eff = date.fromisoformat(str(ch.get("effective_from") or r[4]))
            terms = apply_amendment(terms, ContractTerm(
                r[1], ch["term"], str(ch["value"]), eff, date.fromisoformat(r[5]), doc_id, ch["section"], ch["quote"]))

    con.execute(
        "CREATE OR REPLACE TABLE contract_terms (contract_id VARCHAR, term VARCHAR, value VARCHAR, "
        "effective_from DATE, effective_to_exclusive DATE, source_document VARCHAR, source_section VARCHAR, "
        "source_quote VARCHAR)"
    )
    con.executemany(
        "INSERT INTO contract_terms VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [[t.contract_id, t.term, t.value, t.effective_from, t.effective_to_exclusive, t.source_document,
          t.source_section, t.source_quote] for t in sorted(terms, key=lambda t: (t.contract_id, t.term, t.effective_from))],
    )
    return {"order_forms": len(order_forms), "amendments": len(amendments), "quotes_checked": quotes_checked}
