"""Tests unitaires des fonctions PURES d'E14
(scripts/run_stage23_e14_local_recalibration_over25.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage23_e14_local_recalibration_over25.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage23_e14_local_recalibration_over25", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e14_module():
    return _load_script()


@pytest.fixture(scope="module")
def e11_module(e14_module):
    return e14_module._load_e11()


def _dt(day: int) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


# --- build_walk_forward_probs -------------------------------------------------


def _fake_e7_e8(thresholds_out: dict[float, float] | None = None):
    """Fausses versions minimales d'E7/E8 - suffisantes pour tester
    `build_walk_forward_probs` sans dependre du corpus reel."""

    class _FakeE8:
        @staticmethod
        def attach_walk_forward_scale(source_df, target_df, model):
            lam_col, mu_col = f"{model}_lambda", f"{model}_mu"
            sub = target_df.dropna(subset=[lam_col, mu_col]).sort_values("decision_time").copy()
            scales = []
            for as_of in sub["decision_time"]:
                prior = source_df[source_df["decision_time"] < as_of]
                scales.append(1.0 if len(prior) >= 1 else None)
            sub["scale_c"] = scales
            return sub

    class _FakeE7:
        @staticmethod
        def matrix_for_row(row, model, scale=1.0):
            return "matrix"  # jamais interprete par over_under_probs ci-dessous

        @staticmethod
        def over_under_probs(matrix, thresholds):
            return thresholds_out or {t: 0.5 for t in thresholds}

    return _FakeE7(), _FakeE8()


def test_build_walk_forward_probs_basic_shape(e14_module) -> None:
    e7, e8 = _fake_e7_e8({0.5: 0.9, 1.5: 0.6, 2.5: 0.5, 3.5: 0.3, 4.5: 0.1})
    source = pd.DataFrame(
        {
            "match_id": ["s1"],
            "league": ["premier_league"],
            "season": ["2024_25"],
            "decision_time": [_dt(1)],
            "poisson_simple_lambda": [1.0],
            "poisson_simple_mu": [1.0],
            "total_goals": [2],
        }
    )
    target = pd.DataFrame(
        {
            "match_id": ["a", "b"],
            "league": ["premier_league", "premier_league"],
            "season": ["2024_25", "2024_25"],
            "decision_time": [_dt(5), _dt(6)],
            "poisson_simple_lambda": [1.0, 1.0],
            "poisson_simple_mu": [1.0, 1.0],
            "total_goals": [3, 2],
        }
    )
    out = e14_module.build_walk_forward_probs(e7, e8, source, target, "poisson_simple")
    assert len(out) == 2  # les deux matchs cibles disposent d'un antecedent (source, jour 1)
    assert out.iloc[0]["p_over_2.5"] == pytest.approx(0.5)
    assert out.iloc[0]["outcome_over_2.5"] == 1.0  # total=3 > 2.5
    assert out.iloc[1]["outcome_over_2.5"] == 0.0  # total=2 <= 2.5


def test_build_walk_forward_probs_excludes_target_row_without_strictly_prior_source_row(e14_module) -> None:
    """Quand source == target (cas calibration-interne), un match ne peut
    jamais utiliser un antecedent qui lui est concomitant ou posterieur -
    le PREMIER match chronologique doit toujours etre exclu."""
    e7, e8 = _fake_e7_e8()
    df = pd.DataFrame(
        {
            "match_id": ["a", "b"],
            "league": ["premier_league", "premier_league"],
            "season": ["2024_25", "2024_25"],
            "decision_time": [_dt(5), _dt(6)],
            "poisson_simple_lambda": [1.0, 1.0],
            "poisson_simple_mu": [1.0, 1.0],
            "total_goals": [3, 2],
        }
    )
    out = e14_module.build_walk_forward_probs(e7, e8, df, df, "poisson_simple")
    assert len(out) == 1  # seul "b" (jour 6) a un antecedent strict ("a", jour 5)
    assert out.iloc[0]["match_id"] == "b"


def test_build_walk_forward_probs_excludes_rows_without_scale(e14_module) -> None:
    e7, e8 = _fake_e7_e8()
    df = pd.DataFrame(
        {
            "match_id": ["a"],
            "league": ["premier_league"],
            "season": ["2024_25"],
            "decision_time": [_dt(1)],
            "poisson_simple_lambda": [1.0],
            "poisson_simple_mu": [1.0],
            "total_goals": [2],
        }
    )
    # source vide -> aucune ligne anterieure disponible -> scale_c=None -> exclu
    out = e14_module.build_walk_forward_probs(e7, e8, df.iloc[0:0], df, "poisson_simple")
    assert out.empty


# --- fit_logistic_recalibration / apply_logistic_recalibration ---------------


def test_apply_logistic_recalibration_identity_when_a0_b1(e14_module) -> None:
    p = np.array([0.3, 0.5, 0.7])
    out = e14_module.apply_logistic_recalibration({"intercept": 0.0, "slope": 1.0}, p)
    assert out == pytest.approx(p, abs=1e-6)


def test_apply_logistic_recalibration_shrinks_toward_half_when_slope_below_one(e14_module) -> None:
    p = np.array([0.8])
    out = e14_module.apply_logistic_recalibration({"intercept": 0.0, "slope": 0.5}, p)
    assert 0.5 < out[0] < 0.8  # slope<1 rapproche la probabilite de 0.5 (correction de sur-confiance)


def test_fit_logistic_recalibration_uses_e11_cox_regression(e14_module, e11_module) -> None:
    rng = np.random.default_rng(0)
    p = rng.uniform(0.1, 0.9, size=200)
    y = rng.binomial(1, p).astype(float)
    out = e14_module.fit_logistic_recalibration(p, y, e11_module)
    assert set(out) == {"intercept", "slope", "converged"}


# --- apply_isotonic_recalibration ---------------------------------------------


def test_apply_isotonic_recalibration_monotone(e14_module) -> None:
    from sys_foot_quant.calibration_engine.isotonic_calibration import fit_isotonic_calibration

    p_calib = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
    y_calib = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
    curve = fit_isotonic_calibration(p_calib, y_calib)
    out = e14_module.apply_isotonic_recalibration(curve, np.array([0.2, 0.4, 0.6, 0.8]))
    assert np.all(np.diff(out) >= -1e-9)  # jamais decroissant


# --- walk_forward_recalibrate -------------------------------------------------


def test_walk_forward_recalibrate_excludes_below_min_matches(e14_module) -> None:
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(1), _dt(2)],
            "p_over_2.5": [0.5, 0.6],
            "outcome_over_2.5": [1.0, 0.0],
        }
    )
    test = pd.DataFrame({"match_id": ["m1"], "decision_time": [_dt(10)], "p_over_2.5": [0.65]})
    out = e14_module.walk_forward_recalibrate(
        calib, test, lambda p, y: {"intercept": 0.0, "slope": 1.0}, e14_module.apply_logistic_recalibration, min_matches=5
    )
    assert np.isnan(out.iloc[0]["p_recalibrated"])
    assert out.iloc[0]["n_calibration_used"] == 2


def test_walk_forward_recalibrate_never_uses_future_calibration_rows(e14_module) -> None:
    """Une ligne de calibration POSTERIEURE au match evalue (meme avec une
    valeur aberrante) ne doit jamais influencer le resultat - preuve
    directe d'absence de fuite temporelle."""
    calib = pd.DataFrame(
        {
            "decision_time": [_dt(d) for d in range(1, 6)] + [_dt(100)],
            "p_over_2.5": [0.5] * 5 + [0.99],  # la derniere ligne est "future" et aberrante
            "outcome_over_2.5": [1.0, 0.0, 1.0, 0.0, 1.0] + [0.0],
        }
    )
    test = pd.DataFrame({"match_id": ["m1"], "decision_time": [_dt(10)], "p_over_2.5": [0.5]})

    def fit_fn(p, y):
        return {"n_seen": len(p), "p_mean": float(np.mean(p))}

    def predict_fn(fitted, p):
        assert fitted["n_seen"] == 5  # jamais 6 : la ligne du jour 100 est exclue
        assert fitted["p_mean"] == pytest.approx(0.5)  # jamais influencee par 0.99
        return p

    out = e14_module.walk_forward_recalibrate(calib, test, fit_fn, predict_fn, min_matches=1)
    assert out.iloc[0]["n_calibration_used"] == 5


