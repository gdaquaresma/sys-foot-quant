"""Tests unitaires - jours de repos / congestion intra-championnat
(Brique 1, Phase I/E). Fixtures synthetiques minimales, jamais de lecture
de fichier reel - voir docstring du module pour le perimetre exact."""

from __future__ import annotations

from datetime import datetime

import pytest

from sys_foot_quant.data_engine.market_odds.fixture_congestion import (
    FixtureCongestionError,
    congestion_dataset_for_season,
    congestion_feature_for_match,
    rest_days_before_match,
    rest_days_diff,
)
from sys_foot_quant.data_engine.market_odds.match_catalog import MatchSummary

_COMPETITION = "ligue1"
_SEASON = "2025_26"


def _match(match_id: str, kickoff: datetime, home: str, away: str, is_played: bool = True) -> MatchSummary:
    return MatchSummary(
        match_id=match_id,
        competition=_COMPETITION,
        season=_SEASON,
        kickoff_utc=kickoff,
        home_team=home,
        away_team=away,
        is_played=is_played,
    )


# --- 1. Calcul correct des jours de repos -----------------------------------


def test_rest_days_computed_correctly_for_simple_case() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 16, 20, 0), "Marseille", "Nice")
    result = rest_days_before_match((m1, m2), m2, "Marseille")
    assert result.rest_days == pytest.approx(7.0)
    assert result.previous_match_id == "m1"
    assert result.previous_kickoff_utc == m1.kickoff_utc


def test_rest_days_handles_fractional_days_from_kickoff_time_of_day() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 12, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 12, 18, 0), "Marseille", "Nice")
    result = rest_days_before_match((m1, m2), m2, "Marseille")
    assert result.rest_days == pytest.approx(3.25)


# --- 2. Absence d'historique --------------------------------------------------


def test_no_prior_match_returns_explicit_none_not_zero() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    result = rest_days_before_match((m1,), m1, "Marseille")
    assert result.rest_days is None
    assert result.previous_match_id is None
    assert result.previous_kickoff_utc is None


# --- 3. Match precedent exactement identifie ---------------------------------


def test_previous_match_is_the_closest_one_not_the_oldest() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 16, 17, 0), "Nice", "Marseille")
    m3 = _match("m3", datetime(2025, 8, 23, 15, 0), "Marseille", "Brest")
    result = rest_days_before_match((m1, m2, m3), m3, "Marseille")
    assert result.previous_match_id == "m2"
    assert result.rest_days == pytest.approx(6.0 + 22 / 24)


# --- 4. Exclusion du match courant -------------------------------------------


def test_target_match_never_selected_as_its_own_previous_match() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    # m1 est a la fois la cible et present dans `matches` - ne doit jamais
    # se selectionner lui-meme (kickoff_utc < kickoff_utc est toujours
    # faux pour lui-meme, et match_id est explicitement exclu en plus).
    result = rest_days_before_match((m1,), m1, "Marseille")
    assert result.previous_match_id is None


def test_exclude_match_id_guard_is_redundant_with_strict_time_filter() -> None:
    # Un match dont le match_id est explicitement exclu mais dont le
    # kickoff serait (de facon artificielle) identique a celui de la
    # cible ne doit jamais etre selectionne non plus.
    target = _match("target", datetime(2025, 8, 16, 17, 0), "Marseille", "Nice")
    decoy = _match("target", datetime(2025, 8, 16, 17, 0), "Marseille", "Nice")
    result = rest_days_before_match((decoy,), target, "Marseille")
    assert result.previous_match_id is None


# --- 5. Exclusion de tout match futur ----------------------------------------


def test_future_match_never_selected_as_previous_match() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    future = _match("future", datetime(2025, 9, 1, 20, 0), "Marseille", "Brest")
    result = rest_days_before_match((m1, future), m1, "Marseille")
    assert result.previous_match_id is None  # m1 est le tout premier match, `future` ne doit jamais compter


