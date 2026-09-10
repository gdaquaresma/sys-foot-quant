"""R4 - validation finale du MVP (production, pas une nouvelle campagne
scientifique) : reproductibilite, scenario shadow (match dont le kickoff
est posterieur a TOUT le corpus disponible), garde-fous decisionnels
(aucun BET ne peut etre obtenu via la CLI, quelle que soit la cote
fournie), et absence de dependance cachee a l'heure courante/au reseau/a
l'alea dans le chemin de production (R1+R2+R3+final_engine).

Ne re-verifie PAS le mecanisme point-in-time lui-meme (deja prouve par
R1/R2/R3 - tests/leakage/test_calibration_dataset_point_in_time.py,
test_future_match_dataset_point_in_time.py,
test_predict_match_point_in_time.py)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "predict_match.py"
_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"
_SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "sys_foot_quant"


def _load_predict_match():
    spec = importlib.util.spec_from_file_location("predict_match_for_r4_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def predict_match():
    return _load_predict_match()


@pytest.fixture(scope="module")
def liga_2025_raw():
    with open(_UNDERSTAT_DIR / "liga_2025_datesData.json") as f:
        return json.load(f)


pytestmark = pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat reels non presents.")


# --- 5. reproductibilite ----------------------------------------------------


def test_same_inputs_produce_byte_identical_report(predict_match, liga_2025_raw) -> None:
    kwargs = dict(
        competition="liga",
        season="2025_26",
        home_team="Barcelona",
        away_team="Atletico Madrid",
        kickoff_utc=datetime(2026, 6, 20, 20, 0, 0),
        market_odds={"Over": 1.8, "Under": 2.0},
    )
    output_1 = predict_match.run_prediction(**kwargs)
    output_2 = predict_match.run_prediction(**kwargs)

    assert predict_match.format_decision_report(output_1) == predict_match.format_decision_report(output_2)
    assert output_1.models["poisson_simple"].lam == output_2.models["poisson_simple"].lam
    assert output_1.models["poisson_simple"].mu == output_2.models["poisson_simple"].mu
    assert output_1.calibration["poisson_simple"].scale_c == output_2.calibration["poisson_simple"].scale_c
    assert output_1.decision.decision == output_2.decision.decision
    assert output_1.decision.decision_reason == output_2.decision.decision_reason


def test_no_wall_clock_or_network_dependency_in_production_path() -> None:
    """Garde-fou statique (comme test_e7_never_reimplements_point_in_time_filtering) :
    aucun des modules du chemin de production R1/R2/R3/final_engine n'appelle
    l'heure courante ni le reseau - la seule source de temps est
    ``kickoff_utc``, fourni explicitement par l'appelant."""
    production_dirs = [
        _SRC_DIR / "calibration_engine",
        _SRC_DIR / "data_engine" / "market_odds",
        _SRC_DIR / "final_engine",
        _SRC_DIR / "backtesting_engine",
        _SRC_DIR / "football_model",
    ]
    forbidden = ("datetime.now(", "utcnow(", "date.today(", "import requests", "import httpx", "import urllib")
    offending: list[str] = []
    for directory in production_dirs:
        for path in directory.glob("*.py"):
            source = path.read_text()
            for token in forbidden:
                if token in source:
                    offending.append(f"{path}: {token}")
    assert offending == []
    assert (_SCRIPT_PATH.read_text().count("datetime.now(") == 0)
    assert (_SCRIPT_PATH.read_text().count("import requests") == 0)


# --- 3. scenario futur / shadow mode ----------------------------------------


def test_shadow_scenario_uses_the_full_season_as_history_without_exception(predict_match, liga_2025_raw) -> None:
    """Kickoff CIBLE strictement posterieur a TOUS les matchs du corpus
    charge (fin de saison + marge) - simule le vrai cas d'usage production
    (predire un match qui n'a pas encore eu lieu) : goals_train_df/
    xg_train_df doivent contenir l'integralite de l'historique disponible,
    et aucune exception ne doit etre levee."""
    results = [m for m in liga_2025_raw if m.get("isResult")]
    last_kickoff = max(datetime.strptime(m["datetime"], "%Y-%m-%d %H:%M:%S") for m in results)
    shadow_kickoff = last_kickoff + timedelta(days=30)  # loin apres tout le corpus, jamais ambigu par construction du test suivant
    # Un samedi garanti : evite ambiguous_day_gate pour isoler la verification du scenario shadow.
    while shadow_kickoff.weekday() not in (5, 6):
        shadow_kickoff += timedelta(days=1)
    shadow_kickoff = shadow_kickoff.replace(hour=20, minute=0, second=0)

    inputs = predict_match.build_prediction_inputs("liga", "2025_26", "Barcelona", "Atletico Madrid", shadow_kickoff)
    assert len(inputs.goals_train_df) == len(results)  # tout le corpus est utilisable, rien n'est artificiellement exclu
    assert len(inputs.xg_train_df) == len(results)

    output = predict_match.run_prediction(
        competition="liga", season="2025_26", home_team="Barcelona", away_team="Atletico Madrid",
        kickoff_utc=shadow_kickoff, market_odds={"Over": 1.8, "Under": 2.0},
    )
    assert output.models["poisson_simple"] is not None
    assert output.models["poisson_simple"].n_train_matches == len(results)
    assert output.calibration["poisson_simple"].probabilities is not None
    assert output.decision.decision in ("BET", "NO_BET")


