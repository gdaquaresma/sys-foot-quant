from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sys_foot_quant.polymarket.positions import derive_positions_as_of
from sys_foot_quant.polymarket.schemas import Trade

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _trade(wallet="0xabc", market="m1", side="BUY", size=10.0, outcome="Yes", offset_days=0) -> Trade:
    return Trade(
        wallet_id=wallet,
        market_id=market,
        timestamp_utc=_T0 + timedelta(days=offset_days),
        side=side,
        price=0.5,
        size=size,
        source="polymarket_data_api",
        outcome=outcome,
    )


def test_buy_and_sell_net_correctly() -> None:
    trades = [_trade(side="BUY", size=10.0), _trade(side="SELL", size=4.0)]
    positions = derive_positions_as_of("0xabc", _T0 + timedelta(days=1), trades)
    assert positions == {"m1": {"Yes": 6.0}}


def test_trades_at_or_after_decision_time_are_excluded() -> None:
    trades = [_trade(offset_days=0, size=10.0), _trade(offset_days=1, size=5.0)]
    positions = derive_positions_as_of("0xabc", _T0 + timedelta(hours=12), trades)
    assert positions == {"m1": {"Yes": 10.0}}  # le trade du jour 1 n'est pas encore connu


def test_other_wallets_are_excluded() -> None:
    trades = [_trade(wallet="0xabc", size=10.0), _trade(wallet="0xdef", size=99.0)]
    positions = derive_positions_as_of("0xabc", _T0 + timedelta(days=1), trades)
    assert positions == {"m1": {"Yes": 10.0}}


def test_separate_outcomes_are_tracked_independently() -> None:
    trades = [_trade(outcome="Yes", size=10.0), _trade(outcome="No", size=3.0)]
    positions = derive_positions_as_of("0xabc", _T0 + timedelta(days=1), trades)
    assert positions == {"m1": {"Yes": 10.0, "No": 3.0}}


def test_unknown_side_raises() -> None:
    bad = _trade()
    bad = Trade(**{**bad.__dict__, "side": "HOLD"})
    with pytest.raises(ValueError):
        derive_positions_as_of("0xabc", _T0 + timedelta(days=1), [bad])
