from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sys_foot_quant.backtesting_engine.real_data_walk_forward import RealMatchRecord
from sys_foot_quant.data_engine.market_odds.future_match_dataset import (
    NO_MATCH_TO_EXCLUDE,
    build_match_train_dataframes,
    build_understat_team_id_by_name,
    resolve_match_team_ids,
)
from sys_foot_quant.data_engine.market_odds.matching import UnderstatMatchKey

_T0 = datetime(2024, 1, 1)


def _record(
    match_id: str,
    kickoff: datetime,
    home_team_id: int = 0,
    away_team_id: int = 1,
    home_goals: int = 1,
    away_goals: int = 0,
) -> RealMatchRecord:
    return RealMatchRecord(
        match_id=match_id,
        league="TEST",
        kickoff_utc=kickoff,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=1.2,
        away_xg=0.8,
        goals_knowledge_time=kickoff + timedelta(hours=2.0),
        xg_knowledge_time=kickoff + timedelta(hours=48.0),
    )


def _understat_key(match_id: str, kickoff: datetime, home_id: int, away_id: int, home_name: str, away_name: str) -> UnderstatMatchKey:
    return UnderstatMatchKey(
        match_id=match_id,
        league="liga",
        season="2024_25",
        kickoff_utc=kickoff,
        home_team_id=home_id,
        away_team_id=away_id,
        home_team_name=home_name,
        away_team_name=away_name,
    )


# --- build_match_train_dataframes ------------------------------------------


def test_returns_expected_columns_for_goals_and_xg() -> None:
    records = [_record(str(i), _T0 + timedelta(days=i)) for i in range(5)]
    decision_time = _T0 + timedelta(days=10)
    goals_df, xg_df = build_match_train_dataframes(records, home_team_id=0, away_team_id=1, decision_time=decision_time)

    assert list(goals_df.columns) == ["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
    assert list(xg_df.columns) == ["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"]
    # decision_time = jour 10 : le score (+2h) et le xG (+48h) des 5 matchs
    # (jours 0 a 4) sont tous deja connus a cette date.
    assert len(goals_df) == 5
    assert len(xg_df) == 5


def test_default_exclude_match_id_never_collides_with_a_real_future_match() -> None:
    records = [_record(str(i), _T0 + timedelta(days=i)) for i in range(5)]
    decision_time = _T0 + timedelta(days=10)
    goals_df, _ = build_match_train_dataframes(records, home_team_id=0, away_team_id=1, decision_time=decision_time)
    # Aucun match reel ne doit jamais avoir NO_MATCH_TO_EXCLUDE comme id.
    assert all(str(i) != NO_MATCH_TO_EXCLUDE for i in range(5))
    assert len(goals_df) == 5  # rien n'est exclu par erreur


def test_exclude_match_id_excludes_a_match_present_in_records() -> None:
    """Usage retrospectif (le match cible est deja dans records, walk-forward
    historique comme E7/E8) : il ne doit jamais s'entrainer sur lui-meme."""
    records = [_record(str(i), _T0 + timedelta(days=i)) for i in range(5)]
    target = records[4]
    decision_time = target.kickoff_utc - timedelta(hours=2.0)

    goals_with_exclusion, _ = build_match_train_dataframes(
        records, home_team_id=0, away_team_id=1, decision_time=decision_time, exclude_match_id="4"
    )
    goals_without_exclusion, _ = build_match_train_dataframes(
        records, home_team_id=0, away_team_id=1, decision_time=decision_time
    )
    # Le match "4" a kickoff a decision_time + 2h : son score n'est de toute
    # facon pas encore connu a decision_time, donc l'exclusion explicite ne
    # change rien ici - verifie plutot un cas ou le match cible aurait pu
    # fuiter par coincidence temporelle.
    assert len(goals_with_exclusion) == len(goals_without_exclusion) == 4


def test_exclude_match_id_matters_when_target_kickoff_is_in_the_past() -> None:
    records = [_record(str(i), _T0 + timedelta(days=i)) for i in range(5)]
    # decision_time tres tardif : le match "4" (dernier) a maintenant son
    # score connu et apparaitrait dans l'historique s'il n'etait pas exclu.
    decision_time = _T0 + timedelta(days=100)

    goals_with_exclusion, _ = build_match_train_dataframes(
        records, home_team_id=0, away_team_id=1, decision_time=decision_time, exclude_match_id="4"
    )
    goals_without_exclusion, _ = build_match_train_dataframes(
        records, home_team_id=0, away_team_id=1, decision_time=decision_time
    )
    assert len(goals_with_exclusion) == 4
    assert len(goals_without_exclusion) == 5


def test_team_ids_do_not_filter_the_returned_history() -> None:
    """L'historique retourne est celui de TOUTE la ligue, jamais restreint
    aux deux equipes passees en parametre - meme methodologie que
    PoissonModel/DixonColesModel/XGModel (attaque/defense estimees sur tout
    le championnat)."""
    records = [
        _record("0", _T0, home_team_id=0, away_team_id=1),
        _record("1", _T0 + timedelta(days=1), home_team_id=2, away_team_id=3),
    ]
    decision_time = _T0 + timedelta(days=10)
    goals_df, _ = build_match_train_dataframes(records, home_team_id=0, away_team_id=1, decision_time=decision_time)
    assert len(goals_df) == 2  # inclut aussi le match entre les equipes 2 et 3


# --- resolution de noms d'equipe (matching.py / team_mapping.py reutilises) -


def test_build_understat_team_id_by_name_basic() -> None:
    keys = [
        _understat_key("m1", _T0, 100, 200, "Real Madrid", "Barcelona"),
        _understat_key("m2", _T0 + timedelta(days=7), 200, 100, "Barcelona", "Real Madrid"),
    ]
    mapping = build_understat_team_id_by_name(keys)
    assert mapping == {"Real Madrid": 100, "Barcelona": 200}


def test_build_understat_team_id_by_name_raises_on_ambiguous_name() -> None:
    keys = [
        _understat_key("m1", _T0, 100, 200, "Real Madrid", "Barcelona"),
        _understat_key("m2", _T0 + timedelta(days=7), 999, 200, "Real Madrid", "Barcelona"),
    ]
    with pytest.raises(ValueError, match="ambigu"):
        build_understat_team_id_by_name(keys)


def test_resolve_match_team_ids_uses_team_mapping_translation() -> None:
    keys = [
        _understat_key("m1", _T0, 100, 200, "Real Madrid", "Barcelona"),
    ]
    # "Ath Bilbao" -> Understat name via team_mapping (liga).
    keys_with_athletic = keys + [_understat_key("m2", _T0 + timedelta(days=1), 300, 100, "Athletic Club", "Real Madrid")]
    home_id, away_id = resolve_match_team_ids(
        keys_with_athletic, league="liga", home_team_name_football_data="Ath Bilbao", away_team_name_football_data="Real Madrid"
    )
    assert (home_id, away_id) == (300, 100)


def test_resolve_match_team_ids_raises_for_unknown_team_in_corpus() -> None:
    keys = [_understat_key("m1", _T0, 100, 200, "Real Madrid", "Barcelona")]
    with pytest.raises(KeyError):
        resolve_match_team_ids(keys, league="liga", home_team_name_football_data="Getafe", away_team_name_football_data="Real Madrid")