def test_shadow_scenario_respects_point_in_time(predict_match, liga_2025_raw) -> None:
    results = [m for m in liga_2025_raw if m.get("isResult")]
    last_kickoff = max(datetime.strptime(m["datetime"], "%Y-%m-%d %H:%M:%S") for m in results)
    shadow_kickoff = (last_kickoff + timedelta(days=30)).replace(hour=20, minute=0, second=0)
    decision_time = shadow_kickoff - timedelta(hours=2.0)

    inputs = predict_match.build_prediction_inputs("liga", "2025_26", "Barcelona", "Atletico Madrid", shadow_kickoff)
    for df in (inputs.goals_train_df, inputs.xg_train_df):
        for kt in df["kickoff_time"]:
            assert kt < decision_time
    for calib_df in inputs.calibration_df_by_model.values():
        for dt in calib_df["decision_time"]:
            assert dt <= last_kickoff  # aucune ligne de calibration ne peut provenir d'apres le corpus reel


# --- 4. gates et securite decisionnelle -------------------------------------


@pytest.mark.parametrize("over_odds,under_odds", [(1.5, 2.5), (10.0, 1.02), (100.0, 1.001), (2.5, 2.5)])
def test_no_market_odds_value_ever_produces_a_bet_in_the_current_mvp_config(predict_match, over_odds, under_odds) -> None:
    """min_edge_threshold reste None (PARAMETRE OPERATIONNEL A VALIDER,
    jamais fixe) : edge_threshold_gate se declenche TOUJOURS, quelle que
    soit l'ampleur de l'ecart apparent modele/marche. Aucune option CLI
    n'expose ``min_edge_threshold`` - il est structurellement impossible
    d'obtenir BET via ce runner dans la configuration actuelle."""
    output = predict_match.run_prediction(
        competition="liga", season="2025_26", home_team="Barcelona", away_team="Atletico Madrid",
        kickoff_utc=datetime(2026, 6, 20, 20, 0, 0), market_odds={"Over": over_odds, "Under": under_odds},
    )
    assert output.decision.decision == "NO_BET"
    assert "EDGE_BELOW_THRESHOLD" in output.decision.decision_reason


def test_cli_exposes_no_option_to_override_min_edge_threshold(predict_match) -> None:
    import inspect

    sig = inspect.signature(predict_match.main)
    assert "min_edge_threshold" not in sig.parameters
    assert "operational_thresholds" not in sig.parameters


def test_insufficient_calibration_history_triggers_no_bet(predict_match, liga_2025_raw) -> None:
    """Debut de saison (peu de matchs ecoules) : le facteur d'echelle E7/E8
    ne peut pas etre estime (< MIN_CALIBRATION_MATCHES_FOR_SCALE=30) ->
    NO_BET, jamais une decision fondee sur une calibration absente."""
    results = sorted(
        (m for m in liga_2025_raw if m.get("isResult")), key=lambda m: m["datetime"]
    )
    early_match = results[5]
    kickoff_utc = datetime.strptime(early_match["datetime"], "%Y-%m-%d %H:%M:%S")

    output = predict_match.run_prediction(
        competition="liga", season="2025_26",
        home_team=early_match["h"]["title"], away_team=early_match["a"]["title"],
        kickoff_utc=kickoff_utc, market_odds={"Over": 1.9, "Under": 1.9},
    )
    assert output.decision.decision == "NO_BET"
    assert output.calibration["poisson_simple"].n_calibration_used < 30


def test_invalid_odds_are_refused_before_the_engine_is_ever_invoked(predict_match) -> None:
    """Une cote structurellement invalide ne doit jamais atteindre
    run_match_decision (refus CLI immediat, garantie plus forte qu'un
    simple NO_BET produit par le moteur)."""
    with pytest.raises(predict_match.PredictMatchError):
        predict_match.validate_market_odds(0.5, 1.9)
    with pytest.raises(predict_match.PredictMatchError):
        predict_match.validate_market_odds(float("nan"), 1.9)


def test_missing_odds_always_yields_no_bet_with_market_data_unavailable(predict_match, liga_2025_raw) -> None:
    results = sorted((m for m in liga_2025_raw if m.get("isResult")), key=lambda m: m["datetime"])
    match = results[200]
    kickoff_utc = datetime.strptime(match["datetime"], "%Y-%m-%d %H:%M:%S")
    output = predict_match.run_prediction(
        competition="liga", season="2025_26",
        home_team=match["h"]["title"], away_team=match["a"]["title"],
        kickoff_utc=kickoff_utc, market_odds=None,
    )
    assert output.decision.decision == "NO_BET"
    odds_gate = next(g for g in output.qualification.scientific_gates if g.name == "incomplete_market_odds_gate")
    assert odds_gate.triggered
    assert odds_gate.failure_code == "MARKET_DATA_UNAVAILABLE"
