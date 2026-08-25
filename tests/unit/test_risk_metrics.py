from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.risk_engine.bankroll import BankrollHistory
from sys_foot_quant.risk_engine.metrics import (
    compute_risk_metrics,
    drawdown_curve,
    max_drawdown,
    stepwise_returns,
    volatility,
)

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _curve(balances: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"step": range(len(balances)), "timestamp": [None] * len(balances), "balance": balances})


def test_drawdown_curve_known_value() -> None:
    curve = _curve([1000.0, 1100.0, 990.0, 1200.0])
    out = drawdown_curve(curve)
    assert list(out["running_max"]) == pytest.approx([1000.0, 1100.0, 1100.0, 1200.0])
    assert list(out["drawdown"]) == pytest.approx([0.0, 0.0, -0.1, 0.0])


def test_max_drawdown_known_value() -> None:
    curve = _curve([1000.0, 1100.0, 990.0, 1200.0])
    assert max_drawdown(curve) == pytest.approx(-0.1)


def test_max_drawdown_zero_when_monotonic_increase() -> None:
    curve = _curve([1000.0, 1100.0, 1200.0])
    assert max_drawdown(curve) == pytest.approx(0.0)


def test_drawdown_curve_rejects_empty() -> None:
    with pytest.raises(ValueError):
        drawdown_curve(pd.DataFrame({"step": [], "timestamp": [], "balance": []}))


def test_stepwise_returns_known_value() -> None:
    curve = _curve([1000.0, 1200.0, 800.0])
    returns = stepwise_returns(curve)
    assert returns == pytest.approx([0.2, 800.0 / 1200.0 - 1.0])


def test_stepwise_returns_requires_at_least_two_points() -> None:
    with pytest.raises(ValueError):
        stepwise_returns(_curve([1000.0]))


def test_volatility_matches_manual_std() -> None:
    curve = _curve([1000.0, 1200.0, 800.0, 950.0])
    expected = np.std(stepwise_returns(curve), ddof=0)
    assert volatility(curve) == pytest.approx(expected)


def test_compute_risk_metrics_known_values() -> None:
    curve = _curve([1000.0, 1100.0, 990.0])
    records = pd.DataFrame({"won": [True, False]})
    metrics = compute_risk_metrics(curve, records)
    assert metrics.initial_balance == pytest.approx(1000.0)
    assert metrics.final_balance == pytest.approx(990.0)
    assert metrics.total_return_pct == pytest.approx(-1.0)
    assert metrics.max_drawdown_pct == pytest.approx(-10.0)
    assert metrics.n_bets == 2
    assert metrics.win_rate == pytest.approx(0.5)


def test_compute_risk_metrics_no_bets_gives_zero_volatility_and_return() -> None:
    curve = _curve([1000.0])
    metrics = compute_risk_metrics(curve)
    assert metrics.n_bets == 0
    assert metrics.total_return_pct == pytest.approx(0.0)
    assert metrics.volatility_pct == pytest.approx(0.0)
    assert metrics.win_rate is None


def test_compute_risk_metrics_rejects_empty_curve() -> None:
    with pytest.raises(ValueError):
        compute_risk_metrics(pd.DataFrame({"step": [], "timestamp": [], "balance": []}))


def test_metrics_integrate_with_real_bankroll_history() -> None:
    bh = BankrollHistory(1000.0)
    bh.settle_bet(_T0, 1, "home", stake=100.0, odds=2.0, won=True)
    bh.settle_bet(_T0 + timedelta(days=1), 2, "away", stake=100.0, odds=2.0, won=False)
    bh.settle_bet(_T0 + timedelta(days=2), 3, "home", stake=100.0, odds=3.0, won=True)
    metrics = compute_risk_metrics(bh.balance_curve(), bh.to_dataframe())
    assert metrics.n_bets == 3
    assert metrics.final_balance == pytest.approx(bh.current_balance)
    assert metrics.win_rate == pytest.approx(2.0 / 3.0)


@given(
    balances=st.lists(st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False), min_size=1, max_size=30)
)
@settings(max_examples=100)
def test_max_drawdown_always_non_positive(balances: list[float]) -> None:
    curve = _curve(balances)
    assert max_drawdown(curve) <= 1e-9


@given(
    balances=st.lists(st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False), min_size=2, max_size=30)
)
@settings(max_examples=100)
def test_volatility_always_non_negative(balances: list[float]) -> None:
    curve = _curve(balances)
    assert volatility(curve) >= 0.0
