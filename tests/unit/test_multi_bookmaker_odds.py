"""Tests unitaires de construction pour ``multi_bookmaker_odds.py`` (E9) -
meme style de fixtures que ``test_over_under_odds.py``."""

from __future__ import annotations

from datetime import datetime

import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.multi_bookmaker_odds import build_multi_bookmaker_dataset

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


def _fd(
    date_dt,
    home,
    away,
    b365=(1.8, 3.6, 4.5),
    bw=(1.85, 3.5, 4.4),
    ps=None,
    over=1.85,
    under=1.95,
    league=_LEAGUE,
    season=_SEASON,
):
    return FootballDataMatchRecord(
        league=league, season=season, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=2, away_goals=1,
        b365_home=b365[0], b365_draw=b365[1], b365_away=b365[2],
        b365_over_2_5=over, b365_under_2_5=under,
        bw_home=bw[0] if bw else None, bw_draw=bw[1] if bw else None, bw_away=bw[2] if bw else None,
        ps_home=ps[0] if ps else None, ps_draw=ps[1] if ps else None, ps_away=ps[2] if ps else None,
    )


def test_basic_exploitable_match_multi_bookmaker() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton", ps=(1.83, 3.55, 4.45))]
    report = build_multi_bookmaker_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.match_id == "1"
    assert rec.odds_1x2["H"] == {"B365": pytest.approx(1.8), "BW": pytest.approx(1.85), "PS": pytest.approx(1.83)}
    assert rec.odds_1x2["D"]["B365"] == pytest.approx(3.6)
    assert rec.odds_over_under_2_5["Over"] == {"B365": pytest.approx(1.85)}
    assert rec.odds_over_under_2_5["Under"] == {"B365": pytest.approx(1.95)}
    assert rec.bookmakers_1x2() == {"B365", "BW", "PS"}
    assert rec.bookmakers_over_under_2_5() == {"B365"}
    assert rec.knowledge_time_utc <= rec.decision_time_utc
    assert rec.timestamp_status == "hypothetical_documented"


def test_partial_bookmaker_coverage_never_invents_missing_book() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton", ps=None)]  # PS absent sur ce match
    report = build_multi_bookmaker_dataset(_LEAGUE, _SEASON, raw, fd)
    rec = report.records[0]
    assert "PS" not in rec.odds_1x2["H"]
    assert rec.bookmakers_1x2() == {"B365", "BW"}


def test_match_included_even_without_bw_or_ps() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton", bw=None, ps=None)]
    report = build_multi_bookmaker_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 1
    assert report.records[0].bookmakers_1x2() == {"B365"}


def test_incomplete_b365_1x2_excludes_match() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [
        FootballDataMatchRecord(
            league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
            date_str=_T0.strftime("%d/%m/%Y"), time_str=_T0.strftime("%H:%M"),
            home_team_fd="Arsenal", away_team_fd="Everton", home_goals=2, away_goals=1,
            b365_home=None, b365_draw=3.6, b365_away=4.5,
            b365_over_2_5=1.85, b365_under_2_5=1.95,
        )
    ]
    report = build_multi_bookmaker_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 0
    assert report.n_excluded_incomplete_b365 == 1


def test_incomplete_over_under_still_includes_match_via_b365_1x2() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton", over=None, under=None)]
    report = build_multi_bookmaker_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.odds_over_under_2_5 == {"Over": {}, "Under": {}}
    assert rec.bookmakers_over_under_2_5() == set()


def test_ambiguous_weekday_excluded_and_counted() -> None:
    tuesday = datetime(2024, 8, 6, 20, 0, 0)
    raw = [_us("1", tuesday, "Arsenal", "Everton")]
    fd = [_fd(tuesday, "Arsenal", "Everton")]
    report = build_multi_bookmaker_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 0
    assert report.n_excluded_ambiguous_weekday == 1


def test_multiple_matches_same_report() -> None:
    saturday_2 = datetime(2024, 8, 10, 15, 0, 0)
    raw = [
        _us("1", _T0, "Arsenal", "Everton"),
        _us("2", saturday_2, "Chelsea", "Liverpool"),
    ]
    fd = [
        _fd(_T0, "Arsenal", "Everton"),
        _fd(saturday_2, "Chelsea", "Liverpool", bw=None),
    ]
    report = build_multi_bookmaker_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 2
    by_id = {r.match_id: r for r in report.records}
    assert by_id["1"].bookmakers_1x2() == {"B365", "BW"}
    assert by_id["2"].bookmakers_1x2() == {"B365"}
