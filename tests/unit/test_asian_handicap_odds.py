from __future__ import annotations

from datetime import datetime

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.asian_handicap_odds import build_asian_handicap_dataset

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


def _fd(date_dt, home="Arsenal", away="Everton", hg=1, ag=0, ah_line=-0.75, b365_ah=(1.95, 1.95), p_ah=(1.98, 1.92)):
    return FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=hg, away_goals=ag,
        b365_home=1.8, b365_draw=3.6, b365_away=4.5,
        ah_line=ah_line,
        b365_ah_home=b365_ah[0] if b365_ah else None,
        b365_ah_away=b365_ah[1] if b365_ah else None,
        p_ah_home=p_ah[0] if p_ah else None,
        p_ah_away=p_ah[1] if p_ah else None,
    )


def test_matched_record_carries_line_and_both_bookmakers() -> None:
    report = build_asian_handicap_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)])
    assert report.n_exploitable == 1
    r = report.records[0]
    assert r.ah_line == -0.75
    assert r.b365_ah_home == 1.95
    assert r.b365_ah_away == 1.95
    assert r.p_ah_home == 1.98
    assert r.p_ah_away == 1.92
    assert r.home_goals == 1
    assert r.away_goals == 0


def test_match_without_pinnacle_stays_exploitable_pinnacle_simply_absent() -> None:
    fd = _fd(_T0, p_ah=None)
    report = build_asian_handicap_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [fd])
    assert report.n_exploitable == 1
    r = report.records[0]
    assert r.b365_ah_home == 1.95
    assert r.p_ah_home is None
    assert r.p_ah_away is None
    assert report.n_with_pinnacle_ah == 0


def test_match_without_b365_ah_is_excluded_not_imputed() -> None:
    fd = FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=_T0.strftime("%d/%m/%Y"), time_str=_T0.strftime("%H:%M"),
        home_team_fd="Arsenal", away_team_fd="Everton", home_goals=1, away_goals=0,
        b365_home=1.8, b365_draw=3.6, b365_away=4.5,
        ah_line=None, b365_ah_home=None, b365_ah_away=None,  # AH incomplet
    )
    report = build_asian_handicap_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [fd])
    assert report.n_exploitable == 0
    assert report.n_excluded_incomplete_b365_ah == 1


def test_ah_line_can_be_zero_or_positive() -> None:
    for line in (0.0, 1.5):
        fd = _fd(_T0, ah_line=line)
        report = build_asian_handicap_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [fd])
        assert report.records[0].ah_line == line
