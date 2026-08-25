from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.weighting import (
    exponential_decay_weights,
    flat_weights,
    rolling_window_weights,
)


def test_flat_weights_are_all_ones() -> None:
    w = flat_weights(5)
    assert w.shape == (5,)
    assert (w == 1.0).all()


def test_exponential_decay_weight_at_zero_age_is_one() -> None:
    w = exponential_decay_weights(np.array([0.0, 10.0, 100.0]), half_life_days=10.0)
    assert w[0] == pytest.approx(1.0)


def test_exponential_decay_halves_at_half_life() -> None:
    w = exponential_decay_weights(np.array([0.0, 10.0, 20.0]), half_life_days=10.0)
    assert w[1] == pytest.approx(0.5, rel=1e-6)
    assert w[2] == pytest.approx(0.25, rel=1e-6)


def test_exponential_decay_rejects_non_positive_half_life() -> None:
    with pytest.raises(ValueError):
        exponential_decay_weights(np.array([0.0]), half_life_days=0.0)


def test_rolling_window_weights_binary_cutoff() -> None:
    ranks = np.array([0, 1, 2, 3, 4])
    w = rolling_window_weights(ranks, window_matches=3)
    np.testing.assert_array_equal(w, [1.0, 1.0, 1.0, 0.0, 0.0])


def test_rolling_window_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError):
        rolling_window_weights(np.array([0, 1]), window_matches=0)


@given(
    ages=st.lists(st.floats(min_value=0, max_value=3650, allow_nan=False), min_size=1, max_size=50),
    half_life=st.floats(min_value=0.01, max_value=1000, allow_nan=False),
)
@settings(max_examples=100)
def test_exponential_decay_weights_are_bounded_and_monotonic(ages, half_life) -> None:
    ages_arr = np.array(sorted(ages))
    w = exponential_decay_weights(ages_arr, half_life_days=half_life)
    # Peut sous-flotter a 0.0 pour un age tres grand devant la demi-vie ;
    # la seule garantie mathematique est la non-negativite et la borne haute.
    assert (w >= 0).all()
    assert (w <= 1.0 + 1e-9).all()
    # Plus l'age est grand (ages_arr est trie croissant), plus le poids doit
    # etre decroissant (ou egal).
    assert (np.diff(w) <= 1e-12).all()


@given(n=st.integers(min_value=1, max_value=200))
@settings(max_examples=25)
def test_flat_weights_length_matches_n(n: int) -> None:
    w = flat_weights(n)
    assert len(w) == n
