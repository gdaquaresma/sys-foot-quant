"""Garde-fous point-in-time pour asian_handicap_odds.py (Phase H) - meme
discipline que test_betfair_exchange_odds_point_in_time.py :
knowledge_time <= decision_time toujours verifie, cotes independantes du
resultat, aucune cote de CLOTURE utilisee, non-regression de
l'appariement sur le corpus REEL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.data_engine.market_odds.asian_handicap_odds import build_asian_handicap_dataset
from sys_foot_quant.data_engine.market_odds.football_data_loader import (
    FootballDataMatchRecord,
    load_football_data_csv,
)

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
_T0 = datetime(2024, 8, 3, 15, 0, 0)  # samedi


def _us(match_id, dt, home="Arsenal", away="Everton"):
    return {
        "id": match_id,
        "isResult": True,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
    }


def _fd(date_dt, home="Arsenal", away="Everton", hg=1, ag=0, ah_line=-0.75, b365_ah_home=1.95):
    return FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=hg, away_goals=ag,
        b365_home=1.8, b365_draw=3.6, b365_away=4.5,
        ah_line=ah_line, b365_ah_home=b365_ah_home, b365_ah_away=1.95,
        p_ah_home=1.98, p_ah_away=1.92,
    )


def test_ah_odds_are_independent_of_match_result() -> None:
    raw = [_us("1", _T0), _us("2", _T0 + timedelta(days=1), "Chelsea", "Liverpool")]
    fd = [
        _fd(_T0, hg=5, ag=0),
        _fd(_T0 + timedelta(days=1), "Chelsea", "Liverpool", hg=0, ag=0),
    ]
    report = build_asian_handicap_dataset(_LEAGUE, _SEASON, raw, fd)
    lines = {r.ah_line for r in report.records}
    homes = {r.b365_ah_home for r in report.records}
    assert len(lines) == 1  # meme ligne malgre des scores tres differents
    assert len(homes) == 1


def test_knowledge_time_always_before_or_equal_decision_time_on_exploitable_matches() -> None:
    report = build_asian_handicap_dataset(_LEAGUE, _SEASON, [_us("1", _T0)], [_fd(_T0)])
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.knowledge_time_utc <= rec.decision_time_utc


@given(
    day_offset=st.integers(0, 6),
    hour=st.integers(0, 23),
)
@settings(max_examples=100)
def test_property_knowledge_time_never_exceeds_decision_time_when_not_ambiguous(day_offset, hour) -> None:
    kickoff = datetime(2024, 8, 3, hour, 0, 0) + timedelta(days=day_offset)  # base = un samedi
    raw = [_us("1", kickoff)]
    fd = [_fd(kickoff)]
    report = build_asian_handicap_dataset(_LEAGUE, _SEASON, raw, fd)
    if report.n_exploitable == 1:
        rec = report.records[0]
        assert rec.knowledge_time_utc <= rec.decision_time_utc
    else:
        assert report.n_excluded_ambiguous_weekday + report.n_excluded_pit_violation == 1


def test_asian_handicap_match_record_has_no_closing_odds_field() -> None:
    """Garde-fou structurel : aucune cote de CLOTURE (AHCh, B365CAHH/AHA,
    PCAHH/AHA) n'est jamais chargee par ce module - verifie par
    introspection des champs du dataclass."""
    import dataclasses

    from sys_foot_quant.data_engine.market_odds.asian_handicap_odds import AsianHandicapMatchRecord

    field_names = {f.name for f in dataclasses.fields(AsianHandicapMatchRecord)}
    assert not any("close" in n for n in field_names)


@pytest.mark.skipif(not _FD_DIR.exists(), reason="Fichiers Football-Data reels non presents.")
def test_real_corpus_ah_coverage_is_stable() -> None:
    """Non-regression large sur le corpus REEL - jamais suppose, mesure a
    chaque execution."""
    total_matched = 0
    total_understat = 0
    total_exploitable = 0
    total_with_pinnacle = 0
    total_excluded_incomplete_b365_ah = 0
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        report = build_asian_handicap_dataset(league, season, us_raw, fd_records)
        total_matched += report.n_matched
        total_understat += report.n_understat
        total_exploitable += report.n_exploitable
        total_with_pinnacle += report.n_with_pinnacle_ah
        total_excluded_incomplete_b365_ah += report.n_excluded_incomplete_b365_ah

    assert total_understat == 2132
    assert total_matched == 2123
    # B365 AH quasi-complet (residu de 5 matchs apparies sans AHh/prix
    # complet - coherent avec l'audit brut, docs/ah_experiment_specification.md
    # section 3) - non-regression exacte, pas un seuil approximatif.
    assert total_excluded_incomplete_b365_ah == 5
    # Couverture Pinnacle AH parmi les matchs exploitables - jamais totale,
    # non-regression par SEUIL (comme over_under_odds/betfair_exchange_odds).
    assert total_with_pinnacle / total_exploitable > 0.70
