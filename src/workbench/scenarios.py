"""Scenarios: a copy of one period's inputs with one named, deliberate change, and the results that change
should produce (GLOSSARY: Scenario).

Each Scenario runs the real pipeline on a copy of data/ and is compared with the untouched period:
- a change the review must catch produces exactly the expected difference (Findings, totals, controls);
- a change the review must ignore produces no difference at all.

Scenarios only change raw CSVs and period.yaml; contract PDFs and curated YAML stay as supplied.
Source-line citations are left out of the comparison (reordering rows moves them legitimately).

Run one: make scenario NAME=extra-usage   (writes out/scenarios/<name>/, prints the difference)
Run all: make test                        (tests/test_scenarios.py)
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

PERIOD = "2026-10"
REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- editing a copied period's inputs

class Inputs:
    """The raw CSVs and period.yaml of one copied period, edited in place."""

    def __init__(self, root: Path, period: str = PERIOD):
        self.raw = root / "data" / "raw" / period
        self.period_yaml = root / "data" / "curated" / period / "period.yaml"

    def rows(self, name: str) -> list[dict]:
        with open(self.raw / f"{name}.csv", newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def write(self, name: str, rows: list[dict]) -> None:
        path = self.raw / f"{name}.csv"
        with open(path, newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        path.write_text(buf.getvalue(), encoding="utf-8")

    def append(self, name: str, row: dict) -> None:
        self.write(name, self.rows(name) + [row])

    def set_expected_count(self, name: str, delta: int) -> None:
        """Keep period.yaml's completeness count in step with a deliberate row change."""
        text = self.period_yaml.read_text()
        cfg = yaml.safe_load(text)
        key = f"{name}.csv"
        old = cfg["expected_counts"][key]
        self.period_yaml.write_text(text.replace(f"{key}: {old}\n", f"{key}: {old + delta}\n", 1))

    def add_to_batch(self, service_date: str, records: int, units: int) -> None:
        rows = self.rows("usage_batch_controls")
        for r in rows:
            if r["service_date"] == service_date:
                r["distinct_active_record_count"] = str(int(r["distinct_active_record_count"]) + records)
                r["active_units_total"] = str(int(r["active_units_total"]) + units)
        self.write("usage_batch_controls", rows)


def _usage(record_id: str, account: str, service_date: str, units: int, ingested_at: str, **kw) -> dict:
    return {"record_id": record_id, "product_account_id": account, "sku": "WORKFLOW_RUN", "service_date": service_date,
            "units": str(units), "ingested_at": ingested_at, "record_status": kw.get("status", "active"),
            "replaces_record_id": kw.get("replaces", ""), "batch_id": f"batch-{service_date}"}


BROOKSTONE = "pa_3ecc8f2ea61075"  # Brookstone Data, Inc. (866587): 10,000 included runs, $0.08 overage; clean in October


def extra_usage(i: Inputs, batch: bool = True) -> None:
    i.append("product_usage", _usage("ur_scn_extra_0001", BROOKSTONE, "2026-10-15", 5000, "2026-10-16T02:00:00-06:00"))
    if batch:
        i.add_to_batch("2026-10-15", 1, 5000)


def late_usage(i: Inputs) -> None:
    # Arrives after the usage invoice (Nov 1) but before the close cutoff (Nov 11 18:00).
    i.append("product_usage", _usage("ur_scn_late_0001", BROOKSTONE, "2026-10-15", 5000, "2026-11-05T02:00:00-07:00"))
    i.add_to_batch("2026-10-15", 1, 5000)


def remove_usage(i: Inputs, record_id: str) -> None:
    rows = i.rows("product_usage")
    gone = next(r for r in rows if r["record_id"] == record_id)
    i.write("product_usage", [r for r in rows if r["record_id"] != record_id])
    i.add_to_batch(gone["service_date"], -1, -int(gone["units"]))


def unmapped_account(i: Inputs) -> None:
    # A product account no mapping row assigns to any customer.
    i.append("product_usage", _usage("ur_scn_unmapped_0001", "pa_scn_unmapped01", "2026-10-15", 5000, "2026-10-16T02:00:00-06:00"))
    i.add_to_batch("2026-10-15", 1, 5000)


def missing_platform_invoice(i: Inputs) -> None:
    # Larch Point Services (232251), billed monthly: its October platform invoice never reached Stripe.
    gone = {r["id"] for r in i.rows("stripe_invoices") if r["number"] == "RC-261001-232251-P"}
    assert len(gone) == 1
    i.write("stripe_invoices", [r for r in i.rows("stripe_invoices") if r["id"] not in gone])
    lines = i.rows("stripe_invoice_lines")
    kept = [r for r in lines if r["invoice_id"] not in gone]
    i.write("stripe_invoice_lines", kept)
    i.set_expected_count("stripe_invoices", -1)
    i.set_expected_count("stripe_invoice_lines", len(kept) - len(lines))


