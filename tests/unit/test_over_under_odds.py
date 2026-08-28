"""Tests unitaires de construction pour ``over_under_odds.py`` (E5) -
meme style de fixtures que ``test_economic_dataset.py``."""

from __future__ import annotations

from datetime import datetime

import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.over_under_odds import build_over_under_25_dataset

_LEAGUE = "premier_league"
_SEASON = "2024_25"
_T0 = datetime(2024, 8, 3, 15, 0, 0)  # un samedi


def _us(match_id, dt, home, away, is_result=True):
    return {
        "id": match_id,
        "isResult": is_result,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
    }


def _fd(date_dt, home, away, over=1.85, under=1.95, league=_LEAGUE, season=_SEASON):
    return FootballDataMatchRecord(
        league=league, season=season, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=2, away_goals=1,
        b365_home=1.8, b365_draw=3.6, b365_away=4.5,
        b365_over_2_5=over, b365_under_2_5=under,
    )


def test_basic_exploitable_match() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton")]
    report = build_over_under_25_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.match_id == "1"
    assert rec.b365_over_2_5 == pytest.approx(1.85)
    assert rec.b365_under_2_5 == pytest.approx(1.95)
    assert rec.knowledge_time_utc <= rec.decision_time_utc
    assert rec.timestamp_status == "hypothetical_documented"


def test_ambiguous_weekday_excluded_and_counted() -> None:
    tuesday = datetime(2024, 8, 6, 20, 0, 0)
    raw = [_us("1", tuesday, "Arsenal", "Everton")]
    fd = [_fd(tuesday, "Arsenal", "Everton")]
    report = build_over_under_25_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 0
    assert report.n_excluded_ambiguous_weekday == 1


def test_incomplete_over_under_odds_excluded_and_counted() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [
        FootballDataMatchRecord(
            league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
            date_str=_T0.strftime("%d/%m/%Y"), time_str=_T0.strftime("%H:%M"),
            home_team_fd="Arsenal", away_team_fd="Everton", home_goals=2, away_goals=1,
            b365_home=1.8, b365_draw=3.6, b365_away=4.5,
            b365_over_2_5=None, b365_under_2_5=1.95,
        )
    ]
    report = build_over_under_25_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 0
    assert report.n_excluded_incomplete_odds == 1


def test_unmatched_understat_reported_not_dropped() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd: list[FootballDataMatchRecord] = []
    report = build_over_under_25_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 0
    assert report.n_unmatched_understat == 1
    assert report.n_matched == 0


def test_multiple_matches_same_report() -> None:
    saturday_2 = datetime(2024, 8, 10, 15, 0, 0)
    raw = [
        _us("1", _T0, "Arsenal", "Everton"),
        _us("2", saturday_2, "Chelsea", "Liverpool"),
    ]
    fd = [
        _fd(_T0, "Arsenal", "Everton", over=1.85, under=1.95),
        _fd(saturday_2, "Chelsea", "Liverpool", over=2.10, under=1.75),
    ]
    report = build_over_under_25_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 2
    odds_by_id = {r.match_id: (r.b365_over_2_5, r.b365_under_2_5) for r in report.records}
    assert odds_by_id["1"] == pytest.approx((1.85, 1.95))
    assert odds_by_id["2"] == pytest.approx((2.10, 1.75))
