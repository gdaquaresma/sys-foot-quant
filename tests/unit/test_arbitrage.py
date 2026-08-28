from __future__ import annotations

import pytest

from sys_foot_quant.market_engine.arbitrage import detect_mathematical_arbitrage, find_best_prices


def test_find_best_prices_picks_highest_odds_per_selection() -> None:
    odds = {
        "H": {"B365": 1.90, "BW": 1.95, "PS": 1.88},
        "D": {"B365": 3.50, "BW": 3.40, "PS": 3.55},
        "A": {"B365": 4.00, "BW": 4.10, "PS": 3.90},
    }
    best = find_best_prices(odds)
    assert best["H"] == ("BW", 1.95)
    assert best["D"] == ("PS", 3.55)
    assert best["A"] == ("BW", 4.10)


def test_find_best_prices_empty_selection_raises() -> None:
    with pytest.raises(ValueError):
        find_best_prices({"H": {}})


def test_find_best_prices_no_selections_raises() -> None:
    with pytest.raises(ValueError):
        find_best_prices({})


def test_detect_mathematical_arbitrage_no_arb_when_sum_above_one() -> None:
    odds = {"Over": {"B365": 1.90}, "Under": {"B365": 1.95}}
    out = detect_mathematical_arbitrage(odds)
    assert out["implied_prob_sum"] == pytest.approx(1.0 / 1.90 + 1.0 / 1.95)
    assert out["is_mathematical_arbitrage"] is False
    assert out["arbitrage_margin"] < 0


def test_detect_mathematical_arbitrage_detects_manufactured_arb() -> None:
    # cotes deliberement construites pour une somme < 1 (cas synthetique)
    odds = {"Over": {"B365": 2.20}, "Under": {"BW": 2.20}}
    out = detect_mathematical_arbitrage(odds)
    assert out["implied_prob_sum"] == pytest.approx(2.0 / 2.20)
    assert out["is_mathematical_arbitrage"] is True
    assert out["arbitrage_margin"] > 0


def test_detect_mathematical_arbitrage_three_way_1x2() -> None:
    odds = {
        "H": {"B365": 1.90},
        "D": {"B365": 3.50},
        "A": {"B365": 4.00},
    }
    out = detect_mathematical_arbitrage(odds)
    expected_sum = 1 / 1.90 + 1 / 3.50 + 1 / 4.00
    assert out["implied_prob_sum"] == pytest.approx(expected_sum)
    assert out["is_mathematical_arbitrage"] == (expected_sum < 1.0)


def test_detect_mathematical_arbitrage_reports_best_bookmaker_per_selection() -> None:
    odds = {"Over": {"B365": 1.85, "BW": 1.90}, "Under": {"B365": 2.05}}
    out = detect_mathematical_arbitrage(odds)
    assert out["best_prices"]["Over"] == ("BW", 1.90)
    assert out["best_prices"]["Under"] == ("B365", 2.05)
