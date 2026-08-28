"""Tests unitaires des fonctions PURES d'E9
(scripts/run_stage18_e9_multi_bookmaker_market_layer.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage18_e9_multi_bookmaker_market_layer.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage18_e9_multi_bookmaker_market_layer", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e9_module():
    return _load_script()


# --- bookmaker_odds_by_bookmaker --------------------------------------------


def test_bookmaker_odds_by_bookmaker_transposes(e9_module) -> None:
    odds = {
        "H": {"B365": 1.90, "BW": 1.95},
        "D": {"B365": 3.50, "BW": 3.40},
        "A": {"B365": 4.00, "BW": 4.10},
    }
    out = e9_module.bookmaker_odds_by_bookmaker(odds)
    assert out == {
        "B365": {"H": 1.90, "D": 3.50, "A": 4.00},
        "BW": {"H": 1.95, "D": 3.40, "A": 4.10},
    }


def test_bookmaker_odds_by_bookmaker_drops_partial_bookmaker(e9_module) -> None:
    odds = {
        "H": {"B365": 1.90, "BW": 1.95},
        "D": {"B365": 3.50},  # BW absent sur cette selection
        "A": {"B365": 4.00, "BW": 4.10},
    }
    out = e9_module.bookmaker_odds_by_bookmaker(odds)
    assert set(out) == {"B365"}  # BW jamais normalise sur un marche partiel


# --- normalized_probs_by_selection ------------------------------------------


def test_normalized_probs_sum_to_one_per_bookmaker(e9_module) -> None:
    odds = {
        "H": {"B365": 1.90, "BW": 1.95},
        "D": {"B365": 3.50, "BW": 3.40},
        "A": {"B365": 4.00, "BW": 4.10},
    }
    out = e9_module.normalized_probs_by_selection(odds)
    total_b365 = sum(out[sel]["B365"] for sel in out)
    total_bw = sum(out[sel]["BW"] for sel in out)
    assert total_b365 == pytest.approx(1.0)
    assert total_bw == pytest.approx(1.0)


def test_normalized_probs_empty_selection_stays_empty(e9_module) -> None:
    odds = {"Over": {}, "Under": {}}
    out = e9_module.normalized_probs_by_selection(odds)
    assert out == {"Over": {}, "Under": {}}


# --- overrounds_by_bookmaker -------------------------------------------------


def test_overrounds_by_bookmaker_matches_manual(e9_module) -> None:
    odds = {"Over": {"B365": 1.90}, "Under": {"B365": 2.00}}
    out = e9_module.overrounds_by_bookmaker(odds)
    assert out["B365"] == pytest.approx(1 / 1.90 + 1 / 2.00 - 1.0)


# --- book_anomalies_for_market ----------------------------------------------


def test_book_anomalies_flags_isolated_bookmaker(e9_module) -> None:
    odds = {
        "Over": {"B365": 1.90, "BW": 1.90, "PS": 2.50},  # PS nettement different
        "Under": {"B365": 2.00, "BW": 2.00, "PS": 1.60},
    }
    out = e9_module.book_anomalies_for_market(odds)
    assert out["Over"]["PS"]["classification"] in ("ecart notable", "ecart marque")


def test_book_anomalies_skips_selection_with_no_bookmaker(e9_module) -> None:
    # BW n'a pas de cote Under -> son marche est partiel, jamais normalise ;
    # B365 a les deux cotes -> normalise et evalue normalement.
    odds = {"Over": {"B365": 1.90, "BW": 1.85}, "Under": {"B365": 2.00}}
    out = e9_module.book_anomalies_for_market(odds)
    assert "BW" not in out["Over"]  # marche BW incomplet -> jamais normalise
    assert "B365" in out["Over"]
    assert "B365" in out["Under"]


def test_book_anomalies_empty_when_no_bookmaker_covers_full_market(e9_module) -> None:
    odds = {"Over": {"B365": 1.90}, "Under": {}}  # aucun bookmaker n'a les deux cotes
    out = e9_module.book_anomalies_for_market(odds)
    assert out == {}


# --- arbitrage_for_market -----------------------------------------------------


def test_arbitrage_for_market_none_when_selection_uncovered(e9_module) -> None:
    odds = {"Over": {"B365": 1.90}, "Under": {}}
    assert e9_module.arbitrage_for_market(odds) is None


def test_arbitrage_for_market_delegates_to_detect_mathematical_arbitrage(e9_module) -> None:
    odds = {"Over": {"B365": 1.90}, "Under": {"B365": 2.00}}
    out = e9_module.arbitrage_for_market(odds)
    assert out is not None
    assert out["is_mathematical_arbitrage"] is False


# --- _coverage_report ---------------------------------------------------------


class _FakeRecord:
    def __init__(self, odds_1x2, odds_ou):
        self.odds_1x2 = odds_1x2
        self.odds_over_under_2_5 = odds_ou


def test_coverage_report_counts_bookmakers_correctly(e9_module) -> None:
    records = [
        _FakeRecord({"H": {"B365": 1.9, "BW": 1.95}, "D": {"B365": 3.5, "BW": 3.4}, "A": {"B365": 4.0, "BW": 4.1}}, {}),
        _FakeRecord({"H": {"B365": 1.8}, "D": {"B365": 3.6}, "A": {"B365": 4.5}}, {}),
    ]
    out = e9_module._coverage_report(records, "1x2")
    assert out["n_matches"] == 2
    assert out["n_matches_with_market"] == 2
    assert out["coverage_by_bookmaker"]["B365"] == 2
    assert out["coverage_by_bookmaker"]["BW"] == 1


# --- model_vs_market_report ---------------------------------------------------


def test_model_vs_market_report_only_uses_intersection(e9_module) -> None:
    records_by_id = {
        "1": _FakeRecord({}, {"Over": {"B365": 1.90, "BW": 1.85}, "Under": {"B365": 2.00, "BW": 2.05}}),
    }
    model_probs = {"1": 0.60, "2": 0.55}  # "2" absent du corpus multi-bookmaker
    out = e9_module.model_vs_market_report(records_by_id, model_probs)
    assert out["n"] == 1


def test_model_vs_market_report_never_uses_value_label(e9_module) -> None:
    records_by_id = {
        "1": _FakeRecord({}, {"Over": {"B365": 1.90}, "Under": {"B365": 2.00}}),
    }
    out = e9_module.model_vs_market_report(records_by_id, {"1": 0.60})
    assert "value" not in str(out).lower()
