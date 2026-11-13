"""Scenarios: each deliberate change to October's inputs produces exactly its expected difference, and nothing else."""

import pytest

from workbench import scenarios as sc


@pytest.fixture(scope="session")
def baseline(tmp_path_factory):
    return sc.run_period(sc.prepare(tmp_path_factory.mktemp("baseline"), None))


@pytest.mark.parametrize("scenario", sc.SCENARIOS, ids=lambda s: s.name)
def test_scenario(scenario, baseline, tmp_path):
    got = sc.run_period(sc.prepare(tmp_path / "root", scenario))
    assert "input_error" not in got, got.get("input_error")
    assert sc.diff(baseline, got) == scenario.expected


def test_catch_scenarios_change_something_and_ignore_scenarios_change_nothing():
    for s in sc.SCENARIOS:
        assert s.kind in ("catch", "ignore")
        assert bool(s.expected) == (s.kind == "catch"), s.name
