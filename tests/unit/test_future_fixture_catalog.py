"""Tests unitaires de la logique PURE de future_fixture_catalog.py (Brique
fixtures futures 2026/27, docs/future_fixture_catalog_2026_27.md) -
resolution d'equipe, construction d'identifiant, rapport de couverture.
Les tests dependant des fichiers 2026/27 reellement telecharges sont dans
tests/integration/test_future_fixture_catalog_real_files.py."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from sys_foot_quant.data_engine.market_odds.future_fixture_catalog import (
    FUTURE_FIXTURE_COMPETITIONS,
    FUTURE_FIXTURE_SEASON,
    TeamCoverageReport,
    TeamResolutionError,
    build_match_id,
    resolve_openfootball_team,
)


def test_future_fixture_season_and_competitions_are_the_expected_values() -> None:
    """Registre explicite (docstring du module) - jamais une autre saison
    traitee silencieusement."""
    assert FUTURE_FIXTURE_SEASON == "2026_27"
    assert set(FUTURE_FIXTURE_COMPETITIONS) == {"ligue1", "premier_league", "liga"}


# --------------------------------------------------------------------------
# Resolution d'equipe - succes et echec explicite
# --------------------------------------------------------------------------


def test_resolve_openfootball_team_succeeds_for_a_known_ligue1_club() -> None:
    assert resolve_openfootball_team("ligue1", "Olympique de Marseille") == "Marseille"


def test_resolve_openfootball_team_succeeds_for_the_four_2026_27_promoted_ligue1_clubs() -> None:
    assert resolve_openfootball_team("ligue1", "Le Mans FC") == "Le Mans"
    assert resolve_openfootball_team("ligue1", "FC Lorient") == "Lorient"
    assert resolve_openfootball_team("ligue1", "Paris FC") == "Paris FC"
    assert resolve_openfootball_team("ligue1", "ES Troyes AC") == "Troyes"


def test_resolve_openfootball_team_succeeds_for_leeds_and_sunderland() -> None:
    """Verifies contre epl_2025_datesData.json (Understat) - voir
    openfootball_team_mapping.py, EXTENSION 2026/27."""
    assert resolve_openfootball_team("premier_league", "Leeds United FC") == "Leeds"
    assert resolve_openfootball_team("premier_league", "Sunderland AFC") == "Sunderland"


def test_resolve_openfootball_team_succeeds_for_elche_and_levante() -> None:
    assert resolve_openfootball_team("liga", "Elche CF") == "Elche"
    assert resolve_openfootball_team("liga", "Levante UD") == "Levante"


def test_resolve_openfootball_team_raises_explicitly_for_a_genuinely_unmapped_club() -> None:
    """Coventry City : promu directement en 2026/27, aucun corpus Understat
    (meme 2025/26) ne le contient dans ce depot - JAMAIS un fuzzy matching
    ni un fallback vers le nom brut, une erreur explicite."""
    with pytest.raises(TeamResolutionError, match="Coventry City FC"):
        resolve_openfootball_team("premier_league", "Coventry City FC")


def test_resolve_openfootball_team_never_falls_back_to_a_fuzzy_match() -> None:
    """Un nom presque identique (espace/orthographe differente) ne doit
    JAMAIS resoudre par approximation - preuve negative explicite, meme
    discipline que test_openfootball_team_mapping.py."""
    with pytest.raises(TeamResolutionError):
        resolve_openfootball_team("ligue1", "Olympique  de Marseille")  # double espace
    with pytest.raises(TeamResolutionError):
        resolve_openfootball_team("ligue1", "Marseille")  # nom Understat, pas OpenFootball


# --------------------------------------------------------------------------
# Identifiant deterministe
# --------------------------------------------------------------------------


def test_build_match_id_is_deterministic_and_stable_across_two_identical_calls() -> None:
    fixture_date = date(2026, 8, 21)
    kickoff = datetime(2026, 8, 21, 20, 45)
    id_1 = build_match_id("ligue1", "2026_27", "Marseille", "Strasbourg", fixture_date, kickoff)
    id_2 = build_match_id("ligue1", "2026_27", "Marseille", "Strasbourg", fixture_date, kickoff)
    assert id_1 == id_2


def test_build_match_id_differs_for_different_matches() -> None:
    fixture_date = date(2026, 8, 21)
    kickoff = datetime(2026, 8, 21, 20, 45)
    id_marseille = build_match_id("ligue1", "2026_27", "Marseille", "Strasbourg", fixture_date, kickoff)
    id_lens = build_match_id("ligue1", "2026_27", "Lens", "Auxerre", fixture_date, kickoff)
    assert id_marseille != id_lens


def test_build_match_id_is_never_presented_as_a_provider_id() -> None:
    """Le format doit rester un composite lisible (competition/saison/
    equipes/kickoff), jamais un nombre/UUID qui laisserait croire a un
    identifiant fourni par OpenFootball (qui n'en expose aucun)."""
    match_id = build_match_id(
        "ligue1", "2026_27", "Marseille", "Strasbourg", date(2026, 8, 21), datetime(2026, 8, 21, 20, 45)
    )
    assert match_id == "ligue1:2026_27:Marseille_vs_Strasbourg:2026-08-21T20:45:00"


def test_build_match_id_falls_back_to_date_only_when_kickoff_time_is_unknown() -> None:
    """Etat C - l'identifiant ne peut pas dependre d'une heure absente
    (demande explicite) : retombe sur fixture_date seule, jamais une heure
    fabriquee."""
    match_id = build_match_id("ligue1", "2026_27", "Lens", "Le Havre", date(2026, 12, 5), None)
    assert match_id == "ligue1:2026_27:Lens_vs_Le Havre:2026-12-05"
    assert "None" not in match_id


# --------------------------------------------------------------------------
# TeamCoverageReport
# --------------------------------------------------------------------------


def test_team_coverage_report_is_fully_resolved_only_when_unresolved_is_empty() -> None:
    full = TeamCoverageReport(competition="ligue1", season="2026_27", resolved=("Marseille",), unresolved=())
    partial = TeamCoverageReport(
        competition="premier_league", season="2026_27", resolved=("Arsenal",), unresolved=("Coventry City FC",)
    )
    assert full.is_fully_resolved is True
    assert partial.is_fully_resolved is False
