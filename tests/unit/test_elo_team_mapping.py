"""Tests de elo_team_mapping.py (Phase K) - le mapping a ete verifie a
la main contre les pages reelles clubelo.com/ENG, clubelo.com/ESP et
clubelo.com/FRA (docs/elo_experiment_specification.md section 4,
transcription directe fournie par l'utilisateur)."""

from __future__ import annotations

import pytest

from sys_foot_quant.data_engine.market_odds.elo_team_mapping import (
    FOOTBALL_DATA_TO_CLUBELO,
    MAPPING_VERIFIED_AGAINST_REAL_DATA,
    resolve_clubelo_name,
)
from sys_foot_quant.data_engine.market_odds.team_mapping import FOOTBALL_DATA_TO_UNDERSTAT


def test_mapping_is_verified_against_real_data() -> None:
    """Documente l'etat actuel : verifie a la main (voir docstring du
    module pour la provenance exacte) - ne jamais repasser a False sans
    justification explicite."""
    assert MAPPING_VERIFIED_AGAINST_REAL_DATA is True


def test_resolve_without_allow_unverified_now_works() -> None:
    """Desormais que le mapping est verifie, une resolution sans le
    drapeau explicite fonctionne (le drapeau ne sert plus qu'a debloquer
    des tests sur donnees synthetiques si le mapping redevenait
    non verifie un jour)."""
    assert resolve_clubelo_name("liga", "Barcelona") == "Barcelona"


def test_resolve_corrected_names_that_differed_from_the_initial_draft() -> None:
    """Ces cinq entrees ont ete CORRIGEES lors de la verification manuelle
    (l'ebauche initiale, non verifiee, s'etait trompee) - garde-fou de
    non-regression explicite sur ces cas precis."""
    assert resolve_clubelo_name("premier_league", "Man City") == "Man City"
    assert resolve_clubelo_name("premier_league", "Man United") == "Man United"
    assert resolve_clubelo_name("premier_league", "Nott'm Forest") == "Forest"
    assert resolve_clubelo_name("ligue1", "St Etienne") == "Saint-Etienne"
    assert resolve_clubelo_name("liga", "Ath Bilbao") == "Athletic Club"
    assert resolve_clubelo_name("liga", "Ath Madrid") == "Atlético"
    assert resolve_clubelo_name("liga", "Sociedad") == "Real Sociedad"


def test_resolve_the_three_teams_found_only_via_manual_search() -> None:
    """Leganes/Oviedo/Valladolid n'apparaissaient pas dans la premiere
    capture Espagne (en dessous du seuil affiche) - retrouves ensuite via
    une recherche Ctrl+F dediee sur la page reelle."""
    assert resolve_clubelo_name("liga", "Leganes") == "Leganes"
    assert resolve_clubelo_name("liga", "Oviedo") == "Oviedo"
    assert resolve_clubelo_name("liga", "Valladolid") == "Valladolid"


def test_resolve_unknown_league_raises_key_error() -> None:
    with pytest.raises(KeyError):
        resolve_clubelo_name("bundesliga", "Bayern")


def test_resolve_unknown_team_raises_key_error() -> None:
    with pytest.raises(KeyError):
        resolve_clubelo_name("liga", "Not A Real Team")


def test_mapping_covers_exactly_the_expected_team_counts_per_league() -> None:
    """Non-regression de couverture : 23 Premier League, 21 Ligue 1, 23
    Liga - les memes effectifs que team_mapping.py (Understat), jamais
    plus ni moins sans le documenter."""
    assert len(FOOTBALL_DATA_TO_CLUBELO["premier_league"]) == 23
    assert len(FOOTBALL_DATA_TO_CLUBELO["ligue1"]) == 21
    assert len(FOOTBALL_DATA_TO_CLUBELO["liga"]) == 23


def test_elo_mapping_covers_exactly_the_same_football_data_names_as_understat_mapping() -> None:
    """Le mapping ClubElo doit couvrir EXACTEMENT le meme ensemble de
    noms Football-Data que team_mapping.py (Understat, deja en
    production) pour chaque championnat - ni un club en trop, ni un
    club manquant."""
    for league, understat_table in FOOTBALL_DATA_TO_UNDERSTAT.items():
        assert set(FOOTBALL_DATA_TO_CLUBELO[league].keys()) == set(understat_table.keys()), (
            f"desaccord d'ensemble de cles Football-Data entre les mappings Understat et ClubElo pour {league!r}"
        )


def test_all_mapped_names_are_non_empty_and_distinct_within_each_league() -> None:
    """Aucune collision (deux equipes Football-Data associees au meme nom
    ClubElo) - anomalie qui romprait la jointure silencieusement."""
    for league, table in FOOTBALL_DATA_TO_CLUBELO.items():
        values = list(table.values())
        assert all(v.strip() for v in values), f"nom ClubElo vide dans {league!r}"
        assert len(set(values)) == len(values), f"collision de noms ClubElo dans {league!r}"
