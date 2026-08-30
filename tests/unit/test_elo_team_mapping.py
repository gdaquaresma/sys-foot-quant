"""Tests de elo_team_mapping.py (Phase K) - le mapping doit rester
BLOQUE tant qu'il n'a pas ete verifie a la main contre des donnees
ClubElo reelles (docs/elo_experiment_specification.md section 4)."""

from __future__ import annotations

import pytest

from sys_foot_quant.data_engine.market_odds.elo_team_mapping import (
    MAPPING_VERIFIED_AGAINST_REAL_DATA,
    EloMappingUnverifiedError,
    resolve_clubelo_name,
)


def test_mapping_is_not_yet_verified_against_real_data() -> None:
    """Documente l'etat actuel (bloquant) - ce test devra etre mis a jour
    explicitement le jour ou une verification manuelle reelle est faite,
    jamais silencieusement."""
    assert MAPPING_VERIFIED_AGAINST_REAL_DATA is False


def test_resolve_without_allow_unverified_is_blocked() -> None:
    with pytest.raises(EloMappingUnverifiedError):
        resolve_clubelo_name("liga", "Barcelona")


def test_resolve_with_allow_unverified_works_for_known_team() -> None:
    assert resolve_clubelo_name("liga", "Barcelona", allow_unverified=True) == "Barcelona"
    assert resolve_clubelo_name("premier_league", "Man City", allow_unverified=True) == "Manchester City"
    assert resolve_clubelo_name("ligue1", "Paris SG", allow_unverified=True) == "Paris SG"


def test_resolve_unknown_league_raises_key_error_even_when_allowed() -> None:
    with pytest.raises(KeyError):
        resolve_clubelo_name("bundesliga", "Bayern", allow_unverified=True)


def test_resolve_unknown_team_raises_key_error_even_when_allowed() -> None:
    with pytest.raises(KeyError):
        resolve_clubelo_name("liga", "Not A Real Team", allow_unverified=True)
