"""Four-Eye Check: a second agent classifies every customer × stream from source files alone.

Decision (wayfinder: "How should the independent findings reviewer work?"):
- One call per customer (both streams), `claude-opus-5-5` at effort high, structured output.
- Input: that customer's raw source rows, each prefixed with file:line (Salesforce row, contract
  register rows and documents, its usage rows via the raw mapping file, Stripe invoices, lines and
  credit notes, GL lines, opening balances, revenue-plan rows), plus the full mapping file, all
  Billing Messages and START_HERE. Never our Findings, Contract Terms, validated usage or reconciliations.
- Output per stream: status (clean / error / valid_explanation / needs_info), Billing Effect,
  October Revenue Effect, a reason and citations.
- `make run` compares it with the Findings (same status, amounts equal to the cent). Each Disagreement
  stays open, and `make run` warns, until it is resolved in reviewer_resolutions.yaml with a reason.
  Nothing changes automatically.
- Answers are cached by (model, prompt) and committed, so `make run` and CI never need a key.

Run: make review-findings PERIOD=2026-10
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import yaml

from workbench.agents import ResponseCache, api_key, cache_key
from workbench.pdf import extract_to
from workbench.period import Period, load_period

MODEL = "claude-opus-5-5"
EFFORT = "high"
STREAMS = ("platform", "usage")
STATUSES = ["clean", "error", "valid_explanation", "needs_info"]

_STREAM = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": STATUSES},
        "billing_effect": {"type": ["string", "null"]},
        "october_revenue_effect": {"type": ["string", "null"]},
        "reason": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["status", "billing_effect", "october_revenue_effect", "reason", "citations"],
    "additionalProperties": False,
}
SCHEMA = {"type": "object", "properties": {s: _STREAM for s in STREAMS},
          "required": list(STREAMS), "additionalProperties": False}

INSTRUCTIONS = """You are an independent reviewer in RelayCloud's October 2026 billing review. Working only
from the source material given, decide for ONE customer whether its October billing and October revenue
are right, separately for two streams: platform (subscription fees, product prod_platform, GL 4000) and
usage (workflow-run overage, product prod_workflow_run, GL 4010). START_HERE is the policy; follow it exactly,
including its cutoff, rounding and accounting rules. Billing Messages are evidence; weigh who sent them.

For each stream return:
- status:
  - clean: nothing looks wrong and nothing needs explaining.
  - error: billing or booked October revenue departs from the executed contract terms or validated usage,
    with no approval or policy that explains it.
  - valid_explanation: something looks off at first sight (an absent invoice, a credit note, a concession,
    a void document) but an approval or a policy explains it; no correction is needed.
  - needs_info: it cannot be resolved or quantified from the evidence supplied.
- billing_effect: for October service, the signed USD amount billing is off by, as expected minus billed
  (positive = underbilled, negative = overbilled), e.g. "-120.00". "0.00" when billing is right. null when
  it cannot be supported (needs_info).
- october_revenue_effect: the signed USD amount October's booked revenue is off by, as expected minus booked
  (positive = understated). "0.00" when right. null when not supportable.
- reason: one short paragraph with the arithmetic.
- citations: the file:line references (as given) that your answer relies on.

