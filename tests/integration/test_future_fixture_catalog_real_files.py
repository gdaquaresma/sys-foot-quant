"""Tests d'integration sur les fichiers OpenFootball 2026/27 REELS
(research/fixture_calendar/openfootball/runs/) - docs/future_fixture_catalog_2026_27.md.
Verifie la couverture et le comportement obtenus sur le corpus reel, pas
seulement des fixtures synthetiques (voir aussi
tests/unit/test_future_fixture_catalog.py pour la logique pure).

Si les fichiers 2026/27 venaient a etre deplaces/supprimes du depot, ces
tests echoueraient explicitement - meme discipline que
tests/integration/test_openfootball_calendar_real_files.py (2024/25)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from sys_foot_quant.data_engine.market_odds import openfootball_calendar as ofc
from sys_foot_quant.data_engine.market_odds.future_fixture_catalog import (
    FUTURE_FIXTURE_COMPETITIONS,
    FUTURE_FIXTURE_SEASON,
    build_future_fixtures,
    validate_team_coverage,
)

_RUNS_DIR = Path("research/fixture_calendar/openfootball/runs")


@pytest.mark.parametrize("competition", FUTURE_FIXTURE_COMPETITIONS)
def test_2026_27_real_file_exists_on_disk(competition: str) -> None:
    assert ofc._SOURCE_FILES[FUTURE_FIXTURE_SEASON][competition].exists(), (
        f"Fichier 2026/27 manquant pour {competition!r} - voir "
        f"docs/future_fixture_catalog_2026_27.md pour la provenance exacte."
    )


# --------------------------------------------------------------------------
# Ligue 1 : resolution complete, cas de demonstration reel
# --------------------------------------------------------------------------


def test_ligue1_2026_27_team_coverage_is_fully_resolved() -> None:
    """Les 18 equipes du fichier reel sont TOUTES resolues - verifie
    contre le corpus Understat 2026/27 reel (seul championnat a en avoir
    un dans ce depot)."""
    coverage = validate_team_coverage("ligue1")
    assert coverage.is_fully_resolved, f"Equipes non resolues inattendues : {coverage.unresolved}"
    assert len(coverage.resolved) == 18


def test_ligue1_2026_27_builds_without_error() -> None:
    fixtures = build_future_fixtures("ligue1")
    assert len(fixtures) > 0
    for f in fixtures:
        assert f.competition == "ligue1"
        assert f.season == "2026_27"


def test_a_real_already_played_match_has_is_played_true_and_a_real_score() -> None:
    """Cas reel demande explicitement (etat D) : Marseille-Strasbourg (21
    aout 2026), deja present dans le catalogue principal (match_id
    Understat 31940) - verifie ici cote OpenFootball."""
    fixtures = build_future_fixtures("ligue1")
    match = next(f for f in fixtures if f.home_team == "Marseille" and f.away_team == "Strasbourg")
    assert match.is_played is True
    assert match.fixture_date == date(2026, 8, 21)
    assert match.source_match.home_goals is not None
    assert match.source_match.away_goals is not None
    assert match.kickoff_local_naive.isoformat() == "2026-08-21T20:45:00"
    assert match.kickoff_utc is None  # DECOUVERTE 2 - jamais invente, meme pour un match passe.


def test_a_real_future_match_with_a_published_time_is_state_b() -> None:
    """Cas reel demande explicitement (etat B) : Lens-Lyon, Matchday 6 (9
    octobre 2026), heure locale publiee (20:45) mais kickoff_utc absent -
    heure locale connue, UTC non fiable (DECOUVERTE 2)."""
    fixtures = build_future_fixtures("ligue1")
    match = next(f for f in fixtures if f.home_team == "Lens" and f.away_team == "Lyon")
    assert match.is_played is False
    assert match.fixture_date == date(2026, 10, 9)
    assert match.kickoff_local_naive.isoformat() == "2026-10-09T20:45:00"
    assert match.kickoff_utc is None


def test_a_real_future_match_has_is_played_false_and_no_invented_score() -> None:
    """Cas reel demande explicitement : un match futur (apres le 2026-10-05
    simule) doit avoir is_played=False et AUCUN score invente."""
    fixtures = build_future_fixtures("ligue1")
    future_matches = [f for f in fixtures if not f.is_played]
    assert len(future_matches) > 0, "Aucun match futur trouve - le fichier source a peut-etre change."
    for f in future_matches:
        assert f.source_match.home_goals is None
        assert f.source_match.away_goals is None
        assert f.source_match.score_raw == ""


def test_played_and_unplayed_matches_coexist_in_the_same_real_file() -> None:
    """Demontre explicitement les deux etats sur le meme corpus reel
    (demande explicite du cadrage, section 6)."""
    fixtures = build_future_fixtures("ligue1")
    assert any(f.is_played for f in fixtures)
    assert any(not f.is_played for f in fixtures)


def test_home_and_away_teams_are_preserved_and_never_swapped() -> None:
    """Un championnat a une seule manche par journee : Marseille et
    Strasbourg se rencontrent deux fois dans la saison (aller ET retour,
    dates differentes) - la reciproque existe donc bien QUELQUE PART dans
    la saison, ce n'est pas un bug. Ce qui ne doit JAMAIS arriver : les
    DEUX sens le MEME jour (verifie explicitement ci-dessous)."""
    fixtures = build_future_fixtures("ligue1")
    match = next(f for f in fixtures if f.home_team == "Marseille" and f.away_team == "Strasbourg")
    assert match.home_team_openfootball == "Olympique de Marseille"
    assert match.away_team_openfootball == "RC Strasbourg Alsace"
    assert not any(
        f.home_team == "Strasbourg" and f.away_team == "Marseille" and f.fixture_date == match.fixture_date
        for f in fixtures
    )


def test_competition_and_season_are_tagged_correctly_on_every_fixture() -> None:
    for competition in ("ligue1",):  # seule competition pleinement constructible (voir couverture PL/Liga ci-dessous)
        for f in build_future_fixtures(competition):
            assert f.competition == competition
            assert f.season == FUTURE_FIXTURE_SEASON


def test_match_ids_are_unique_within_a_competition() -> None:
    fixtures = build_future_fixtures("ligue1")
    ids = [f.match_id for f in fixtures]
    assert len(ids) == len(set(ids))


def test_match_id_is_stable_across_two_independent_builds() -> None:
    """Rebatir le catalogue deux fois (deux lectures independantes du
    meme fichier) doit produire EXACTEMENT les memes identifiants, dans
    le meme ordre - jamais une dependance a l'ordre de lecture."""
    first = build_future_fixtures("ligue1")
    second = build_future_fixtures("ligue1")
    assert [f.match_id for f in first] == [f.match_id for f in second]


