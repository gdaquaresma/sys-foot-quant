"""Tests de src/sys_foot_quant/polymarket/imports.py (Phase N).

IMPORTANT (etape 11 de la consigne) : TOUS les tests de ce fichier
utilisent des donnees SYNTHETIQUES construites a la main. Aucun ne
constitue une preuve de faisabilite sur des donnees Polymarket REELLES -
seul un export reel (non disponible dans cet environnement, voir
docs/polymarket_data_collection_protocol.md) pourrait le demontrer. Ces
tests verifient uniquement que le mecanisme de validation lui-meme est
correct, pas que Polymarket se comporte ainsi en pratique."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sys_foot_quant.polymarket.imports import (
    IMPORT_REJECT_DUPLICATE,
    IMPORT_REJECT_FUTURE_DATA_AS_PREMATCH,
    IMPORT_REJECT_INCONSISTENT_IDENTIFIER,
    IMPORT_REJECT_INVALID_TIMESTAMP,
    IMPORT_REJECT_RESOLUTION_BEFORE_ITS_TIME,
    INFORMATION_AFTER_DECISION_TIME,
    INFORMATION_AVAILABLE_AT_DECISION_TIME,
    MARKET_RESOLUTION_INFORMATION,
    classify_information_timing,
    compute_coverage_report,
    is_unresolved_match,
    parse_price_point,
    validate_market_resolution_consistency,
    validate_premarket_trades_bundle,
    validate_price_history_export,
    validate_trades_export,
)
from sys_foot_quant.polymarket.reason_codes import POLYMARKET_MATCH_AMBIGUOUS, POLYMARKET_MATCH_UNMATCHED
from sys_foot_quant.polymarket.schemas import Market, MarketMatchResult, Trade

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _raw_trade(**overrides) -> dict:
    base = {
        "proxyWallet": "0xabc",
        "market": "m1",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "side": "buy",
        "price": 0.6,
        "size": 10.0,
    }
    base.update(overrides)
    return base


# --- classify_information_timing (etape 4) -----------------------------------


def test_classify_before_decision_time_is_available() -> None:
    result = classify_information_timing(_T0, _T0 + timedelta(hours=1))
    assert result == INFORMATION_AVAILABLE_AT_DECISION_TIME


def test_classify_at_or_after_decision_time_is_after() -> None:
    assert classify_information_timing(_T0, _T0) == INFORMATION_AFTER_DECISION_TIME
    assert classify_information_timing(_T0 + timedelta(hours=2), _T0) == INFORMATION_AFTER_DECISION_TIME


def test_classify_resolution_information_is_always_resolution_regardless_of_timestamp() -> None:
    """Une resolution reste MARKET_RESOLUTION_INFORMATION meme si son
    timestamp brut precederait decision_time - jamais requalifiee en
    information "disponible" ordinaire (etape 4 : "verifier qu'une donnee
    de resolution ne peut jamais contaminer la prediction pre-match")."""
    result = classify_information_timing(_T0, _T0 + timedelta(days=10), is_resolution_information=True)
    assert result == MARKET_RESOLUTION_INFORMATION


# --- validate_trades_export ---------------------------------------------------


def test_validate_trades_export_accepts_valid_records() -> None:
    report = validate_trades_export([_raw_trade(id="t1"), _raw_trade(id="t2")], source="manual_export")
    assert report.n_accepted == 2
    assert report.n_rejected == 0


def test_validate_trades_export_rejects_invalid_timestamp_explicitly() -> None:
    report = validate_trades_export([_raw_trade(timestamp="2025-01-01T00:00:00")], source="manual_export")  # sans fuseau
    assert report.n_accepted == 0
    assert report.n_rejected == 1
    assert report.rejected[0].reason_code == IMPORT_REJECT_INVALID_TIMESTAMP


def test_validate_trades_export_rejects_incomplete_record_explicitly() -> None:
    raw = _raw_trade()
    del raw["price"]
    report = validate_trades_export([raw], source="manual_export")
    assert report.rejected[0].reason_code == IMPORT_REJECT_INCONSISTENT_IDENTIFIER


def test_validate_trades_export_rejects_duplicates_explicitly_never_silently() -> None:
    report = validate_trades_export([_raw_trade(id="t1"), _raw_trade(id="t1", price=0.7)], source="manual_export")
    assert report.n_accepted == 1
    assert report.n_rejected == 1
    assert report.rejected[0].reason_code == IMPORT_REJECT_DUPLICATE


def test_validate_trades_export_one_bad_record_does_not_crash_the_batch() -> None:
    good = _raw_trade(id="t1")
    bad = _raw_trade()
    del bad["side"]
    report = validate_trades_export([good, bad], source="manual_export")
    assert report.n_accepted == 1
    assert report.n_rejected == 1


# --- validate_premarket_trades_bundle -----------------------------------------


def test_validate_premarket_trades_bundle_accepts_trades_strictly_before_decision_time() -> None:
    trades = [Trade(wallet_id="0xabc", market_id="m1", timestamp_utc=_T0, side="BUY", price=0.5, size=1.0, source="s")]
    report = validate_premarket_trades_bundle(trades, decision_time=_T0 + timedelta(hours=1))
    assert report.n_accepted == 1
    assert report.n_rejected == 0


def test_validate_premarket_trades_bundle_rejects_future_data_used_as_prematch() -> None:
    """Reproduit exactement l'exigence de l'etape 10 : des donnees
    posterieures a decision_time ne doivent jamais etre acceptees comme
    pre-match - et le rejet doit etre EXPLICITE (code dedie), pas un
    simple filtrage silencieux."""
    trades = [
        Trade(wallet_id="0xabc", market_id="m1", timestamp_utc=_T0, side="BUY", price=0.5, size=1.0, source="s"),
        Trade(
            wallet_id="0xabc", market_id="m1", timestamp_utc=_T0 + timedelta(hours=2), side="BUY", price=0.9,
            size=1.0, source="s",
        ),
    ]
    report = validate_premarket_trades_bundle(trades, decision_time=_T0 + timedelta(hours=1))
    assert report.n_accepted == 1
    assert report.n_rejected == 1
    assert report.rejected[0].reason_code == IMPORT_REJECT_FUTURE_DATA_AS_PREMATCH


def test_validate_premarket_trades_bundle_rejects_trade_exactly_at_decision_time() -> None:
    trades = [Trade(wallet_id="0xabc", market_id="m1", timestamp_utc=_T0, side="BUY", price=0.5, size=1.0, source="s")]
    report = validate_premarket_trades_bundle(trades, decision_time=_T0)
    assert report.n_accepted == 0
    assert report.rejected[0].reason_code == IMPORT_REJECT_FUTURE_DATA_AS_PREMATCH


# --- validate_market_resolution_consistency -----------------------------------


def test_resolution_before_its_time_is_rejected() -> None:
    """Un Market qui porte deja une issue gagnante alors que sa
    resolution_time est posterieure (ou absente) au moment ou l'export
    pretend avoir ete pris - signal de fuite dans l'export lui-meme."""
    market = Market(
        market_id="m1", source="manual_export", outcome="Yes",
        resolution_time=_T0 + timedelta(days=1),
    )
    rejection = validate_market_resolution_consistency(market, claimed_snapshot_time=_T0)
    assert rejection is not None
    assert rejection.reason_code == IMPORT_REJECT_RESOLUTION_BEFORE_ITS_TIME


def test_resolution_known_before_snapshot_time_is_accepted() -> None:
    market = Market(
        market_id="m1", source="manual_export", outcome="Yes",
        resolution_time=_T0 - timedelta(days=1),
    )
    assert validate_market_resolution_consistency(market, claimed_snapshot_time=_T0) is None


def test_unresolved_market_without_outcome_is_never_flagged() -> None:
    market = Market(market_id="m1", source="manual_export")
    assert validate_market_resolution_consistency(market, claimed_snapshot_time=_T0) is None


# --- prix ----------------------------------------------------------------------


def test_parse_price_point_accepts_short_key_names() -> None:
    point = parse_price_point({"t": 1735689600, "p": 0.55}, market_id="m1", source="manual_export")
    assert point.market_id == "m1"
    assert point.price == 0.55


def test_parse_price_point_missing_field_raises() -> None:
    with pytest.raises(ValueError):
        parse_price_point({"t": 1735689600}, market_id="m1", source="manual_export")


def test_validate_price_history_export_rejects_duplicate_timestamps() -> None:
    raw = [{"t": 1735689600, "p": 0.5}, {"t": 1735689600, "p": 0.51}]
    report = validate_price_history_export(raw, market_id="m1", source="manual_export")
    assert report.n_accepted == 1
    assert report.rejected[0].reason_code == IMPORT_REJECT_DUPLICATE


def test_validate_price_history_export_rejects_naive_timestamp_string() -> None:
    raw = [{"timestamp": "2025-01-01T00:00:00", "price": 0.5}]  # sans fuseau
    report = validate_price_history_export(raw, market_id="m1", source="manual_export")
    assert report.n_accepted == 0
    assert report.rejected[0].reason_code == IMPORT_REJECT_INVALID_TIMESTAMP


# --- matching UNRESOLVED (etape 5) --------------------------------------------


def test_unmatched_result_is_unresolved() -> None:
    result = MarketMatchResult(polymarket_market_id="pm1", match_id=None, reason_code=POLYMARKET_MATCH_UNMATCHED)
    assert is_unresolved_match(result)


def test_ambiguous_result_is_unresolved() -> None:
    result = MarketMatchResult(polymarket_market_id="pm1", match_id=None, reason_code=POLYMARKET_MATCH_AMBIGUOUS)
    assert is_unresolved_match(result)


def test_matched_result_is_not_unresolved() -> None:
    result = MarketMatchResult(polymarket_market_id="pm1", match_id="fd_1", reason_code=None)
    assert not is_unresolved_match(result)


# --- couverture (etape 6) - outillage uniquement, sur donnees synthetiques ----


def test_compute_coverage_report_on_empty_input() -> None:
    report = compute_coverage_report([], [])
    assert report.n_markets == 0
    assert report.match_rate == 0.0
    assert report.earliest_start_time is None


def test_compute_coverage_report_counts_matched_unmatched_ambiguous() -> None:
    markets = [
        Market(market_id="pm1", source="s", league="synthetic_league", start_time=_T0),
        Market(market_id="pm2", source="s", league="synthetic_league", start_time=_T0 + timedelta(days=1)),
        Market(market_id="pm3", source="s", league="other_league", start_time=_T0 + timedelta(days=2)),
    ]
    results = [
        MarketMatchResult(polymarket_market_id="pm1", match_id="fd_1", reason_code=None),
        MarketMatchResult(polymarket_market_id="pm2", match_id=None, reason_code=POLYMARKET_MATCH_UNMATCHED),
        MarketMatchResult(polymarket_market_id="pm3", match_id=None, reason_code=POLYMARKET_MATCH_AMBIGUOUS),
    ]
    report = compute_coverage_report(markets, results)
    assert report.n_markets == 3
    assert report.n_matched == 1
    assert report.n_unmatched == 1
    assert report.n_ambiguous == 1
    assert report.match_rate == 1 / 3
    assert report.competitions == ("other_league", "synthetic_league")
    assert report.earliest_start_time == _T0
    assert report.latest_start_time == _T0 + timedelta(days=2)
