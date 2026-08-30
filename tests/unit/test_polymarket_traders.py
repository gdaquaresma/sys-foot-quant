from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sys_foot_quant.polymarket.schemas import Market, Trade
from sys_foot_quant.polymarket.traders import EligibilityRules, compute_trader_stats_as_of, eligible_traders_as_of

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _trade(wallet="0xabc", market="m1", side="BUY", price=0.5, size=10.0, outcome="Yes", offset_days=0) -> Trade:
    return Trade(
        wallet_id=wallet,
        market_id=market,
        timestamp_utc=_T0 + timedelta(days=offset_days),
        side=side,
        price=price,
        size=size,
        source="polymarket_data_api",
        outcome=outcome,
        notional=price * size,
    )


def _resolved_market(market_id="m1", outcome="Yes", resolution_offset_days=0.5) -> Market:
    return Market(
        market_id=market_id,
        source="polymarket_gamma_api",
        outcome=outcome,
        resolution_time=_T0 + timedelta(days=resolution_offset_days),
    )


def test_winning_buy_trade_yields_positive_realized_pnl() -> None:
    # BUY 10 shares "Yes" a 0.5 ; marche resolu "Yes" -> redemption 1.0/part.
    trades = [_trade(side="BUY", price=0.5, size=10.0, outcome="Yes")]
    markets = {"m1": _resolved_market(outcome="Yes")}
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.n_resolved_trades == 1
    assert stats.realized_pnl == 5.0  # 10 * (1.0 - 0.5)
    assert stats.win_rate == 1.0


def test_losing_buy_trade_yields_negative_realized_pnl() -> None:
    trades = [_trade(side="BUY", price=0.5, size=10.0, outcome="No")]
    markets = {"m1": _resolved_market(outcome="Yes")}  # "Yes" gagne, le trader avait "No"
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.realized_pnl == -5.0  # 10 * (0.0 - 0.5)
    assert stats.win_rate == 0.0


def test_unresolved_market_yields_none_realized_pnl_and_win_rate() -> None:
    trades = [_trade()]
    markets = {"m1": Market(market_id="m1", source="polymarket_gamma_api")}  # jamais resolu
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.n_resolved_trades == 0
    assert stats.realized_pnl is None
    assert stats.win_rate is None


def test_without_markets_argument_stats_stay_none_never_optimistic() -> None:
    trades = [_trade()]
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets=None)
    assert stats.realized_pnl is None
    assert stats.win_rate is None
    assert stats.n_trades == 1  # le volume/nombre de trades restent calculables sans `markets`


def test_resolution_known_only_after_decision_time_is_not_counted() -> None:
    """Une resolution connue APRES decision_time ne doit jamais compter
    comme une information disponible (etape 5)."""
    trades = [_trade(offset_days=0)]
    markets = {"m1": _resolved_market(resolution_offset_days=5)}  # resolu bien apres
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.n_resolved_trades == 0
    assert stats.realized_pnl is None


def test_eligible_traders_as_of_with_no_rules_applies_no_filter() -> None:
    trades_by_wallet = {"0xabc": [_trade(wallet="0xabc")], "0xdef": [_trade(wallet="0xdef", size=1.0)]}
    result = eligible_traders_as_of(_T0 + timedelta(days=1), trades_by_wallet, markets=None, rules=EligibilityRules())
    assert {s.wallet_id for s in result} == {"0xabc", "0xdef"}


def test_eligible_traders_as_of_filters_by_min_volume() -> None:
    trades_by_wallet = {
        "0xabc": [_trade(wallet="0xabc", price=0.5, size=100.0)],
        "0xdef": [_trade(wallet="0xdef", price=0.5, size=1.0)],
    }
    rules = EligibilityRules(min_volume_notional=10.0)
    result = eligible_traders_as_of(_T0 + timedelta(days=1), trades_by_wallet, markets=None, rules=rules)
    assert {s.wallet_id for s in result} == {"0xabc"}


def test_eligible_traders_as_of_top_n_by_realized_pnl() -> None:
    trades_by_wallet = {
        "0xabc": [_trade(wallet="0xabc", outcome="Yes")],  # gagnant
        "0xdef": [_trade(wallet="0xdef", outcome="No")],  # perdant
    }
    markets = {"m1": _resolved_market(outcome="Yes")}
    rules = EligibilityRules(top_n_by="realized_pnl", top_n=1)
    result = eligible_traders_as_of(_T0 + timedelta(days=1), trades_by_wallet, markets, rules)
    assert len(result) == 1
    assert result[0].wallet_id == "0xabc"


def test_eligible_traders_as_of_never_uses_trades_after_decision_time() -> None:
    trades_by_wallet = {
        "0xabc": [_trade(wallet="0xabc", offset_days=0, size=1.0), _trade(wallet="0xabc", offset_days=10, size=999.0)]
    }
    rules = EligibilityRules()
    result = eligible_traders_as_of(_T0 + timedelta(days=1), trades_by_wallet, markets=None, rules=rules)
    assert result[0].n_trades == 1
    assert result[0].volume_notional == pytest.approx(0.5)