def test_no_fixture_ever_has_a_populated_kickoff_utc() -> None:
    """Garde-fou explicite (DECOUVERTE 2 du module) : ``kickoff_utc``
    EXISTE desormais comme champ (modele A/B/C/D) mais doit rester
    TOUJOURS None aujourd'hui, pour TOUTE fixture - aucune regle de
    conversion suffisamment fiable n'est implementee."""
    fixtures = build_future_fixtures("ligue1")
    assert len(fixtures) > 0
    for f in fixtures:
        assert f.kickoff_utc is None
        assert hasattr(f, "fixture_date")
        assert hasattr(f, "kickoff_local_naive")


# --------------------------------------------------------------------------
# Etat C - fixture future sans heure publiee (desormais conservee)
# --------------------------------------------------------------------------


def test_a_real_future_match_without_a_published_time_is_preserved_as_state_c() -> None:
    """Cas reel demande explicitement : Racing Club de Lens - Le Havre AC,
    Matchday 13 (5 decembre 2026), aucune heure publiee par la source -
    doit desormais etre une fixture C (conservee), pas une exclusion."""
    fixtures = build_future_fixtures("ligue1")
    match = next(f for f in fixtures if f.home_team == "Lens" and f.away_team == "Le Havre")
    assert match.fixture_date == date(2026, 12, 5)
    assert match.kickoff_local_naive is None
    assert match.kickoff_utc is None
    assert match.is_played is False
    assert match.source_match.home_goals is None
    assert match.source_match.away_goals is None


def test_future_fixtures_are_no_longer_silently_dropped_for_ligue1() -> None:
    """Avant cette extension, 192/306 matchs futurs de Ligue 1 etaient
    invisibles (exclusions non structurees). Verrouille le compte exact
    desormais conserve - un ecart signalerait soit une regression, soit un
    changement du fichier source."""
    fixtures = build_future_fixtures("ligue1")
    state_d = [f for f in fixtures if f.is_played]
    state_b = [f for f in fixtures if not f.is_played and f.kickoff_local_naive is not None]
    state_c = [f for f in fixtures if f.kickoff_local_naive is None]
    assert len(state_d) == 45
    assert len(state_b) == 69
    assert len(state_c) == 192
    assert len(fixtures) == 306


# --------------------------------------------------------------------------
# Premier League / Liga : resolution PARTIELLE attendue, catalogue PARTIEL
# desormais accepte (EXTENSION - demande produit explicite : une seule
# equipe non resolue ne doit plus faire echouer TOUTE la competition).
# --------------------------------------------------------------------------


