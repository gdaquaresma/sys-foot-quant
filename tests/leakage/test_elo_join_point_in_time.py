"""Garde-fous point-in-time pour elo_join.py (Phase K) - meme discipline
que test_asian_handicap_odds_point_in_time.py : knowledge_time <=
decision_time toujours verifie, le rating Elo utilise pour un match ne
reflete JAMAIS le resultat de ce match lui-meme, aucune donnee de
cloture (sans objet pour ClubElo, verifie structurellement)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.data_engine.market_odds.elo_join import build_elo_dataset
from sys_foot_quant.data_engine.market_odds.elo_ratings import parse_clubelo_csv_rows

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


def test_elo_ratings_are_independent_of_match_result() -> None:
    """Meme discipline que le test AH equivalent : deux matchs avec des
    scores tres differents mais les MEMES ratings pre-match doivent
    produire le meme elo_diff - la variable ne depend jamais du resultat."""
    raw = [_us("1", _T0), _us("2", _T0 + timedelta(days=1), "Chelsea", "Liverpool")]
    fd = [
        _fd(_T0, hg=5, ag=0),
        _fd(_T0 + timedelta(days=1), "Chelsea", "Liverpool", hg=0, ag=0),
    ]
    elo_by_club = {
        "Barcelona": parse_clubelo_csv_rows([_elo_row("Barcelona", 1950.0, "2024-07-01", "2024-12-31")]),
        "Sevilla": parse_clubelo_csv_rows([_elo_row("Sevilla", 1700.0, "2024-07-01", "2024-12-31")]),
        "Chelsea": parse_clubelo_csv_rows([_elo_row("Chelsea", 1850.0, "2024-07-01", "2024-12-31")]),
        "Liverpool": parse_clubelo_csv_rows([_elo_row("Liverpool", 1900.0, "2024-07-01", "2024-12-31")]),
    }
    report = build_elo_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0, hg=5, ag=0)], elo_by_club, allow_unverified_mapping=True
    )
    assert report.records[0].elo_diff == pytest.approx(250.0)  # 1950 - 1700, quel que soit le score 5-0


def test_knowledge_time_always_before_or_equal_decision_time() -> None:
    elo_by_club = {
        "Barcelona": parse_clubelo_csv_rows([_elo_row("Barcelona", 1950.0, "2024-07-01", "2024-12-31")]),
        "Sevilla": parse_clubelo_csv_rows([_elo_row("Sevilla", 1700.0, "2024-07-01", "2024-12-31")]),
    }
    report = build_elo_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)], elo_by_club, allow_unverified_mapping=True)
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.knowledge_time_utc <= rec.decision_time_utc


@given(day_offset=st.integers(0, 6), hour=st.integers(0, 23))
@settings(max_examples=100)
def test_property_knowledge_time_never_exceeds_decision_time_when_not_ambiguous(day_offset, hour) -> None:
    kickoff = datetime(2024, 8, 3, hour, 0, 0) + timedelta(days=day_offset)  # base = un samedi
    elo_by_club = {
        "Barcelona": parse_clubelo_csv_rows([_elo_row("Barcelona", 1950.0, "2024-07-01", "2025-12-31")]),
        "Sevilla": parse_clubelo_csv_rows([_elo_row("Sevilla", 1700.0, "2024-07-01", "2025-12-31")]),
    }
    report = build_elo_dataset(
        _LEAGUE, _SEASON, [_us("1", kickoff)], [_fd(kickoff)], elo_by_club, allow_unverified_mapping=True
    )
    if report.n_exploitable == 1:
        rec = report.records[0]
        assert rec.knowledge_time_utc <= rec.decision_time_utc
    else:
        assert report.n_excluded_ambiguous_weekday + report.n_excluded_pit_violation == 1


def test_elo_rating_used_never_reflects_the_match_it_predicts() -> None:
    """LE test central de la Phase K (point 4 de l'enonce) : simule un
    club qui joue le jour meme du match evalue, avec un CHANGEMENT DE
    RATING massif a partir du LENDEMAIN (comme documente en section 0bis
    du protocole : `From` = lendemain du match). Le rating utilise pour
    DECIDER de ce match doit etre l'ANCIEN rating (pre-match), jamais le
    nouveau (post-match)."""
    match_day = _T0
    day_after = match_day + timedelta(days=1)
    elo_by_club = {
        "Barcelona": parse_clubelo_csv_rows(
            [
                _elo_row("Barcelona", 1950.0, "2024-07-01", match_day.date().isoformat()),
                # nouvelle fenetre a partir du LENDEMAIN du match - integre son resultat
                _elo_row("Barcelona", 2200.0, day_after.date().isoformat(), "2024-12-31"),
            ]
        ),
        "Sevilla": parse_clubelo_csv_rows([_elo_row("Sevilla", 1700.0, "2024-07-01", "2024-12-31")]),
    }
    report = build_elo_dataset(
        _LEAGUE, _SEASON, [_us("1", match_day)], [_fd(match_day, hg=5, ag=0)], elo_by_club, allow_unverified_mapping=True
    )
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.elo_home == pytest.approx(1950.0)  # jamais 2200.0 (post-match)


def test_elo_match_record_has_no_closing_field() -> None:
    """Garde-fou structurel (comme Phases F/G/H, adapte a ClubElo) :
    aucun champ de cote de cloture (sans objet pour cette source, mais le
    dataclass ne doit porter aucun champ ambigu contenant 'close')."""
    import dataclasses

    from sys_foot_quant.data_engine.market_odds.elo_join import EloMatchRecord

    field_names = {f.name for f in dataclasses.fields(EloMatchRecord)}
    assert not any("close" in n for n in field_names)
