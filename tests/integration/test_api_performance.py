"""Tests d'integration HTTP reels (Phase UI-2-B) pour ``GET /performance``
- requetes ASGI reelles via ``TestClient``, coherence stricte avec
``shadow_mode.journal.evaluate_shadow`` (INCHANGEE) : la route ne doit
JAMAIS recalculer ou filtrer quoi que ce soit, uniquement serialiser le
retour de cette fonction tel quel."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sys_foot_quant.api import routes_shadow
from sys_foot_quant.api.app import app
from sys_foot_quant.shadow_mode.journal import evaluate_shadow, record_prediction, settle_prediction

client = TestClient(app)

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "predict_match.py"
_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"

pytestmark = pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat reels non presents.")


def _load_predict_match():
    spec = importlib.util.spec_from_file_location("predict_match_for_api_performance_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def predict_match():
    return _load_predict_match()


@pytest.fixture
def fixture_journal_with_settled_observation(tmp_path, monkeypatch, predict_match):
    journal_path = tmp_path / "fixture_predictions.jsonl"
    output = predict_match.run_prediction(
        competition="liga",
        season="2024_25",
        home_team="Real Madrid",
        away_team="Barcelona",
        kickoff_utc=datetime(2024, 10, 26, 15, 0, 0),
        market_odds={"Over": 1.9, "Under": 1.9},
    )
    record, _already_existed = record_prediction(
        output,
        competition="liga",
        season="2024_25",
        home_team="Real Madrid",
        away_team="Barcelona",
        kickoff_utc=datetime(2024, 10, 26, 15, 0, 0),
        decision_offset_hours=2.0,
        market_odds_over_2_5=1.9,
        market_odds_under_2_5=1.9,
        journal_path=journal_path,
    )
    settle_prediction(record["prediction_id"], home_goals=2, away_goals=1, journal_path=journal_path)
    monkeypatch.setattr(routes_shadow, "DEFAULT_JOURNAL_PATH", journal_path)
    return journal_path


def test_performance_on_empty_journal_matches_evaluate_shadow_exactly(tmp_path, monkeypatch) -> None:
    absent_path = tmp_path / "absent.jsonl"
    monkeypatch.setattr(routes_shadow, "DEFAULT_JOURNAL_PATH", absent_path)
    response = client.get("/performance")
    assert response.status_code == 200
    body = response.json()
    direct = evaluate_shadow(absent_path)
    assert body == direct
    assert body["n_total"] == 0
    assert body["betting"]["n_bet"] == 0
    assert "echantillon insuffisant" in body["betting"]["message"]


def test_performance_with_fixture_observations_matches_evaluate_shadow_exactly(
    fixture_journal_with_settled_observation,
) -> None:
    response = client.get("/performance")
    assert response.status_code == 200
    body = response.json()
    direct = evaluate_shadow(fixture_journal_with_settled_observation)
    assert body == direct
    assert body["n_total"] == 1
    assert body["n_settled"] == 1


def test_performance_never_recomputes_or_adds_metrics(fixture_journal_with_settled_observation) -> None:
    """Aucune cle ni valeur supplementaire par rapport a ce que produit
    ``evaluate_shadow`` - preuve que l'API ne recalcule rien."""
    response = client.get("/performance")
    body = response.json()
    direct = evaluate_shadow(fixture_journal_with_settled_observation)
    assert set(body.keys()) == set(direct.keys())


def test_performance_accepts_no_temporal_filter_query_parameters() -> None:
    """``evaluate_shadow`` n'accepte structurellement aucun parametre de
    plage temporelle - un appel avec des parametres de ce type doit etre
    silencieusement ignore par FastAPI (aucun parametre declare sur la
    route), jamais interprete comme un filtre."""
    response = client.get("/performance", params={"start_date": "2024-01-01", "end_date": "2024-12-31"})
    assert response.status_code == 200
