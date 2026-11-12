"""Independent Review: committed reviews replay without a key, and `make run` compares them with the Findings."""

import json

import pytest

from workbench.agents import reviewer
from workbench.period import load_period
from workbench.pipeline import run

REVIEWS = "data/curated/2026-10/reviews"


def _independent_review(result):
    return next(c for c in result.controls if c.name == "independent_review")


def test_replays_committed_reviews_without_a_key(repo_copy, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = reviewer.run(load_period("2026-10", repo_copy))
    assert len(out["reviews"]) == 60


def test_reviewer_agrees_on_all_but_willow_usage(repo_copy):
    (repo_copy / REVIEWS / "reviewer_resolutions.yaml").unlink(missing_ok=True)
    c = _independent_review(run("2026-10", repo_copy))
    assert (c.status, c.count) == ("warn", 1) and "Willow Passage, Inc. usage (status differs)" in c.detail


def test_amount_difference_is_a_disagreement(repo_copy):
    p = repo_copy / REVIEWS / "reviewer.json"
    data = json.loads(p.read_text())
    for r in data["reviews"]:
        if r["customer_id"] == "639373" and r["stream"] == "usage":
            r["billing_effect"] = "-3096.79"
    p.write_text(json.dumps(data))
    c = _independent_review(run("2026-10", repo_copy))
    assert "Cedar Harbor Labs, Inc. usage (amount differs)" in c.detail


def test_resolution_closes_a_disagreement(repo_copy):
    (repo_copy / REVIEWS / "reviewer_resolutions.yaml").write_text(
        'resolutions:\n  - customer_id: "839653"\n    stream: usage\n    resolution: rules_correct\n    reason: test\n')
    assert _independent_review(run("2026-10", repo_copy)).status == "pass"
