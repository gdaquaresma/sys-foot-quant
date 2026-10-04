"""Garde-fous anti-fuite - consensus multi-bookmaker Max/Avg Over/Under 2.5
(Stage32, docs/multi_bookmaker_consensus_experiment_specification.md).

Couvre :
1. seules les cotes D'OUVERTURE sont utilisees (jamais MaxC/AvgC) ;
2. les cotes ne dependent jamais du resultat reel du match ;
3. un match non apparie n'est jamais invente ;
4. `_ALLOWED_COLUMNS` ne contient aucune colonne de cloture Max/Avg."""

from __future__ import annotations

from datetime import datetime

from sys_foot_quant.data_engine.market_odds.football_data_loader import (
    _ALLOWED_COLUMNS,
    FootballDataMatchRecord,
)
from sys_foot_quant.data_engine.market_odds.multi_bookmaker_over_under import (
    build_multi_bookmaker_over_under_dataset,
)

_LEAGUE = "liga"
_SEASON = "2024_25"
_T0 = datetime(2024, 8, 3, 20, 0, 0)


def _us(match_id, dt, home="Barcelona", away="Sevilla"):
    return {
        "id": match_id, "isResult": True, "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": 1, "title": home}, "a": {"id": 2, "title": away},
    }


def _fd(date_dt, home="Barcelona", away="Sevilla", hg=2, ag=1):
    return FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=hg, away_goals=ag,
        b365_home=1.8, b365_draw=3.6, b365_away=4.5,
        b365_over_2_5=1.85, b365_under_2_5=1.95,
        max_over_2_5=1.92, max_under_2_5=1.98,
        avg_over_2_5=1.87, avg_under_2_5=1.90,
    )


# --- 1. Seules les colonnes d'ouverture existent dans _ALLOWED_COLUMNS -----


def test_allowed_columns_never_contain_a_closing_max_avg_column() -> None:
    assert not any(c.startswith(("MaxC", "AvgC")) for c in _ALLOWED_COLUMNS)


# --- 2. Les cotes ne dependent jamais du resultat reel ----------------------


def test_odds_are_independent_of_match_result() -> None:
    report_a = build_multi_bookmaker_over_under_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0, hg=5, ag=0)])
    report_b = build_multi_bookmaker_over_under_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0, hg=0, ag=3)])
    rec_a, rec_b = report_a.records[0], report_b.records[0]
    assert rec_a.max_over_2_5 == rec_b.max_over_2_5
    assert rec_a.avg_over_2_5 == rec_b.avg_over_2_5
    assert rec_a.b365_over_2_5 == rec_b.b365_over_2_5


# --- 3. Un match non apparie n'est jamais invente ---------------------------


def test_unmatched_match_never_fabricates_an_entry() -> None:
    report = build_multi_bookmaker_over_under_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0, "Barcelona", "Sevilla")], [_fd(_T0, "Real Madrid", "Valencia")]
    )
    assert len(report.records) == 0


# --- 4. Un futur match n'affecte jamais les cotes d'un match deja apparie ---


def test_adding_a_future_match_does_not_change_an_existing_record() -> None:
    from datetime import timedelta

    report_before = build_multi_bookmaker_over_under_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)])

    future_us = _us("2", _T0 + timedelta(days=7), "Real Madrid", "Valencia")
    future_fd = _fd(_T0 + timedelta(days=7), "Real Madrid", "Valencia")
    report_after = build_multi_bookmaker_over_under_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0), future_us], [_fd(_T0), future_fd]
    )

    rec_before = report_before.records[0]
    rec_after = next(r for r in report_after.records if r.match_id == "1")
    assert rec_before == rec_after