@pytest.mark.parametrize("competition,expected_unresolved", [
    ("premier_league", {"Coventry City FC", "Hull City AFC"}),
    ("liga", {"Málaga CF", "RC Deportivo La Coruña", "Real Racing Club de Santander"}),
])
def test_coverage_report_lists_every_unresolved_club_without_stopping_at_the_first(
    competition: str, expected_unresolved: set[str]
) -> None:
    """Test EXHAUSTIF demande explicitement : validate_team_coverage ne
    doit jamais s'arreter au premier club non resolu, et doit enumerer
    EXACTEMENT l'ensemble attendu (ni plus, ni moins) - un ecart
    signalerait soit une regression de mapping, soit un changement du
    fichier source."""
    coverage = validate_team_coverage(competition)
    assert set(coverage.unresolved) == expected_unresolved
    assert coverage.is_fully_resolved is False


@pytest.mark.parametrize("competition", ["premier_league", "liga"])
def test_build_future_fixtures_no_longer_raises_for_a_partially_unresolved_competition(
    competition: str,
) -> None:
    """EXTENSION (resolution partielle) - non-regression explicite du
    changement de comportement demande : une equipe non resolue (Coventry
    City/Hull City, Malaga/Deportivo/Racing Santander) ne doit PLUS faire
    echouer la construction de TOUTE la competition."""
    fixtures = build_future_fixtures(competition)
    assert len(fixtures) > 0
    assert any(f.resolution_status == "unresolved" for f in fixtures)
    assert any(f.resolution_status == "resolved" for f in fixtures)


@pytest.mark.parametrize("competition,declared_total", [("premier_league", 380), ("liga", 380)])
def test_build_future_fixtures_covers_the_full_declared_file_resolved_and_unresolved_together(
    competition: str, declared_total: int
) -> None:
    """Chaque match du fichier source est represente UNE fois (resolu OU
    non resolu) - aucun match perdu par la resolution partielle, aucun
    double compte."""
    fixtures = build_future_fixtures(competition)
    assert len(fixtures) == declared_total
    resolved = [f for f in fixtures if f.resolution_status == "resolved"]
    unresolved = [f for f in fixtures if f.resolution_status == "unresolved"]
    assert len(resolved) + len(unresolved) == declared_total


def test_an_unresolved_fixture_never_fabricates_an_understat_name() -> None:
    """Cas reel : Arsenal (resolu) - Coventry City FC (non resolu), 21 aout
    2026. Le cote non resolu reste a ``None`` - JAMAIS le nom OpenFootball
    brut substitue comme si c'etait un nom Understat verifie."""
    fixtures = build_future_fixtures("premier_league")
    match = next(f for f in fixtures if f.home_team_openfootball == "Arsenal FC" and f.away_team_openfootball == "Coventry City FC")
    assert match.resolution_status == "unresolved"
    assert match.home_team == "Arsenal"
    assert match.away_team is None
    assert match.away_team_openfootball == "Coventry City FC"
    assert match.kickoff_utc is None


def test_an_unresolved_fixture_can_have_the_home_side_unresolved_instead() -> None:
    """Cas reel symmetrique : Real Racing Club de Santander (non resolu,
    domicile) - Villarreal (resolu), 16 aout 2026."""
    fixtures = build_future_fixtures("liga")
    match = next(
        f for f in fixtures
        if f.home_team_openfootball == "Real Racing Club de Santander" and f.away_team_openfootball == "Villarreal CF"
    )
    assert match.resolution_status == "unresolved"
    assert match.home_team is None
    assert match.away_team == "Villarreal"


def test_a_real_future_unresolved_fixture_still_has_no_kickoff_utc_and_a_stable_id() -> None:
    """Cas reel FUTUR (pas encore joue) : Hull City - Everton, 11 octobre
    2026 - reste identifiable (``resolution_status=="unresolved"``,
    ``is_played=False``) et son identifiant demeure STABLE entre deux
    constructions independantes, meme sans nom Understat cote domicile."""
    first = build_future_fixtures("premier_league")
    second = build_future_fixtures("premier_league")
    match_id = "premier_league:2026_27:Hull City AFC_vs_Everton:2026-10-11T14:00:00"
    first_match = next(f for f in first if f.match_id == match_id)
    second_match = next(f for f in second if f.match_id == match_id)
    assert first_match.resolution_status == "unresolved"
    assert first_match.is_played is False
    assert first_match.home_team is None
    assert first_match.away_team == "Everton"
    assert first_match.kickoff_utc is None
    assert second_match.match_id == first_match.match_id


def test_unresolved_fixtures_never_collide_in_match_id_with_resolved_ones() -> None:
    fixtures = build_future_fixtures("premier_league")
    ids = [f.match_id for f in fixtures]
    assert len(ids) == len(set(ids))


def test_premier_league_resolved_clubs_still_cover_eighteen_of_twenty() -> None:
    """Contre-epreuve positive : 18 clubs sur 20 SONT resolus (seuls 2
    genuinement non mappables faute de corpus Understat) - la resolution
    partielle n'est pas un echec total du mapping."""
    coverage = validate_team_coverage("premier_league")
    assert len(coverage.resolved) == 18
