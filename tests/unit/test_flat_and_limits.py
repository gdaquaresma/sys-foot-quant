from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.risk_engine.flat import flat_stake
from sys_foot_quant.risk_engine.limits import StakeLimits, apply_stake_limits


def test_flat_stake_known_value() -> None:
    assert flat_stake(1000.0, 0.02) == pytest.approx(20.0)


def test_flat_stake_is_constant_regardless_of_current_balance() -> None:
    # Par construction, flat_stake ne prend meme pas la bankroll courante
    # en parametre : deux appels avec la meme bankroll INITIALE donnent
    # toujours la meme mise, meme si le solde courant a change entre-temps.
    s1 = flat_stake(1000.0, 0.02)
    s2 = flat_stake(1000.0, 0.02)
    assert s1 == s2 == 20.0


def test_flat_stake_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        flat_stake(0.0, 0.02)
    with pytest.raises(ValueError):
        flat_stake(1000.0, 0.0)
    with pytest.raises(ValueError):
        flat_stake(1000.0, 1.5)


@given(
    initial_bankroll=st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False),
    fraction=st.floats(min_value=1e-6, max_value=1.0, allow_nan=False),
)
@settings(max_examples=100)
def test_flat_stake_never_exceeds_initial_bankroll(initial_bankroll, fraction) -> None:
    stake = flat_stake(initial_bankroll, fraction)
    assert 0.0 < stake <= initial_bankroll + 1e-9


def test_stake_limits_rejects_invalid_fraction() -> None:
    with pytest.raises(ValueError):
        StakeLimits(max_fraction_of_current_balance=0.0)
    with pytest.raises(ValueError):
        StakeLimits(max_fraction_of_current_balance=1.5)
    with pytest.raises(ValueError):
        StakeLimits(max_fraction_of_current_balance=0.05, max_absolute_stake=-10.0)


def test_apply_stake_limits_caps_to_fraction() -> None:
    limits = StakeLimits(max_fraction_of_current_balance=0.05)
    capped = apply_stake_limits(raw_stake=1000.0, current_balance=1000.0, limits=limits)
    assert capped == pytest.approx(50.0)


def test_apply_stake_limits_respects_absolute_cap() -> None:
    limits = StakeLimits(max_fraction_of_current_balance=0.50, max_absolute_stake=30.0)
    capped = apply_stake_limits(raw_stake=1000.0, current_balance=1000.0, limits=limits)
    assert capped == pytest.approx(30.0)


def test_apply_stake_limits_never_exceeds_current_balance() -> None:
    limits = StakeLimits(max_fraction_of_current_balance=1.0)
    capped = apply_stake_limits(raw_stake=500.0, current_balance=100.0, limits=limits)
    assert capped == pytest.approx(100.0)


def test_apply_stake_limits_zero_balance_gives_zero_stake() -> None:
    limits = StakeLimits(max_fraction_of_current_balance=0.05)
    assert apply_stake_limits(raw_stake=10.0, current_balance=0.0, limits=limits) == 0.0


def test_apply_stake_limits_rejects_negative_raw_stake() -> None:
    limits = StakeLimits(max_fraction_of_current_balance=0.05)
    with pytest.raises(ValueError):
        apply_stake_limits(raw_stake=-1.0, current_balance=100.0, limits=limits)


@given(
    raw_stake=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False),
    current_balance=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False),
    max_fraction=st.floats(min_value=1e-6, max_value=1.0, allow_nan=False),
)
@settings(max_examples=150)
def test_apply_stake_limits_always_within_bounds(raw_stake, current_balance, max_fraction) -> None:
    limits = StakeLimits(max_fraction_of_current_balance=max_fraction)
    capped = apply_stake_limits(raw_stake, current_balance, limits)
    assert 0.0 <= capped <= current_balance + 1e-9
    assert capped <= raw_stake + 1e-9
    assert capped <= current_balance * max_fraction + 1e-6
