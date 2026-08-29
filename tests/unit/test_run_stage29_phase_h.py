"""Tests des fonctions pures de run_stage29 (Phase H) - AVANT toute
execution sur donnees reelles (protocole etape 13). Script charge via
importlib (meme convention que Phases F/G/E16)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "run_stage29_phase_h_ah_incremental_information.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage29_phase_h_ah_incremental_information", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def stage29():
    return _load_script()


# --------------------------------------------------------------------------
# settle_fraction / ah_outcome_class
# --------------------------------------------------------------------------


def test_settle_fraction_full_win_full_loss_on_half_line(stage29) -> None:
    assert stage29.settle_fraction(2, -1.5) == pytest.approx(1.0)  # domicile gagne par 2, ligne -1.5 -> couvre
    assert stage29.settle_fraction(0, -1.5) == pytest.approx(-1.0)  # nul, ligne -1.5 -> ne couvre pas


def test_settle_fraction_push_on_integer_line(stage29) -> None:
    assert stage29.settle_fraction(1, -1.0) == pytest.approx(0.0)  # domicile gagne par 1 pile, ligne -1 -> push


def test_settle_fraction_half_win_half_loss_on_quarter_line(stage29) -> None:
    # ligne -0.25 = moitie 0, moitie -0.5 ; d=0 -> push sur 0 (0.5*0), perte sur -0.5 (0.5*-1) -> -0.5
    assert stage29.settle_fraction(0, -0.25) == pytest.approx(-0.5)
    # d=1 -> gain sur 0 (0.5*1), gain sur -0.5 (0.5*1) -> +1 (gain plein)
    assert stage29.settle_fraction(1, -0.25) == pytest.approx(1.0)


def test_ah_outcome_class_matches_settle_sign(stage29) -> None:
    assert stage29.ah_outcome_class(2, -1.5) == 0  # Home
    assert stage29.ah_outcome_class(0, -1.5) == 2  # Away
    assert stage29.ah_outcome_class(1, -1.0) == 1  # Push


# --------------------------------------------------------------------------
# clean_population : filtre reglement +-1 uniquement
# --------------------------------------------------------------------------


def test_clean_population_excludes_push_and_partial_settlements(stage29) -> None:
    df = pd.DataFrame(
        {
            "p_model_home_condl": [0.6, 0.5, 0.55, 0.7],
            "p_market_home": [0.55, 0.5, 0.5, 0.65],
            "settle": [1.0, 0.0, 0.5, -1.0],
            "decision_time": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
            "league": ["liga"] * 4,
            "season": ["2024_25"] * 4,
            "ah_line": [-1.0, -1.0, -0.25, -0.5],
        }
    )
    clean = stage29.clean_population(df)
    assert len(clean) == 2  # settle=1.0 et settle=-1.0 uniquement
    assert set(clean["settle"]) == {1.0, -1.0}
    assert clean.loc[clean["settle"] == 1.0, "outcome"].iloc[0] == 1.0
    assert clean.loc[clean["settle"] == -1.0, "outcome"].iloc[0] == 0.0


# --------------------------------------------------------------------------
# build_model_vs_market : walk-forward logistique (E16, REUTILISE)
# --------------------------------------------------------------------------


def _synthetic_clean(n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    p_model = rng.uniform(0.3, 0.7, size=n)
    p_market = rng.uniform(0.3, 0.7, size=n)
    outcome = rng.integers(0, 2, size=n).astype(float)
    return pd.DataFrame(
        {
            "decision_time": pd.date_range("2024-01-01", periods=n, freq="D"),
            "league": ["liga"] * n,
            "season": ["2024_25"] * n,
            "ah_line": [-1.0] * n,
            "p_model_home_condl": p_model,
            "p_market_home": p_market,
            "outcome": outcome,
        }
    )


def test_build_model_vs_market_drops_warmup_rows(stage29) -> None:
    e16 = stage29._load_e16()
    clean = _synthetic_clean(50)
    compared = stage29.build_model_vs_market(clean, e16)
    assert len(compared) <= 20  # min_train=30
    assert compared["p_model_recal"].notna().all()
    assert compared["p_model_market"].notna().all()


def test_build_model_vs_market_never_uses_future_rows(stage29) -> None:
    e16 = stage29._load_e16()
    clean = _synthetic_clean(40)
    compared_a = stage29.build_model_vs_market(clean, e16)

    perturbed = clean.copy()
    perturbed.loc[perturbed.index[-1], "p_market_home"] = 0.999
    perturbed.loc[perturbed.index[-1], "outcome"] = 1.0 - perturbed.loc[perturbed.index[-1], "outcome"]
    compared_b = stage29.build_model_vs_market(perturbed, e16)

    n_common = min(len(compared_a), len(compared_b)) - 1
    np.testing.assert_allclose(
        compared_a["p_model_market"].to_numpy()[:n_common], compared_b["p_model_market"].to_numpy()[:n_common]
    )


# --------------------------------------------------------------------------
# evaluate_model_vs_market : Brier/bootstrap
# --------------------------------------------------------------------------


def test_evaluate_identical_predictions_yields_zero_diff(stage29) -> None:
    n = 50
    rng = np.random.default_rng(1)
    p = rng.uniform(0.3, 0.7, size=n)
    y = rng.integers(0, 2, size=n).astype(float)
    compared = pd.DataFrame({"p_model_home_condl": p, "p_model_recal": p, "p_model_market": p, "outcome": y})
    res = stage29.evaluate_model_vs_market(compared)
    assert res["boot_combo_minus_recal"]["ci_low"] == pytest.approx(0.0)
    assert res["boot_combo_minus_recal"]["ci_high"] == pytest.approx(0.0)


def test_evaluate_recalibration_alone_explains_gain_is_not_falsely_validated(stage29) -> None:
    n = 200
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, size=n).astype(float)
    p_model = np.full(n, 0.9)
    p_recalibrated = rng.uniform(0.3, 0.7, size=n)
    compared = pd.DataFrame(
        {"p_model_home_condl": p_model, "p_model_recal": p_recalibrated, "p_model_market": p_recalibrated, "outcome": y}
    )
    res = stage29.evaluate_model_vs_market(compared)
    assert res["brier_combo"] < res["brier_model"]
    assert res["boot_combo_minus_recal"]["ci_low"] == pytest.approx(0.0)
    assert res["boot_combo_minus_recal"]["ci_high"] == pytest.approx(0.0)


# --------------------------------------------------------------------------
# classify_verdict : grille figee (5 valeurs autorisees)
# --------------------------------------------------------------------------


def test_verdict_donnees_insuffisantes_when_pool_too_small(stage29) -> None:
    global_res = {"boot_combo_minus_recal": {"ci_low": -0.05, "ci_high": -0.01}, "calibration_recal": 0.05, "calibration_combo": 0.05}
    assert stage29.classify_verdict(global_res, [], n_global_pool=10) == "DONNEES INSUFFISANTES"


def test_verdict_valide_when_improvement_significant_and_stable(stage29) -> None:
    global_res = {"boot_combo_minus_recal": {"ci_low": -0.05, "ci_high": -0.01}, "calibration_recal": 0.05, "calibration_combo": 0.05}
    scope_boots = [{"ci_low": -0.06, "ci_high": -0.005}]
    assert stage29.classify_verdict(global_res, scope_boots, n_global_pool=200) == "VALIDE"


def test_verdict_non_valide_when_scope_inverts(stage29) -> None:
    global_res = {"boot_combo_minus_recal": {"ci_low": -0.05, "ci_high": -0.01}, "calibration_recal": 0.05, "calibration_combo": 0.05}
    scope_boots = [{"ci_low": 0.001, "ci_high": 0.02}]
    assert stage29.classify_verdict(global_res, scope_boots, n_global_pool=200) == "NON VALIDE"


def test_verdict_absence_de_preuve_when_ci_wide_and_uninformative(stage29) -> None:
    global_res = {"boot_combo_minus_recal": {"ci_low": -0.10, "ci_high": 0.10}, "calibration_recal": 0.05, "calibration_combo": 0.05}
    assert stage29.classify_verdict(global_res, [], n_global_pool=200) == "ABSENCE DE PREUVE"


def test_verdict_only_five_authorized_values_used(stage29) -> None:
    allowed = {"VALIDE", "NON VALIDE", "ABSENCE DE PREUVE", "DONNEES INSUFFISANTES", "PROBLEME METHODOLOGIQUE"}
    cases = [
        ({"boot_combo_minus_recal": {"ci_low": -0.05, "ci_high": -0.01}, "calibration_recal": 0.05, "calibration_combo": 0.05}, [], 200),
        ({"boot_combo_minus_recal": {"ci_low": -0.01, "ci_high": 0.01}, "calibration_recal": 0.05, "calibration_combo": 0.05}, [], 200),
        ({"boot_combo_minus_recal": {"ci_low": -0.05, "ci_high": -0.01}, "calibration_recal": 0.05, "calibration_combo": 0.05}, [], 5),
    ]
    for global_res, scope_boots, n in cases:
        assert stage29.classify_verdict(global_res, scope_boots, n_global_pool=n) in allowed