# --- 6. Invariance PIT : un match futur ne change jamais la feature ---------


def test_adding_a_future_match_does_not_change_the_target_feature() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 16, 17, 0), "Marseille", "Nice")
    before = rest_days_before_match((m1, m2), m2, "Marseille")

    future = _match("future", datetime(2025, 9, 1, 20, 0), "Marseille", "Brest")
    after = rest_days_before_match((m1, m2, future), m2, "Marseille")

    assert before.rest_days == after.rest_days
    assert before.previous_match_id == after.previous_match_id


def test_modifying_a_future_match_kickoff_does_not_change_the_target_feature() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 16, 17, 0), "Marseille", "Nice")
    future_a = _match("future", datetime(2025, 9, 1, 20, 0), "Marseille", "Brest")
    future_b = _match("future", datetime(2025, 8, 17, 0, 0), "Marseille", "Brest")  # deplace mais toujours > m2

    result_a = rest_days_before_match((m1, m2, future_a), m2, "Marseille")
    result_b = rest_days_before_match((m1, m2, future_b), m2, "Marseille")
    assert result_a.rest_days == result_b.rest_days
    assert result_a.previous_match_id == result_b.previous_match_id


# --- 7. Cas domicile/exterieur ------------------------------------------------


def test_is_home_flag_reflects_the_team_role_in_the_target_match() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 16, 17, 0), "Nice", "Marseille")
    home_result = rest_days_before_match((m1, m2), m1, "Marseille")
    away_result = rest_days_before_match((m1, m2), m2, "Marseille")
    assert home_result.is_home is True
    assert away_result.is_home is False


def test_previous_match_lookup_is_identical_whether_team_was_home_or_away() -> None:
    # Le "dernier match" de Marseille doit etre trouve qu'il ait ete joue
    # a domicile ou a l'exterieur - l'historique d'une equipe n'est jamais
    # limite a ses seuls matchs a domicile (ou exterieur).
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Lyon", "Marseille")  # Marseille a l'exterieur
    m2 = _match("m2", datetime(2025, 8, 16, 17, 0), "Marseille", "Nice")  # Marseille a domicile
    result = rest_days_before_match((m1, m2), m2, "Marseille")
    assert result.previous_match_id == "m1"


def test_congestion_feature_for_match_combines_both_sides_independently() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 17, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 14, 17, 0), "Strasbourg", "Nice")
    target = _match("target", datetime(2025, 8, 16, 17, 0), "Marseille", "Strasbourg")

    feature = congestion_feature_for_match((m1, m2, target), target)
    assert feature.home_rest_days == pytest.approx(7.0)  # Marseille : m1 -> target
    assert feature.away_rest_days == pytest.approx(2.0)  # Strasbourg : m2 -> target
    assert feature.home_previous_match_id == "m1"
    assert feature.away_previous_match_id == "m2"


def test_rest_days_diff_is_home_minus_away() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 14, 20, 0), "Strasbourg", "Nice")
    target = _match("target", datetime(2025, 8, 16, 17, 0), "Marseille", "Strasbourg")
    feature = congestion_feature_for_match((m1, m2, target), target)
    assert rest_days_diff(feature) == pytest.approx(5.0)


def test_rest_days_diff_is_none_when_either_side_has_insufficient_history() -> None:
    target = _match("target", datetime(2025, 8, 16, 17, 0), "Marseille", "Strasbourg")
    feature = congestion_feature_for_match((target,), target)  # aucun historique pour les deux equipes
    assert feature.home_rest_days is None
    assert feature.away_rest_days is None
    assert rest_days_diff(feature) is None


# --- Garde-fous explicites ----------------------------------------------------


def test_raises_when_team_does_not_play_the_target_match() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    with pytest.raises(FixtureCongestionError):
        rest_days_before_match((m1,), m1, "Monaco")


