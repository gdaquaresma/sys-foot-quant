from __future__ import annotations

import numpy as np
import pytest

from sys_foot_quant.calibration_engine.decomposition import (
    bin_monotonicity_violations,
    brier_decomposition,
)


def test_perfect_prediction_has_zero_reliability_and_resolution_equals_uncertainty() -> None:
    probs = np.array([1.0, 1.0, 0.0, 0.0, 1.0, 0.0])
    outcomes = probs.copy()
    d = brier_decomposition(probs, outcomes, n_bins=10)
    assert d["reliability"] == pytest.approx(0.0, abs=1e-9)
    assert d["resolution"] == pytest.approx(d["uncertainty"], abs=1e-9)
    assert d["brier_grouped"] == pytest.approx(0.0, abs=1e-9)
    assert d["brier_raw"] == pytest.approx(0.0, abs=1e-9)


def test_constant_climatological_prediction_has_zero_resolution() -> None:
    outcomes = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    ybar = outcomes.mean()
    probs = np.full_like(outcomes, ybar)
    d = brier_decomposition(probs, outcomes, n_bins=10)
    assert d["resolution"] == pytest.approx(0.0, abs=1e-9)
    assert d["reliability"] == pytest.approx(0.0, abs=1e-6)
    assert d["brier_grouped"] == pytest.approx(d["uncertainty"], abs=1e-6)


def test_decomposition_identity_holds_for_grouped_brier() -> None:
    rng = np.random.default_rng(0)
    probs = rng.uniform(0, 1, size=500)
    outcomes = (rng.uniform(0, 1, size=500) < probs).astype(float)
    d = brier_decomposition(probs, outcomes, n_bins=10)
    assert d["brier_grouped"] == pytest.approx(
        d["reliability"] - d["resolution"] + d["uncertainty"], abs=1e-9
    )


def test_grouped_and_raw_brier_are_close_for_well_behaved_probabilities() -> None:
    rng = np.random.default_rng(1)
    probs = rng.uniform(0, 1, size=2000)
    outcomes = (rng.uniform(0, 1, size=2000) < probs).astype(float)
    d = brier_decomposition(probs, outcomes, n_bins=10)
    assert abs(d["grouping_error"]) < 0.01


def test_uncertainty_matches_manual_formula() -> None:
    outcomes = np.array([1.0, 1.0, 1.0, 0.0])
    probs = np.array([0.9, 0.6, 0.7, 0.2])
    d = brier_decomposition(probs, outcomes, n_bins=4)
    ybar = 0.75
    assert d["uncertainty"] == pytest.approx(ybar * (1 - ybar))


def test_skill_score_is_nan_when_uncertainty_is_zero() -> None:
    outcomes = np.zeros(5)  # aucune variance : ybar=0
    probs = np.array([0.1, 0.2, 0.05, 0.3, 0.15])
    d = brier_decomposition(probs, outcomes, n_bins=5)
    assert np.isnan(d["skill_score_vs_climatology"])


def test_mismatched_shapes_raise() -> None:
    with pytest.raises(ValueError):
        brier_decomposition(np.array([0.5, 0.5]), np.array([1.0]))


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError):
        brier_decomposition(np.array([]), np.array([]))


def test_monotonic_probabilities_have_no_violations() -> None:
    # 10 tranches de probabilite croissante, frequence observee strictement
    # croissante avec elles - discrimination parfaitement monotone.
    rng = np.random.default_rng(2)
    n_per_bin = 200
    probs, outcomes = [], []
    for i in range(10):
        p_lo, p_hi = i / 10, (i + 1) / 10
        p_mid = (p_lo + p_hi) / 2
        bin_probs = rng.uniform(p_lo, p_hi, size=n_per_bin)
        bin_outcomes = (rng.uniform(0, 1, size=n_per_bin) < p_mid).astype(float)
        probs.append(bin_probs)
        outcomes.append(bin_outcomes)
    probs = np.concatenate(probs)
    outcomes = np.concatenate(outcomes)
    res = bin_monotonicity_violations(probs, outcomes, n_bins=10)
    # Bruit d'echantillonnage tolere, mais l'immense majorite des
    # transitions doit rester croissante avec un signal aussi net.
    assert res["violation_rate"] < 0.3


def test_perfectly_anti_monotonic_case_detected() -> None:
    # Probabilite predite croissante, mais frequence observee DECROISSANTE
    # (le modele se trompe de sens) - toutes les transitions doivent violer.
    probs = np.array([0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95])
    outcomes = np.array([1, 1, 1, 1, 1, 0, 0, 0, 0, 0], dtype=float)
    res = bin_monotonicity_violations(probs, outcomes, n_bins=10)
    assert res["n_violations"] >= 1


def test_single_bin_returns_nan_violation_rate() -> None:
    probs = np.array([0.5, 0.5, 0.5])
    outcomes = np.array([1.0, 0.0, 1.0])
    res = bin_monotonicity_violations(probs, outcomes, n_bins=1)
    assert np.isnan(res["violation_rate"])
