from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.risk_engine.bankroll import BankrollHistory

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_initial_balance() -> None:
    bh = BankrollHistory(1000.0)
    assert bh.current_balance == 1000.0
    assert bh.records == []


def test_rejects_non_positive_initial_balance() -> None:
    with pytest.raises(ValueError):
        BankrollHistory(0.0)
    with pytest.raises(ValueError):
        BankrollHistory(-100.0)


def test_settle_bet_win_updates_balance_correctly() -> None:
    bh = BankrollHistory(1000.0)
    record = bh.settle_bet(_T0, match_id=1, selection="home", stake=100.0, odds=2.5, won=True)
    assert record.pnl == pytest.approx(150.0)
    assert record.balance_before == pytest.approx(1000.0)
    assert record.balance_after == pytest.approx(1150.0)
    assert bh.current_balance == pytest.approx(1150.0)


def test_settle_bet_loss_updates_balance_correctly() -> None:
    bh = BankrollHistory(1000.0)
    record = bh.settle_bet(_T0, match_id=1, selection="home", stake=100.0, odds=2.5, won=False)
    assert record.pnl == pytest.approx(-100.0)
    assert bh.current_balance == pytest.approx(900.0)


def test_settle_bet_rejects_stake_over_balance() -> None:
    bh = BankrollHistory(100.0)
    with pytest.raises(ValueError, match="decouvert"):
        bh.settle_bet(_T0, 1, "home", stake=101.0, odds=2.0, won=True)


def test_settle_bet_rejects_invalid_stake_or_odds() -> None:
    bh = BankrollHistory(1000.0)
    with pytest.raises(ValueError):
        bh.settle_bet(_T0, 1, "home", stake=0.0, odds=2.0, won=True)
    with pytest.raises(ValueError):
        bh.settle_bet(_T0, 1, "home", stake=10.0, odds=1.0, won=True)


def test_settle_bet_rejects_non_chronological_order() -> None:
    bh = BankrollHistory(1000.0)
    bh.settle_bet(_T0, 1, "home", stake=10.0, odds=2.0, won=True)
    with pytest.raises(ValueError, match="chronologique"):
        bh.settle_bet(_T0 - timedelta(seconds=1), 2, "away", stake=10.0, odds=2.0, won=True)


def test_settle_bet_allows_equal_timestamps() -> None:
    # Deux mises simultanees (meme journee de matchs) sont autorisees ;
    # seul un ordre STRICTEMENT decroissant est refuse.
    bh = BankrollHistory(1000.0)
    bh.settle_bet(_T0, 1, "home", stake=10.0, odds=2.0, won=True)
    bh.settle_bet(_T0, 2, "away", stake=10.0, odds=2.0, won=False)
    assert len(bh.records) == 2


def test_balance_curve_matches_records() -> None:
    bh = BankrollHistory(1000.0)
    bh.settle_bet(_T0, 1, "home", stake=100.0, odds=2.0, won=True)
    bh.settle_bet(_T0 + timedelta(days=1), 2, "away", stake=50.0, odds=3.0, won=False)
    curve = bh.balance_curve()
    assert list(curve["balance"]) == pytest.approx([1000.0, 1100.0, 1050.0])
    assert list(curve["step"]) == [0, 1, 2]


def test_to_dataframe_has_one_row_per_bet() -> None:
    bh = BankrollHistory(1000.0)
    bh.settle_bet(_T0, 1, "home", stake=10.0, odds=2.0, won=True)
    bh.settle_bet(_T0, 2, "away", stake=10.0, odds=2.0, won=False)
    df = bh.to_dataframe()
    assert len(df) == 2
    assert set(df["match_id"]) == {1, 2}


@given(
    stakes_and_outcomes=st.lists(
        st.tuples(st.floats(min_value=1.0, max_value=50.0), st.floats(min_value=1.01, max_value=10.0), st.booleans()),
        min_size=1,
        max_size=30,
    )
)
@settings(max_examples=100)
def test_balance_never_goes_negative_when_stakes_bounded(stakes_and_outcomes) -> None:
    bh = BankrollHistory(1000.0)
    t = _T0
    for stake, odds, won in stakes_and_outcomes:
        if stake > bh.current_balance:
            continue  # ne pas tester un cas deja rejete explicitement ailleurs
        bh.settle_bet(t, 1, "home", stake=stake, odds=odds, won=won)
        t += timedelta(hours=1)
    assert bh.current_balance >= 0.0


@given(
    n=st.integers(min_value=2, max_value=20),
)
@settings(max_examples=30)
def test_out_of_order_timestamps_always_rejected(n: int) -> None:
    bh = BankrollHistory(10_000.0)
    bh.settle_bet(_T0, 1, "home", stake=10.0, odds=2.0, won=True)
    earlier = _T0 - timedelta(minutes=n)
    with pytest.raises(ValueError, match="chronologique"):
        bh.settle_bet(earlier, 2, "away", stake=10.0, odds=2.0, won=True)
