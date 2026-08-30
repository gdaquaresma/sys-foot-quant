"""Tests unitaires de elo_join.py (Phase K) - construction du dataset
Elo apparie, point-in-time, avec comptage explicite de chaque exclusion.
Utilise `allow_unverified_mapping=True` (donnees SYNTHETIQUES uniquement -
jamais en dehors des tests, docs/elo_experiment_specification.md section 4)."""

from __future__ import annotations

from datetime import datetime

import pytest

from sys_foot_quant.data_engine.market_odds.elo_join import build_elo_dataset
from sys_foot_quant.data_engine.market_odds.elo_ratings import parse_clubelo_csv_rows
from sys_foot_quant.data_engine.market_odds.elo_team_mapping import EloMappingUnverifiedError
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord

_LEAGUE = "liga"
_SEASON = "2024_25"
_T0 = datetime(2024, 8, 3, 20, 0, 0)  # samedi


def _us(match_id, dt, home="Barcelona", away="Sevilla"):
    return {
        "id": match_id,
        "isResult": True,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
    }


def _fd(date_dt, home="Barcelona", away="Sevilla", hg=2, ag=1):
    return FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=hg, away_goals=ag,
        b365_home=1.8, b365_draw=3.6, b365_away=4.5,
    )


def _elo_row(club, elo, frm, to):
    return {"Rank": "1", "Club": club, "Country": "ESP", "Level": "1", "Elo": str(elo), "From": frm, "To": to}


def _elo_by_club():
    return {
        "Barcelona": parse_clubelo_csv_rows([_elo_row("Barcelona", 1950.0, "2024-07-01", "2024-12-31")]),
        "Sevilla": parse_clubelo_csv_rows([_elo_row("Sevilla", 1700.0, "2024-07-01", "2024-12-31")]),
    }


def test_matched_record_computes_elo_diff_correctly() -> None:
    report = build_elo_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)], _elo_by_club(), allow_unverified_mapping=True
    )
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.elo_home == pytest.approx(1950.0)
    assert rec.elo_away == pytest.approx(1700.0)
    assert rec.elo_diff == pytest.approx(250.0)


def test_default_call_without_allow_unverified_is_blocked() -> None:
    """Garde-fou de production : sans `allow_unverified_mapping=True`
    explicite, toute jointure reelle echoue - jamais silencieusement."""
    with pytest.raises(EloMappingUnverifiedError):
        build_elo_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)], _elo_by_club())


def test_match_excluded_when_team_not_mapped(monkeypatch) -> None:
    """``Alaves`` est un club Liga valide cote Understat/team_mapping.py
    (l'appariement Understat<->Football-Data reussit) mais retire ICI du
    mapping ClubElo pour simuler une equipe non couverte par cette
    seconde table - exclusion attendue au niveau elo_join, pas au
    niveau matching.py."""
    import sys_foot_quant.data_engine.market_odds.elo_team_mapping as etm

    patched = {**etm.FOOTBALL_DATA_TO_CLUBELO["liga"]}
    del patched["Alaves"]
    monkeypatch.setitem(etm.FOOTBALL_DATA_TO_CLUBELO, "liga", patched)

    raw = [_us("1", _T0, "Barcelona", "Alaves")]
    fd = [_fd(_T0, "Barcelona", "Alaves")]
    elo_by_club = {**_elo_by_club(), "Alaves": parse_clubelo_csv_rows([_elo_row("Alaves", 1500.0, "2024-07-01", "2024-12-31")])}
    report = build_elo_dataset(_LEAGUE, _SEASON, raw, fd, elo_by_club, allow_unverified_mapping=True)
    assert report.n_exploitable == 0
    assert report.n_excluded_team_not_mapped == 1
    assert "Alaves" in report.unmapped_teams


def test_match_excluded_when_no_elo_rating_available_at_pit_date() -> None:
    elo_by_club = {
        "Barcelona": parse_clubelo_csv_rows([_elo_row("Barcelona", 1950.0, "2030-01-01", "2030-01-31")]),
        "Sevilla": parse_clubelo_csv_rows([_elo_row("Sevilla", 1700.0, "2024-07-01", "2024-12-31")]),
    }
    report = build_elo_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)], elo_by_club, allow_unverified_mapping=True
    )
    assert report.n_exploitable == 0
    assert report.n_excluded_no_elo_rating == 1


def test_match_excluded_when_club_absent_from_elo_ratings_dict() -> None:
    elo_by_club = {"Barcelona": parse_clubelo_csv_rows([_elo_row("Barcelona", 1950.0, "2024-07-01", "2024-12-31")])}
    report = build_elo_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)], elo_by_club, allow_unverified_mapping=True
    )
    assert report.n_exploitable == 0
    assert report.n_excluded_no_elo_rating == 1


def test_ambiguous_elo_window_is_excluded_and_counted() -> None:
    elo_by_club = {
        "Barcelona": parse_clubelo_csv_rows(
            [
                _elo_row("Barcelona", 1900.0, "2024-07-01", "2024-08-31"),
                _elo_row("Barcelona", 1990.0, "2024-08-01", "2024-09-30"),  # chevauche
            ]
        ),
        "Sevilla": parse_clubelo_csv_rows([_elo_row("Sevilla", 1700.0, "2024-07-01", "2024-12-31")]),
    }
    report = build_elo_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)], elo_by_club, allow_unverified_mapping=True
    )
    assert report.n_exploitable == 0
    assert report.n_excluded_ambiguous_elo_window == 1


def test_decision_time_is_kickoff_minus_offset() -> None:
    from sys_foot_quant.data_engine.market_odds.economic_dataset import DECISION_OFFSET_HOURS

    report = build_elo_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)], _elo_by_club(), allow_unverified_mapping=True
    )
    rec = report.records[0]
    assert (rec.kickoff_utc - rec.decision_time_utc).total_seconds() == pytest.approx(DECISION_OFFSET_HOURS * 3600)
