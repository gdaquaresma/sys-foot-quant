"""Tests de fuite temporelle explicites pour la couche Polymarket (Phase L,
etape 5 - point le plus important de la phase). Reproduit l'exemple
obligatoire de la consigne : un wallet avec 100 trades avant
``decision_time`` et 20 trades apres ne doit JAMAIS laisser les 20
derniers influencer n_trades/volume/ROI/win_rate/positions/ranking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sys_foot_quant.polymarket.pit import get_trader_information_as_of
from sys_foot_quant.polymarket.schemas import Market, Trade
from sys_foot_quant.polymarket.traders import EligibilityRules, compute_trader_stats_as_of, eligible_traders_as_of

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
_DECISION_TIME = _T0 + timedelta(days=100)


def _trade(day: int, wallet="0xabc", market="m1", price=0.5, size=1.0, outcome="Yes") -> Trade:
    return Trade(
        wallet_id=wallet,
        market_id=market,
        timestamp_utc=_T0 + timedelta(days=day),
        side="BUY",
        price=price,
        size=size,
        source="polymarket_data_api",
        outcome=outcome,
        notional=price * size,
    )


def _make_100_before_20_after() -> list[Trade]:
    before = [_trade(day=d) for d in range(100)]  # jours 0..99, tous < decision_time (jour 100)
    after = [_trade(day=100 + d) for d in range(20)]  # jours 100..119, tous >= decision_time
    return before + after


def test_trades_as_of_never_includes_a_future_trade() -> None:
    trades = _make_100_before_20_after()
    info = get_trader_information_as_of("0xabc", _DECISION_TIME, trades)
    assert len(info.trades_as_of) == 100
    assert all(t.timestamp_utc < _DECISION_TIME for t in info.trades_as_of)


def test_n_trades_as_of_ignores_the_20_future_trades() -> None:
    trades = _make_100_before_20_after()
    stats = compute_trader_stats_as_of("0xabc", _DECISION_TIME, trades, markets=None)
    assert stats.n_trades == 100


def test_volume_as_of_ignores_the_20_future_trades() -> None:
    trades = _make_100_before_20_after()
    stats = compute_trader_stats_as_of("0xabc", _DECISION_TIME, trades, markets=None)
    assert stats.volume_notional == 100 * 0.5  # seulement les 100 trades d'avant, jamais les 20 d'apres


def test_positions_as_of_ignores_the_20_future_trades() -> None:
    trades = _make_100_before_20_after()
    info = get_trader_information_as_of("0xabc", _DECISION_TIME, trades)
    assert info.positions_as_of == {"m1": {"Yes": 100.0}}  # 100, jamais 120


def test_realized_pnl_and_win_rate_never_use_a_resolution_known_only_in_the_future() -> None:
    """Un marche resolu APRES decision_time (meme si son resultat existe
    deja dans les donnees fournies) ne doit jamais alimenter le profit ou
    le win rate observes a decision_time."""
    trades = [_trade(day=0, market="m_past", outcome="Yes"), _trade(day=0, market="m_future", outcome="Yes")]
    markets = {
        "m_past": Market(market_id="m_past", source="polymarket_gamma_api", outcome="Yes", resolution_time=_T0 + timedelta(days=1)),
        "m_future": Market(market_id="m_future", source="polymarket_gamma_api", outcome="Yes", resolution_time=_DECISION_TIME + timedelta(days=1)),
    }
    stats = compute_trader_stats_as_of("0xabc", _DECISION_TIME, trades, markets)
    assert stats.n_resolved_trades == 1  # uniquement m_past
    assert stats.realized_pnl == 0.5  # 1 * (1.0 - 0.5), jamais 1.0 (les deux marches)


def test_ranking_selection_never_uses_future_trades() -> None:
    """eligible_traders_as_of (etape 8) : le classement a decision_time
    ne doit jamais etre influence par des trades futurs, meme tres
    volumineux."""
    trades = [_trade(day=0, wallet="0xabc", size=1.0), _trade(day=200, wallet="0xabc", size=100000.0)]
    rules = EligibilityRules(min_volume_notional=100.0)  # seul le trade futur depasserait ce seuil
    result = eligible_traders_as_of(_DECISION_TIME, {"0xabc": trades}, markets=None, rules=rules)
    assert result == []  # le trade futur ne doit jamais rendre le wallet eligible a decision_time


def test_two_different_decision_times_yield_different_stats_never_cached_or_reused() -> None:
    trades = _make_100_before_20_after()
    stats_early = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets=None)
    stats_late = compute_trader_stats_as_of("0xabc", _DECISION_TIME, trades, markets=None)
    assert stats_early.n_trades == 1
    assert stats_late.n_trades == 100
    assert stats_early.as_of != stats_late.as_of
