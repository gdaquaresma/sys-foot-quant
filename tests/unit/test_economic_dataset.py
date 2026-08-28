"""Tests unitaires de construction pour ``economic_dataset.py`` (etape 1-3,
premiere experience economique reelle - poisson_simple vs marche B365)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sys_foot_quant.data_engine.market_odds.economic_dataset import (
    MIN_TRAIN_MATCHES,
    SELECTIONS,
    build_economic_dataset,
)
from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord

_LEAGUE = "premier_league"
_SEASON = "2024_25"
_T0 = datetime(2024, 8, 3, 15, 0, 0)  # un samedi


def _us(match_id, dt, home, away, home_id, away_id, hg=1, ag=0, hxg=1.1, axg=0.9, is_result=True):
    return {
        "id": match_id,
        "isResult": is_result,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": home_id, "title": home},
        "a": {"id": away_id, "title": away},
        "goals": {"h": hg, "a": ag},
        "xG": {"h": hxg, "a": axg},
    }


def _fd(date_dt, home, away, b365=(1.8, 3.6, 4.5), league=_LEAGUE, season=_SEASON):
    return FootballDataMatchRecord(
        league=league, season=season, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=1, away_goals=0,
        b365_home=b365[0], b365_draw=b365[1], b365_away=b365[2],
    )


_TEAMS = ["Arsenal", "Chelsea", "Liverpool", "Everton"]


def _burn_in(n: int, start: datetime) -> list[dict]:
    """``n`` matchs d'echauffement, un samedi sur deux, entre des equipes
    fixes, pour depasser MIN_TRAIN_MATCHES avant le match evalue."""
    raw = []
    for i in range(n):
        home, away = _TEAMS[i % 2], _TEAMS[2 + (i % 2)]
        raw.append(_us(f"burn{i}", start - timedelta(days=7 * (n - i)), home, away, home_id=i % 2, away_id=2 + (i % 2)))
    return raw


def _build_simple_dataset(n_burn_in=12, eval_home="Arsenal", eval_away="Everton", b365=(1.8, 3.6, 4.5)):
    raw = _burn_in(n_burn_in, _T0)
    raw.append(_us("eval1", _T0, eval_home, eval_away, home_id=0, away_id=3))
    fd = [_fd(_T0, eval_home, eval_away, b365=b365)]
    return build_economic_dataset(_LEAGUE, _SEASON, raw, fd)


def test_basic_exploitable_match_produces_expected_fields() -> None:
    report = _build_simple_dataset()
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.match_id == "eval1"
    assert rec.league == _LEAGUE
    assert rec.season == _SEASON
    assert set(rec.model_probs) == set(SELECTIONS)
    assert abs(sum(rec.model_probs.values()) - 1.0) < 1e-9
    assert rec.market_odds == {"home": 1.8, "draw": 3.6, "away": 4.5}
    assert rec.outcome_selection in SELECTIONS
    assert rec.timestamp_status == "hypothetical_documented"


def test_edge_raw_and_edge_norm_are_both_reported_and_differ_when_overround_present() -> None:
    report = _build_simple_dataset()
    rec = report.records[0]
    for s in SELECTIONS:
        assert s in rec.edge_raw
        assert s in rec.edge_norm
    # overround > 0 ici (1/1.8+1/3.6+1/4.5 > 1) => edge_raw != edge_norm pour au moins une issue
    assert rec.overround > 0
    assert any(abs(rec.edge_raw[s] - rec.edge_norm[s]) > 1e-9 for s in SELECTIONS)


def test_ev_matches_expected_value_formula() -> None:
    report = _build_simple_dataset()
    rec = report.records[0]
    for s in SELECTIONS:
        expected = rec.model_probs[s] * rec.market_odds[s] - 1.0
        assert abs(rec.ev[s] - expected) < 1e-9


def test_insufficient_history_excludes_match() -> None:
    report = _build_simple_dataset(n_burn_in=2)  # < MIN_TRAIN_MATCHES
    assert report.n_exploitable == 0
    assert report.n_excluded_insufficient_history == 1


def test_ambiguous_weekday_excludes_match_and_is_counted() -> None:
    tuesday = datetime(2024, 8, 6, 20, 0, 0)  # un mardi
    raw = _burn_in(12, tuesday)
    raw.append(_us("eval1", tuesday, "Arsenal", "Everton", home_id=0, away_id=3))
    fd = [_fd(tuesday, "Arsenal", "Everton")]
    report = build_economic_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 0
    assert report.n_excluded_ambiguous_weekday == 1


def test_incomplete_odds_excludes_match() -> None:
    raw = _burn_in(12, _T0)
    raw.append(_us("eval1", _T0, "Arsenal", "Everton", home_id=0, away_id=3))
    fd = [_fd(_T0, "Arsenal", "Everton", b365=(1.8, 3.6, 4.5))]
    fd[0] = FootballDataMatchRecord(
        league=_LEAGUE, season=_SEASON, source="football_data", bookmaker="B365", market="1x2",
        date_str=_T0.strftime("%d/%m/%Y"), time_str=_T0.strftime("%H:%M"),
        home_team_fd="Arsenal", away_team_fd="Everton", home_goals=1, away_goals=0,
        b365_home=None, b365_draw=3.6, b365_away=4.5,
    )
    report = build_economic_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_exploitable == 0
    assert report.n_excluded_incomplete_odds == 1


def test_unmatched_understat_reported_not_silently_dropped() -> None:
    raw = _burn_in(12, _T0)
    raw.append(_us("eval1", _T0, "Arsenal", "Everton", home_id=0, away_id=3))
    # Cotes fournies pour tous les matchs d'echauffement, mais PAS pour
    # eval1 - seul eval1 doit apparaitre comme non apparie.
    fd = [
        _fd(_T0 - timedelta(days=7 * (12 - i)), *(_TEAMS[i % 2], _TEAMS[2 + (i % 2)]))
        for i in range(12)
    ]
    report = build_economic_dataset(_LEAGUE, _SEASON, raw, fd)
    assert report.n_unmatched_understat == 1
    assert report.n_matched == 12
    assert "eval1" not in {r.match_id for r in report.records}


def test_min_train_matches_constant_matches_prior_experiments() -> None:
    assert MIN_TRAIN_MATCHES == 10
