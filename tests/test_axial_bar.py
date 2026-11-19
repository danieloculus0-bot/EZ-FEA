import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from ezfea.axial_bar import solve


def model():
    return {
        "elements": [{"length_m": 2.0, "area_m2": 0.01, "youngs_modulus_pa": 200e9}],
        "nodal_forces_n": [0.0, 1000.0],
        "prescribed_displacements_m": {"0": 0.0},
    }


def test_single_bar_closed_form():
    result = solve(model())
    assert result["displacements_m"][1] == pytest.approx(1e-6)
    assert result["elements"][0]["stress_pa"] == pytest.approx(100000.0)
    assert result["reactions_n"]["0"] == pytest.approx(-1000.0)
    assert abs(result["force_balance_residual_n"]) < 1e-8


def test_two_elements_series():
    case = model()
    case["elements"] *= 2
    case["nodal_forces_n"] = [0.0, 0.0, 1000.0]
    result = solve(case)
    assert result["displacements_m"] == pytest.approx([0.0, 1e-6, 2e-6])


def test_prescribed_extension():
    case = model()
    case["nodal_forces_n"] = [0.0, 0.0]
    case["prescribed_displacements_m"] = {"0": 0.0, "1": 0.001}
    result = solve(case)
    assert result["reactions_n"]["0"] == pytest.approx(-1e6)
    assert result["reactions_n"]["1"] == pytest.approx(1e6)


@pytest.mark.parametrize("change", [
    {"prescribed_displacements_m": {}},
    {"nodal_forces_n": [0.0]},
    {"nodal_forces_n": [0.0, float("nan")]},
])
def test_invalid_models(change):
    case = model()
    case.update(change)
    with pytest.raises(ValueError):
        solve(case)


def test_cli(tmp_path):
    input_file = tmp_path / "model.json"
    input_file.write_text(json.dumps(model()), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "ezfea.axial_bar", str(input_file)],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["displacements_m"][1] == pytest.approx(1e-6)
