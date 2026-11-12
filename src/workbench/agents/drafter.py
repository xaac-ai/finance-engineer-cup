"""Amendment-term drafter: Claude reads an executed Amendment and drafts its Contract Term changes.

Decision (wayfinder: "How should the Amendment-term drafter work?"):
- Model `claude-opus-5-5` through the Anthropic SDK, with structured output (a JSON schema) so every
  draft is checkable. The server-side refusal fallback is on; the model that answered is recorded.
- Input per Amendment: its extracted text, the parsed terms of the Order Form it amends, and the
  term vocabulary. It never sees the curated amendment_terms.yaml.
- Output: data/curated/<period>/drafts/amendment_terms.yaml, the curated file's shape plus
  confidence, notes, quote_check and used_by_engine. Never written into the curated file: a person
  diffs and copies what they accept (a Drafted Term has no effect until then).
- Every drafted quote goes through the same word-for-word gate as curated quotes.
- Responses are cached by (model, prompt, document) in drafter_cache.json, committed, so a rerun
  without a key replays them. Each run is scored against the curated file (drafter_eval.json).

Run: make draft-terms PERIOD=2026-10
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import yaml

from workbench.agents import ResponseCache, api_key, cache_key
from workbench.contracts import parse_order_form
from workbench.pdf import extract_to, normalize
from workbench.period import Period, load_period

MODEL = "claude-opus-5-5"
EFFORT = "high"

# The term names the workbench knows. used_by_engine: the review's calculations read this term.
VOCABULARY = {
    "included_runs_per_month": ("Included workflow runs per calendar month (integer).", True),
    "overage_rate": ("Overage price in USD per excess run (decimal, e.g. 0.40).", True),
    "platform_annual_rate": ("Annual platform consideration in USD per year (e.g. 60000.00).", True),
    "platform_invoice_amount": ("Amount of each regular platform invoice in USD (e.g. 5000.00).", True),
    "billing_frequency": ("annual or monthly.", True),
    "billing_anchor_day": ("Day of month platform invoices are issued (integer).", False),
    "payment_terms": ("Payment terms text, e.g. 'Net 30 days / USD'.", False),
    "service_end_exclusive": ("First day after the service term (ISO date).", True),
    "allowance_weighting_rule": ("How a mid-month allowance change applies to that month (short text).", False),
    "catch_up_amount": ("A stated one-off charge in USD for service before the next regular invoice.", True),
    "incremental_consideration": ("Stated total incremental consideration in USD over the remaining term.", False),
    "final_invoice_credit": ("Stated credit in USD on the final invoice.", False),
}

SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "value": {"type": "string"},
                    "effective_from": {"type": "string"},
                    "section": {"type": "string"},
                    "quote": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "notes": {"type": "string"},
                },
                "required": ["term", "value", "effective_from", "section", "quote", "confidence", "notes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["changes"],
    "additionalProperties": False,
}

SYSTEM = """You extract contract term changes from an executed contract Amendment for a billing review.
Your draft is checked by a person and by an exact-quote gate, so precision matters more than coverage.

Rules:
- Report every commercial term the Amendment changes, and every amount or rule it states for applying
  the change (for example a one-off catch-up charge, an incremental consideration total, a final
  credit, or how a mid-month change is weighted). Do not report terms it leaves unchanged.
- Use a name from the vocabulary when one fits. Only if none fits, invent a short snake_case name and
  say so in notes.
- value: plain values, no currency symbols or thousands separators (45000, 0.40, 60000.00); ISO dates;
  short plain text for rules.
