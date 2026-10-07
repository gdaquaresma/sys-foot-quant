"""Tests de openfootball_team_mapping.py (Brique 2) - verifie l'absence
de collision et la correction des deux cas corriges a la main lors de la
construction (voir docstring du module : Manchester City/United, Rennes).
Les tests d'existence reelle contre les fichiers telecharges sont dans
tests/integration/test_openfootball_calendar_real_files.py (plus lent,
depend des fichiers sur disque)."""

from __future__ import annotations

import pytest

from sys_foot_quant.data_engine.market_odds.openfootball_team_mapping import (
    LEAGUE_COMPETITION_KEY,
    OPENFOOTBALL_TEAM_MAPPING,
    team_name_by_competition,
)


def test_covers_exactly_the_expected_team_counts_per_league() -> None:
    """Chaque championnat est passe de 18/20/20 a 22 : EXTENSION 2026/27
    (voir docstring du module) - entrees ajoutees pour des clubs promus
    entre 2024/25 et 2026/27, verifiees contre le corpus Understat le plus
    recent disponible, SANS jamais supprimer les clubs 2024/25 relegues
    depuis (toujours utiles pour l'usage 2024/25 d'origine) :

    - ligue1   : 18 + 4 (Le Mans, Lorient, Paris FC, Troyes)  = 22
    - liga     : 20 + 2 (Elche, Levante)                      = 22
    - premier_league : 20 + 2 (Leeds, Sunderland)             = 22
    """
    assert len(OPENFOOTBALL_TEAM_MAPPING["ligue1"]) == 22
    assert len(OPENFOOTBALL_TEAM_MAPPING["liga"]) == 22
    assert len(OPENFOOTBALL_TEAM_MAPPING["premier_league"]) == 22


def test_every_team_has_a_league_entry() -> None:
    for league, teams in OPENFOOTBALL_TEAM_MAPPING.items():
        for understat, entry in teams.items():
            assert "league" in entry, f"{league}/{understat} n'a pas d'entree 'league'"
            assert entry["league"].strip()


def test_resolve_corrects_manchester_city_and_united_despite_normalization_collision() -> None:
    """Cas corrige a la main (docstring du module) : une premiere
    normalisation automatique faisait collisionner 'Manchester City' et
    'Manchester United' sur le meme nom - non-regression explicite."""
    assert team_name_by_competition("premier_league", "Manchester City")["premier_league"] == "Manchester City FC"
    assert team_name_by_competition("premier_league", "Manchester United")["premier_league"] == "Manchester United FC"


def test_resolve_corrects_rennes_demonym_mismatch() -> None:
    assert team_name_by_competition("ligue1", "Rennes")["ligue1"] == "Stade Rennais FC 1901"


def test_resolve_the_four_2026_27_promoted_clubs() -> None:
    """EXTENSION 2026/27 - les 4 noms ont ete verifies directement contre
    ligue1_2026_datesData.json (Understat), jamais devines (voir docstring
    du module)."""
    assert team_name_by_competition("ligue1", "Le Mans")["ligue1"] == "Le Mans FC"
    assert team_name_by_competition("ligue1", "Lorient")["ligue1"] == "FC Lorient"
    assert team_name_by_competition("ligue1", "Paris FC")["ligue1"] == "Paris FC"
    assert team_name_by_competition("ligue1", "Troyes")["ligue1"] == "ES Troyes AC"


def test_resolve_leeds_and_sunderland_premier_league_2026_27() -> None:
    """Verifies contre epl_2025_datesData.json (Understat) - voir docstring
    du module, EXTENSION 2026/27."""
    assert team_name_by_competition("premier_league", "Leeds")["premier_league"] == "Leeds United FC"
    assert team_name_by_competition("premier_league", "Sunderland")["premier_league"] == "Sunderland AFC"


def test_resolve_elche_and_levante_liga_2026_27() -> None:
    assert team_name_by_competition("liga", "Elche")["liga"] == "Elche CF"
    assert team_name_by_competition("liga", "Levante")["liga"] == "Levante UD"


def test_2024_25_relegated_clubs_remain_mapped_not_deleted() -> None:
    """Montpellier/Nantes/Reims/Saint-Etienne ne jouent plus en Ligue 1 en
    2026/27 mais restent necessaires pour l'usage 2024/25 d'origine
    (congestion multi-competitions) - jamais supprimes par l'extension."""
    for team in ("Montpellier", "Nantes", "Reims", "Saint-Etienne"):
        assert team in OPENFOOTBALL_TEAM_MAPPING["ligue1"]


def test_resolve_substitutes_league_key_with_the_real_competition_key() -> None:
    resolved = team_name_by_competition("liga", "Barcelona")
    assert "league" not in resolved
    assert resolved["liga"] == "FC Barcelona"
    assert resolved["copa_del_rey"] == "FC Barcelona"
    assert resolved["champions_league"] == "FC Barcelona"


def test_resolve_unknown_league_raises_key_error() -> None:
    with pytest.raises(KeyError):
        team_name_by_competition("bundesliga", "Bayern")


def test_resolve_unknown_team_raises_key_error() -> None:
    with pytest.raises(KeyError):
        team_name_by_competition("liga", "Not A Real Team")


def test_no_accidental_value_collision_within_the_same_competition() -> None:
    """Deux clubs Understat distincts ne doivent jamais partager le meme
    nom OpenFootball au sein d'une meme competition - une telle collision
    romprait silencieusement la jointure (voir docstring, cas Manchester)."""
    for league, teams in OPENFOOTBALL_TEAM_MAPPING.items():
        by_competition: dict[str, dict[str, str]] = {}
        for understat, entry in teams.items():
            for competition, name in entry.items():
                seen = by_competition.setdefault(competition, {})
                assert name not in seen, (
                    f"collision dans {league}/{competition} : {seen.get(name)!r} et {understat!r} "
                    f"partagent tous deux le nom OpenFootball {name!r}"
                )
                seen[name] = understat


def test_league_competition_key_covers_all_three_primary_leagues() -> None:
    assert set(LEAGUE_COMPETITION_KEY) == {"ligue1", "liga", "premier_league"}
