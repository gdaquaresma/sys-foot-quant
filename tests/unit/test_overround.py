from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.market_engine.overround import (
    hold_percentage,
    remove_overround_proportional,
)


def test_remove_overround_sums_to_one() -> None:
    odds = {"home": 2.00, "draw": 3.40, "away": 4.00}
    fair = remove_overround_proportional(odds)
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-9)


def test_remove_overround_preserves_relative_ordering() -> None:
    odds = {"home": 1.50, "draw": 4.00, "away": 6.00}
    fair = remove_overround_proportional(odds)
    assert fair["home"] > fair["draw"] > fair["away"]


def test_hold_percentage_known_value() -> None:
    # -110/-110 americain classique ~ 1.909/1.909 decimal -> hold ~4.76%
    odds = {"a": 1.909, "b": 1.909}
    hold = hold_percentage(odds)
    assert hold == pytest.approx(0.0476, abs=1e-3)


def test_remove_overround_rejects_odds_at_or_below_one() -> None:
    with pytest.raises(ValueError):
        remove_overround_proportional({"home": 1.0, "away": 2.0})
    with pytest.raises(ValueError):
        remove_overround_proportional({"home": 0.9, "away": 2.0})


def test_remove_overround_rejects_empty_market() -> None:
    with pytest.raises(ValueError):
        remove_overround_proportional({})


@given(
    odds=st.lists(
        st.floats(min_value=1.01, max_value=50.0, allow_nan=False),
        min_size=2,
        max_size=5,
    )
)
@settings(max_examples=150)
def test_remove_overround_always_sums_to_one_and_stays_in_bounds(odds: list[float]) -> None:
    market = {f"sel_{i}": o for i, o in enumerate(odds)}
    fair = remove_overround_proportional(market)
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-6)
    for p in fair.values():
        assert 0.0 < p < 1.0
