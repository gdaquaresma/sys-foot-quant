"""Tests pour ``data_engine.market_odds.match_catalog`` (Phase UI-2-A) :
catalogue en lecture seule des matchs/equipes disponibles, futur support de
l'explorateur de matchs du site web. Verifie explicitement l'absence de
melange entre competitions, le comportement de refus explicite sur des
parametres/donnees invalides, et la non-modification des sources lues."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sys_foot_quant.data_engine.market_odds import match_catalog

_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"
_LIGUE1_2024_PATH = _UNDERSTAT_DIR / "ligue1_2024_datesData.json"
_LIGUE1_2026_PATH = _UNDERSTAT_DIR / "ligue1_2026_datesData.json"
_LIGA_2024_PATH = _UNDERSTAT_DIR / "liga_2024_datesData.json"

pytestmark = pytest.mark.skipif(
    not (_LIGUE1_2024_PATH.exists() and _LIGUE1_2026_PATH.exists() and _LIGA_2024_PATH.exists()),
    reason="Fichiers Understat reels non presents.",
)


# --- 1. enumeration des matchs pour une competition/saison valides ---------


def test_list_matches_returns_all_matches_for_a_valid_selection() -> None:
    with open(_LIGUE1_2024_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    matches = match_catalog.list_matches("ligue1", "2024_25")
    assert len(matches) == len(raw)
    assert all(isinstance(m, match_catalog.MatchSummary) for m in matches)


def test_list_matches_2026_27_returns_only_the_current_season_file_not_the_training_aggregate() -> None:
    """Verifie explicitement la separation avec predict_match._CURRENT_SEASON_SOURCES
    (qui agrege 3 fichiers pour l'entrainement) - ce catalogue doit retourner
    UNIQUEMENT les 36 matchs reels de la saison 2026/27 elle-meme, jamais
    ~650 matchs agregeant l'historique."""
    with open(_LIGUE1_2026_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    matches = match_catalog.list_matches("ligue1", "2026_27")
    assert len(matches) == len(raw) == 36
    assert all(m.season == "2026_27" for m in matches)


def test_list_matches_includes_the_real_brest_psg_match() -> None:
    matches = match_catalog.list_matches("ligue1", "2026_27")
    brest_psg = next((m for m in matches if m.match_id == "31975"), None)
    assert brest_psg is not None
    assert brest_psg.home_team == "Brest"
    assert brest_psg.away_team == "Paris Saint Germain"
    assert brest_psg.kickoff_utc == datetime(2026, 9, 13, 18, 45, 0, tzinfo=timezone.utc)


# --- 2. extraction des equipes reellement presentes -------------------------


def test_list_teams_returns_teams_actually_present_in_the_matches() -> None:
    teams = match_catalog.list_teams("ligue1", "2026_27")
    matches = match_catalog.list_matches("ligue1", "2026_27")
    expected = {m.home_team for m in matches} | {m.away_team for m in matches}
    assert set(teams) == expected
    assert "Brest" in teams
    assert "Paris Saint Germain" in teams


# --- 3. absence de doublons injustifies -------------------------------------


def test_list_teams_has_no_duplicates() -> None:
    teams = match_catalog.list_teams("ligue1", "2024_25")
    assert len(teams) == len(set(teams))


def test_list_matches_has_no_duplicate_match_ids() -> None:
    matches = match_catalog.list_matches("ligue1", "2024_25")
    ids = [m.match_id for m in matches]
    assert len(ids) == len(set(ids))


# --- 4. respect de la separation entre competitions -------------------------


def test_list_matches_never_mixes_competitions() -> None:
    ligue1_matches = match_catalog.list_matches("ligue1", "2024_25")
    liga_matches = match_catalog.list_matches("liga", "2024_25")
    assert all(m.competition == "ligue1" for m in ligue1_matches)
    assert all(m.competition == "liga" for m in liga_matches)
    ligue1_ids = {m.match_id for m in ligue1_matches}
    liga_ids = {m.match_id for m in liga_matches}
    assert ligue1_ids.isdisjoint(liga_ids)


def test_list_teams_never_mixes_competitions() -> None:
    ligue1_teams = set(match_catalog.list_teams("ligue1", "2024_25"))
    liga_teams = set(match_catalog.list_teams("liga", "2024_25"))
    # Paris Saint Germain (Ligue 1) ne doit jamais apparaitre dans la liste Liga.
    assert "Paris Saint Germain" in ligue1_teams
    assert "Paris Saint Germain" not in liga_teams


# --- 5. competition inconnue -------------------------------------------------


def test_list_matches_rejects_unknown_competition() -> None:
    with pytest.raises(match_catalog.MatchCatalogError, match="Competition inconnue"):
        match_catalog.list_matches("bundesliga", "2024_25")


def test_list_teams_rejects_unknown_competition() -> None:
    with pytest.raises(match_catalog.MatchCatalogError):
        match_catalog.list_teams("bundesliga", "2024_25")


def test_list_matches_rejects_a_competition_not_available_for_the_current_season() -> None:
    """``premier_league``/``liga`` n'ont pas de fichier 2026/27 dans ce
    catalogue (seul ``ligue1`` en a un) - refus explicite, jamais un
    catalogue vide silencieux."""
    with pytest.raises(match_catalog.MatchCatalogError, match="Competition inconnue"):
        match_catalog.list_matches("premier_league", "2026_27")


# --- 6. saison inconnue ------------------------------------------------------


def test_list_matches_rejects_unknown_season() -> None:
    with pytest.raises(match_catalog.MatchCatalogError, match="Saison inconnue"):
        match_catalog.list_matches("ligue1", "2099_00")


# --- 7. fichier absent / donnees invalides ----------------------------------


def test_list_matches_rejects_a_missing_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(
        match_catalog._SEASON_FILES,
        "2024_25",
        {**match_catalog._SEASON_FILES["2024_25"], "ligue1": ("Ligue_1", tmp_path / "absent.json")},
    )
    with pytest.raises(match_catalog.MatchCatalogError, match="introuvable"):
        match_catalog.list_matches("ligue1", "2024_25")


def test_list_matches_rejects_corrupted_json(monkeypatch, tmp_path) -> None:
    bad_file = tmp_path / "corrupted.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setitem(
        match_catalog._SEASON_FILES,
        "2024_25",
        {**match_catalog._SEASON_FILES["2024_25"], "ligue1": ("Ligue_1", bad_file)},
    )
    with pytest.raises(match_catalog.MatchCatalogError, match="corrompu"):
        match_catalog.list_matches("ligue1", "2024_25")


def test_list_matches_rejects_a_match_entry_missing_required_fields(monkeypatch, tmp_path) -> None:
    """Une entree malformee (ici : cle 'a' absente) ne doit jamais etre
    silencieusement ignoree ou transformee en donnee par defaut - refus
    explicite (Etape C : "ne pas transformer silencieusement des donnees
    invalides en donnees valides")."""
    bad_file = tmp_path / "malformed.json"
    bad_file.write_text(
        json.dumps([{"id": "1", "isResult": True, "h": {"id": "1", "title": "Equipe A"}, "datetime": "2024-08-16 18:45:00"}]),
        encoding="utf-8",
    )
    monkeypatch.setitem(
        match_catalog._SEASON_FILES,
        "2024_25",
        {**match_catalog._SEASON_FILES["2024_25"], "ligue1": ("Ligue_1", bad_file)},
    )
    with pytest.raises(match_catalog.MatchCatalogError, match="invalide"):
        match_catalog.list_matches("ligue1", "2024_25")


def test_list_matches_rejects_a_non_list_json_payload(monkeypatch, tmp_path) -> None:
    bad_file = tmp_path / "not_a_list.json"
    bad_file.write_text(json.dumps({"unexpected": "object"}), encoding="utf-8")
    monkeypatch.setitem(
        match_catalog._SEASON_FILES,
        "2024_25",
        {**match_catalog._SEASON_FILES["2024_25"], "ligue1": ("Ligue_1", bad_file)},
    )
    with pytest.raises(match_catalog.MatchCatalogError, match="Format inattendu"):
        match_catalog.list_matches("ligue1", "2024_25")


# --- 8. coherence des dates retournees --------------------------------------


def test_list_matches_are_sorted_chronologically() -> None:
    matches = match_catalog.list_matches("ligue1", "2024_25")
    kickoffs = [m.kickoff_utc for m in matches]
    assert kickoffs == sorted(kickoffs)


def test_list_matches_kickoff_utc_is_timezone_aware() -> None:
    matches = match_catalog.list_matches("ligue1", "2026_27")
    assert all(m.kickoff_utc.tzinfo is not None for m in matches)


def test_is_played_reflects_is_result_without_inventing_a_status(tmp_path, monkeypatch) -> None:
    """Aucun fichier canonique reel ne contient de match non joue
    (isResult=false) a ce jour (constat verifie, voir docstring du module)
    - ce test utilise donc une fixture isolee pour prouver que le champ
    ``is_played`` refleterait fidelement un futur match non joue, sans
    inventer un statut ni s'appuyer sur des donnees canoniques modifiees."""
    fixture_file = tmp_path / "fixture_with_unplayed_match.json"
    fixture_file.write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "isResult": True,
                    "h": {"id": "1", "title": "Equipe A"},
                    "a": {"id": "2", "title": "Equipe B"},
                    "datetime": "2024-08-16 18:45:00",
                },
                {
                    "id": "2",
                    "isResult": False,
                    "h": {"id": "3", "title": "Equipe C"},
                    "a": {"id": "4", "title": "Equipe D"},
                    "datetime": "2099-01-01 12:00:00",
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(
        match_catalog._SEASON_FILES,
        "2024_25",
        {**match_catalog._SEASON_FILES["2024_25"], "ligue1": ("Ligue_1", fixture_file)},
    )
    matches = match_catalog.list_matches("ligue1", "2024_25")
    assert len(matches) == 2
    played = next(m for m in matches if m.match_id == "1")
    unplayed = next(m for m in matches if m.match_id == "2")
    assert played.is_played is True
    assert unplayed.is_played is False


# --- 9. absence de modification des donnees sources -------------------------


def test_list_matches_does_not_modify_the_source_file() -> None:
    original_bytes = _LIGUE1_2024_PATH.read_bytes()
    match_catalog.list_matches("ligue1", "2024_25")
    assert _LIGUE1_2024_PATH.read_bytes() == original_bytes


def test_list_matches_is_deterministic_across_repeated_calls() -> None:
    first = match_catalog.list_matches("ligue1", "2024_25")
    second = match_catalog.list_matches("ligue1", "2024_25")
    assert first == second


# --- 10. compatibilite avec les formats de donnees reellement presents -----


@pytest.mark.parametrize("competition,season", [
    ("ligue1", "2024_25"), ("premier_league", "2024_25"), ("liga", "2024_25"),
    ("ligue1", "2025_26"), ("premier_league", "2025_26"), ("liga", "2025_26"),
    ("ligue1", "2026_27"),
])
def test_list_matches_works_for_every_real_canonical_file(competition, season) -> None:
    matches = match_catalog.list_matches(competition, season)
    assert len(matches) > 0
    assert all(m.match_id for m in matches)
    assert all(m.home_team and m.away_team for m in matches)


def test_list_competitions_and_list_seasons_match_module_constants() -> None:
    assert match_catalog.list_competitions() == match_catalog.COMPETITIONS
    assert match_catalog.list_seasons() == match_catalog.SEASONS
    assert "2026_27" in match_catalog.list_seasons()
    assert "ligue1" in match_catalog.list_competitions()


# --- non-regression : separation stricte d'avec predict_match.py -----------


def test_module_does_not_import_predict_match_script() -> None:
    """Garde-fou statique : ce catalogue ne doit jamais dependre de
    ``scripts/predict_match.py`` (script isole, pas une bibliotheque) -
    aucun couplage, aucun risque de second chemin de prediction. Seule la
    mention en prose (docstring, pour expliquer la separation des roles)
    est autorisee - aucune ligne ``import``/``from`` ne doit reference
    ``predict_match``."""
    source_lines = Path(match_catalog.__file__).read_text().splitlines()
    import_lines = [
        line for line in source_lines
        if (line.strip().startswith("import ") or line.strip().startswith("from ")) and "predict_match" in line
    ]
    assert import_lines == []
