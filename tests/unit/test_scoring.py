from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.scoring import outcome_probabilities, score_matrix


def test_score_matrix_shape() -> None:
    m = score_matrix(1.5, 1.1, max_goals=10)
    assert m.shape == (11, 11)


def test_score_matrix_sums_close_to_one_for_reasonable_lambdas() -> None:
    m = score_matrix(1.3, 1.1, max_goals=15)
    assert m.sum() == pytest.approx(1.0, abs=1e-9)


def test_score_matrix_rejects_non_positive_lambda() -> None:
    with pytest.raises(ValueError):
        score_matrix(0.0, 1.0)
    with pytest.raises(ValueError):
        score_matrix(1.0, -1.0)


def test_outcome_probabilities_sum_matches_matrix_sum() -> None:
    m = score_matrix(1.8, 0.9, max_goals=15)
    home_win, draw, away_win = outcome_probabilities(m)
    assert (home_win + draw + away_win) == pytest.approx(m.sum(), abs=1e-9)


def test_outcome_probabilities_symmetric_lambdas_give_symmetric_win_probs() -> None:
    m = score_matrix(1.4, 1.4, max_goals=15)
    home_win, draw, away_win = outcome_probabilities(m)
    assert home_win == pytest.approx(away_win, abs=1e-9)


def test_higher_home_lambda_increases_home_win_probability() -> None:
    m_low = score_matrix(1.0, 1.4, max_goals=15)
    m_high = score_matrix(2.0, 1.4, max_goals=15)
    home_low, _, _ = outcome_probabilities(m_low)
    home_high, _, _ = outcome_probabilities(m_high)
    assert home_high > home_low


@given(
    lam=st.floats(min_value=0.05, max_value=6.0, allow_nan=False),
    mu=st.floats(min_value=0.05, max_value=6.0, allow_nan=False),
)
@settings(max_examples=100)
def test_score_matrix_is_a_valid_probability_distribution(lam: float, mu: float) -> None:
    m = score_matrix(lam, mu, max_goals=20)
    assert (m >= 0).all()
    assert m.sum() <= 1.0 + 1e-9
    assert m.sum() >= 1.0 - 1e-4


@given(
    lam=st.floats(min_value=0.05, max_value=6.0, allow_nan=False),
    mu=st.floats(min_value=0.05, max_value=6.0, allow_nan=False),
)
@settings(max_examples=100)
def test_outcome_probabilities_are_non_negative_and_bounded(lam: float, mu: float) -> None:
    m = score_matrix(lam, mu, max_goals=20)
    home_win, draw, away_win = outcome_probabilities(m)
    for p in (home_win, draw, away_win):
        assert -1e-9 <= p <= 1.0 + 1e-9