# --- zone_mask / zone_summary --------------------------------------------------


def test_zone_mask_boundaries_half_open() -> None:
    e14 = _load_script()
    p = np.array([0.599, 0.6, 0.699, 0.7])
    mask = e14.zone_mask(p, 0.6, 0.7)
    assert list(mask) == [False, True, True, False]


def test_zone_summary_basic() -> None:
    e14 = _load_script()
    p = np.array([0.6, 0.6, 0.6, 0.6])
    y = np.array([1.0, 1.0, 0.0, 0.0])
    out = e14.zone_summary(p, y)
    assert out["n"] == 4
    assert out["p_moyen"] == pytest.approx(0.6)
    assert out["freq_reelle"] == pytest.approx(0.5)
    assert out["biais"] == pytest.approx(-0.1)
    assert out["insuffisant"] is True  # n=4 < 30


def test_zone_summary_empty() -> None:
    e14 = _load_script()
    out = e14.zone_summary(np.array([]), np.array([]))
    assert out["n"] == 0
    assert out["insuffisant"] is True


# --- compare_brier_paired ------------------------------------------------------


def test_compare_brier_paired_zero_when_identical(e14_module) -> None:
    p = np.array([0.5, 0.6, 0.7])
    y = np.array([1.0, 0.0, 1.0])
    out = e14_module.compare_brier_paired(p, p, y)
    assert out["boot"]["mean_diff"] == pytest.approx(0.0, abs=1e-9)


