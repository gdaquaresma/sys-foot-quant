from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss


def test_brier_score_perfect_prediction_is_zero() -> None:
    probs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    outcomes = np.array([0, 1])
    assert brier_score(probs, outcomes) == pytest.approx(0.0, abs=1e-9)


def test_brier_score_uniform_prediction_known_value() -> None:
    probs = np.array([[1 / 3, 1 / 3, 1 / 3]])
    outcomes = np.array([0])
    # (1/3-1)^2 + (1/3-0)^2 + (1/3-0)^2 = 4/9 + 1/9 + 1/9 = 6/9
    assert brier_score(probs, outcomes) == pytest.approx(6 / 9, abs=1e-9)


def test_brier_score_worst_case_is_two() -> None:
    probs = np.array([[1.0, 0.0, 0.0]])
    outcomes = np.array([2])
    # (1-0)^2 + (0-0)^2 + (0-1)^2 = 2
    assert brier_score(probs, outcomes) == pytest.approx(2.0, abs=1e-9)


def test_log_loss_perfect_prediction_is_near_zero() -> None:
    probs = np.array([[0.999999, 0.0000005, 0.0000005]])
    outcomes = np.array([0])
    assert log_loss(probs, outcomes) < 1e-4


def test_log_loss_uniform_prediction_known_value() -> None:
    probs = np.array([[1 / 3, 1 / 3, 1 / 3]])
    outcomes = np.array([0])
    assert log_loss(probs, outcomes) == pytest.approx(np.log(3), abs=1e-9)


def test_log_loss_clips_zero_probabilities_instead_of_raising() -> None:
    probs = np.array([[0.0, 1.0, 0.0]])
    outcomes = np.array([0])  # predicted prob of true class is exactly 0
    value = log_loss(probs, outcomes)
    assert np.isfinite(value)
    assert value > 0


def test_brier_and_log_loss_reject_mismatched_lengths() -> None:
    probs = np.array([[1 / 3, 1 / 3, 1 / 3]])
    outcomes = np.array([0, 1])
    with pytest.raises(ValueError):
        brier_score(probs, outcomes)
    with pytest.raises(ValueError):
        log_loss(probs, outcomes)


def test_brier_and_log_loss_reject_rows_not_summing_to_one() -> None:
    probs = np.array([[0.5, 0.5, 0.5]])
    outcomes = np.array([0])
    with pytest.raises(ValueError):
        brier_score(probs, outcomes)
    with pytest.raises(ValueError):
        log_loss(probs, outcomes)


def _simplex_triplets():
    return st.lists(
        st.floats(min_value=0.001, max_value=1.0, allow_nan=False), min_size=3, max_size=3
    ).map(lambda xs: [x / sum(xs) for x in xs])


@given(row=_simplex_triplets(), outcome=st.integers(min_value=0, max_value=2))
@settings(max_examples=100)
def test_brier_score_always_in_valid_range(row, outcome) -> None:
    probs = np.array([row])
    outcomes = np.array([outcome])
    b = brier_score(probs, outcomes)
    assert -1e-9 <= b <= 2.0 + 1e-9


@given(row=_simplex_triplets(), outcome=st.integers(min_value=0, max_value=2))
@settings(max_examples=100)
def test_log_loss_always_non_negative(row, outcome) -> None:
    probs = np.array([row])
    outcomes = np.array([outcome])
    ll = log_loss(probs, outcomes)
    assert ll >= -1e-9
