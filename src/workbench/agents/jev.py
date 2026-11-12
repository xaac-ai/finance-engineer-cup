"""Jev term check: after the quote gate, does the Amendment text support each Contract Term change?

Decision (wayfinder: "Can Jev tell a supported Amendment term from an unsupported one?" and
"Wire the Jev term check into the workbench"):
- TypeSafe's System One model `jev-1.14.0`, one fixed-choice question per term:
  supports / contradicts / says_nothing.
- The claim is a sentence built from the term, value and effective date. The section text is every
  numbered section the Amendment's terms are quoted from (03 and 04 in October). In the spike a table
  section alone lacked the effective date and scored low; the two sections together scored 0.96 and up.
- Gate: `supports` with confidence >= 0.8 is auto-accepted; anything else goes to human review.
- Checks curated terms (gating) and drafted terms (shown alongside). Answers are cached and committed,
  so `make run` and CI read the results without a key. A curated term with no matching check fails
  a control in `make run`, so changed curation forces a re-check.

Run: make jev-check PERIOD=2026-10
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from workbench.agents import ResponseCache, api_key, cache_key
from workbench.pdf import extract_to
from workbench.period import Period, load_period

MODEL = "jev-1.14.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
AUTO_ACCEPT = 0.8
QUESTION = {
    "type": "choice",
    "instructions": "How does `section` relate to `claim`?",
    "criteria": {
        "supports": "The section states the claim or directly implies that it is true",
        "contradicts": "The section states the opposite of the claim or implies it is false",
        "says_nothing": "The section does not address what the claim asserts, either way",
    },
}


def _usd(v: str) -> str:
    return f"USD {Decimal(v):,.2f}"


def claim(term: str, value: str, effective: date) -> str:
    """The sentence Jev judges. Dates are written as the Amendments write them."""
    on = f"{effective:%B} {effective.day}, {effective.year}"
    try:
        templates = {
            "included_runs_per_month": lambda: f"From {on} the customer's included workflow runs are {int(value):,} per calendar month.",
            "overage_rate": lambda: f"From {on} the overage rate is USD {Decimal(value):.2f} per excess run.",
            "platform_annual_rate": lambda: f"From {on} the annual platform rate is {_usd(value)} per year.",
            "platform_invoice_amount": lambda: f"From {on} each monthly platform invoice is {_usd(value)}.",
            "catch_up_amount": lambda: f"The upgrade catch-up charge is {_usd(value)}.",
            "incremental_consideration": lambda: f"Incremental consideration for the remaining service term is {_usd(value)}.",
            "final_invoice_credit": lambda: f"The final platform invoice includes a {_usd(value)} credit.",
            "allowance_weighting_rule": lambda: f"The amendment states this allowance rule: {value}.",
        }
        if term in templates:
            return templates[term]()
    except (InvalidOperation, ValueError):
        pass
    return f"From {on}, {term.replace('_', ' ')} is {value}."


def sections(text: str, prefixes: list[str]) -> str:
    """The given numbered sections of an extracted document, whitespace-normalised, in document order."""
    parts = []
    for p in sorted(set(prefixes)):
        m = re.search(rf"(?ms)^{re.escape(p)} [A-Z][A-Z /]+$.*?(?=^\d\d [A-Z][A-Z /]+$|\Z)", text)
        if not m:
            sys.exit(f"Section {p} not found in the Amendment text.")
        parts.append(re.sub(r"\s+", " ", m.group(0)).strip())
    return " ".join(parts)


def ask(key: str, claim_text: str, section: str) -> dict:
    body = json.dumps({"model": MODEL, "state": {"claim": claim_text, "section": section},
                       "questions": {"relation": QUESTION}}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "workbench-jev-check"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"TypeSafe API error {e.code}: {e.read().decode()[:300]}")
    a = resp["answers"]["relation"]
    return {"choice": a["choice"], "confidence": a["confidence"], "probabilities": a["probabilities"],
            "model": resp.get("model") or MODEL}


def _terms(path: Path, source: str) -> list[dict]:
    doc = yaml.safe_load(path.read_text()) if path.exists() else {}
    return [{**c, "document_id": a["document_id"], "source": source}
            for a in (doc or {}).get("amendments") or [] for c in a.get("changes") or []]


def check_id(t: dict, effective: str) -> str:
    """Identity of what was checked: changing the term, value, date or quote needs a new check."""
    return cache_key(t["document_id"], t["term"], str(t["value"]), effective, t["quote"])


def run(period: Period) -> dict:
    with open(period.raw_dir / "contract_register.csv", newline="", encoding="utf-8") as fh:
        register = {r["document_id"]: r for r in csv.DictReader(fh)}
    terms = _terms(period.curated_dir / "amendment_terms.yaml", "curated") + \
        _terms(period.curated_dir / "drafts" / "amendment_terms.yaml", "drafted")
    cited = {}
    for t in terms:
        cited.setdefault(t["document_id"], set()).add(t["section"].split()[0])
    cache = ResponseCache(period.curated_dir / "term_checks" / "jev_cache.json")
    key, rows = None, []
    for t in terms:
        reg = register[t["document_id"]]
        effective = str(t.get("effective_from") or reg["effective_from"])
        text = extract_to(period.raw_dir / "contracts" / reg["document_filename"], period.extracted_dir)
        c = claim(t["term"], str(t["value"]), date.fromisoformat(effective))
        sec = sections(text, sorted(cited[t["document_id"]]))
        k = cache_key(MODEL, QUESTION, c, sec)
        answer = cache.get(k)
        if answer is None:
            key = key or api_key("TYPESAFE_API_KEY", period.root)
            if not key:
                sys.exit(f"No cached Jev answer for {t['document_id']} {t['term']} and no TYPESAFE_API_KEY (env or .env).")
            answer = ask(key, c, sec)
            cache.put(k, answer)
        auto = answer["choice"] == "supports" and answer["confidence"] >= AUTO_ACCEPT
        rows.append({"source": t["source"], "document_id": t["document_id"], "term": t["term"], "value": str(t["value"]),
                     "effective_from": effective, "check_id": check_id(t, effective), "claim": c,
                     "sections": sorted(cited[t["document_id"]]), "choice": answer["choice"],
                     "confidence": answer["confidence"], "probabilities": answer["probabilities"],
                     "model": answer["model"], "gate": "auto" if auto else "review"})
    out = {"model": MODEL, "auto_accept": AUTO_ACCEPT, "checks": rows}
    path = period.curated_dir / "term_checks" / "jev_checks.json"
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--period", required=True)
    out = run(load_period(ap.parse_args().period))
    for src in ("curated", "drafted"):
        rs = [r for r in out["checks"] if r["source"] == src]
        print(f"{src}: {sum(r['gate'] == 'auto' for r in rs)}/{len(rs)} auto-accepted; review: "
              + (", ".join(f"{r['document_id']} {r['term']} ({r['choice']} {r['confidence']:.2f})"
                           for r in rs if r["gate"] == "review") or "none"))


if __name__ == "__main__":
    main()


def controls(period: Period) -> list:
    """Controls for `make run`, from the committed check results (no key, no network):
    every curated term has a current Jev check (fail), and every curated term was auto-accepted (warn)."""
    from workbench.controls import ControlResult
    path = period.curated_dir / "term_checks" / "jev_checks.json"
    checks = json.loads(path.read_text())["checks"] if path.exists() else []
    by_id = {r["check_id"]: r for r in checks if r["source"] == "curated"}
    with open(period.raw_dir / "contract_register.csv", newline="", encoding="utf-8") as fh:
        register = {r["document_id"]: r for r in csv.DictReader(fh)}
    curated = _terms(period.curated_dir / "amendment_terms.yaml", "curated")
    missing, review = [], []
    for t in curated:
        r = by_id.get(check_id(t, str(t.get("effective_from") or register[t["document_id"]]["effective_from"])))
        if r is None:
            missing.append(f"{t['document_id']} {t['term']}")
        elif r["gate"] != "auto":
            review.append(f"{t['document_id']} {t['term']} ({r['choice']} {r['confidence']:.2f})")
    return [
        ControlResult("agents", "jev_current", "Every curated Amendment term has a current Jev check (rerun `make jev-check` after curating)",
                      "fail" if missing else "pass", len(missing), None,
                      "; ".join(missing) if missing else f"{len(curated)} curated terms checked with {MODEL}"),
        ControlResult("agents", "jev_supported", f"Jev finds every curated Amendment term supported by the Amendment text (confidence >= {AUTO_ACCEPT})",
                      "warn" if review else "pass", len(review), None,
                      "needs human review: " + "; ".join(review) if review else f"{len(curated) - len(missing)} supported"),
    ]
