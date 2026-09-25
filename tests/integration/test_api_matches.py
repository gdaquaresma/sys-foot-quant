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
    response = client.get("/matches", params={"competition": "ligue1", "season": "2026_27"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 36
    assert all(m["competition"] == "ligue1" and m["season"] == "2026_27" for m in body)


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
