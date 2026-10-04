from __future__ import annotations

import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.matching import (
    build_understat_keys,
    match_league_season,
    opening_over_under_2_5_by_match_id,
)


def _fd(
    date_str, home, away, league="premier_league", season="2024_25", b365=(1.5, 4.0, 6.0),
    b365_ou=(None, None), p_ou=(None, None), b365_close_ou=(None, None),
):
    return FootballDataMatchRecord(
        league=league, season=season, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_str, time_str="15:00", home_team_fd=home, away_team_fd=away,
        home_goals=1, away_goals=0, b365_home=b365[0], b365_draw=b365[1], b365_away=b365[2],
        b365_over_2_5=b365_ou[0], b365_under_2_5=b365_ou[1],
        p_over_2_5=p_ou[0], p_under_2_5=p_ou[1],
        b365_close_over_2_5=b365_close_ou[0], b365_close_under_2_5=b365_close_ou[1],
    )


def _us_raw(match_id, date_str, home, away, is_result=True):
    return {
        "id": match_id,
        "isResult": is_result,
        "datetime": f"{date_str} 15:00:00",
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
    }


def test_simple_one_to_one_match() -> None:
    understat = build_understat_keys(
        [_us_raw("1", "2024-08-16", "Manchester United", "Fulham")], "premier_league", "2024_25"
    )
    fd = [_fd("16/08/2024", "Man United", "Fulham")]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    assert report.n_matched == 1
    assert report.n_unmatched_understat == 0
    assert report.n_unmatched_football_data == 0
    assert report.matched[0].understat.match_id == "1"


def test_unmatched_on_both_sides_reported_separately() -> None:
    understat = build_understat_keys(
        [_us_raw("1", "2024-08-16", "Arsenal", "Chelsea")], "premier_league", "2024_25"
    )
    fd = [_fd("16/08/2024", "Man United", "Fulham")]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    assert report.n_matched == 0
    assert report.n_unmatched_understat == 1
    assert report.n_unmatched_football_data == 1


def test_understat_future_fixture_excluded_via_is_result() -> None:
    understat = build_understat_keys(
        [_us_raw("1", "2024-08-16", "Arsenal", "Chelsea", is_result=False)], "premier_league", "2024_25"
    )
    assert understat == []


def test_duplicate_understat_key_is_not_silently_matched() -> None:
    understat = build_understat_keys(
        [
            _us_raw("1", "2024-08-16", "Arsenal", "Chelsea"),
            _us_raw("2", "2024-08-16", "Arsenal", "Chelsea"),  # doublon artificiel de cle
        ],
        "premier_league",
        "2024_25",
    )
    fd = [_fd("16/08/2024", "Arsenal", "Chelsea")]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    assert report.n_duplicate_keys_understat == 1
    assert report.n_matched == 0  # jamais apparie automatiquement en cas d'ambiguite


def test_duplicate_football_data_key_is_not_silently_matched() -> None:
    understat = build_understat_keys(
        [_us_raw("1", "2024-08-16", "Arsenal", "Chelsea")], "premier_league", "2024_25"
    )
    fd = [_fd("16/08/2024", "Arsenal", "Chelsea"), _fd("16/08/2024", "Arsenal", "Chelsea")]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    assert report.n_duplicate_keys_football_data == 1
    assert report.n_matched == 0


def test_league_and_season_filter_is_respected() -> None:
    understat = build_understat_keys(
        [_us_raw("1", "2024-08-16", "Arsenal", "Chelsea")], "premier_league", "2024_25"
    )
    fd = [_fd("16/08/2024", "Arsenal", "Chelsea", league="premier_league", season="2025_26")]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    assert report.n_football_data == 0
    assert report.n_matched == 0


# --- pont vers run_prediction(market_odds=...) ----------------------------


def test_opening_over_under_2_5_by_match_id_found() -> None:
    understat = build_understat_keys(
        [_us_raw("31940", "2024-08-16", "Manchester United", "Fulham")], "premier_league", "2024_25"
    )
    fd = [_fd("16/08/2024", "Man United", "Fulham", b365_ou=(1.85, 1.95))]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    result = opening_over_under_2_5_by_match_id(report, "31940")
    assert result == {"Over": pytest.approx(1.85), "Under": pytest.approx(1.95)}


def test_opening_over_under_2_5_by_match_id_unmatched_is_none() -> None:
    understat = build_understat_keys(
        [_us_raw("31940", "2024-08-16", "Manchester United", "Fulham")], "premier_league", "2024_25"
    )
    report = match_league_season(understat, [], "premier_league", "2024_25")
    assert opening_over_under_2_5_by_match_id(report, "31940") is None


def test_opening_over_under_2_5_by_match_id_unknown_id_is_none() -> None:
    understat = build_understat_keys(
        [_us_raw("31940", "2024-08-16", "Manchester United", "Fulham")], "premier_league", "2024_25"
    )
    fd = [_fd("16/08/2024", "Man United", "Fulham", b365_ou=(1.85, 1.95))]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    assert opening_over_under_2_5_by_match_id(report, "no-such-id") is None


def test_opening_over_under_2_5_by_match_id_bookmaker_without_complete_odds_is_none() -> None:
    # B365 absent sur ce match (None/None) - seul Pinnacle est complet.
    understat = build_understat_keys(
        [_us_raw("31940", "2024-08-16", "Manchester United", "Fulham")], "premier_league", "2024_25"
    )
    fd = [_fd("16/08/2024", "Man United", "Fulham", p_ou=(1.80, 1.90))]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    assert opening_over_under_2_5_by_match_id(report, "31940", bookmaker="B365") is None
    assert opening_over_under_2_5_by_match_id(report, "31940", bookmaker="P") == {
        "Over": pytest.approx(1.80), "Under": pytest.approx(1.90)
    }


def test_opening_over_under_2_5_by_match_id_never_returns_closing_odds() -> None:
    """Meme si le match porte des cotes de cloture volontairement
    incoherentes, seule l'ouverture doit etre retournee - ce test
    echouerait si la cloture etait lue par erreur."""
    understat = build_understat_keys(
        [_us_raw("31940", "2024-08-16", "Manchester United", "Fulham")], "premier_league", "2024_25"
    )
    fd = [_fd("16/08/2024", "Man United", "Fulham", b365_ou=(1.85, 1.95), b365_close_ou=(99.0, 99.0))]
    report = match_league_season(understat, fd, "premier_league", "2024_25")
    assert opening_over_under_2_5_by_match_id(report, "31940") == {
        "Over": pytest.approx(1.85), "Under": pytest.approx(1.95)
    }
