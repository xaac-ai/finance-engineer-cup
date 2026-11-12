"""Amendment-term drafter: replays the committed cache without a key, and scores against curation."""

import shutil
from pathlib import Path

import pytest

from workbench.agents import drafter
from workbench.period import load_period

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # repo_copy has no .env


def test_replays_committed_answers_without_a_key(repo_copy, no_key):
    ev = drafter.run(load_period("2026-10", repo_copy))
    t = ev["totals"]
    assert (t["found"], t["curated"], t["quote_pass"], t["drafted"], t["extra"]) == (7, 7, 7, 7, 0)
    assert all(c["replayed"] for c in ev["calls"])
    assert (repo_copy / "data/curated/2026-10/drafts/amendment_terms.yaml").read_text().startswith("# DRAFT")


def test_never_writes_the_curated_terms(repo_copy, no_key):
    curated = repo_copy / "data/curated/2026-10/amendment_terms.yaml"
    before = curated.read_text()
    drafter.run(load_period("2026-10", repo_copy))
    assert curated.read_text() == before


def test_missing_cache_and_no_key_stops(repo_copy, no_key):
    (repo_copy / "data/curated/2026-10/drafts/drafter_cache.json").unlink()
    with pytest.raises(SystemExit, match="no ANTHROPIC_API_KEY"):
        drafter.run(load_period("2026-10", repo_copy))


def test_score_counts_misses_mismatches_and_extras():
    register = {"AM-1": {"effective_from": "2026-10-16"}}
    curated = {"AM-1": [{"term": "overage_rate", "value": "0.40"},
                        {"term": "included_runs_per_month", "value": "45000"},
                        {"term": "platform_invoice_amount", "value": "5000.00", "effective_from": "2026-11-01"}]}
    drafts = {"AM-1": [
        {"term": "overage_rate", "value": "0.4", "effective_from": "2026-10-16", "quote_check": "passed"},
        {"term": "platform_invoice_amount", "value": "5,500.00", "effective_from": "2026-10-16", "quote_check": "failed"},
        {"term": "made_up", "value": "1", "effective_from": "2026-10-16", "quote_check": "passed"}]}
    t = drafter.score(drafts, curated, register)["totals"]
    assert (t["found"], t["value_match"], t["date_match"], t["quote_pass"], t["extra"]) == (2, 1, 1, 2, 1)
