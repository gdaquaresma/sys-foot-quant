"""Garde-fous anti-fuite - jours de repos / congestion intra-championnat
(Brique 1, Phase I/E, docs/fixture_congestion_experiment_specification.md).
Couvre explicitement :

1. seuls les matchs strictement anterieurs au coup d'envoi cible sont
   utilises pour trouver le "dernier match" d'une equipe ;
2. le match cible lui-meme est toujours exclu, meme s'il est present
   dans l'entree ;
3. aucun match posterieur n'est jamais utilise, quelle que soit sa
   proximite temporelle ;
4. invariance stricte : ajouter, modifier ou retirer un match futur ne
   change jamais la feature d'un match deja passe ;
5. le resultat (score) d'un match, meme deja joue, n'entre jamais dans ce
   calcul - seule la date de coup d'envoi compte (contrairement a
   `shots_on_target`/`economic_dataset`, aucune donnee post-match n'est
   utilisee ici, le risque de fuite est donc structurellement plus
   faible, mais verifie explicitement plutot que suppose)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sys_foot_quant.data_engine.market_odds.fixture_congestion import (
    congestion_dataset_for_season,
    congestion_feature_for_match,
    rest_days_before_match,
)
from sys_foot_quant.data_engine.market_odds.match_catalog import MatchSummary

_COMPETITION = "ligue1"
_SEASON = "2025_26"
_T0 = datetime(2025, 8, 9, 20, 0)


def _match(match_id: str, kickoff: datetime, home: str, away: str) -> MatchSummary:
    return MatchSummary(
        match_id=match_id, competition=_COMPETITION, season=_SEASON,
        kickoff_utc=kickoff, home_team=home, away_team=away, is_played=True,
    )


# --- 1. Seuls les matchs strictement anterieurs sont eligibles --------------


def test_only_matches_strictly_before_target_kickoff_are_considered() -> None:
    earlier = _match("earlier", _T0 - timedelta(days=7), "Marseille", "Lyon")
    same_instant = _match("same_instant", _T0, "Marseille", "Brest")  # meme coup d'envoi que la cible, pas anterieur
    target = _match("target", _T0, "Marseille", "Nice")

    result = rest_days_before_match((earlier, same_instant, target), target, "Marseille")
    # "same_instant" n'est pas STRICTEMENT anterieur (kickoff egal) -> jamais eligible.
    assert result.previous_match_id == "earlier"


# --- 2. Le match cible est toujours exclu, meme present dans l'entree -------


def test_target_match_present_in_input_is_never_used_as_its_own_history() -> None:
    target = _match("target", _T0, "Marseille", "Nice")
    result = rest_days_before_match((target,), target, "Marseille")
    assert result.rest_days is None
    assert result.previous_match_id is None


# --- 3. Aucun match posterieur, quelle que soit sa proximite ----------------


def test_match_one_second_after_target_is_never_selected() -> None:
    target = _match("target", _T0, "Marseille", "Nice")
    almost_simultaneous_future = _match("future", _T0 + timedelta(seconds=1), "Marseille", "Brest")
    result = rest_days_before_match((target, almost_simultaneous_future), target, "Marseille")
    assert result.previous_match_id is None


def test_future_match_never_used_even_when_it_is_the_only_other_match() -> None:
    target = _match("target", _T0, "Marseille", "Nice")
    future = _match("future", _T0 + timedelta(days=1), "Marseille", "Brest")
    result = rest_days_before_match((target, future), target, "Marseille")
    assert result.previous_match_id is None
    assert result.rest_days is None


# --- 4. Invariance stricte : un match futur ne change jamais le passe -------


def test_feature_is_invariant_to_adding_removing_or_moving_future_matches() -> None:
    earlier = _match("earlier", _T0 - timedelta(days=7), "Marseille", "Lyon")
    target = _match("target", _T0, "Marseille", "Nice")

    baseline = congestion_feature_for_match((earlier, target), target)

    scenarios = [
        (earlier, target, _match("f1", _T0 + timedelta(days=1), "Marseille", "Brest")),
        (earlier, target, _match("f1", _T0 + timedelta(days=100), "Marseille", "Brest")),
        (earlier, target, _match("f1", _T0 + timedelta(seconds=1), "Marseille", "Brest")),
    ]
    for matches in scenarios:
        feature = congestion_feature_for_match(matches, target)
        assert feature.home_rest_days == baseline.home_rest_days
        assert feature.home_previous_match_id == baseline.home_previous_match_id

    # Retirer le match futur ne change rien non plus, par construction
    # (il n'etait deja jamais utilise).
    without_future = congestion_feature_for_match((earlier, target), target)
    assert without_future == baseline


def test_dataset_level_invariance_target_feature_unaffected_by_later_matches() -> None:
    # Meme garantie au niveau du dataset complet : la feature d'un match
    # donne ne doit jamais dependre des matchs qui le suivent dans le
    # calendrier, meme quand le dataset entier est recalcule.
    m1 = _match("m1", _T0, "Marseille", "Lyon")
    m2 = _match("m2", _T0 + timedelta(days=7), "Marseille", "Nice")

    dataset_short = congestion_dataset_for_season(_COMPETITION, (m1, m2))
    m3 = _match("m3", _T0 + timedelta(days=14), "Marseille", "Brest")
    dataset_long = congestion_dataset_for_season(_COMPETITION, (m1, m2, m3))

    feature_m1_short = next(f for f in dataset_short if f.match_id == "m1")
    feature_m1_long = next(f for f in dataset_long if f.match_id == "m1")
    feature_m2_short = next(f for f in dataset_short if f.match_id == "m2")
    feature_m2_long = next(f for f in dataset_long if f.match_id == "m2")

    assert feature_m1_short == feature_m1_long
    assert feature_m2_short == feature_m2_long


# --- 5. Aucune donnee post-match (score) n'entre dans ce calcul -------------


def test_match_summary_carries_no_score_field_the_feature_could_leak() -> None:
    # Garde-fou structurel : MatchSummary (match_catalog) ne porte aucun
    # champ de score/resultat - il est impossible pour ce module de lire
    # un resultat meme par erreur, contrairement a des modules qui lisent
    # des DataFrames larges (ou une fuite par colonne mal filtree est
    # possible). Verifie explicitement plutot que suppose.
    import dataclasses

    from sys_foot_quant.data_engine.market_odds.match_catalog import MatchSummary as MS

    field_names = {f.name for f in dataclasses.fields(MS)}
    assert field_names == {"match_id", "competition", "season", "kickoff_utc", "home_team", "away_team", "is_played"}
    assert not any("goal" in name or "score" in name or "result" in name for name in field_names if name != "is_played")


def test_source_never_reads_a_goals_or_score_attribute() -> None:
    import ast
    import inspect

    from sys_foot_quant.data_engine.market_odds import fixture_congestion

    source = inspect.getsource(fixture_congestion)
    tree = ast.parse(source)
    attr_names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden = {"goals", "home_goals", "away_goals", "score", "outcome"}
    assert attr_names.isdisjoint(forbidden)


@pytest.mark.parametrize("n_future_matches", [0, 1, 5])
def test_number_of_future_matches_never_affects_rest_days_value(n_future_matches: int) -> None:
    earlier = _match("earlier", _T0 - timedelta(days=10), "Marseille", "Lyon")
    target = _match("target", _T0, "Marseille", "Nice")
    future_matches = tuple(
        _match(f"future{i}", _T0 + timedelta(days=i + 1), "Marseille", "Brest") for i in range(n_future_matches)
    )
    result = rest_days_before_match((earlier, target, *future_matches), target, "Marseille")
    assert result.rest_days == pytest.approx(10.0)
    assert result.previous_match_id == "earlier"
