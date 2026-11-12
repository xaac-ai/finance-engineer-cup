"""Jev term check: committed answers replay without a key, and `make run` enforces them."""

from datetime import date

import pytest

from workbench.agents import jev
from workbench.period import load_period
from workbench.pipeline import run

TERMS = "data/curated/2026-10/amendment_terms.yaml"


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)  # repo_copy has no .env


def _status(result, name):
    return next(c for c in result.controls if c.name == name).status


def test_replays_committed_answers_without_a_key(repo_copy, no_key):
    out = jev.run(load_period("2026-10", repo_copy))
    gates = [(r["source"], r["gate"]) for r in out["checks"]]
    assert gates.count(("curated", "auto")) == 7 and gates.count(("drafted", "auto")) == 7


def test_changed_curation_without_a_recheck_fails_the_run(repo_copy):
    p = repo_copy / TERMS
    p.write_text(p.read_text().replace('value: "5000.00"', 'value: "5500.00"'))
    assert _status(run("2026-10", repo_copy), "jev_current") == "fail"


def test_wrong_value_is_contradicted_and_sent_to_review(repo_copy, no_key):
    p = repo_copy / TERMS
    p.write_text(p.read_text().replace('value: "5000.00"', 'value: "5500.00"'))
    out = jev.run(load_period("2026-10", repo_copy))  # this answer is in the committed cache
    wrong = next(r for r in out["checks"] if r["source"] == "curated" and r["value"] == "5500.00")
    assert (wrong["choice"], wrong["gate"]) == ("contradicts", "review")
    result = run("2026-10", repo_copy)
    assert (_status(result, "jev_current"), _status(result, "jev_supported")) == ("pass", "warn")


def test_claims_read_like_the_amendments():
    assert jev.claim("platform_annual_rate", "60000.00", date(2026, 10, 16)) == \
        "From October 16, 2026 the annual platform rate is USD 60,000.00 per year."
    assert jev.claim("included_runs_per_month", "45000", date(2026, 10, 16)) == \
        "From October 16, 2026 the customer's included workflow runs are 45,000 per calendar month."
