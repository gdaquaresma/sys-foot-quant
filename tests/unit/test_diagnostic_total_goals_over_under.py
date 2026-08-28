"""Tests unitaires des fonctions PURES du diagnostic total de buts /
Over-Under (scripts/run_stage8_diagnostic_total_goals_over_under.py) -
verifie les calculs avant toute lecture des chiffres reels."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import poisson

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage8_diagnostic_total_goals_over_under.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage8_diagnostic_total_goals_over_under", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def diag_module():
    return _load_script()


def _independent_matrix(lam: float, mu: float, max_goals: int = 15) -> np.ndarray:
    goals = np.arange(0, max_goals + 1)
    p_home = poisson.pmf(goals, lam)
    p_away = poisson.pmf(goals, mu)
    m = np.outer(p_home, p_away)
    return m / m.sum()


def test_over_under_probs_sum_to_one_with_under(diag_module) -> None:
    m = _independent_matrix(1.4, 1.1)
    probs = diag_module.over_under_probs(m, thresholds=(2.5,))
    p_over = probs[2.5]
    assert 0.0 <= p_over <= 1.0
    # under = 1 - over par construction (pas de troisieme categorie)
    assert p_over + (1 - p_over) == pytest.approx(1.0)


def test_over_under_probs_known_case_0_0_always_under() -> None:
    # Matrice degenere concentree entierement sur 0-0 : Over 0.5 doit valoir 0.
    m = np.zeros((5, 5))
    m[0, 0] = 1.0
    mod = _load_script()
    probs = mod.over_under_probs(m, thresholds=(0.5,))
    assert probs[0.5] == pytest.approx(0.0)


def test_over_under_probs_higher_lambda_mu_gives_higher_over_probability(diag_module) -> None:
    low = _independent_matrix(0.8, 0.8)
    high = _independent_matrix(2.2, 2.0)
    p_low = diag_module.over_under_probs(low, thresholds=(2.5,))[2.5]
    p_high = diag_module.over_under_probs(high, thresholds=(2.5,))[2.5]
    assert p_high > p_low


def test_total_goals_distribution_sums_to_one(diag_module) -> None:
    m = _independent_matrix(1.5, 1.2)
    dist = diag_module.total_goals_distribution(m, max_bucket=6)
    assert dist.sum() == pytest.approx(1.0)
    assert len(dist) == 7  # 0..5 + "6+"


def test_total_goals_distribution_matches_manual_computation_for_low_totals(diag_module) -> None:
    lam, mu = 1.3, 0.9
    m = _independent_matrix(lam, mu, max_goals=15)
    dist = diag_module.total_goals_distribution(m, max_bucket=6)
    # P(total=0) = P(X=0)*P(Y=0) exactement (poisson independants)
    expected_p0 = poisson.pmf(0, lam) * poisson.pmf(0, mu)
    assert dist[0] == pytest.approx(expected_p0, abs=1e-9)


def test_binary_brier_and_logloss_perfect_prediction_is_zero_brier(diag_module) -> None:
    p = np.array([1.0, 0.0, 1.0, 0.0])
    y = np.array([1.0, 0.0, 1.0, 0.0])
    brier, logloss = diag_module._binary_brier_and_logloss(p, y)
    assert brier == pytest.approx(0.0, abs=1e-9)
    assert logloss == pytest.approx(0.0, abs=1e-6)


def test_binary_brier_worst_case_prediction_is_one(diag_module) -> None:
    p = np.array([0.0, 1.0])
    y = np.array([1.0, 0.0])
    brier, _ = diag_module._binary_brier_and_logloss(p, y)
    assert brier == pytest.approx(1.0)


def test_binary_brier_uninformative_half_prediction(diag_module) -> None:
    p = np.array([0.5, 0.5, 0.5, 0.5])
    y = np.array([1.0, 0.0, 1.0, 0.0])
    brier, _ = diag_module._binary_brier_and_logloss(p, y)
    assert brier == pytest.approx(0.25)
