from __future__ import annotations

import pytest

from sys_foot_quant.data_engine.market_odds.current_season_contract import (
    CurrentSeasonContractError,
    validate_current_season_understat_raw,
)


def _valid_match(match_id: str = "1") -> dict:
    return {
        "id": match_id,
        "isResult": True,
        "datetime": "2026-08-15 19:45:00",
        "h": {"id": "279", "title": "Brest"},
        "a": {"id": "296", "title": "Marseille"},
        "goals": {"h": "1", "a": "2"},
        "xG": {"h": "1.32", "a": "1.87"},
    }


def test_valid_file_passes_without_raising() -> None:
    validate_current_season_understat_raw([_valid_match("1"), _valid_match("2")])


def test_rejects_non_list_input() -> None:
    with pytest.raises(CurrentSeasonContractError):
        validate_current_season_understat_raw({"not": "a list"})  # type: ignore[arg-type]


def test_rejects_empty_file() -> None:
    with pytest.raises(CurrentSeasonContractError):
        validate_current_season_understat_raw([])


def test_rejects_missing_top_level_key() -> None:
    match = _valid_match()
    del match["datetime"]
    with pytest.raises(CurrentSeasonContractError):
        validate_current_season_understat_raw([match])


def test_rejects_unplayed_match() -> None:
    match = _valid_match()
    match["isResult"] = False
    with pytest.raises(CurrentSeasonContractError, match="isResult"):
        validate_current_season_understat_raw([match])


def test_rejects_missing_goals() -> None:
    match = _valid_match()
    del match["goals"]
    with pytest.raises(CurrentSeasonContractError, match="goals"):
        validate_current_season_understat_raw([match])


def test_rejects_incomplete_goals() -> None:
    match = _valid_match()
    match["goals"] = {"h": "1"}
    with pytest.raises(CurrentSeasonContractError):
        validate_current_season_understat_raw([match])


def test_rejects_missing_xg() -> None:
    match = _valid_match()
    del match["xG"]
    with pytest.raises(CurrentSeasonContractError, match="xG"):
        validate_current_season_understat_raw([match])


def test_rejects_incomplete_xg() -> None:
    match = _valid_match()
    match["xG"] = {"h": "1.1"}
    with pytest.raises(CurrentSeasonContractError):
        validate_current_season_understat_raw([match])


def test_rejects_missing_team_fields() -> None:
    match = _valid_match()
    del match["h"]["title"]
    with pytest.raises(CurrentSeasonContractError):
        validate_current_season_understat_raw([match])


def test_rejects_duplicate_match_id_within_file() -> None:
    with pytest.raises(CurrentSeasonContractError, match="duplique"):
        validate_current_season_understat_raw([_valid_match("1"), _valid_match("1")])


def test_error_message_identifies_the_offending_match() -> None:
    match_ok = _valid_match("1")
    match_bad = _valid_match("2")
    match_bad["isResult"] = False
    with pytest.raises(CurrentSeasonContractError, match=r"id='2'"):
        validate_current_season_understat_raw([match_ok, match_bad])


def test_rejects_negative_goals() -> None:
    match = _valid_match()
    match["goals"] = {"h": "-1", "a": "2"}
    with pytest.raises(CurrentSeasonContractError, match="goals.h"):
        validate_current_season_understat_raw([match])


def test_rejects_non_numeric_goals() -> None:
    match = _valid_match()
    match["goals"] = {"h": "not-a-number", "a": "2"}
    with pytest.raises(CurrentSeasonContractError, match="goals.h"):
        validate_current_season_understat_raw([match])


def test_rejects_negative_xg() -> None:
    match = _valid_match()
    match["xG"] = {"h": "-0.5", "a": "1.0"}
    with pytest.raises(CurrentSeasonContractError, match="xG.h"):
        validate_current_season_understat_raw([match])


def test_rejects_non_finite_xg() -> None:
    match = _valid_match()
    match["xG"] = {"h": "nan", "a": "1.0"}
    with pytest.raises(CurrentSeasonContractError, match="fini"):
        validate_current_season_understat_raw([match])


def test_accepts_zero_goals_and_zero_xg() -> None:
    match = _valid_match()
    match["goals"] = {"h": "0", "a": "0"}
    match["xG"] = {"h": "0", "a": "0"}
    validate_current_season_understat_raw([match])


def test_rejects_home_equals_away_team() -> None:
    match = _valid_match()
    match["a"] = {"id": match["h"]["id"], "title": "Autre nom"}
    with pytest.raises(CurrentSeasonContractError, match="identiques"):
        validate_current_season_understat_raw([match])
