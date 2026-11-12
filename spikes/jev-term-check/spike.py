"""SPIKE (throwaway): can Jev tell a supported Amendment term from an unsupported one?

Wayfinder ticket: "Can Jev tell a supported Amendment term from an unsupported one?" (xaac-ai/finance-engineer-cup#13).
Pattern: TypeSafe's "Double-checking citations" cookbook. The word-for-word quote check already
passed; Jev reads the quote's section and picks supports / contradicts / says_nothing for a claim.

For each curated October Amendment term we ask about the correct claim and about deliberately
wrong claims (wrong value, wrong date, wrong rule), each REPEATS times to measure flip rate.

Key: read from $TYPESAFE_API_KEY, else the repo's gitignored .env, else ~/.config/typesafe/api_key. Never committed.
Answers are cached in cache.json (committed), so a rerun without a key makes no requests.

Run:  uv run python spikes/jev-term-check/spike.py      (from the repo root, after `make run`)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
EXTRACTED = ROOT / "out" / "2026-10" / "extracted"
CACHE = HERE / "cache.json"
MODEL = "jev-1.14.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
REPEATS = 3
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

# (case id, document, section heading prefix, expected relation, claim)
CASES = [
    # AM-OF-2026-157 · included_runs_per_month = 45000 from 2026-10-16
    ("157_runs_ok", "AM-OF-2026-157", "03", "supports",
     "From October 16, 2026 the customer's included workflow runs are 45,000 per calendar month."),
    ("157_runs_wrong_value", "AM-OF-2026-157", "03", "contradicts",
     "From October 16, 2026 the customer's included workflow runs are 40,000 per calendar month."),
    # Same two claims, given sections 03+04 together (the table lacks the effective date, which is in 04)
    ("157_runs_ok_s0304", "AM-OF-2026-157", "03+04", "supports",
     "From October 16, 2026 the customer's included workflow runs are 45,000 per calendar month."),
    ("157_runs_wrong_value_s0304", "AM-OF-2026-157", "03+04", "contradicts",
     "From October 16, 2026 the customer's included workflow runs are 40,000 per calendar month."),
    ("157_runs_wrong_date", "AM-OF-2026-157", "04", "contradicts",
     "The increase to 45,000 included workflow runs takes effect on October 1, 2026."),
    # AM-OF-2026-157 · allowance_weighting_rule
    ("157_weighting_ok", "AM-OF-2026-157", "04", "supports",
     "For October 2026, the allowance weights 30,000 runs for October 1-15 and 45,000 runs for October 16-31 by calendar days, rounded once to a whole run, half up."),
    ("157_weighting_wrong", "AM-OF-2026-157", "04", "contradicts",
     "For October 2026, the full amended allowance of 45,000 runs applies to the whole month."),
    # AM-OF-2026-157 · decoy: overage rate untouched
    ("157_overage_decoy", "AM-OF-2026-157", "04", "contradicts",
     "The amendment reduces the overage rate to USD 0.30 per run."),
    # AM-OF-2026-164 · platform_annual_rate = 60000.00 from 2026-10-16
    ("164_rate_ok", "AM-OF-2026-164", "03", "supports",
     "The annual platform rate becomes USD 60,000.00 per year."),
    ("164_rate_wrong_value", "AM-OF-2026-164", "03", "contradicts",
     "The annual platform rate becomes USD 64,000.00 per year."),
    ("164_rate_wrong_date", "AM-OF-2026-164", "04", "contradicts",
     "The annual platform rate increase takes effect on November 1, 2026."),
    # AM-OF-2026-164 · platform_invoice_amount = 5000.00 from 2026-11-01
    ("164_invoice_ok", "AM-OF-2026-164", "04", "supports",
     "Monthly platform invoices are USD 5,000.00 from November 2026 through August 2027."),
    ("164_invoice_wrong_value", "AM-OF-2026-164", "04", "contradicts",
     "Monthly platform invoices are USD 5,500.00 from November 2026 through August 2027."),
    # AM-OF-2026-164 · catch_up_amount = 526.03
    ("164_catchup_ok", "AM-OF-2026-164", "04", "supports",
     "The October upgrade catch-up is USD 526.03."),
    ("164_catchup_wrong_value", "AM-OF-2026-164", "04", "contradicts",
     "The October upgrade catch-up is USD 562.03."),
    ("164_catchup_wrong_basis", "AM-OF-2026-164", "04", "contradicts",
     "The October upgrade catch-up is computed as USD 12,000 x 15 / 365."),
    # AM-OF-2026-164 · incremental_consideration = 10520.55
    ("164_incremental_ok", "AM-OF-2026-164", "04", "supports",
     "Incremental consideration for the 320 remaining service days is USD 10,520.55."),
    ("164_incremental_wrong", "AM-OF-2026-164", "04", "contradicts",
     "Incremental consideration for the 320 remaining service days is USD 10,250.55."),
    # AM-OF-2026-164 · final_invoice_credit = 5.48
    ("164_credit_ok", "AM-OF-2026-164", "04", "supports",
     "The final platform invoice includes a USD 5.48 credit."),
    ("164_credit_wrong_sign", "AM-OF-2026-164", "04", "contradicts",
     "The final platform invoice includes an additional USD 5.48 charge."),
    # AM-OF-2026-164 · decoy: usage terms unchanged; and a says_nothing case
    ("164_usage_decoy", "AM-OF-2026-164", "04", "contradicts",
     "The amendment changes the workflow-run overage rate to USD 0.10 per run."),
    ("164_says_nothing", "AM-OF-2026-164", "03", "says_nothing",
     "The customer must pay invoices within Net 45 days."),
]


def section_text(doc: str, prefix: str) -> str:
    """The text of section `prefix` (e.g. '04', or '03+04' for both) up to the next numbered section heading."""
    if "+" in prefix:
        return " ".join(section_text(doc, p) for p in prefix.split("+"))
    text = (EXTRACTED / f"{doc}.txt").read_text()
    m = re.search(rf"(?ms)^{prefix} [A-Z][A-Z /]+$.*?(?=^\d\d [A-Z][A-Z /]+$|\Z)", text)
    if not m:
        sys.exit(f"section {prefix} not found in {doc}; run `make run` first")
    return re.sub(r"\s+", " ", m.group(0)).strip()


def api_key() -> str | None:
    if os.environ.get("TYPESAFE_API_KEY"):
        return os.environ["TYPESAFE_API_KEY"]
    env = ROOT / ".env"  # gitignored; KEY=value lines
    if env.exists():
        for line in env.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "TYPESAFE_API_KEY" and v.strip():
                return v.strip().strip('"').strip("'")
    p = Path.home() / ".config" / "typesafe" / "api_key"
    return p.read_text().strip() if p.exists() else None


def ask(key: str, claim: str, section: str) -> dict:
    body = json.dumps({"model": MODEL, "state": {"claim": claim, "section": section},
                       "questions": {"relation": QUESTION}}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"TypeSafe API error {e.code}: {e.read().decode()[:500]}")
    a = resp["answers"]["relation"]
    return {"choice": a["choice"], "confidence": a["confidence"], "probabilities": a["probabilities"],
            "seconds": round(time.perf_counter() - t0, 2), "model": resp.get("model"),
            "input_tokens": (resp.get("usage") or {}).get("input_tokens")}


def main() -> None:
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    key = api_key()
    for cid, doc, sec, _, claim in CASES:
        for i in range(REPEATS):
            k = f"{cid}#{i}"
            if k in cache:
                continue
            if not key:
                sys.exit(f"No cached answer for {k} and no API key. Set TYPESAFE_API_KEY or ~/.config/typesafe/api_key.")
            cache[k] = ask(key, claim, section_text(doc, sec))
            CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")

    rows, correct, flips, tokens, secs = [], 0, 0, 0, []
    for cid, doc, sec, expected, claim in CASES:
        answers = [cache[f"{cid}#{i}"] for i in range(REPEATS)]
        choices = [a["choice"] for a in answers]
        majority = max(set(choices), key=choices.count)
        conf = min(a["confidence"] for a in answers)
        ok = majority == expected
        correct += ok
        flips += len(set(choices)) > 1
        tokens += sum(a["input_tokens"] or 0 for a in answers)
        secs += [a["seconds"] for a in answers]
        rows.append(f"| `{cid}` | {expected} | {'/'.join(choices)} | {conf:.2f} | {'auto' if conf >= AUTO_ACCEPT else 'review'} | {'✅' if ok else '❌'} |")
    caught = sum(1 for c in CASES if c[3] != "supports" and cache[f"{c[0]}#0"]["choice"] != "supports")
    wrong_total = sum(1 for c in CASES if c[3] != "supports")
    report = "\n".join([
        f"# Jev term-check spike ({MODEL})", "",
        f"- Cases: {len(CASES)} × {REPEATS} repeats. Majority verdict correct: **{correct}/{len(CASES)}**.",
        f"- Wrong claims not marked `supports` (first run): **{caught}/{wrong_total}**.",
        f"- Cases whose verdict changed across repeats: **{flips}/{len(CASES)}**.",
        f"- Input tokens total: {tokens:,} (≈ ${tokens * 0.042 / 1e6:.4f}). Median latency: {sorted(secs)[len(secs)//2]} s.", "",
        "| Case | Expected | Answers | Min confidence | Gate (≥0.8) | Majority right |",
        "|---|---|---|---|---|---|", *rows, ""])
    (HERE / "RESULTS.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
