"""Tests d'integration HTTP reels (Phase UI-2-B) pour les routes du
catalogue de matchs (``GET /matches``, ``GET /matches/{match_id}``) -
envoie de veritables requetes ASGI via ``TestClient`` (jamais un appel
direct des fonctions Python de route) et verifie les reponses HTTP
(code, corps JSON) ainsi que la coherence stricte avec un appel direct de
``match_catalog.list_matches`` (fonction metier reutilisee, INCHANGEE)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sys_foot_quant.api.app import app
from sys_foot_quant.data_engine.market_odds import match_catalog

client = TestClient(app)


# --- GET /matches ------------------------------------------------------------


def test_get_matches_with_valid_parameters_returns_200_and_the_full_catalogue() -> None:
    """EXTENSION (integration du catalogue de fixtures futures) : le
    catalogue fusionne pour ligue1/2026_27 contient desormais les 36
    matchs Understat deja joues (D) PLUS les 261 fixtures futures B/C
    d'OpenFootball (69 B + 192 C, is_played=False - voir
    docs/future_fixture_catalog_2026_27.md) - jamais les 45 matchs "joues"
    cote OpenFootball (deja couverts, de facon faisant autorite, par
    Understat)."""
    response = client.get("/matches", params={"competition": "ligue1", "season": "2026_27"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 297
    assert all(m["competition"] == "ligue1" and m["season"] == "2026_27" for m in body)
    assert sum(1 for m in body if m["is_played"]) == 36
    assert sum(1 for m in body if not m["is_played"]) == 261


def test_get_matches_missing_required_parameters_returns_422() -> None:
    response = client.get("/matches")
    assert response.status_code == 422


def test_get_matches_missing_season_only_returns_422() -> None:
    response = client.get("/matches", params={"competition": "ligue1"})
    assert response.status_code == 422


def test_get_matches_unknown_competition_returns_explicit_error() -> None:
    response = client.get("/matches", params={"competition": "bundesliga", "season": "2024_25"})
    assert response.status_code == 400
    assert "bundesliga" in response.json()["detail"]


def test_get_matches_unknown_season_returns_explicit_error() -> None:
    response = client.get("/matches", params={"competition": "ligue1", "season": "2099_00"})
    assert response.status_code == 400
    assert "2099_00" in response.json()["detail"]


def test_get_matches_http_response_matches_direct_business_function_call() -> None:
    """Coherence stricte : la reponse HTTP doit correspondre exactement a
    un appel direct de ``match_catalog.list_matches`` (fonction metier
    reutilisee, jamais recopiee)."""
    response = client.get("/matches", params={"competition": "liga", "season": "2024_25"})
    assert response.status_code == 200
    body = response.json()
    direct = match_catalog.list_matches("liga", "2024_25")
    assert len(body) == len(direct)
    assert [m["match_id"] for m in body] == [m.match_id for m in direct]
    assert [m["home_team"] for m in body] == [m.home_team for m in direct]
    assert [m["away_team"] for m in body] == [m.away_team for m in direct]


# --- GET /matches/{match_id} -------------------------------------------------


def test_get_match_by_id_with_competition_and_season_returns_the_match() -> None:
    response = client.get(
        "/matches/31975", params={"competition": "ligue1", "season": "2026_27"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["home_team"] == "Brest"
    assert body["away_team"] == "Paris Saint Germain"
    assert body["match_id"] == "31975"


def test_get_match_by_id_unknown_returns_404() -> None:
    response = client.get(
        "/matches/999999999", params={"competition": "ligue1", "season": "2026_27"}
    )
    assert response.status_code == 404
    assert "999999999" in response.json()["detail"]


def test_get_match_by_id_requires_competition_and_season() -> None:
    response = client.get("/matches/31975")
    assert response.status_code == 422


def test_get_match_by_id_never_searches_globally_across_competitions() -> None:
    """31975 (Brest-PSG, Ligue 1) n'existe pas dans le corpus 'liga' -
    prouve que la recherche reste STRICTEMENT bornee au perimetre fourni,
    jamais une recherche implicite sur tout le catalogue."""
    response = client.get(
        "/matches/31975", params={"competition": "liga", "season": "2024_25"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("competition,season", [("bundesliga", "2024_25"), ("ligue1", "2099_00")])
def test_get_match_by_id_unknown_competition_or_season_returns_explicit_error(competition, season) -> None:
    response = client.get("/matches/31975", params={"competition": competition, "season": season})
    assert response.status_code == 400


# --- EXTENSION : integration du catalogue de fixtures futures (2026/27) -----
#
# Etat B : heure locale publiee mais kickoff_utc absent (Lens-Lyon, 9
# octobre 2026 - voir tests/integration/test_future_fixture_catalog_real_files.py).
# Etat C : aucune heure publiee (Lens-Le Havre, 5 decembre 2026 - idem).

_REAL_STATE_B_MATCH_ID = "ligue1:2026_27:Lens_vs_Lyon:2026-10-09T20:45:00"
_REAL_STATE_C_MATCH_ID = "ligue1:2026_27:Lens_vs_Le Havre:2026-12-05"


def test_get_matches_includes_a_real_state_b_future_fixture_with_null_kickoff_utc() -> None:
    response = client.get("/matches", params={"competition": "ligue1", "season": "2026_27"})
    assert response.status_code == 200
    body = response.json()
    match = next(m for m in body if m["match_id"] == _REAL_STATE_B_MATCH_ID)
    assert match["home_team"] == "Lens"
    assert match["away_team"] == "Lyon"
    assert match["fixture_date"] == "2026-10-09"
    assert match["kickoff_local_naive"] == "2026-10-09T20:45:00"
    assert match["kickoff_utc"] is None
    assert match["is_played"] is False


def test_get_matches_includes_a_real_state_c_future_fixture_with_null_kickoff_local_naive() -> None:
    response = client.get("/matches", params={"competition": "ligue1", "season": "2026_27"})
    assert response.status_code == 200
    body = response.json()
    match = next(m for m in body if m["match_id"] == _REAL_STATE_C_MATCH_ID)
    assert match["home_team"] == "Lens"
    assert match["away_team"] == "Le Havre"
    assert match["fixture_date"] == "2026-12-05"
    assert match["kickoff_local_naive"] is None
    assert match["kickoff_utc"] is None
    assert match["is_played"] is False


def test_get_match_by_id_finds_a_real_state_b_future_fixture() -> None:
    response = client.get(
        f"/matches/{_REAL_STATE_B_MATCH_ID}", params={"competition": "ligue1", "season": "2026_27"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kickoff_utc"] is None
    assert body["kickoff_local_naive"] == "2026-10-09T20:45:00"


def test_get_match_by_id_finds_a_real_state_c_future_fixture() -> None:
    response = client.get(
        f"/matches/{_REAL_STATE_C_MATCH_ID}", params={"competition": "ligue1", "season": "2026_27"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kickoff_utc"] is None
    assert body["kickoff_local_naive"] is None


def test_get_match_by_id_still_finds_a_real_already_played_d_match_unchanged() -> None:
    """Non-regression explicite : un match D (deja analysable) reste
    trouve et inchange apres la fusion du catalogue."""
    response = client.get("/matches/31975", params={"competition": "ligue1", "season": "2026_27"})
    assert response.status_code == 200
    body = response.json()
    assert body["home_team"] == "Brest"
    assert body["away_team"] == "Paris Saint Germain"
    assert body["is_played"] is True
    assert body["kickoff_utc"] is not None


def test_get_matches_invalid_id_absent_from_catalogue_still_returns_404() -> None:
    response = client.get(
        "/matches/does-not-exist-anywhere", params={"competition": "ligue1", "season": "2026_27"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("competition,expected_count", [("premier_league", 265), ("liga", 223)])
def test_get_matches_for_2026_27_with_partially_unresolved_clubs_now_returns_200(
    competition: str, expected_count: int
) -> None:
    """EXTENSION (resolution partielle du catalogue de fixtures futures) :
    premier_league/liga 2026_27 ne refusent PLUS globalement a cause de
    Coventry City/Hull City/Malaga/Deportivo/Racing Santander - les
    fixtures RESOLUES (ex. Arsenal-Leeds) restent accessibles, seules les
    fixtures impliquant une equipe non resolue sont absentes (voir
    ``routes_matches._list_catalog_entries`` pour la limite documentee)."""
    response = client.get("/matches", params={"competition": competition, "season": "2026_27"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == expected_count
    assert all(m["is_played"] is False for m in body)


@pytest.mark.parametrize(
    "competition,home_openfootball,away_openfootball",
    [("premier_league", "Arsenal FC", "Coventry City FC"), ("liga", "Real Racing Club de Santander", "Villarreal CF")],
)
def test_get_matches_never_exposes_a_fixture_with_an_unresolved_team(
    competition: str, home_openfootball: str, away_openfootball: str
) -> None:
    """Garde-fou explicite : aucune fixture dont une equipe est non
    resolue n'apparait dans la reponse HTTP - meme nom brut OpenFootball
    inclus, pour prouver qu'aucune des deux graphies (resolue ou brute)
    ne fuite dans le catalogue produit tant que l'equipe reste non
    verifiee."""
    response = client.get("/matches", params={"competition": competition, "season": "2026_27"})
    assert response.status_code == 200
    body = response.json()
    assert not any(home_openfootball in m["home_team"] or away_openfootball in m["away_team"] for m in body)


def test_get_match_by_id_for_an_unresolved_fixture_returns_404_not_a_server_error() -> None:
    """Une fixture non resolue (Hull City - Everton, 11 octobre 2026,
    etat B, Premier League) n'est PAS exposee par le catalogue fusionne -
    sa recherche par id doit donc se comporter EXACTEMENT comme un match
    inexistant (404), jamais une erreur serveur, jamais une tentative de
    la construire a la volee."""
    match_id = "premier_league:2026_27:Hull City AFC_vs_Everton:2026-10-11T14:00:00"
    response = client.get(f"/matches/{match_id}", params={"competition": "premier_league", "season": "2026_27"})
    assert response.status_code == 404


def test_get_matches_other_seasons_are_never_merged_with_future_fixtures() -> None:
    """Garde-fou explicite : la fusion ne s'applique JAMAIS a une saison
    autre que FUTURE_FIXTURE_SEASON, meme pour une competition enregistree
    dans future_fixture_catalog."""
    response = client.get("/matches", params={"competition": "liga", "season": "2024_25"})
    assert response.status_code == 200
    direct = match_catalog.list_matches("liga", "2024_25")
    assert len(response.json()) == len(direct)
