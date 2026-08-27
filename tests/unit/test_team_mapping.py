from __future__ import annotations

import pytest

from sys_foot_quant.data_engine.market_odds.team_mapping import (
    FOOTBALL_DATA_TO_UNDERSTAT,
    resolve_understat_name,
    validate_mapping_bijective,
)

# Ensembles complets d'equipes Understat attendus (union 2024/25 + 2025/26),
# extraits manuellement des fichiers reels research/xg_feasibility/runs/.
_EXPECTED_UNDERSTAT_TEAMS = {
    "premier_league": {
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Burnley",
        "Chelsea", "Crystal Palace", "Everton", "Fulham", "Ipswich", "Leeds",
        "Leicester", "Liverpool", "Manchester City", "Manchester United",
        "Newcastle United", "Nottingham Forest", "Southampton", "Sunderland",
        "Tottenham", "West Ham", "Wolverhampton Wanderers",
    },
    "ligue1": {
        "Angers", "Auxerre", "Brest", "Le Havre", "Lens", "Lille", "Lorient", "Lyon",
        "Marseille", "Metz", "Monaco", "Montpellier", "Nantes", "Nice", "Paris FC",
        "Paris Saint Germain", "Reims", "Rennes", "Saint-Etienne", "Strasbourg", "Toulouse",
    },
    "liga": {
        "Alaves", "Athletic Club", "Atletico Madrid", "Barcelona", "Celta Vigo", "Elche",
        "Espanyol", "Getafe", "Girona", "Las Palmas", "Leganes", "Levante", "Mallorca",
        "Osasuna", "Rayo Vallecano", "Real Betis", "Real Madrid", "Real Oviedo",
        "Real Sociedad", "Real Valladolid", "Sevilla", "Valencia", "Villarreal",
    },
}


@pytest.mark.parametrize("league", ["premier_league", "ligue1", "liga"])
def test_mapping_is_bijective_no_collision_no_gap(league: str) -> None:
    validate_mapping_bijective(league, _EXPECTED_UNDERSTAT_TEAMS[league])


def test_resolve_known_examples() -> None:
    assert resolve_understat_name("premier_league", "Man United") == "Manchester United"
    assert resolve_understat_name("ligue1", "Paris SG") == "Paris Saint Germain"
    assert resolve_understat_name("liga", "Ath Bilbao") == "Athletic Club"
    assert resolve_understat_name("liga", "Sociedad") == "Real Sociedad"
    assert resolve_understat_name("liga", "Espanol") == "Espanyol"


def test_resolve_unknown_team_raises_explicitly() -> None:
    with pytest.raises(KeyError):
        resolve_understat_name("premier_league", "Team That Does Not Exist")


def test_resolve_unknown_league_raises_explicitly() -> None:
    with pytest.raises(KeyError):
        resolve_understat_name("serie_a", "Juventus")


def test_no_silent_fuzzy_fallback_for_near_miss_names() -> None:
    # "Manchester Utd" ressemble a "Man United" mais n'est pas une cle du
    # mapping - doit lever, jamais etre resolu par proximite textuelle.
    with pytest.raises(KeyError):
        resolve_understat_name("premier_league", "Manchester Utd")


@pytest.mark.parametrize("league", ["premier_league", "ligue1", "liga"])
def test_validate_mapping_detects_injected_collision(league: str) -> None:
    table = dict(FOOTBALL_DATA_TO_UNDERSTAT[league])
    keys = list(table)
    table[keys[1]] = table[keys[0]]  # force une collision artificielle
    from sys_foot_quant.data_engine.market_odds import team_mapping as tm

    original = tm.FOOTBALL_DATA_TO_UNDERSTAT[league]
    tm.FOOTBALL_DATA_TO_UNDERSTAT[league] = table
    try:
        with pytest.raises(ValueError, match="Collision"):
            validate_mapping_bijective(league, _EXPECTED_UNDERSTAT_TEAMS[league])
    finally:
        tm.FOOTBALL_DATA_TO_UNDERSTAT[league] = original


@pytest.mark.parametrize("league", ["premier_league", "ligue1", "liga"])
def test_validate_mapping_detects_missing_understat_team(league: str) -> None:
    # Un ensemble Understat attendu SUPERIEUR a ce que le mapping couvre
    # reellement doit declencher "non couvertes" (une equipe Understat
    # pertinente n'a aucune entree Football-Data qui pointe vers elle).
    expanded = set(_EXPECTED_UNDERSTAT_TEAMS[league]) | {"Equipe Fantome FC"}
    with pytest.raises(ValueError, match="non couvertes"):
        validate_mapping_bijective(league, expanded)
