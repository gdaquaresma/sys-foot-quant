from __future__ import annotations

from datetime import datetime, timezone

from sys_foot_quant.polymarket.schemas import (
    Market,
    MarketMatchResult,
    PricePoint,
    Trade,
    Trader,
    TraderInformationAsOf,
    TraderStatsAsOf,
)


def test_market_requires_only_id_and_source_rest_optional() -> None:
    m = Market(market_id="m1", source="polymarket_gamma_api")
    assert m.event_id is None
    assert m.home_team is None
    assert m.resolution_time is None


def test_trade_requires_core_fields_rest_optional() -> None:
    t = Trade(
        wallet_id="0xabc",
        market_id="m1",
        timestamp_utc=datetime(2025, 1, 1, tzinfo=timezone.utc),
        side="BUY",
        price=0.6,
        size=10.0,
        source="polymarket_data_api",
    )
    assert t.trade_id is None
    assert t.notional is None  # calcule au parsing (trades.py), pas ici


def test_trader_never_carries_a_statistic_field() -> None:
    t = Trader(wallet_id="0xabc", source="polymarket_data_api")
    assert not hasattr(t, "roi")
    assert not hasattr(t, "win_rate")
    assert not hasattr(t, "ranking")


def test_trader_stats_as_of_is_explicitly_timestamped() -> None:
    stats = TraderStatsAsOf(
        wallet_id="0xabc",
        as_of=datetime(2025, 1, 1, tzinfo=timezone.utc),
        n_trades=5,
        n_resolved_trades=2,
        volume_notional=100.0,
        realized_pnl=10.0,
        win_rate=0.5,
        open_position_count=1,
    )
    assert stats.as_of == datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_trader_information_as_of_bundles_trades_positions_and_stats() -> None:
    as_of = datetime(2025, 1, 1, tzinfo=timezone.utc)
    stats = TraderStatsAsOf(
        wallet_id="0xabc", as_of=as_of, n_trades=0, n_resolved_trades=0,
        volume_notional=0.0, realized_pnl=None, win_rate=None, open_position_count=0,
    )
    info = TraderInformationAsOf(
        wallet_id="0xabc", as_of=as_of, trades_as_of=(), positions_as_of={}, stats_as_of=stats,
    )
    assert info.trades_as_of == ()
    assert info.stats_as_of is stats


def test_price_point_requires_only_core_fields_rest_optional() -> None:
    p = PricePoint(market_id="m1", timestamp_utc=datetime(2025, 1, 1, tzinfo=timezone.utc), price=0.5, source="s")
    assert p.token_id is None
    assert p.outcome is None


def test_market_match_result_carries_candidates_only_when_ambiguous() -> None:
    unmatched = MarketMatchResult(polymarket_market_id="pm1", match_id=None, reason_code="POLYMARKET_MATCH_UNMATCHED")
    assert unmatched.candidates == ()
    matched = MarketMatchResult(polymarket_market_id="pm1", match_id="fd_123", reason_code=None)
    assert matched.match_id == "fd_123"
