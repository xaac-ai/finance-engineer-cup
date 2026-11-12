"""One review run for a period: inputs -> contract terms -> messages -> books -> controls -> outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workbench import contracts, db, findings, inputs, ledger, messages, outputs, pdf
from workbench.controls import ControlResult, passed, run_controls
from workbench.period import Period, load_period


@dataclass(frozen=True)
class RunResult:
    period: Period
    controls: list[ControlResult]
    outputs: list[str]

    @property
    def failed(self) -> list[ControlResult]:
        return [c for c in self.controls if c.status == "fail"]


def run(period_key: str, root: Path | None = None) -> RunResult:
    """Run the whole review. Raises WorkbenchError if inputs can't be trusted (nothing is written then)."""
    period = load_period(period_key, root)
    inputs.check_inputs(period)
    con = db.connect(period, period.out_dir / "workbench.duckdb")

    counts = inputs.load_raw(con, period)
    # Policies are coded as cited constants; the extracted text is kept so reviewers can check citations.
    pdf.extract_to(period.raw_dir / "START_HERE.pdf", period.extracted_dir)
    contract_stats = contracts.build_contract_terms(con, period)
    n_messages = messages.load_billing_messages(con, period)
    n_journal = ledger.build_journal(con, period)
    # Streams -> reconciliations -> finding rules (which add Proposed Entries to journal_lines),
    # so the ledger controls below also check every Proposed Entry.
    ctx = findings.run(con, period)

    results = [
        passed("contracts", "order_forms_parsed", "Order Forms parsed from the template and agree with contract_register.csv",
               f"{contract_stats['order_forms']} Order Forms"),
        passed("contracts", "amendment_quotes", "Every curated Amendment quote appears verbatim in the document text",
               f"{contract_stats['quotes_checked']} quotes across {contract_stats['amendments']} Amendments"),
        passed("inputs", "billing_messages_parsed", "Billing Messages parsed from billing_followups.pdf", f"{n_messages} messages"),
    ]
    results += run_controls(con, "inputs")
    results += ledger.run_ledger_controls(con)
    results += run_controls(con, "findings")

    stats = {"row_counts": counts, "journal_lines": n_journal, "billing_messages": n_messages,
             "streams": ctx.streams, **contract_stats}
    written = outputs.write_workpapers(con, period, results)
    written.append(outputs.write_report(con, period, results, stats, written))
    con.close()
    return RunResult(period=period, controls=results, outputs=written)
