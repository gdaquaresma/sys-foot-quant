"""Tests unitaires des fonctions PURES d'E8
(scripts/run_stage16_e8_walk_forward_validation.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage16_e8_walk_forward_validation.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage16_e8_walk_forward_validation", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e8_module():
    return _load_script()


@pytest.fixture(scope="module")
def e7_module(e8_module):
    return e8_module._load_e7()


def _dt(day: int) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


# --- fit_scale_correction_as_of ---------------------------------------------


def test_fit_scale_correction_as_of_uses_only_prior_rows(e8_module) -> None:
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(1), _dt(2), _dt(3), _dt(10)],
            "poisson_simple_lambda": [1.0, 1.0, 1.0, 1.0],
            "poisson_simple_mu": [1.0, 1.0, 1.0, 1.0],
            "total_goals": [2.0, 2.0, 2.0, 99.0],  # la ligne du 10 est "future" -> ne doit jamais compter
        }
    )
    c, n = e8_module.fit_scale_correction_as_of(calib, "poisson_simple", _dt(5), min_matches=1)
    assert n == 3
    assert c == pytest.approx(1.0)  # (2+2+2)/3 total vs (1+1)*3 predicted = 1.0, jamais influence par la ligne du 10


def test_fit_scale_correction_as_of_returns_none_below_min_matches(e8_module) -> None:
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(1), _dt(2)],
            "poisson_simple_lambda": [1.0, 1.0],
            "poisson_simple_mu": [1.0, 1.0],
            "total_goals": [2.0, 3.0],
        }
    )
    c, n = e8_module.fit_scale_correction_as_of(calib, "poisson_simple", _dt(5), min_matches=30)
    assert c is None
    assert n == 2


def test_fit_scale_correction_as_of_matches_manual_ratio(e8_module) -> None:
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(1), _dt(2), _dt(3)],
            "poisson_simple_lambda": [1.0, 1.5, 2.0],
            "poisson_simple_mu": [1.0, 1.0, 1.0],
            "total_goals": [3, 3, 3],
        }
    )
    c, n = e8_module.fit_scale_correction_as_of(calib, "poisson_simple", _dt(10), min_matches=1)
    predicted_mean = np.mean([2.0, 2.5, 3.0])
    assert n == 3
    assert c == pytest.approx(3.0 / predicted_mean)


def test_fit_scale_correction_as_of_drops_nan_rows(e8_module) -> None:
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(1), _dt(2), _dt(3)],
            "poisson_simple_lambda": [1.0, np.nan, 2.0],
            "poisson_simple_mu": [1.0, 1.0, 1.0],
            "total_goals": [2.0, 99.0, 3.0],
        }
    )
    c, n = e8_module.fit_scale_correction_as_of(calib, "poisson_simple", _dt(10), min_matches=1)
    assert n == 2
    predicted_mean = np.mean([2.0, 3.0])
    assert c == pytest.approx(np.mean([2.0, 3.0]) / predicted_mean)


# --- attach_walk_forward_scale ----------------------------------------------


def test_attach_walk_forward_scale_grows_with_time(e8_module) -> None:
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(d) for d in range(1, 41)],
            "poisson_simple_lambda": [1.0] * 40,
            "poisson_simple_mu": [1.0] * 40,
            "total_goals": [2.0] * 40,
        }
    )
    test_df = pd.DataFrame(
        {
            "decision_time": [_dt(20), _dt(50)],
            "poisson_simple_lambda": [1.0, 1.0],
            "poisson_simple_mu": [1.0, 1.0],
            "total_goals": [2.0, 2.0],
        }
    )
    out = e8_module.attach_walk_forward_scale(calib, test_df, "poisson_simple")
    row_day20 = out[out["decision_time"] == _dt(20)].iloc[0]
    row_day50 = out[out["decision_time"] == _dt(50)].iloc[0]
    assert row_day20["n_calibration_used"] == 19  # days 1..19 strictement anterieurs
    assert row_day50["n_calibration_used"] == 40  # tous les 40 jours de calibration


def test_attach_walk_forward_scale_never_uses_test_rows(e8_module) -> None:
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(d) for d in range(1, 40)],
            "poisson_simple_lambda": [1.0] * 39,
            "poisson_simple_mu": [1.0] * 39,
            "total_goals": [2.0] * 39,
        }
    )
    test_df = pd.DataFrame(
        {
            "decision_time": [_dt(50), _dt(51)],
            "poisson_simple_lambda": [1.0, 1.0],
            "poisson_simple_mu": [1.0, 1.0],
            "total_goals": [2.0, 999.0],  # valeur aberrante sur un AUTRE match de test
        }
    )
    out = e8_module.attach_walk_forward_scale(calib, test_df, "poisson_simple")
    # le facteur du match du 50 ne doit jamais etre influence par le match du 51 (autre ligne de test)
    row_50 = out[out["decision_time"] == _dt(50)].iloc[0]
    assert row_50["scale_c"] == pytest.approx(1.0)


# --- summarize_scale_stability ----------------------------------------------


def test_summarize_scale_stability_basic_stats(e8_module) -> None:
    df = pd.DataFrame({"scale_c": [0.8, 0.9, 1.0, 1.1, 1.2], "season": ["s1", "s1", "s1", "s2", "s2"]})
    out = e8_module.summarize_scale_stability(df)
    assert out["n"] == 5
    assert out["mean"] == pytest.approx(1.0)
    assert out["median"] == pytest.approx(1.0)
    assert out["min"] == pytest.approx(0.8)
    assert out["max"] == pytest.approx(1.2)
    assert set(out["by_season"]) == {"s1", "s2"}
    assert out["by_season"]["s1"]["n"] == 3


def test_summarize_scale_stability_excludes_none(e8_module) -> None:
    df = pd.DataFrame({"scale_c": [0.8, None, 1.2], "season": ["s1", "s1", "s1"]})
    out = e8_module.summarize_scale_stability(df)
    assert out["n"] == 2


def test_summarize_scale_stability_empty(e8_module) -> None:
    df = pd.DataFrame({"scale_c": [None, None], "season": ["s1", "s1"]})
    out = e8_module.summarize_scale_stability(df)
    assert out["n"] == 0


# --- classify_verdict_e8 ------------------------------------------------------


def test_verdict_a_when_global_improved_and_no_scope_inversion(e8_module) -> None:
    global_boot = {"ci_low": -0.01, "ci_high": -0.002}
    scope_boots = [{"ci_low": -0.02, "ci_high": -0.001}, {"ci_low": -0.005, "ci_high": 0.001}]
    stability = {"coefficient_of_variation": 0.05}
    v = e8_module.classify_verdict_e8(global_boot, scope_boots, stability)
    assert v == "A - VALIDATION REUSSIE"


def test_verdict_b_when_scope_inversion(e8_module) -> None:
    global_boot = {"ci_low": -0.01, "ci_high": -0.002}
    scope_boots = [{"ci_low": 0.001, "ci_high": 0.02}]  # inversion locale
    stability = {"coefficient_of_variation": 0.05}
    v = e8_module.classify_verdict_e8(global_boot, scope_boots, stability)
    assert v == "B - VALIDATION PARTIELLE"


def test_verdict_b_when_scale_unstable(e8_module) -> None:
    global_boot = {"ci_low": -0.01, "ci_high": -0.002}
    scope_boots = [{"ci_low": -0.02, "ci_high": -0.001}]
    stability = {"coefficient_of_variation": 0.25}
    v = e8_module.classify_verdict_e8(global_boot, scope_boots, stability)
    assert v == "B - VALIDATION PARTIELLE"


def test_verdict_c_when_global_inversion(e8_module) -> None:
    global_boot = {"ci_low": 0.001, "ci_high": 0.02}
    scope_boots = [{"ci_low": -0.02, "ci_high": -0.001}]
    stability = {"coefficient_of_variation": 0.05}
    v = e8_module.classify_verdict_e8(global_boot, scope_boots, stability)
    assert v == "C - VALIDATION ECHOUEE"


def test_verdict_c_when_no_evidence_anywhere(e8_module) -> None:
    global_boot = {"ci_low": -0.005, "ci_high": 0.01}  # contient 0 -> pas d'amelioration demontree
    scope_boots = [{"ci_low": -0.003, "ci_high": 0.008}]  # idem partout
    stability = {"coefficient_of_variation": 0.05}
    v = e8_module.classify_verdict_e8(global_boot, scope_boots, stability)
    assert v == "C - VALIDATION ECHOUEE"


def test_verdict_b_when_no_global_evidence_but_scope_evidence(e8_module) -> None:
    global_boot = {"ci_low": -0.005, "ci_high": 0.01}
    scope_boots = [{"ci_low": -0.02, "ci_high": -0.001}]  # une decoupe montre une amelioration
    stability = {"coefficient_of_variation": 0.05}
    v = e8_module.classify_verdict_e8(global_boot, scope_boots, stability)
    assert v == "B - VALIDATION PARTIELLE"


# --- _ou_metrics --------------------------------------------------------------


def test_ou_metrics_perfect_predictions_zero_brier(e8_module, e7_module) -> None:
    p = np.array([1.0, 0.0, 1.0, 0.0])
    y = np.array([1.0, 0.0, 1.0, 0.0])
    out = e8_module._ou_metrics(p, y, e7_module._calibration_weighted_error)
    assert out["brier"] == pytest.approx(0.0)
    assert out["biais"] == pytest.approx(0.0)


def test_ou_metrics_biais_matches_manual(e8_module, e7_module) -> None:
    p = np.array([0.6, 0.6, 0.6, 0.6])
    y = np.array([1.0, 0.0, 0.0, 0.0])
    out = e8_module._ou_metrics(p, y, e7_module._calibration_weighted_error)
    assert out["biais"] == pytest.approx(0.6 - 0.25)


# --- evaluate_walk_forward (synthetique, sur poisson_simple) ----------------


def _synthetic_df_with_scale(n: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    lam = rng.uniform(1.0, 1.6, size=n)
    mu = rng.uniform(0.8, 1.4, size=n)
    total_goals = rng.poisson(lam + mu)
    return pd.DataFrame(
        {
            "poisson_simple_lambda": lam,
            "poisson_simple_mu": mu,
            "total_goals": total_goals,
            "scale_c": np.full(n, 1.0),  # scale neutre -> raw == corrige
        }
    )


def test_evaluate_walk_forward_neutral_scale_gives_identical_raw_and_corrected(e8_module, e7_module) -> None:
    df = _synthetic_df_with_scale()
    res = e8_module.evaluate_walk_forward(df, "poisson_simple", e7_module)
    assert res["brier_raw"] == pytest.approx(res["brier_corr"], abs=1e-9)
    assert res["bias_raw"] == pytest.approx(res["bias_corr"], abs=1e-9)
    assert res["boot_brier_corr_minus_raw"]["mean_diff"] == pytest.approx(0.0, abs=1e-9)


def test_evaluate_walk_forward_excludes_rows_without_scale(e8_module, e7_module) -> None:
    df = _synthetic_df_with_scale(n=10)
    df.loc[0:2, "scale_c"] = np.nan
    res = e8_module.evaluate_walk_forward(df, "poisson_simple", e7_module)
    assert res["n"] == 7
    assert res["n_excluded"] == 3


def test_evaluate_walk_forward_reports_ou_thresholds(e8_module, e7_module) -> None:
    df = _synthetic_df_with_scale()
    res = e8_module.evaluate_walk_forward(df, "poisson_simple", e7_module)
    assert set(res["ou_results"]) == {1.5, 2.5, 3.5}
    for t, ou in res["ou_results"].items():
        assert set(ou["raw"]) == {"brier", "log_loss", "biais", "calibration", "resolution"}
