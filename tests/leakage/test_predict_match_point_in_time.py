"""Integration reelle et garde-fous anti-fuite pour le CLI de production R3
(``scripts/predict_match.py``) : assemble R1 + R2 (deja testes
independamment) et ``final_engine.orchestrator.run_match_decision``
(INCHANGE) sur le corpus reel Understat. Ne re-verifie PAS le mecanisme
point-in-time lui-meme (deja prouve par
``tests/leakage/test_calibration_dataset_point_in_time.py`` et
``tests/leakage/test_future_match_dataset_point_in_time.py``) - verifie
que le CLI ne re-introduit aucune fuite en les assemblant (aucun filtrage
supplementaire, aucune donnee posterieure a ``decision_time`` transmise au
moteur)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "predict_match.py"
_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"


def _load_predict_match():
    spec = importlib.util.spec_from_file_location("predict_match_for_leakage_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def predict_match():
    return _load_predict_match()


@pytest.fixture(scope="module")
def liga_2024_raw():
    with open(_UNDERSTAT_DIR / "liga_2024_datesData.json") as f:
        return json.load(f)


pytestmark = pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat reels non presents.")


# --- 3. integration reelle R1 + R2 + run_match_decision ---------------------


def test_build_prediction_inputs_wires_r1_and_r2_correctly(predict_match, liga_2024_raw) -> None:
    home, away, kickoff = liga_2024_raw[150]["h"]["title"], liga_2024_raw[150]["a"]["title"], liga_2024_raw[150]["datetime"]
    from datetime import datetime

    kickoff_utc = datetime.strptime(kickoff, "%Y-%m-%d %H:%M:%S")
    inputs = predict_match.build_prediction_inputs("liga", "2024_25", home, away, kickoff_utc)

    assert list(inputs.goals_train_df.columns) == ["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
    assert list(inputs.xg_train_df.columns) == ["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"]
    assert set(inputs.calibration_df_by_model.keys()) == {"poisson_simple", "dixon_coles", "xg_model"}
    assert len(inputs.goals_train_df) > 0


def test_run_prediction_produces_a_match_decision_output(predict_match, liga_2024_raw) -> None:
    from datetime import datetime

    home, away, kickoff = liga_2024_raw[150]["h"]["title"], liga_2024_raw[150]["a"]["title"], liga_2024_raw[150]["datetime"]
    kickoff_utc = datetime.strptime(kickoff, "%Y-%m-%d %H:%M:%S")

    output = predict_match.run_prediction(
        competition="liga", season="2024_25", home_team=home, away_team=away,
        kickoff_utc=kickoff_utc, market_odds={"Over": 1.9, "Under": 1.9},
    )
    assert output.primary_model == "poisson_simple"
    assert output.models["poisson_simple"] is not None
    assert output.market is not None
    assert output.decision.decision in ("BET", "NO_BET")


# --- 4. execution sur au moins un match historique connu du corpus ---------


def test_end_to_end_on_a_known_historical_match(predict_match, liga_2024_raw) -> None:
    from datetime import datetime

    match = liga_2024_raw[300]
    home, away = match["h"]["title"], match["a"]["title"]
    kickoff_utc = datetime.strptime(match["datetime"], "%Y-%m-%d %H:%M:%S")

    output = predict_match.run_prediction(
        competition="liga", season="2024_25", home_team=home, away_team=away, kickoff_utc=kickoff_utc, market_odds=None
    )
    report = predict_match.format_decision_report(output)
    assert home in output.match_id and away in output.match_id
    assert "DECISION FINALE" in report


# --- 5. respect des gates odds ----------------------------------------------


def test_missing_market_odds_triggers_market_data_unavailable_gate(predict_match, liga_2024_raw) -> None:
    from datetime import datetime

    match = liga_2024_raw[200]
    home, away = match["h"]["title"], match["a"]["title"]
    kickoff_utc = datetime.strptime(match["datetime"], "%Y-%m-%d %H:%M:%S")

    output = predict_match.run_prediction(
        competition="liga", season="2024_25", home_team=home, away_team=away, kickoff_utc=kickoff_utc, market_odds=None
    )
    assert output.market is None
    assert "MARKET_DATA_UNAVAILABLE" in output.decision.decision_reason
    assert output.decision.decision == "NO_BET"


def test_ambiguous_collection_day_reflected_in_reasons_when_applicable(predict_match, liga_2024_raw) -> None:
    """Ne force pas artificiellement un jour ambigu (le CLI ne reimplemente
    jamais la regle) - verifie seulement que, LORSQUE le match reel tombe un
    jour ambigu (lundi/mardi/vendredi), le code apparait bien dans les
    raisons - preuve que ambiguous_day_gate (INCHANGE) est bien cablee."""
    from datetime import datetime

    from sys_foot_quant.data_engine.market_odds.time_resolution import AmbiguousCollectionWindowError, conservative_knowledge_time_utc

    ambiguous_match = None
    for match in liga_2024_raw:
        if not match.get("isResult"):
            continue
        kickoff_utc = datetime.strptime(match["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=None)
        from datetime import timezone

        try:
            conservative_knowledge_time_utc(kickoff_utc.replace(tzinfo=timezone.utc))
        except AmbiguousCollectionWindowError:
            ambiguous_match = match
            break
    if ambiguous_match is None:
        pytest.skip("Aucun match ambigu trouve dans ce fichier de corpus.")

    kickoff_utc = datetime.strptime(ambiguous_match["datetime"], "%Y-%m-%d %H:%M:%S")
    output = predict_match.run_prediction(
        competition="liga", season="2024_25",
        home_team=ambiguous_match["h"]["title"], away_team=ambiguous_match["a"]["title"],
        kickoff_utc=kickoff_utc, market_odds={"Over": 1.9, "Under": 1.9},
    )
    assert "AMBIGUOUS_COLLECTION_DAY" in output.decision.decision_reason


# --- 6. aucun acces a des donnees posterieures a decision_time -------------


def test_no_row_in_train_dataframes_is_at_or_after_decision_time(predict_match, liga_2024_raw) -> None:
    from datetime import datetime

    match = liga_2024_raw[250]
    home, away = match["h"]["title"], match["a"]["title"]
    kickoff_utc = datetime.strptime(match["datetime"], "%Y-%m-%d %H:%M:%S")
    decision_time = kickoff_utc - timedelta(hours=2.0)

    inputs = predict_match.build_prediction_inputs("liga", "2024_25", home, away, kickoff_utc)
    for df in (inputs.goals_train_df, inputs.xg_train_df):
        for kt in df["kickoff_time"]:
            assert kt < decision_time


def test_adding_a_future_match_to_the_corpus_never_changes_an_earlier_prediction(predict_match, liga_2024_raw, tmp_path) -> None:
    """Copie le fichier de corpus reel en y ajoutant un match FICTIF tres
    futur (kickoff tres eloigne), et verifie que la prediction d'un match
    ANTERIEUR reste rigoureusement identique - preuve que l'assemblage du
    CLI (chargement + R1 + R2) n'introduit aucune fuite supplementaire au
    dela de celle deja garantie par R1/R2."""
    from datetime import datetime

    target = liga_2024_raw[150]
    kickoff_utc = datetime.strptime(target["datetime"], "%Y-%m-%d %H:%M:%S")

    output_before = predict_match.run_prediction(
        competition="liga", season="2024_25",
        home_team=target["h"]["title"], away_team=target["a"]["title"],
        kickoff_utc=kickoff_utc, market_odds={"Over": 1.9, "Under": 1.9},
    )

    future_match = dict(liga_2024_raw[0])
    future_match = {**future_match, "id": "999999", "datetime": "2099-01-01 12:00:00"}
    augmented_raw = liga_2024_raw + [future_match]
    augmented_path = tmp_path / "liga_2024_datesData.json"
    augmented_path.write_text(json.dumps(augmented_raw))

    original_seasons = predict_match._SEASONS
    predict_match._SEASONS = {
        "2024_25": {**original_seasons["2024_25"], "liga": ("La_liga", augmented_path)},
        "2025_26": original_seasons["2025_26"],
    }
    try:
        output_after = predict_match.run_prediction(
            competition="liga", season="2024_25",
            home_team=target["h"]["title"], away_team=target["a"]["title"],
            kickoff_utc=kickoff_utc, market_odds={"Over": 1.9, "Under": 1.9},
        )
    finally:
        predict_match._SEASONS = original_seasons

    assert output_before.models["poisson_simple"].lam == output_after.models["poisson_simple"].lam
    assert output_before.models["poisson_simple"].mu == output_after.models["poisson_simple"].mu
    assert output_before.calibration["poisson_simple"].scale_c == output_after.calibration["poisson_simple"].scale_c
    assert output_before.decision.decision == output_after.decision.decision


# --- 7. comportement propre en cas de NO_BET --------------------------------


def test_no_bet_report_always_carries_at_least_one_reason(predict_match, liga_2024_raw) -> None:
    from datetime import datetime

    match = liga_2024_raw[50]
    kickoff_utc = datetime.strptime(match["datetime"], "%Y-%m-%d %H:%M:%S")
    output = predict_match.run_prediction(
        competition="liga", season="2024_25",
        home_team=match["h"]["title"], away_team=match["a"]["title"],
        kickoff_utc=kickoff_utc, market_odds=None,
    )
    if output.decision.decision == "NO_BET":
        assert len(output.decision.decision_reason) > 0
        report = predict_match.format_decision_report(output)
        assert "Raisons :" in report
        assert all(code in report for code in output.decision.decision_reason)