- effective_from: the ISO date the change applies from, as stated in the Amendment.
- section: the numbered section heading the quote comes from, exactly as written (e.g. "03 CHANGES TO
  COMMERCIAL TERMS").
- quote: a contiguous passage copied character for character from the Amendment text that states the
  change. Do not paraphrase, reorder, or join separate passages. Line breaks may be written as spaces.
- confidence: high only when the text states the value and date explicitly."""


def _register(period: Period) -> dict[str, dict]:
    with open(period.raw_dir / "contract_register.csv", newline="", encoding="utf-8") as fh:
        return {r["document_id"]: r for r in csv.DictReader(fh)}


def _prompt(doc_id: str, text: str, base_doc: str, base_terms: list, register_row: dict) -> str:
    previous = "\n".join(f"- {t.term} = {t.value}" for t in base_terms)
    vocab = "\n".join(f"- {k}: {d}" for k, (d, _) in VOCABULARY.items())
    return (f"Amendment {doc_id} amends Order Form {base_doc}. The contract register lists its effective date "
            f"as {register_row['effective_from']}.\n\nTerms of {base_doc} before this Amendment:\n{previous}\n\n"
            f"Vocabulary:\n{vocab}\n\nAmendment text:\n<amendment>\n{text}\n</amendment>")


def _call(key: str, user: str) -> dict:
    import anthropic  # agents dependency group only; `make run` never imports this module

    client = anthropic.Anthropic(api_key=key)
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=16000, system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        sys.exit(f"The model declined ({resp.stop_details}). Nothing written.")
    if resp.stop_reason == "max_tokens":
        sys.exit("The response hit max_tokens. Nothing written.")
    text = next(b.text for b in resp.content if b.type == "text")
    return {"output": json.loads(text), "model": resp.model, "request_id": resp._request_id,
            "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _num(v) -> Decimal | None:
    try:
        return Decimal(str(v).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None


def score(drafts: dict[str, list[dict]], curated: dict[str, list[dict]], register: dict[str, dict]) -> dict:
    """Compare drafted terms with the hand-curated ones, per Amendment."""
    docs, totals = [], {"curated": 0, "found": 0, "value_match": 0, "value_comparable": 0,
                        "date_match": 0, "drafted": 0, "quote_pass": 0, "extra": 0}
    for doc_id, cur in sorted(curated.items()):
        drafted = {d["term"]: d for d in drafts.get(doc_id, [])}
        rows = []
        for c in cur:
            d = drafted.get(c["term"])
            want_date = str(c.get("effective_from") or register[doc_id]["effective_from"])
            row = {"term": c["term"], "curated_value": str(c["value"]), "found": d is not None}
            if d:
                cv, dv = _num(c["value"]), _num(d["value"])
                row.update(drafted_value=d["value"], quote_check=d["quote_check"],
                           value_match=(cv == dv) if cv is not None and dv is not None else None,
                           date_match=d["effective_from"] == want_date)
            rows.append(row)
        extra = sorted(set(drafted) - {c["term"] for c in cur})
        docs.append({"document_id": doc_id, "terms": rows, "extra_terms": extra})
        totals["curated"] += len(cur)
        totals["found"] += sum(r["found"] for r in rows)
        totals["value_comparable"] += sum(r.get("value_match") is not None for r in rows)
        totals["value_match"] += sum(r.get("value_match") is True for r in rows)
        totals["date_match"] += sum(r.get("date_match") is True for r in rows)
        totals["drafted"] += len(drafted)
        totals["quote_pass"] += sum(d["quote_check"] == "passed" for d in drafted.values())
        totals["extra"] += len(extra)
    return {"totals": totals, "documents": docs}


def run(period: Period) -> dict:
    register = _register(period)
    amendments = sorted(d for d, r in register.items() if r["document_type"] == "amendment")
    drafts_dir = period.curated_dir / "drafts"
    cache = ResponseCache(drafts_dir / "drafter_cache.json")
    key = None
    drafts: dict[str, list[dict]] = {}
    calls = []
    for doc_id in amendments:
        row = register[doc_id]
        base = row["supersedes_document_id"]
        text = extract_to(period.raw_dir / "contracts" / row["document_filename"], period.extracted_dir)
        base_text = extract_to(period.raw_dir / "contracts" / register[base]["document_filename"], period.extracted_dir)
        _, base_terms = parse_order_form(base, base_text)
        user = _prompt(doc_id, text, base, base_terms, row)
        k = cache_key(MODEL, EFFORT, SYSTEM, SCHEMA, user)
        hit = cache.get(k)
        replayed = hit is not None
        if hit is None:
            key = key or api_key("ANTHROPIC_API_KEY", period.root)
            if not key:
                sys.exit(f"No cached draft for {doc_id} and no ANTHROPIC_API_KEY (env or .env).")
            hit = _call(key, user)
            hit = {"document_id": doc_id, **hit}
            cache.put(k, hit)
        calls.append({"document_id": doc_id, "cache_key": k, "model": hit["model"], "usage": hit["usage"],
                      "recorded_at": hit["recorded_at"], "replayed": replayed})
        haystack = normalize(text)
        drafts[doc_id] = [{
            **c,
            "quote_check": "passed" if normalize(c["quote"]) in haystack else "failed",
            "used_by_engine": VOCABULARY.get(c["term"], ("", False))[1],
            "in_vocabulary": c["term"] in VOCABULARY,
        } for c in hit["output"]["changes"]]

    drafts_dir.mkdir(parents=True, exist_ok=True)
    out = {"amendments": [{"document_id": d, "changes": drafts[d]} for d in amendments]}
    header = (f"# DRAFT - generated by `make draft-terms` with {MODEL} (effort {EFFORT}). Not used by the review.\n"
              f"# A Drafted Term has no effect until a person copies it into ../amendment_terms.yaml.\n"
              f"# quote_check: the word-for-word gate; used_by_engine: the review's calculations read this term.\n")
    (drafts_dir / "amendment_terms.yaml").write_text(
        header + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=120))

    curated_doc = yaml.safe_load((period.curated_dir / "amendment_terms.yaml").read_text()) or {}
    curated = {a["document_id"]: a.get("changes") or [] for a in curated_doc.get("amendments") or []}
    evaluation = {"model": MODEL, "effort": EFFORT, "calls": calls, **score(drafts, curated, register)}
    (drafts_dir / "drafter_eval.json").write_text(json.dumps(evaluation, indent=1, sort_keys=True) + "\n")
    return evaluation


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--period", required=True)
    ev = run(load_period(ap.parse_args().period))
    t = ev["totals"]
    print(f"Drafted {t['drafted']} terms; {t['found']}/{t['curated']} curated terms found, "
          f"values {t['value_match']}/{t['value_comparable']} (numeric), dates {t['date_match']}/{t['found']}, "
          f"quotes passing {t['quote_pass']}/{t['drafted']}, extra {t['extra']}.")


if __name__ == "__main__":
    main()
