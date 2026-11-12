import json
import shutil

import pytest

from workbench.errors import InputError
from workbench.pipeline import run


def test_end_to_end_writes_outputs_and_passes(repo_copy):
    result = run("2026-10", repo_copy)
    assert result.failed == []
    out = repo_copy / "out" / "2026-10"
    for name in ["report.html", "trial_balance.csv", "proposed_journal_entries.csv", "controls.csv", "contract_terms.csv"]:
        assert (out / name).exists(), name
    assert len(list((out / "extracted").glob("*.txt"))) == 34  # 32 contracts + 2 policy PDFs
    html = (out / "report.html").read_text()
    blob = html.split('<script id="report-data" type="application/json">')[1].split("</script>")[0]
    data = json.loads(blob)
    assert len(data["customers"]) == 30
    assert {f["status"] for f in data["findings"]} <= {"error", "valid_explanation", "needs_info"}


def test_rerun_is_deterministic(repo_copy):
    run("2026-10", repo_copy)
    first = (repo_copy / "out" / "2026-10" / "trial_balance.csv").read_bytes()
    run("2026-10", repo_copy)
    assert (repo_copy / "out" / "2026-10" / "trial_balance.csv").read_bytes() == first


def test_missing_inputs_listed_in_one_message(repo_copy):
    (repo_copy / "data" / "raw" / "2026-10" / "stripe_invoices.csv").unlink()
    shutil.rmtree(repo_copy / "data" / "raw" / "2026-10" / "contracts")
    with pytest.raises(InputError) as e:
        run("2026-10", repo_copy)
    assert "stripe_invoices.csv" in str(e.value) and "contracts" in str(e.value)


def test_new_period_without_curated_file(repo_copy):
    with pytest.raises(InputError, match="period.yaml"):
        run("2026-11", repo_copy)