def test_raises_when_matches_mix_a_different_competition_or_season() -> None:
    target = _match("target", datetime(2025, 8, 16, 17, 0), "Marseille", "Nice")
    other_season = MatchSummary(
        match_id="other", competition=_COMPETITION, season="2024_25",
        kickoff_utc=datetime(2025, 8, 9, 20, 0), home_team="Marseille", away_team="Lyon", is_played=True,
    )
    with pytest.raises(FixtureCongestionError):
        rest_days_before_match((other_season, target), target, "Marseille")


def test_congestion_dataset_for_season_raises_on_empty_matches() -> None:
    with pytest.raises(FixtureCongestionError):
        congestion_dataset_for_season(_COMPETITION, ())


def test_congestion_dataset_for_season_covers_every_match_deterministically() -> None:
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 16, 20, 0), "Marseille", "Nice")
    dataset = congestion_dataset_for_season(_COMPETITION, (m1, m2))
    assert [f.match_id for f in dataset] == ["m1", "m2"]
    assert dataset[0].home_rest_days is None  # premier match de Marseille
    assert dataset[1].home_rest_days == pytest.approx(7.0)

    # Determinisme : rejouer exactement le meme calcul donne exactement
    # le meme resultat (aucun etat global, aucun ordre d'iteration non
    # garanti).
    dataset_again = congestion_dataset_for_season(_COMPETITION, (m1, m2))
    assert dataset == dataset_again


# --- 8. Invariance a l'ordre des matchs en entree (audit, gap identifie) ----


def test_rest_days_is_invariant_to_the_order_of_matches_in_the_input_tuple() -> None:
    """``rest_days_before_match`` appelle ``max(prior, key=(kickoff_utc,
    match_id))`` sur les matchs eligibles (voir ``_team_matches_strictly_
    before``) - le choix du dernier match anterieur ne doit donc jamais
    dependre de la position de ce match dans le tuple ``matches`` fourni
    en entree, uniquement de son ``kickoff_utc``. Scenario volontairement
    construit pour que le dernier match pertinent de Marseille (``m3``)
    ne soit NI en premiere NI en derniere position dans l'ordre
    "original" - un bug d'implementation qui lirait silencieusement le
    premier/dernier element d'un iterable au lieu de calculer un vrai
    maximum passerait a cote de ce piege precis."""
    m1 = _match("m1", datetime(2025, 8, 9, 20, 0), "Marseille", "Lyon")
    m2 = _match("m2", datetime(2025, 8, 16, 17, 0), "Nice", "Marseille")
    m3 = _match("m3", datetime(2025, 8, 23, 15, 0), "Marseille", "Brest")  # dernier match anterieur pertinent
    other = _match("other", datetime(2025, 8, 12, 10, 0), "Lyon", "Nice")  # bruit : ne concerne pas Marseille
    target = _match("target", datetime(2025, 8, 30, 20, 0), "Marseille", "Monaco")

    original_order = (m1, other, m2, m3, target)  # m3 (la bonne reponse) ni premier ni dernier
    result_original = rest_days_before_match(original_order, target, "Marseille")

    # Deux melanges distincts de la MEME entree (tuple -> liste -> inversee,
    # et un second ordre arbitraire different) - jamais la meme permutation
    # que l'original, pour eviter qu'un test "trie" accidentellement.
    reversed_order = tuple(reversed(original_order))
    shuffled_order = (target, m2, other, m3, m1)

    result_reversed = rest_days_before_match(reversed_order, target, "Marseille")
    result_shuffled = rest_days_before_match(shuffled_order, target, "Marseille")

    # Le resultat attendu est connu independamment de l'ordre : le dernier
    # match anterieur reel de Marseille avant `target` est m3 (23 aout),
    # pas m1/m2 (plus anciens) ni `other`/`target` (hors scope/futur).
    assert result_original.previous_match_id == "m3"
    assert result_original.rest_days == pytest.approx(7.0 + 5 / 24)

    assert result_reversed == result_original
    assert result_shuffled == result_original