Issues with later service (e.g. a November-service invoice) are follow-ups: mention them in the reason but
do not include them in the October effects. Usage that no verified mapping assigns to this customer is not
its usage."""


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _rows(raw: Path, name: str, keep) -> str:
    """Raw CSV lines whose parsed row satisfies keep(row), each prefixed with its file:line."""
    lines = _lines(raw / name)
    header = next(csv.reader([lines[0]]))
    out = [f"{name} header: {lines[0]}"]
    for i, ln in enumerate(lines[1:], start=2):
        row = dict(zip(header, next(csv.reader([ln]))))
        if keep(row):
            out.append(f"data/raw/{raw.name}/{name}:{i}: {ln}")
    return "\n".join(out)


def common_context(period: Period) -> str:
    raw = period.raw_dir
    start_here = extract_to(raw / "START_HERE.pdf", period.extracted_dir)
    messages = extract_to(raw / "billing_followups.pdf", period.extracted_dir)
    return (f"<start_here file=\"data/raw/{period.key}/START_HERE.pdf\">\n{start_here}\n</start_here>\n\n"
            f"<billing_messages file=\"data/raw/{period.key}/billing_followups.pdf\">\n{messages}\n</billing_messages>\n\n"
            f"<product_account_mapping>\n{_rows(raw, 'product_account_mapping.csv', lambda r: True)}\n</product_account_mapping>")


def customer_context(period: Period, account: dict) -> str:
    raw = period.raw_dir
    sf, ns, stripe = account["AccountId"], account["NetSuiteCustomerInternalId__c"], account["StripeCustomerId__c"]
    reg = [r for r in csv.DictReader(open(raw / "contract_register.csv", encoding="utf-8")) if r["salesforce_account_id"] == sf]
    pas = {r["product_account_id"] for r in csv.DictReader(open(raw / "product_account_mapping.csv", encoding="utf-8"))
           if r["salesforce_account_id"] == sf}
    invoices = {r["id"] for r in csv.DictReader(open(raw / "stripe_invoices.csv", encoding="utf-8")) if r["customer_id"] == stripe}
    notes = {r["id"] for r in csv.DictReader(open(raw / "stripe_credit_notes.csv", encoding="utf-8")) if r["customer_id"] == stripe}
    docs = "\n\n".join(
        f"<document file=\"data/raw/{period.key}/contracts/{r['document_filename']}\">\n"
        f"{extract_to(raw / 'contracts' / r['document_filename'], period.extracted_dir)}\n</document>" for r in reg)
    parts = [
        _rows(raw, "salesforce_accounts.csv", lambda r: r["AccountId"] == sf),
        _rows(raw, "contract_register.csv", lambda r: r["salesforce_account_id"] == sf),
        _rows(raw, "product_usage.csv", lambda r: r["product_account_id"] in pas),
        _rows(raw, "stripe_invoices.csv", lambda r: r["id"] in invoices),
        _rows(raw, "stripe_invoice_lines.csv", lambda r: r["invoice_id"] in invoices),
        _rows(raw, "stripe_credit_notes.csv", lambda r: r["id"] in notes),
        _rows(raw, "stripe_credit_note_lines.csv", lambda r: r["credit_note_id"] in notes),
        _rows(raw, "netsuite_opening_balances.csv", lambda r: r["Customer Internal ID"] == ns),
        _rows(raw, "netsuite_gl_detail.csv", lambda r: r["Customer Internal ID"] == ns),
        _rows(raw, "netsuite_revenue_plan_detail.csv", lambda r: r["Customer Internal ID"] == ns),
    ]
    return (f"Customer: {account['AccountName']} (Salesforce {sf}, NetSuite {ns}, Stripe {stripe}).\n\n"
            f"{docs}\n\n<source_rows>\n" + "\n\n".join(parts) + "\n</source_rows>")


def _call(key: str, system: list, user: str) -> dict:
    import anthropic  # agents dependency group only

    client = anthropic.Anthropic(api_key=key)
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=16000, system=system, messages=[{"role": "user", "content": user}],
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    )
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"stop_reason {resp.stop_reason}")
    text = next(b.text for b in resp.content if b.type == "text")
    return {"output": json.loads(text), "model": resp.model,
            "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                      "cache_read_input_tokens": resp.usage.cache_read_input_tokens or 0},
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def run(period: Period, workers: int = 6, only: list[str] | None = None) -> dict:
    accounts = list(csv.DictReader(open(period.raw_dir / "salesforce_accounts.csv", encoding="utf-8")))
    if only:
        accounts = [a for a in accounts if a["NetSuiteCustomerInternalId__c"] in only]
    common = common_context(period)
    system = [{"type": "text", "text": INSTRUCTIONS},
              {"type": "text", "text": common, "cache_control": {"type": "ephemeral"}}]
    cache = ResponseCache(period.curated_dir / "reviews" / "reviewer_cache.json")
    jobs = {}
    for a in accounts:
        user = customer_context(period, a)
        jobs[a["NetSuiteCustomerInternalId__c"]] = (a, user, cache_key(MODEL, EFFORT, INSTRUCTIONS, common, SCHEMA, user))
    todo = {cid: j for cid, j in jobs.items() if cache.get(j[2]) is None}
    if todo:
        key = api_key("ANTHROPIC_API_KEY", period.root)
        if not key:
            sys.exit(f"{len(todo)} customers have no cached review and there is no ANTHROPIC_API_KEY (env or .env).")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {cid: pool.submit(_call, key, system, j[1]) for cid, j in todo.items()}
            for cid, f in futures.items():
                try:
                    cache.put(jobs[cid][2], {"customer_id": cid, **f.result()})
                    print(f"  reviewed {jobs[cid][0]['AccountName']}", flush=True)
                except Exception as e:  # keep the others; a rerun retries only what is missing
                    print(f"  FAILED {jobs[cid][0]['AccountName']}: {e}", file=sys.stderr, flush=True)
    reviews = []
    for cid, (a, _, k) in jobs.items():
        hit = cache.get(k)
        if hit is None:
            sys.exit("Some reviews failed; rerun `make review-findings` to retry them.")
        for s in STREAMS:
            reviews.append({"customer_id": cid, "customer_name": a["AccountName"], "stream": s, **hit["output"][s]})
    calls = [{"customer_id": cid, "model": cache.get(k)["model"], "usage": cache.get(k)["usage"],
              "recorded_at": cache.get(k)["recorded_at"]} for cid, (_, _, k) in jobs.items()]
    out = {"model": MODEL, "effort": EFFORT, "reviews": reviews, "calls": calls}
    if only:
        return out  # trial on a subset: answers are cached, the committed results are untouched
    (period.curated_dir / "reviews" / "reviewer.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return out


# ---- comparison, used by `make run` (no key, no network) ----------------------------------------

def _dec(v) -> Decimal | None:
    return None if v in (None, "") else Decimal(str(v)).quantize(Decimal("0.01"))


def compare(con, period: Period):
    """Create `four_eye_check` (one row per customer × stream) and return its control."""
    from workbench.controls import ControlResult
    path = period.curated_dir / "reviews" / "reviewer.json"
    con.execute("""CREATE OR REPLACE TABLE four_eye_check (customer_id VARCHAR, customer_name VARCHAR, stream VARCHAR,
        rules_status VARCHAR, rules_billing DECIMAL(18,2), rules_revenue DECIMAL(18,2), finding_ids VARCHAR,
        reviewer_status VARCHAR, reviewer_billing DECIMAL(18,2), reviewer_revenue DECIMAL(18,2), reviewer_reason VARCHAR,
        reviewer_citations VARCHAR, agreement VARCHAR, resolution VARCHAR, resolution_reason VARCHAR)""")
    if not path.exists():
        return ControlResult("agents", "four_eye", "Four-Eye Check: every Disagreement with the independent reviewer is resolved",
                             "warn", 0, None, "Four-Eye Check not run (make review-findings)")
    reviews = {(r["customer_id"], r["stream"]): r for r in json.loads(path.read_text())["reviews"]}
    res_path = period.curated_dir / "reviews" / "reviewer_resolutions.yaml"
    resolutions = {(str(r["customer_id"]), r["stream"]): r
                   for r in ((yaml.safe_load(res_path.read_text()) or {}).get("resolutions") or [] if res_path.exists() else [])}
    rules = con.execute("""
        SELECT c.customer_id, c.customer_name, c.stream, c.status,
               sum(f.billing_effect) FILTER (WHERE NOT f.follow_up), sum(f.october_revenue_effect) FILTER (WHERE NOT f.follow_up),
               c.finding_ids
        FROM coverage c LEFT JOIN findings f ON f.customer_id = c.customer_id AND f.stream = c.stream
        GROUP BY ALL ORDER BY c.customer_name, c.stream""").fetchall()
    open_items = []
    for cid, name, stream, status, rb, rr, fids in rules:
        rv = reviews.get((cid, stream), {})
        rbill, rrev = rb if status in ("error", "valid_explanation") else (Decimal("0.00") if status == "clean" else None), \
            rr if status in ("error", "valid_explanation") else (Decimal("0.00") if status == "clean" else None)
        vb, vr = _dec(rv.get("billing_effect")), _dec(rv.get("october_revenue_effect"))
        if not rv:
            agreement = "not reviewed"
        elif rv["status"] != status:
            agreement = "status differs"
        elif (rbill or 0) != (vb or 0) or (rrev or 0) != (vr or 0):
            agreement = "amount differs"
        else:
            agreement = "agrees"
        res = resolutions.get((cid, stream))
        if agreement != "agrees" and not res:
            open_items.append(f"{name} {stream} ({agreement})")
        con.execute("INSERT INTO four_eye_check VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            cid, name, stream, status, rbill, rrev, fids, rv.get("status"), vb, vr, rv.get("reason"),
            "; ".join(rv.get("citations") or []), agreement,
            res["resolution"] if res else None, res.get("reason") if res else None])
    n = len(rules)
    agreed = n - con.execute("SELECT count(*) FROM four_eye_check WHERE agreement <> 'agrees'").fetchone()[0]
    return ControlResult("agents", "four_eye", "Four-Eye Check: every Disagreement with the independent reviewer is resolved",
                         "warn" if open_items else "pass", len(open_items), "four_eye_check",
                         f"agrees on {agreed}/{n} customer-streams; open: " + "; ".join(open_items) if open_items
                         else f"agrees on {agreed}/{n} customer-streams; all others resolved")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--period", required=True)
    ap.add_argument("--only", nargs="*", help="NetSuite customer ids to review (trial; does not write results)")
    args = ap.parse_args()
    out = run(load_period(args.period), only=args.only)
    tokens = sum(c["usage"]["input_tokens"] + c["usage"].get("cache_read_input_tokens", 0) for c in out["calls"])
    print(f"Reviewed {len(out['calls'])} customers ({tokens:,} input tokens incl. cache reads). Run `make run` to compare.")


if __name__ == "__main__":
    main()
