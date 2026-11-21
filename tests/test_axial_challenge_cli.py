"""Subprocess acceptance for the synthetic axial design agent contract."""
import json
import subprocess
import sys

from test_axial_design_challenge import challenge
from ezfea.axial_design_challenge import evaluate_axial_design, rank_axial_options


def invoke(request):
    return subprocess.run(
        [sys.executable, "-m", "ezfea.axial_challenge_cli"],
        input=json.dumps(request), text=True, capture_output=True, check=False,
    )


def test_external_evaluation_matches_independent_solver_and_ignores_claimed_score():
    c = challenge()
    request = {"action": "evaluate", "challenge": c,
               "proposal": {"option_id": "medium", "claimed_score": 1e100}}
    completed = invoke(request)
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["ok"] is True
    assert receipt["result"] == evaluate_axial_design(c, {"option_id": "medium"})
    assert completed.stdout == invoke(request).stdout


def test_external_ranking_matches_solver_and_preserves_order():
    c = challenge()
    completed = invoke({"action": "rank", "challenge": c})
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["results"] == rank_axial_options(c)
    assert [item["option_id"] for item in receipt["results"]] == ["medium", "thick", "thin"]


def test_unknown_proposal_rejected_with_machine_readable_error():
    completed = invoke({"action": "evaluate", "challenge": challenge(),
                        "proposal": {"option_id": "unknown"}})
    assert completed.returncode == 2
    receipt = json.loads(completed.stdout)
    assert receipt["ok"] is False
    assert "unknown option_id" in receipt["error"]


def test_extra_fields_and_malformed_json_rejected():
    extra = invoke({"action": "rank", "challenge": challenge(), "proposal": {}})
    assert extra.returncode == 2
    assert json.loads(extra.stdout)["ok"] is False
    malformed = subprocess.run(
        [sys.executable, "-m", "ezfea.axial_challenge_cli"],
        input="{broken", text=True, capture_output=True, check=False,
    )
    assert malformed.returncode == 2
    assert json.loads(malformed.stdout)["ok"] is False


def test_bounded_input_and_invalid_model_fail_without_non_json_output():
    oversized = subprocess.run(
        [sys.executable, "-m", "ezfea.axial_challenge_cli"],
        input=" " * 1_000_001, text=True, capture_output=True, check=False,
    )
    assert oversized.returncode == 2
    assert "1 MB" in json.loads(oversized.stdout)["error"]
    c = challenge()
    c["model"]["elements"][0]["youngs_modulus_pa"] = -1
    bad = invoke({"action": "rank", "challenge": c})
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["ok"] is False
