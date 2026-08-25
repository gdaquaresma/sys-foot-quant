"""Tests unitaires des fonctions pures Dixon-Coles du generateur
synthetique (data_engine/synthetic/generator.py, hypothese B1).

Duplication assumee avec tests/unit/test_dixon_coles.py (football_model) :
c'est precisement le point souleve par l'ADR 0005 (le Data Engine ne doit
pas dependre du Football Model, la logique tau est dupliquee ici cote
generateur) - ces tests verifient la copie du Data Engine independamment
de celle du Football Model.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.data_engine.synthetic.generator import (
    _dixon_coles_outcome_probabilities,
    _dixon_coles_rho_bounds,
    _dixon_coles_score_matrix,
    _dixon_coles_tau,
    _validate_dixon_coles_rho,
)


def test_tau_formula() -> None:
    lam, mu, rho = 1.35, 1.10, -0.13
    assert _dixon_coles_tau(0, 0, lam, mu, rho) == pytest.approx(1.0 - lam * mu * rho)
    assert _dixon_coles_tau(1, 0, lam, mu, rho) == pytest.approx(1.0 + mu * rho)
    assert _dixon_coles_tau(0, 1, lam, mu, rho) == pytest.approx(1.0 + lam * rho)
    assert _dixon_coles_tau(1, 1, lam, mu, rho) == pytest.approx(1.0 - rho)
    assert _dixon_coles_tau(3, 2, lam, mu, rho) == 1.0


def test_tau_identity_at_rho_zero() -> None:
    for x, y in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        assert _dixon_coles_tau(x, y, lam=1.35, mu=1.10, rho=0.0) == pytest.approx(1.0)


def test_rho_bounds_literary_value_is_valid_for_typical_lambdas() -> None:
    lo, hi = _dixon_coles_rho_bounds(lam=1.35, mu=1.10)
    assert lo <= -0.13 <= hi


def test_validate_rho_raises_outside_bounds() -> None:
    lo, hi = _dixon_coles_rho_bounds(lam=1.35, mu=1.10)
    with pytest.raises(ValueError):
        _validate_dixon_coles_rho(lo - 0.5, lam=1.35, mu=1.10)
    with pytest.raises(ValueError):
        _validate_dixon_coles_rho(hi + 0.5, lam=1.35, mu=1.10)
    # Ne leve rien a l'interieur des bornes (y compris aux bornes elles-memes).
    _validate_dixon_coles_rho(lo, lam=1.35, mu=1.10)
    _validate_dixon_coles_rho(hi, lam=1.35, mu=1.10)
    _validate_dixon_coles_rho(-0.13, lam=1.35, mu=1.10)


def test_score_matrix_sums_to_one_and_is_nonnegative() -> None:
    matrix = _dixon_coles_score_matrix(lam=1.35, mu=1.10, rho=-0.13)
    assert matrix.sum() == pytest.approx(1.0, abs=1e-9)
    assert (matrix >= 0.0).all()


def test_score_matrix_rho_zero_matches_independent_poisson_outer_product() -> None:
    from scipy.stats import poisson as scipy_poisson

    lam, mu = 1.35, 1.10
    matrix = _dixon_coles_score_matrix(lam, mu, rho=0.0, max_goals=15)
    goals = np.arange(0, 16)
    expected = np.outer(scipy_poisson.pmf(goals, lam), scipy_poisson.pmf(goals, mu))
    expected = expected / expected.sum()
    assert np.allclose(matrix, expected, atol=1e-12)


def test_score_matrix_negative_rho_increases_00_and_11() -> None:
    lam, mu, rho = 1.35, 1.10, -0.13
    with_rho = _dixon_coles_score_matrix(lam, mu, rho)
    without_rho = _dixon_coles_score_matrix(lam, mu, 0.0)
    assert with_rho[0, 0] > without_rho[0, 0]
    assert with_rho[1, 1] > without_rho[1, 1]
    assert with_rho[1, 0] < without_rho[1, 0]
    assert with_rho[0, 1] < without_rho[0, 1]


def test_outcome_probabilities_sum_to_one() -> None:
    probs = _dixon_coles_outcome_probabilities(lam=1.35, mu=1.10, rho=-0.13)
    assert sum(probs) == pytest.approx(1.0, abs=1e-9)
    assert all(p >= 0.0 for p in probs)


def test_outcome_probabilities_rho_zero_matches_true_outcome_probabilities() -> None:
    from sys_foot_quant.data_engine.synthetic.generator import _true_outcome_probabilities

    lam, mu = 1.35, 1.10
    dc = _dixon_coles_outcome_probabilities(lam, mu, rho=0.0)
    plain = _true_outcome_probabilities(lam, mu)
    assert dc == pytest.approx(plain, abs=1e-9)


@given(
    lam=st.floats(min_value=0.3, max_value=4.0),
    mu=st.floats(min_value=0.3, max_value=4.0),
)
@settings(max_examples=100)
def test_score_matrix_always_valid_distribution_within_bounds(lam: float, mu: float) -> None:
    lo, hi = _dixon_coles_rho_bounds(lam, mu)
    for rho in (lo, lo / 2.0 if lo < 0 else lo, 0.0, hi):
        matrix = _dixon_coles_score_matrix(lam, mu, rho, max_goals=15)
        assert matrix.sum() == pytest.approx(1.0, abs=1e-6)
        assert (matrix >= -1e-12).all()
