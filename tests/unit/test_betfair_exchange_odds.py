from __future__ import annotations

from datetime import datetime, timedelta

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.betfair_exchange_odds import build_betfair_exchange_dataset

_LEAGUE = "premier_league"
_SEASON = "2024_25"
_T0 = datetime(2024, 8, 3, 15, 0, 0)  # samedi - jamais un jour ambigu


def _us(match_id, dt, home="Arsenal", away="Everton"):
    return {
        "id": match_id,
        "isResult": True,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
    }


def _fd(
    date_dt,
    home="Arsenal",
    away="Everton",
    hg=1,
    ag=0,
    b365=(1.8, 3.6, 4.5),
    bfe=(1.85, 3.7, 4.4),
    b365_ou=(1.85, 1.95),
    bfe_ou=(1.90, 1.90),
):
    return FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=hg, away_goals=ag,
        b365_home=b365[0], b365_draw=b365[1], b365_away=b365[2],
        bfe_home=bfe[0] if bfe else None, bfe_draw=bfe[1] if bfe else None, bfe_away=bfe[2] if bfe else None,
        b365_over_2_5=b365_ou[0], b365_under_2_5=b365_ou[1],
        bfe_over_2_5=bfe_ou[0] if bfe_ou else None, bfe_under_2_5=bfe_ou[1] if bfe_ou else None,
    )


def test_matched_record_carries_both_b365_and_bfe() -> None:
    report = build_betfair_exchange_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)])
    assert report.n_exploitable == 1
    r = report.records[0]
    assert r.b365_1x2 == {"H": 1.8, "D": 3.6, "A": 4.5}
    assert r.bfe_1x2 == {"H": 1.85, "D": 3.7, "A": 4.4}
    assert r.b365_over_under_2_5 == {"Over": 1.85, "Under": 1.95}
    assert r.bfe_over_under_2_5 == {"Over": 1.90, "Under": 1.90}


def test_match_without_bfe_stays_exploitable_bfe_simply_absent() -> None:
    """BFE absent sur ~5-8% des matchs 2025/26 - le match reste
    exploitable pour B365, jamais exclu ni impute."""
    fd = _fd(_T0, bfe=None, bfe_ou=None)
    report = build_betfair_exchange_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [fd])
    assert report.n_exploitable == 1
    r = report.records[0]
    assert r.b365_1x2 == {"H": 1.8, "D": 3.6, "A": 4.5}
    assert r.bfe_1x2 is None
    assert r.bfe_over_under_2_5 is None
    assert report.n_with_bfe_1x2 == 0
    assert report.n_with_bfe_over_under_2_5 == 0


def test_match_without_b365_1x2_is_excluded_not_imputed() -> None:
    fd = FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=_T0.strftime("%d/%m/%Y"), time_str=_T0.strftime("%H:%M"),
        home_team_fd="Arsenal", away_team_fd="Everton", home_goals=1, away_goals=0,
        b365_home=None, b365_draw=None, b365_away=None,  # B365 1X2 incomplet
    )
    report = build_betfair_exchange_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [fd])
    assert report.n_exploitable == 0
    assert report.n_excluded_incomplete_b365_1x2 == 1


def test_bfe_counts_are_reported_separately_per_market() -> None:
    """BFE peut etre disponible sur un marche mais pas l'autre - compte
    separement, jamais fusionne."""
    fd = _fd(_T0, bfe=(1.85, 3.7, 4.4), bfe_ou=None)
    report = build_betfair_exchange_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [fd])
    assert report.n_with_bfe_1x2 == 1
    assert report.n_with_bfe_over_under_2_5 == 0
    assert report.records[0].bfe_1x2 is not None
    assert report.records[0].bfe_over_under_2_5 is None


def test_total_goals_matches_football_data_score() -> None:
    fd = _fd(_T0, hg=3, ag=2)
    report = build_betfair_exchange_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [fd])
    r = report.records[0]
    assert r.home_goals == 3
    assert r.away_goals == 2
    assert r.total_goals == 5
