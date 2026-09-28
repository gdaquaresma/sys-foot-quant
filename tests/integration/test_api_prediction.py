"""Tests d'integration HTTP reels pour ``GET /matches/{match_id}/prediction``
(integration moteur -> API) - requetes ASGI reelles via ``TestClient``.
Verifie que la route se contente d'orchestrer ``match_catalog`` +
``prediction_adapter.run_prediction`` (INCHANGES) sans jamais dupliquer de
logique scientifique, et que ``kickoff_utc``/``decision_offset_hours``/
``min_edge_threshold`` ne peuvent jamais etre controles par le client."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from sys_foot_quant.api import routes_prediction
from sys_foot_quant.api.app import app
from sys_foot_quant.data_engine.market_odds import match_catalog

client = TestClient(app)

_UNDERSTAT_DIR_EXISTS = match_catalog._SEASON_FILES["2026_27"]["ligue1"][1].exists()
pytestmark = pytest.mark.skipif(not _UNDERSTAT_DIR_EXISTS, reason="Fichiers Understat reels non presents.")

_REAL_MATCH_ID = "31975"  # Brest - Paris Saint Germain, 2026-09-13 18:45:00


def _spy_on_run_prediction(monkeypatch):
    """Espionne ``run_prediction`` sans changer son comportement (appelle
    la fonction reelle) - permet de verifier les arguments transmis sans
    jamais mocker la logique scientifique elle-meme."""
    calls: list[dict] = []
    original = routes_prediction.run_prediction

    def _spy(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(routes_prediction, "run_prediction", _spy)
    return calls


# --- 1. match valide -> appel du moteur avec les bonnes donnees du catalogue -


def test_valid_match_calls_the_engine_with_real_catalog_data(monkeypatch) -> None:
    calls = _spy_on_run_prediction(monkeypatch)
    response = client.get(f"/matches/{_REAL_MATCH_ID}/prediction", params={"competition": "ligue1", "season": "2026_27"})

    assert response.status_code == 200
    assert len(calls) == 1
    call = calls[0]
    assert call["competition"] == "ligue1"
    assert call["season"] == "2026_27"
    assert call["home_team"] == "Brest"
    assert call["away_team"] == "Paris Saint Germain"
    assert call["kickoff_utc"] == datetime(2026, 9, 13, 18, 45, 0)  # naif, reel, issu du catalogue

    body = response.json()
    assert body["match_id"]  # genere par run_prediction, present
    assert body["primary_model"] == "poisson_simple"
    assert set(body["models"].keys()) == {"poisson_simple", "dixon_coles", "xg_model"}


# --- 2. match inconnu -> 404 -------------------------------------------------


def test_unknown_match_id_returns_404() -> None:
    response = client.get("/matches/999999999/prediction", params={"competition": "ligue1", "season": "2026_27"})
    assert response.status_code == 404
    assert "999999999" in response.json()["detail"]


# --- 3. competition/saison invalide -> erreur API coherente ------------------


def test_unknown_competition_returns_400() -> None:
    response = client.get(f"/matches/{_REAL_MATCH_ID}/prediction", params={"competition": "bundesliga", "season": "2024_25"})
    assert response.status_code == 400
    assert "bundesliga" in response.json()["detail"]


def test_unknown_season_returns_400() -> None:
    response = client.get(f"/matches/{_REAL_MATCH_ID}/prediction", params={"competition": "ligue1", "season": "2099_00"})
    assert response.status_code == 400


def test_missing_required_parameters_returns_422() -> None:
    response = client.get(f"/matches/{_REAL_MATCH_ID}/prediction")
    assert response.status_code == 422


# --- 4. aucune cote -> le moteur recoit market_odds=None, reponse normale ---


def test_no_odds_passes_none_to_the_engine_and_returns_a_normal_response(monkeypatch) -> None:
    calls = _spy_on_run_prediction(monkeypatch)
    response = client.get(f"/matches/{_REAL_MATCH_ID}/prediction", params={"competition": "ligue1", "season": "2026_27"})

    assert response.status_code == 200
    assert calls[0]["market_odds"] is None
    body = response.json()
    assert body["market"] is None
    assert "MARKET_DATA_UNAVAILABLE" in body["decision"]["decision_reason"]


# --- 5. une seule cote -> rejet ----------------------------------------------


def test_single_odds_value_is_rejected() -> None:
    response = client.get(
        f"/matches/{_REAL_MATCH_ID}/prediction",
        params={"competition": "ligue1", "season": "2026_27", "over_2_5": "1.9"},
    )
    assert response.status_code == 400


# --- 6. cote invalide -> rejet ------------------------------------------------


def test_invalid_odds_value_is_rejected() -> None:
    response = client.get(
        f"/matches/{_REAL_MATCH_ID}/prediction",
        params={"competition": "ligue1", "season": "2026_27", "over_2_5": "0.5", "under_2_5": "1.9"},
    )
    assert response.status_code == 400


def test_valid_odds_are_accepted_and_transmitted(monkeypatch) -> None:
    calls = _spy_on_run_prediction(monkeypatch)
    response = client.get(
        f"/matches/{_REAL_MATCH_ID}/prediction",
        params={"competition": "ligue1", "season": "2026_27", "over_2_5": "1.9", "under_2_5": "1.9"},
    )
    assert response.status_code == 200
    assert calls[0]["market_odds"] == {"Over": 1.9, "Under": 1.9}


# --- 7. kickoff_utc client ignore --------------------------------------------


def test_client_supplied_kickoff_utc_is_ignored(monkeypatch) -> None:
    calls = _spy_on_run_prediction(monkeypatch)
    response = client.get(
        f"/matches/{_REAL_MATCH_ID}/prediction",
        params={"competition": "ligue1", "season": "2026_27", "kickoff_utc": "2099-01-01T00:00:00"},
    )
    assert response.status_code == 200
    # Le kickoff transmis au moteur reste le VRAI kickoff du catalogue,
    # jamais la valeur fantaisiste fournie en parametre de requete.
    assert calls[0]["kickoff_utc"] == datetime(2026, 9, 13, 18, 45, 0)


# --- 8. decision_offset_hours non controlable --------------------------------


def test_client_cannot_control_decision_offset_hours(monkeypatch) -> None:
    calls = _spy_on_run_prediction(monkeypatch)
    response = client.get(
        f"/matches/{_REAL_MATCH_ID}/prediction",
        params={"competition": "ligue1", "season": "2026_27", "decision_offset_hours": "0"},
    )
    assert response.status_code == 200
    # La route ne transmet jamais ce parametre - absent des kwargs recus
    # par run_prediction, quelle que soit la valeur fournie par le client.
    assert "decision_offset_hours" not in calls[0]


# --- 9. min_edge_threshold non controlable -----------------------------------


def test_client_cannot_control_min_edge_threshold(monkeypatch) -> None:
    calls = _spy_on_run_prediction(monkeypatch)
    response = client.get(
        f"/matches/{_REAL_MATCH_ID}/prediction",
        params={"competition": "ligue1", "season": "2026_27", "min_edge_threshold": "0.5", "operational_thresholds": "anything"},
    )
    assert response.status_code == 200
    assert "min_edge_threshold" not in calls[0]
    assert "operational_thresholds" not in calls[0]
    # Comportement reel inchange : NO_BET toujours du a EDGE_BELOW_THRESHOLD,
    # jamais influence par le parametre fantaisiste fourni.
    assert "EDGE_BELOW_THRESHOLD" in response.json()["decision"]["decision_reason"]


def test_no_prediction_route_parameter_named_like_a_scientific_threshold() -> None:
    """Garde-fou structurel : le schema OpenAPI reel de la route ne declare
    aucun parametre nomme d'apres un seuil scientifique."""
    schema = client.get("/openapi.json").json()
    route_schema = schema["paths"]["/matches/{match_id}/prediction"]["get"]
    forbidden = ("min_edge_threshold", "operational_thresholds", "decision_offset_hours", "kickoff_utc")
    declared_params = {p["name"] for p in route_schema.get("parameters", [])}
    assert declared_params.isdisjoint(forbidden)


# --- 10. NO_BET est une reponse valide (200), jamais une erreur --------------


def test_no_bet_is_returned_as_a_valid_200_response_not_an_error() -> None:
    response = client.get(f"/matches/{_REAL_MATCH_ID}/prediction", params={"competition": "ligue1", "season": "2026_27"})
    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == "NO_BET"
    assert len(body["decision"]["decision_reason"]) > 0
