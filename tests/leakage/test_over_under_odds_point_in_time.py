"""Garde-fous point-in-time pour over_under_odds.py (E5) - meme discipline
que test_football_data_point_in_time.py (1X2) : knowledge_time <=
decision_time toujours verifie, cotes independantes du resultat,
non-regression de l'appariement sur le corpus REEL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.data_engine.market_odds.football_data_loader import (
    FootballDataMatchRecord,
    load_football_data_csv,
)
from sys_foot_quant.data_engine.market_odds.over_under_odds import build_over_under_25_dataset

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FD_DIR = _REPO_ROOT / "research" / "market_odds" / "football_data" / "runs"
_US_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"

_DATASETS = {
    ("premier_league", "2024_25"): ("E0_2024_25.csv", "epl_2024_datesData.json"),
    ("premier_league", "2025_26"): ("E0_2025_26.csv", "epl_2025_datesData.json"),
    ("ligue1", "2024_25"): ("F1_2024_25.csv", "ligue1_2024_datesData.json"),
    ("ligue1", "2025_26"): ("F1_2025_26.csv", "ligue1_2025_datesData.json"),
    ("liga", "2024_25"): ("SP1_2024_25.csv", "liga_2024_datesData.json"),
    ("liga", "2025_26"): ("SP1_2025_26.csv", "liga_2025_datesData.json"),
}

_LEAGUE = "premier_league"
_SEASON = "2024_25"
_T0 = datetime(2024, 8, 3, 15, 0, 0)


def _us(match_id, dt, home, away):
    return {
        "id": match_id,
        "isResult": True,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
    }


def _fd(date_dt, home, away, hg, ag, over=1.85, under=1.95):
    return FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=hg, away_goals=ag,
        b365_home=1.8, b365_draw=3.6, b365_away=4.5,
        b365_over_2_5=over, b365_under_2_5=under,
    )


def test_over_under_odds_are_independent_of_match_result() -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton"), _us("2", _T0 + timedelta(days=1), "Chelsea", "Liverpool")]
    fd = [
        _fd(_T0, "Arsenal", "Everton", hg=5, ag=0, over=1.85, under=1.95),
        _fd(_T0 + timedelta(days=1), "Chelsea", "Liverpool", hg=0, ag=0, over=1.85, under=1.95),
    ]
    report = build_over_under_25_dataset(_LEAGUE, _SEASON, raw, fd)
    odds = {(r.b365_over_2_5, r.b365_under_2_5) for r in report.records}
    assert len(odds) == 1  # memes cotes malgre des scores tres differents


def test_knowledge_time_always_before_or_equal_decision_time_on_exploitable_matches() -> None:
    report = build_over_under_25_dataset(
        _LEAGUE, _SEASON, [_us("1", _T0, "Arsenal", "Everton")], [_fd(_T0, "Arsenal", "Everton", 2, 1)]
    )
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.knowledge_time_utc <= rec.decision_time_utc


@given(
    day_offset=st.integers(0, 6),  # jour de la semaine a partir d'un samedi de reference
    hour=st.integers(0, 23),
)
@settings(max_examples=100)
def test_property_knowledge_time_never_exceeds_decision_time_when_not_ambiguous(day_offset, hour) -> None:
    kickoff = datetime(2024, 8, 3, hour, 0, 0) + timedelta(days=day_offset)  # base = un samedi
    raw = [_us("1", kickoff, "Arsenal", "Everton")]
    fd = [_fd(kickoff, "Arsenal", "Everton", 2, 1)]
    report = build_over_under_25_dataset(_LEAGUE, _SEASON, raw, fd)
    # soit exclu (jour ambigu ou violation PIT), soit strictement respectueux du PIT
    if report.n_exploitable == 1:
        rec = report.records[0]
        assert rec.knowledge_time_utc <= rec.decision_time_utc
    else:
        assert report.n_excluded_ambiguous_weekday + report.n_excluded_pit_violation == 1


@pytest.mark.skipif(not _FD_DIR.exists(), reason="Fichiers Football-Data reels non presents.")
def test_real_corpus_over_under_25_coverage_is_stable() -> None:
    """Non-regression large (pas une egalite exacte, contrairement au 1X2
    deja verifie ailleurs) : la couverture Over/Under 2.5 doit rester tres
    proche de la couverture 1X2 deja etablie (2123/2132), puisque les
    cotes O/U sont completes a 100% sur les six fichiers reels (verifie
    manuellement avant l'extension) - seules les exclusions deja connues
    (jour ambigu, residu d'appariement) s'appliquent."""
    total_matched = 0
    total_understat = 0
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        report = build_over_under_25_dataset(league, season, us_raw, fd_records)
        assert report.n_excluded_incomplete_odds == 0  # cotes O/U completes a 100%, verifie prealablement
        assert report.n_excluded_pit_violation == 0
        total_matched += report.n_matched
        total_understat += report.n_understat

    assert total_understat == 2132
    assert total_matched == 2123  # identique au 1X2 (meme appariement sous-jacent)
