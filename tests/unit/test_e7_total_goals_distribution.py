"""Tests unitaires des fonctions PURES d'E7
(scripts/run_stage15_e7_total_goals_distribution.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson as scipy_poisson

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage15_e7_total_goals_distribution.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage15_e7_total_goals_distribution", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e7_module():
    return _load_script()


# --- independent_matrix / dixon_coles_matrix -----------------------------


def test_independent_matrix_sums_to_one_and_non_negative(e7_module) -> None:
    m = e7_module.independent_matrix(1.4, 1.1)
    assert m.sum() == pytest.approx(1.0)
    assert (m >= 0).all()


def test_dixon_coles_matrix_sums_to_one_and_non_negative(e7_module) -> None:
    m = e7_module.dixon_coles_matrix(1.4, 1.1, rho=-0.05)
    assert m.sum() == pytest.approx(1.0)
    assert (m >= 0).all()


def test_dixon_coles_matrix_rho_zero_matches_independent(e7_module) -> None:
    m_dc = e7_module.dixon_coles_matrix(1.4, 1.1, rho=0.0)
    m_indep = e7_module.independent_matrix(1.4, 1.1)
    np.testing.assert_allclose(m_dc, m_indep, atol=1e-9)


# --- total_goals_distribution / over_under_probs --------------------------


def test_total_goals_distribution_sums_to_one(e7_module) -> None:
    m = e7_module.independent_matrix(1.5, 1.2)
    dist = e7_module.total_goals_distribution(m)
    assert dist.sum() == pytest.approx(1.0)
    assert len(dist) == e7_module._MAX_BUCKET + 1


def test_total_goals_distribution_matches_manual_low_totals(e7_module) -> None:
    lam, mu = 1.3, 0.9
    m = e7_module.independent_matrix(lam, mu)
    dist = e7_module.total_goals_distribution(m)
    expected_p0 = scipy_poisson.pmf(0, lam) * scipy_poisson.pmf(0, mu)
    assert dist[0] == pytest.approx(expected_p0, abs=1e-6)


def test_over_under_probs_higher_rate_gives_higher_over_probability(e7_module) -> None:
    low = e7_module.independent_matrix(0.8, 0.8)
    high = e7_module.independent_matrix(2.2, 2.0)
    p_low = e7_module.over_under_probs(low, thresholds=(2.5,))[2.5]
    p_high = e7_module.over_under_probs(high, thresholds=(2.5,))[2.5]
    assert p_high > p_low


# --- coherence checks (etape 4) --------------------------------------------


def test_check_distribution_validity_true_for_valid_distribution(e7_module) -> None:
    dist = e7_module.total_goals_distribution(e7_module.independent_matrix(1.5, 1.3))
    result = e7_module.check_distribution_validity(dist)
    assert result["all_non_negative"] is True
    assert result["sums_to_one"] is True


def test_check_distribution_validity_false_for_invalid_distribution(e7_module) -> None:
    dist = np.array([0.5, 0.5, 0.5, -0.1, 0.0, 0.0, 0.0])
    result = e7_module.check_distribution_validity(dist)
    assert result["all_non_negative"] is False
    assert result["sums_to_one"] is False


def test_check_over_under_monotonic_true_for_real_distribution(e7_module) -> None:
    m = e7_module.independent_matrix(1.6, 1.2)
    ou = e7_module.over_under_probs(m)
    assert e7_module.check_over_under_monotonic(ou) is True


def test_check_over_under_monotonic_false_for_manufactured_violation(e7_module) -> None:
    ou = {1.5: 0.55, 2.5: 0.58, 3.5: 0.61}  # viole P(1.5)>=P(2.5)>=P(3.5)
    assert e7_module.check_over_under_monotonic(ou) is False


@pytest.mark.parametrize("lam,mu,rho", [(1.5, 1.2, 0.0), (2.3, 0.9, -0.08), (0.7, 0.6, 0.03)])
def test_over_under_always_monotonic_across_many_rates(e7_module, lam, mu, rho) -> None:
    m = e7_module.dixon_coles_matrix(lam, mu, rho)
    ou = e7_module.over_under_probs(m)
    assert e7_module.check_over_under_monotonic(ou) is True


def test_check_over_under_matches_distribution_true_by_construction(e7_module) -> None:
    m = e7_module.independent_matrix(1.7, 1.4)
    dist = e7_module.total_goals_distribution(m)
    ou = e7_module.over_under_probs(m)
    assert e7_module.check_over_under_matches_distribution(dist, ou) is True


def test_check_over_under_matches_distribution_false_when_ou_computed_separately(e7_module) -> None:
    m1 = e7_module.independent_matrix(1.7, 1.4)
    m2 = e7_module.independent_matrix(2.5, 2.0)  # matrice DIFFERENTE -> incoherent
    dist = e7_module.total_goals_distribution(m1)
    ou = e7_module.over_under_probs(m2)
    assert e7_module.check_over_under_matches_distribution(dist, ou) is False


# --- fit_scale_correction ---------------------------------------------------


def test_fit_scale_correction_matches_manual_ratio(e7_module) -> None:
    df = pd.DataFrame(
        {
            "poisson_simple_lambda": [1.0, 1.5, 2.0],
            "poisson_simple_mu": [1.0, 1.0, 1.0],
            "total_goals": [3, 3, 3],
        }
    )
    c = e7_module.fit_scale_correction(df, "poisson_simple")
    predicted_mean = np.mean([2.0, 2.5, 3.0])
    assert c == pytest.approx(3.0 / predicted_mean)


def test_fit_scale_correction_is_one_when_already_unbiased(e7_module) -> None:
    rng = np.random.default_rng(0)
    lam = rng.uniform(1.0, 2.0, size=500)
    mu = rng.uniform(0.8, 1.8, size=500)
    df = pd.DataFrame({"poisson_simple_lambda": lam, "poisson_simple_mu": mu, "total_goals": lam + mu})
    c = e7_module.fit_scale_correction(df, "poisson_simple")
    assert c == pytest.approx(1.0, abs=1e-9)


def test_fit_scale_correction_drops_nan_rows(e7_module) -> None:
    df = pd.DataFrame(
        {
            "poisson_simple_lambda": [1.0, np.nan, 2.0],
            "poisson_simple_mu": [1.0, 1.0, 1.0],
            "total_goals": [2.0, 99.0, 3.0],  # la ligne NaN a un total absurde, ne doit pas compter
        }
    )
    c = e7_module.fit_scale_correction(df, "poisson_simple")
    predicted_mean = np.mean([2.0, 3.0])
    actual_mean = np.mean([2.0, 3.0])
    assert c == pytest.approx(actual_mean / predicted_mean)


# --- diagnostic de queue (etape 2) -----------------------------------------


def test_poisson_reference_distribution_sums_to_one(e7_module) -> None:
    ref = e7_module.poisson_reference_distribution(2.79)
    assert ref.sum() == pytest.approx(1.0)


def test_poisson_reference_distribution_matches_scipy_low_values(e7_module) -> None:
    ref = e7_module.poisson_reference_distribution(2.5)
    assert ref[0] == pytest.approx(scipy_poisson.pmf(0, 2.5))
    assert ref[3] == pytest.approx(scipy_poisson.pmf(3, 2.5))


def test_dispersion_index_is_one_for_poisson_samples(e7_module) -> None:
    rng = np.random.default_rng(1)
    samples = rng.poisson(3.0, size=200_000).astype(float)
    idx = e7_module.dispersion_index(samples)
    assert idx == pytest.approx(1.0, abs=0.02)


def test_dispersion_index_above_one_for_overdispersed_data(e7_module) -> None:
    rng = np.random.default_rng(2)
    # melange de deux Poisson de moyennes differentes -> surdispersion connue
    samples = np.concatenate([rng.poisson(1.0, size=5000), rng.poisson(5.0, size=5000)]).astype(float)
    assert e7_module.dispersion_index(samples) > 1.5


# --- matrix_for_row ---------------------------------------------------------


def test_matrix_for_row_returns_none_when_history_insufficient(e7_module) -> None:
    row = pd.Series({"poisson_simple_lambda": np.nan, "poisson_simple_mu": np.nan})
    assert e7_module.matrix_for_row(row, "poisson_simple") is None


def test_matrix_for_row_applies_scale(e7_module) -> None:
    row = pd.Series({"poisson_simple_lambda": 1.0, "poisson_simple_mu": 1.0})
    m_raw = e7_module.matrix_for_row(row, "poisson_simple", scale=1.0)
    m_scaled = e7_module.matrix_for_row(row, "poisson_simple", scale=1.5)
    # une esperance plus haute -> P(Over 2.5) plus haute
    ou_raw = e7_module.over_under_probs(m_raw, thresholds=(2.5,))[2.5]
    ou_scaled = e7_module.over_under_probs(m_scaled, thresholds=(2.5,))[2.5]
    assert ou_scaled > ou_raw


def test_matrix_for_row_dixon_coles_uses_rho(e7_module) -> None:
    row = pd.Series({"dixon_coles_lambda": 1.5, "dixon_coles_mu": 1.2, "dixon_coles_rho": -0.1})
    m = e7_module.matrix_for_row(row, "dixon_coles", scale=1.0)
    expected = e7_module.dixon_coles_matrix(1.5, 1.2, -0.1)
    np.testing.assert_allclose(m, expected)