def test_compare_brier_paired_none_when_too_few(e14_module) -> None:
    assert e14_module.compare_brier_paired(np.array([0.5]), np.array([0.6]), np.array([1.0])) is None


# --- coherence_gate -------------------------------------------------------------


def test_coherence_gate_detects_violation(e14_module) -> None:
    baseline = pd.DataFrame({"match_id": ["m1"], "p_over_1.5": [0.55], "p_over_3.5": [0.10]})
    recal = pd.DataFrame({"match_id": ["m1"], "p_recalibrated": [0.60]})  # > p_over_1.5 -> violation
    out = e14_module.coherence_gate(baseline, recal)
    assert out["n"] == 1
    assert out["n_violations"] == 1
    assert out["max_amplitude"] == pytest.approx(0.05, abs=1e-9)


def test_coherence_gate_no_violation_when_within_bounds(e14_module) -> None:
    baseline = pd.DataFrame({"match_id": ["m1"], "p_over_1.5": [0.70], "p_over_3.5": [0.10]})
    recal = pd.DataFrame({"match_id": ["m1"], "p_recalibrated": [0.50]})
    out = e14_module.coherence_gate(baseline, recal)
    assert out["n_violations"] == 0
    assert out["max_amplitude"] == pytest.approx(0.0)


def test_coherence_gate_ignores_nan_recalibrated_rows(e14_module) -> None:
    baseline = pd.DataFrame({"match_id": ["m1", "m2"], "p_over_1.5": [0.7, 0.7], "p_over_3.5": [0.1, 0.1]})
    recal = pd.DataFrame({"match_id": ["m1", "m2"], "p_recalibrated": [0.5, np.nan]})
    out = e14_module.coherence_gate(baseline, recal)
    assert out["n"] == 1  # la ligne NaN est exclue


