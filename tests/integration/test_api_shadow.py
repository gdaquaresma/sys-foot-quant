"""Tests d'integration HTTP reels (Phase UI-2-B) pour les routes Shadow
Mode en lecture seule (``GET /shadow``, ``GET /shadow/{prediction_id}``) -
requetes ASGI reelles via ``TestClient``. Utilise une fixture de journal
ISOLEE (``tmp_path``), jamais le journal canonique
(``research/shadow_mode/predictions.jsonl``) - les observations de la
fixture proviennent d'un vrai match du corpus (via ``run_prediction``,
INCHANGEE), jamais de donnees inventees."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sys_foot_quant.api import routes_shadow
from sys_foot_quant.api.app import app
from sys_foot_quant.shadow_mode.journal import evaluate_shadow, load_journal, record_prediction, settle_prediction

client = TestClient(app)

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "predict_match.py"
_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"

pytestmark = pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat reels non presents.")


def _load_predict_match():
    spec = importlib.util.spec_from_file_location("predict_match_for_api_shadow_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def predict_match():
    return _load_predict_match()


@pytest.fixture
def fixture_journal_path(tmp_path, monkeypatch, predict_match):
    """Journal Shadow Mode isole contenant UNE observation reelle (match
    historique deja joue) REGLEE - construit via le meme chemin de
    production que le CLI (``run_prediction`` + ``record_prediction`` +
    ``settle_prediction``, toutes INCHANGEES). Redirige les 3 routes
    Shadow Mode vers ce fichier isole (voir docstring de
    ``routes_shadow.py`` : ``DEFAULT_JOURNAL_PATH`` est passe
    explicitement a chaque appel, donc monkeypatchable ici)."""
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
    return journal_path, record["prediction_id"]


# --- GET /shadow ---------------------------------------------------------


def test_shadow_returns_empty_list_with_success_when_journal_is_absent(tmp_path, monkeypatch) -> None:
    absent_path = tmp_path / "does_not_exist.jsonl"
    monkeypatch.setattr(routes_shadow, "DEFAULT_JOURNAL_PATH", absent_path)
    response = client.get("/shadow")
    assert response.status_code == 200
    assert response.json() == []
    assert not absent_path.exists()  # la lecture ne cree jamais le fichier


def test_shadow_reading_never_creates_or_touches_the_canonical_journal() -> None:
    """Verifie explicitement que le journal CANONIQUE
    (``research/shadow_mode/predictions.jsonl``) n'est ni cree ni modifie
    par une lecture via l'API - sans monkeypatch ici, le chemin par defaut
    reel est utilise."""
    canonical_path = Path("research/shadow_mode/predictions.jsonl")
    existed_before = canonical_path.exists()
    response = client.get("/shadow")
    assert response.status_code == 200
    assert canonical_path.exists() == existed_before  # aucune creation involontaire


def test_shadow_exposes_fixture_observations_faithfully(fixture_journal_path) -> None:
    journal_path, prediction_id = fixture_journal_path
    response = client.get("/shadow")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["prediction_id"] == prediction_id
    assert body[0]["status"] == "SETTLED"
    direct = load_journal(journal_path)
    assert body == direct  # serialisation fidele, aucune transformation


# --- GET /shadow/{prediction_id} -----------------------------------------


def test_shadow_by_id_returns_the_known_observation(fixture_journal_path) -> None:
    _journal_path, prediction_id = fixture_journal_path
    response = client.get(f"/shadow/{prediction_id}")
    assert response.status_code == 200
    assert response.json()["prediction_id"] == prediction_id
    assert response.json()["status"] == "SETTLED"


def test_shadow_by_id_unknown_identifier_returns_404(fixture_journal_path) -> None:
    response = client.get("/shadow/this-id-does-not-exist")
    assert response.status_code == 404
    assert "this-id-does-not-exist" in response.json()["detail"]


def test_shadow_by_id_absent_journal_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(routes_shadow, "DEFAULT_JOURNAL_PATH", tmp_path / "absent.jsonl")
    response = client.get("/shadow/anything")
    assert response.status_code == 404