def duplicate_usage_row(i: Inputs) -> None:
    rows = i.rows("product_usage")
    target = next(r for r in rows if r["product_account_id"] == BROOKSTONE and r["service_date"] == "2026-10-15")
    i.write("product_usage", rows + [dict(target)])


def shuffled_rows(i: Inputs) -> None:
    rng = random.Random(20261029)
    for path in sorted(i.raw.glob("*.csv")):
        rows = i.rows(path.stem)
        rng.shuffle(rows)
        i.write(path.stem, rows)


def restated_usage(i: Inputs) -> None:
    # One Brookstone record is restated: the original is superseded by a correction with the same units.
    rows = i.rows("product_usage")
    old = next(r for r in rows if r["product_account_id"] == BROOKSTONE and r["service_date"] == "2026-10-15")
    i.append("product_usage", _usage("ur_scn_restated_0001", BROOKSTONE, old["service_date"], int(old["units"]),
                                     "2026-10-17T02:00:00-06:00", replaces=old["record_id"]))


# ---------------------------------------------------------------- comparing results

FINDING_FIELDS = ("rule", "customer_id", "stream", "service_period", "status",
                  "billing_effect", "october_revenue_effect", "exposure", "follow_up")


def fingerprint(out_dir: Path) -> dict:
    """What a Scenario compares: Findings (without citations), totals by stream, and every control's status."""
    def read(name):
        with open(out_dir / name, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    return {
        "findings": sorted(tuple(r[k] for k in FINDING_FIELDS) for r in read("findings.csv")),
        "totals": {r["stream"]: {k: v for k, v in r.items() if k != "stream"} for r in read("totals_by_stream.csv")},
        "controls": {f"{r['group']}.{r['name']}": r["status"] for r in read("controls.csv")},
    }


def diff(base: dict, new: dict) -> dict:
    """The difference between two fingerprints, in a form a person can read and a test can compare."""
    out: dict = {}
    added = sorted(set(new["findings"]) - set(base["findings"]))
    removed = sorted(set(base["findings"]) - set(new["findings"]))
    if added:
        out["findings_added"] = [dict(zip(FINDING_FIELDS, f)) for f in added]
    if removed:
        out["findings_removed"] = [dict(zip(FINDING_FIELDS, f)) for f in removed]
    totals = {s: {k: (base["totals"].get(s, {}).get(k), v) for k, v in row.items()
                  if base["totals"].get(s, {}).get(k) != v}
              for s, row in new["totals"].items()}
    totals = {s: t for s, t in totals.items() if t}
    if totals:
        out["totals"] = totals
    controls = {k: (base["controls"].get(k), v) for k, v in new["controls"].items() if base["controls"].get(k) != v}
    controls.update({k: (v, None) for k, v in base["controls"].items() if k not in new["controls"]})
    if controls:
        out["controls"] = controls
    return out


# ---------------------------------------------------------------- the Scenarios

@dataclass(frozen=True)
class Scenario:
    name: str
    kind: str  # "catch" or "ignore"
    description: str
    change: Callable[[Inputs], None]
    expected: dict = field(default_factory=dict)  # the expected diff(); empty for "ignore"


def _finding(rule, customer, status, billing, revenue, stream="usage", exposure="", follow_up="false"):
    return {"rule": rule, "customer_id": customer, "stream": stream, "service_period": PERIOD, "status": status,
            "billing_effect": billing, "october_revenue_effect": revenue, "exposure": exposure, "follow_up": follow_up}


def _usage_totals(underbilled=None, overbilled=None, understated=None, overstated=None, errors=None, needs_info=None):
    """Expected changes to the usage row of totals_by_stream, from October's 6,309.50 / -3,096.80 / 6,209.50 / -3,096.80."""
    base = {"underbilled": "6309.50", "overbilled": "-3096.80", "october_understated": "6209.50",
            "october_overstated": "-3096.80", "errors": "4", "needs_info": "2"}
    new = {"underbilled": underbilled, "overbilled": overbilled, "october_understated": understated,
           "october_overstated": overstated, "errors": errors, "needs_info": needs_info}
    return {"usage": {k: (base[k], v) for k, v in new.items() if v is not None}}


# The Independent Review compares the Findings with committed reviews of the *unchanged* October data, so a
# new Finding on a reviewed customer is a Disagreement until the reviewer is rerun (`make review-findings`).
STALE_REVIEW = {"agents.independent_review": ("pass", "warn")}

# Brookstone's October: 35,513 validated runs, 10,000 included, 25,513 overage at $0.08 = $2,041.04, billed on
# RC-261101-866587-U (25,513 runs) and accrued for the same amount.
SCENARIOS: list[Scenario] = [
    Scenario(
        "extra-usage", "catch",
        "Brookstone Data gets 5,000 more runs on Oct 15, ingested Oct 16 (before the Nov 1 invoice); batch totals updated.",
        extra_usage,
        {"findings_added": [_finding("usage_quantity", "866587", "error", "400.00", "400.00")],  # 5,000 × $0.08
         "totals": _usage_totals(underbilled="6709.50", understated="6609.50", errors="5"),
         "controls": STALE_REVIEW},
    ),
    Scenario(
        "extra-usage-no-batch", "catch",
        "As extra-usage, but the daily batch control is not updated: the extract no longer ties out.",
        lambda i: extra_usage(i, batch=False),
        {"findings_added": [_finding("usage_quantity", "866587", "error", "400.00", "400.00")],
         "totals": _usage_totals(underbilled="6709.50", understated="6609.50", errors="5"),
         "controls": {"usage.01_batch_tieout": ("pass", "fail"), **STALE_REVIEW}},
    ),
    Scenario(
        "fewer-usage-records", "catch",
        "Brookstone Data's Oct 15 record (1,322 runs) is withdrawn from the usage export; batch totals updated.",
        lambda i: remove_usage(i, "ur_7d4cbe65603fc8"),
        {"findings_added": [_finding("usage_quantity", "866587", "error", "-105.76", "-105.76")],  # 1,322 × $0.08
         "totals": _usage_totals(overbilled="-3202.56", overstated="-3202.56", errors="5"),
         "controls": STALE_REVIEW},
    ),
    Scenario(
        "late-usage", "catch",
        "Brookstone Data gets 5,000 more runs on Oct 15, ingested Nov 5: after the usage invoice, before the cutoff.",
        late_usage,
        {"findings_added": [_finding("usage_late_record", "866587", "error", "400.00", "400.00")],
         "totals": _usage_totals(underbilled="6709.50", understated="6609.50", errors="5"),
         "controls": STALE_REVIEW},
    ),
    Scenario(
        "unmapped-account", "catch",
        "5,000 October runs on a product account that no mapping assigns to a customer.",
        unmapped_account,
        {"findings_added": [_finding("usage_unverified", "", "needs_info", "", "", exposure=(
            "Unpriced: 5,000 runs. $0 if the workspace is internal; otherwise the owner's overage on its combined "
            "October runs under its executed contract."))],
         "totals": _usage_totals(needs_info="3")},
    ),
    Scenario(
        "missing-platform-invoice", "catch",
        "Larch Point Services' October platform invoice ($3,000.00, billed monthly) is missing from Stripe; row counts "
        "updated. NetSuite still holds its posting; nothing flags that mismatch directly.",
        missing_platform_invoice,
        {"findings_added": [_finding("platform_missing_document", "232251", "error", "3000.00", "0.00", stream="platform")],
         "totals": {"platform": {"underbilled": ("526.03", "3526.03"), "errors": ("2", "3")}},
         "controls": STALE_REVIEW},
    ),
    Scenario("duplicate-usage-row", "ignore", "One usage row is exported twice, exactly.", duplicate_usage_row),
    Scenario("shuffled-rows", "ignore", "The rows of every CSV are reordered.", shuffled_rows),
    Scenario("restated-usage", "ignore",
             "One Brookstone record is superseded by a correction with the same units.", restated_usage),
]


def run_period(root: Path, period: str = PERIOD) -> dict:
    """Run the real pipeline on a copied root and return its fingerprint."""
    from workbench.errors import WorkbenchError
    from workbench.pipeline import run

    try:
        run(period, root)
    except WorkbenchError as e:
        return {"input_error": str(e)}
    return fingerprint(root / "out" / period)


def prepare(root: Path, scenario: Scenario | None, source: Path = REPO) -> Path:
    """Copy data/ under root and apply the Scenario's change (None = the untouched period)."""
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(source / "data", root / "data")
    if scenario:
        scenario.change(Inputs(root))
    return root


def get(name: str) -> Scenario:
    for s in SCENARIOS:
        if s.name == name:
            return s
    sys.exit(f"Unknown Scenario {name!r}. Known: {', '.join(s.name for s in SCENARIOS)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one Scenario and show how its results differ from the untouched period.")
    ap.add_argument("name", nargs="?", help="Scenario name; omit to list them")
    args = ap.parse_args()
    if not args.name:
        for s in SCENARIOS:
            print(f"{s.name:28} {s.kind:6} {s.description}")
        return
    s = get(args.name)
    base_root = REPO / "out" / "scenarios" / "_baseline"
    root = REPO / "out" / "scenarios" / s.name
    print(f"Scenario {s.name} ({s.kind}): {s.description}")
    base = run_period(prepare(base_root, None))
    got = diff(base, run_period(prepare(root, s)))
    print(yaml.safe_dump(got or {"difference": "none"}, sort_keys=False, width=120))
    print(f"Report: {(root / 'out' / PERIOD / 'report.html').relative_to(REPO)}")
    ok = got == s.expected
    print("As expected." if ok else "NOT as expected. Expected:\n" + yaml.safe_dump(s.expected or {"difference": "none"}, sort_keys=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