# --- classify_e14_verdict -------------------------------------------------------


def _boot(lo: float, hi: float) -> dict:
    return {"ci_low": lo, "ci_high": hi}


def test_verdict_validee_when_all_criteria_met(e14_module) -> None:
    coherence = {"n": 100, "n_violations": 0, "rate": 0.0, "max_amplitude": 0.0}
    verdict, _ = e14_module.classify_e14_verdict(
        target_zone_boot=_boot(-0.05, -0.01),
        global_boot=_boot(-0.01, 0.001),
        adjacent_zone_boot=_boot(-0.002, 0.001),
        coherence=coherence,
        n_target=120,
    )
    assert verdict == e14_module.VERDICT_VALIDEE


def test_verdict_non_validee_when_target_zone_not_improved(e14_module) -> None:
    coherence = {"n": 100, "n_violations": 0, "rate": 0.0, "max_amplitude": 0.0}
    verdict, reasons = e14_module.classify_e14_verdict(
        target_zone_boot=_boot(-0.01, 0.02),  # contient 0 -> pas demontre
        global_boot=_boot(-0.01, 0.001),
        adjacent_zone_boot=_boot(-0.002, 0.001),
        coherence=coherence,
        n_target=120,
    )
    assert verdict == e14_module.VERDICT_NON_VALIDEE
    assert any("non demontree" in r for r in reasons)


def test_verdict_non_validee_when_insufficient_sample(e14_module) -> None:
    coherence = {"n": 10, "n_violations": 0, "rate": 0.0, "max_amplitude": 0.0}
    verdict, reasons = e14_module.classify_e14_verdict(
        target_zone_boot=_boot(-0.05, -0.01),
        global_boot=_boot(-0.01, 0.001),
        adjacent_zone_boot=_boot(-0.002, 0.001),
        coherence=coherence,
        n_target=10,
        min_n=30,
    )
    assert verdict == e14_module.VERDICT_NON_VALIDEE
    assert any("insuffisant" in r for r in reasons)


def test_verdict_non_validee_when_global_degraded(e14_module) -> None:
    coherence = {"n": 100, "n_violations": 0, "rate": 0.0, "max_amplitude": 0.0}
    verdict, reasons = e14_module.classify_e14_verdict(
        target_zone_boot=_boot(-0.05, -0.01),
        global_boot=_boot(0.001, 0.02),  # inversion globale
        adjacent_zone_boot=_boot(-0.002, 0.001),
        coherence=coherence,
        n_target=120,
    )
    assert verdict == e14_module.VERDICT_NON_VALIDEE
    assert any("global" in r for r in reasons)


def test_verdict_non_validee_when_adjacent_zone_degraded(e14_module) -> None:
    coherence = {"n": 100, "n_violations": 0, "rate": 0.0, "max_amplitude": 0.0}
    verdict, reasons = e14_module.classify_e14_verdict(
        target_zone_boot=_boot(-0.05, -0.01),
        global_boot=_boot(-0.01, 0.001),
        adjacent_zone_boot=_boot(0.001, 0.02),  # inversion locale zone adjacente
        coherence=coherence,
        n_target=120,
    )
    assert verdict == e14_module.VERDICT_NON_VALIDEE
    assert any("adjacente" in r for r in reasons)


def test_verdict_non_validee_when_coherence_violated(e14_module) -> None:
    coherence = {"n": 100, "n_violations": 3, "rate": 0.03, "max_amplitude": 0.02}
    verdict, reasons = e14_module.classify_e14_verdict(
        target_zone_boot=_boot(-0.05, -0.01),
        global_boot=_boot(-0.01, 0.001),
        adjacent_zone_boot=_boot(-0.002, 0.001),
        coherence=coherence,
        n_target=120,
    )
    assert verdict == e14_module.VERDICT_NON_VALIDEE
    assert any("coherence" in r for r in reasons)
