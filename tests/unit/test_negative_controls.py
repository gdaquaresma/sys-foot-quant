from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.negative_controls import (
    is_calendar_congested,
    is_must_win_proxy,
    rolling_win_rate,
)

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_is_calendar_congested_false_with_no_history() -> None:
    assert is_calendar_congested(_T0, []) is False


def test_is_calendar_congested_true_with_two_recent_matches() -> None:
    prior = [_T0 - timedelta(days=2), _T0 - timedelta(days=5)]
    assert is_calendar_congested(_T0, prior) is True


def test_is_calendar_congested_false_when_matches_outside_window() -> None:
    prior = [_T0 - timedelta(days=10), _T0 - timedelta(days=20)]
    assert is_calendar_congested(_T0, prior) is False


def test_is_calendar_congested_boundary_is_inclusive() -> None:
    prior = [_T0 - timedelta(days=7), _T0 - timedelta(days=3)]
    assert is_calendar_congested(_T0, prior, window_days=7.0) is True


def test_is_calendar_congested_rejects_invalid_min_matches() -> None:
    with pytest.raises(ValueError):
        is_calendar_congested(_T0, [], min_matches_in_window=0)


def test_rolling_win_rate_none_when_insufficient_history() -> None:
    results = [(_T0 - timedelta(days=i), True) for i in range(5)]
    assert rolling_win_rate(results, window=10) is None


def test_rolling_win_rate_known_value() -> None:
    results = [(_T0 - timedelta(days=i), i % 2 == 0) for i in range(10)]  # 5 wins, 5 losses
    assert rolling_win_rate(results, window=10) == pytest.approx(0.5)


def test_rolling_win_rate_uses_only_most_recent_window() -> None:
    old_losses = [(_T0 - timedelta(days=100 + i), False) for i in range(20)]
    recent_wins = [(_T0 - timedelta(days=i), True) for i in range(5)]
    results = old_losses + recent_wins
    assert rolling_win_rate(results, window=5) == pytest.approx(1.0)


def test_rolling_win_rate_sorts_unordered_input() -> None:
    shuffled = [
        (_T0 - timedelta(days=1), True),
        (_T0 - timedelta(days=5), False),
        (_T0 - timedelta(days=3), True),
        (_T0 - timedelta(days=2), True),
        (_T0 - timedelta(days=4), False),
    ]
    assert rolling_win_rate(shuffled, window=5) == pytest.approx(3 / 5)


def test_rolling_win_rate_rejects_invalid_window() -> None:
    with pytest.raises(ValueError):
        rolling_win_rate([], window=0)


def test_is_must_win_proxy_none_propagates() -> None:
    assert is_must_win_proxy(None) is None


def test_is_must_win_proxy_below_threshold() -> None:
    assert is_must_win_proxy(0.1, threshold=0.3) is True


def test_is_must_win_proxy_above_threshold() -> None:
    assert is_must_win_proxy(0.5, threshold=0.3) is False


def test_is_must_win_proxy_boundary_is_exclusive() -> None:
    assert is_must_win_proxy(0.3, threshold=0.3) is False


@given(
    n_prior=st.integers(min_value=0, max_value=20),
    window_days=st.floats(min_value=1.0, max_value=30.0),
)
@settings(max_examples=50)
def test_is_calendar_congested_never_true_with_zero_prior_matches(n_prior, window_days) -> None:
    if n_prior == 0:
        assert is_calendar_congested(_T0, [], window_days=window_days) is False


@given(win_rate=st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0, allow_nan=False)))
@settings(max_examples=30)
def test_is_must_win_proxy_returns_bool_or_none(win_rate) -> None:
    result = is_must_win_proxy(win_rate)
    assert result is None or isinstance(result, bool)
