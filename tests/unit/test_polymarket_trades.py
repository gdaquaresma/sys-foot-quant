from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sys_foot_quant.polymarket.trades import deduplicate_trades, parse_trade, parse_trades


def _raw_trade(**overrides) -> dict:
    base = {
        "proxyWallet": "0xabc",
        "market": "m1",
        "timestamp": "2025-01-08T18:00:00Z",
        "side": "buy",
        "price": 0.6,
        "size": 10.0,
    }
    base.update(overrides)
    return base


def test_parse_trade_computes_notional() -> None:
    t = parse_trade(_raw_trade(), source="polymarket_data_api")
    assert t.wallet_id == "0xabc"
    assert t.side == "BUY"
    assert t.notional == pytest.approx(6.0)


def test_parse_trade_accepts_unix_timestamp() -> None:
    t = parse_trade(_raw_trade(timestamp=1736359200), source="polymarket_data_api")
    assert isinstance(t.timestamp_utc, datetime)


def test_parse_trade_missing_required_field_raises() -> None:
    raw = _raw_trade()
    del raw["price"]
    with pytest.raises(ValueError):
        parse_trade(raw, source="polymarket_data_api")


def test_parse_trade_naive_timestamp_string_raises() -> None:
    with pytest.raises(ValueError):
        parse_trade(_raw_trade(timestamp="2025-01-08T18:00:00"), source="polymarket_data_api")  # sans fuseau


def test_parse_trade_missing_wallet_raises() -> None:
    raw = _raw_trade()
    del raw["proxyWallet"]
    with pytest.raises(ValueError):
        parse_trade(raw, source="polymarket_data_api")


def test_parse_trade_optional_trade_id_defaults_to_none() -> None:
    t = parse_trade(_raw_trade(), source="polymarket_data_api")
    assert t.trade_id is None


def test_parse_trade_uses_trade_id_when_present() -> None:
    t = parse_trade(_raw_trade(id="tx_1"), source="polymarket_data_api")
    assert t.trade_id == "tx_1"


def test_parse_trades_parses_a_list() -> None:
    raws = [_raw_trade(id="tx_1"), _raw_trade(id="tx_2")]
    trades = parse_trades(raws, source="polymarket_data_api")
    assert [t.trade_id for t in trades] == ["tx_1", "tx_2"]


def test_deduplicate_trades_by_trade_id() -> None:
    t1 = parse_trade(_raw_trade(id="tx_1"), source="polymarket_data_api")
    t1_dup = parse_trade(_raw_trade(id="tx_1", price=0.7), source="polymarket_data_api")  # meme id, autre prix
    result = deduplicate_trades([t1, t1_dup])
    assert len(result) == 1
    assert result[0] is t1  # premiere occurrence conservee


def test_deduplicate_trades_without_trade_id_uses_full_tuple() -> None:
    t1 = parse_trade(_raw_trade(), source="polymarket_data_api")
    t1_identical = parse_trade(_raw_trade(), source="polymarket_data_api")
    t2_different_price = parse_trade(_raw_trade(price=0.7), source="polymarket_data_api")
    result = deduplicate_trades([t1, t1_identical, t2_different_price])
    assert len(result) == 2


def test_parse_trade_market_field_carries_the_condition_id_on_real_payloads() -> None:
    """Un vrai trade Data API n'a pas de champ ``market``/``market_id`` -
    seulement ``conditionId``, qui devient ``Trade.market_id``."""
    raw = _raw_trade()
    del raw["market"]
    raw["conditionId"] = "0xfe0ebcbb0a3de954dcf08c7d1ef0c1333d94a89d7f0effa03591e1f7bb0a0ebc"
    t = parse_trade(raw, source="polymarket_data_api")
    assert t.market_id == "0xfe0ebcbb0a3de954dcf08c7d1ef0c1333d94a89d7f0effa03591e1f7bb0a0ebc"


def test_parse_trade_reads_token_id_from_asset_field() -> None:
    t = parse_trade(_raw_trade(asset="20076506283589584596606774059885927045312670930336534845403126008074405160402"), source="polymarket_data_api")
    assert t.token_id == "20076506283589584596606774059885927045312670930336534845403126008074405160402"


def test_parse_trade_token_id_is_none_when_absent() -> None:
    t = parse_trade(_raw_trade(), source="polymarket_data_api")
    assert t.token_id is None
