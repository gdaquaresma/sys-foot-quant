"""Tests unitaires du CLI de production R3 (``scripts/predict_match.py``) :
parsing/validation des arguments, refus propre des parametres manquants ou
incoherents, et formatage du rapport - AUCUN de ces tests n'appelle
``run_match_decision`` sur donnees reelles (voir
``tests/leakage/test_predict_match_point_in_time.py`` pour l'integration
bout-en-bout)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sys_foot_quant.final_engine.types import (
    CalibratedGoalDistribution,
    DecisionResult,
    MatchDecisionOutput,
    ModelPrediction,
    PricingResult,
    QualificationResult,
)

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "predict_match.py"


def _load_predict_match():
    spec = importlib.util.spec_from_file_location("predict_match_for_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def predict_match():
    return _load_predict_match()


runner = CliRunner()


# --- 1. parsing/validation des arguments CLI --------------------------------


def test_parse_kickoff_utc_accepts_naive_iso_datetime(predict_match) -> None:
    parsed = predict_match.parse_kickoff_utc("2025-05-11T19:00:00")
    assert parsed == datetime(2025, 5, 11, 19, 0, 0)


def test_parse_kickoff_utc_rejects_malformed_string(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="invalide"):
        predict_match.parse_kickoff_utc("not-a-date")


def test_parse_kickoff_utc_rejects_timezone_aware_string(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="naif"):
        predict_match.parse_kickoff_utc("2025-05-11T19:00:00+02:00")


def test_validate_market_odds_returns_none_when_absent(predict_match) -> None:
    assert predict_match.validate_market_odds(None, None) is None


def test_validate_market_odds_returns_dict_when_both_present(predict_match) -> None:
    assert predict_match.validate_market_odds(1.85, 1.95) == {"Over": 1.85, "Under": 1.95}


# --- 2. refus propre des parametres manquants ou incoherents ----------------


def test_validate_market_odds_rejects_partial_pair_over_only(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="ensemble"):
        predict_match.validate_market_odds(1.85, None)


def test_validate_market_odds_rejects_partial_pair_under_only(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="ensemble"):
        predict_match.validate_market_odds(None, 1.95)


def test_validate_market_odds_rejects_odds_below_one(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError):
        predict_match.validate_market_odds(0.9, 1.95)


def test_resolve_team_id_direct_understat_name(predict_match) -> None:
    team_id_by_name = {"Real Madrid": 100, "Barcelona": 200}
    assert predict_match.resolve_team_id("Real Madrid", team_id_by_name, "liga") == 100


def test_resolve_team_id_falls_back_to_football_data_translation(predict_match) -> None:
    team_id_by_name = {"Athletic Club": 300}
    assert predict_match.resolve_team_id("Ath Bilbao", team_id_by_name, "liga") == 300


def test_resolve_team_id_raises_for_completely_unknown_team(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="Equipe inconnue"):
        predict_match.resolve_team_id("Not A Real Team", {}, "liga")


def test_resolve_team_id_raises_when_translated_name_absent_from_corpus(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="absent du corpus"):
        predict_match.resolve_team_id("Ath Bilbao", {"Barcelona": 200}, "liga")


def test_build_prediction_inputs_rejects_identical_home_and_away_team(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="distinctes"):
        predict_match.build_prediction_inputs(
            "liga", "2024_25", "Real Madrid", "Real Madrid", datetime(2025, 1, 1)
        )


def test_load_understat_raw_rejects_unknown_competition(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="Competition inconnue"):
        predict_match._load_understat_raw("bundesliga", "2024_25")


def test_load_understat_raw_rejects_unknown_season(predict_match) -> None:
    with pytest.raises(predict_match.PredictMatchError, match="Saison inconnue"):
        predict_match._load_understat_raw("liga", "1999_00")


def test_cli_exits_nonzero_on_missing_required_option(predict_match) -> None:
    result = runner.invoke(predict_match.app, ["--competition", "liga", "--season", "2024_25"])
    assert result.exit_code != 0


def test_cli_exits_1_on_invalid_kickoff(predict_match) -> None:
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "not-a-date",
        ],
    )
    assert result.exit_code == 1
    assert "ERREUR" in result.output


def test_cli_exits_1_on_partial_market_odds(predict_match) -> None:
    result = runner.invoke(
        predict_match.app,
        [
            "--competition", "liga", "--season", "2024_25",
            "--home-team", "Real Madrid", "--away-team", "Barcelona",
            "--kickoff-utc", "2025-05-11T19:00:00",
            "--market-odds-over-2-5", "1.85",
        ],
    )
    assert result.exit_code == 1
    assert "ensemble" in result.output


# --- formatage du rapport (aucun appel reel a run_match_decision) ----------


def _minimal_no_bet_output(predict_match) -> MatchDecisionOutput:
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.1, rho=None, n_train_matches=50)
    calib = CalibratedGoalDistribution(
        model="poisson_simple", scale_c=0.9, n_calibration_used=40, goal_distribution=(0.1,) * 7, probabilities={2.5: 0.55}
    )
    return MatchDecisionOutput(
        match_id="test-match",
        timestamp_decision=datetime(2025, 1, 1, tzinfo=timezone.utc),
        competition="liga",
        season="2024_25",
        primary_model="poisson_simple",
        models={"poisson_simple": pred, "dixon_coles": None, "xg_model": None},
        calibration={"poisson_simple": calib},
        pricing={"poisson_simple": PricingResult(fair_price={2.5: 1.818})},
        market=None,
        qualification=QualificationResult(
            calibration_status={2.5: "OK"},
            discrimination_status="DEMONTREE",
            data_quality=["OK"],
            scientific_gates=[],
            operational_gates=[],
        ),
        decision=DecisionResult(decision="NO_BET", decision_reason=["MARKET_DATA_UNAVAILABLE"]),
        engine_version="test-version",
        parameters_snapshot={},
    )


def test_format_decision_report_shows_decision_and_reason(predict_match) -> None:
    report = predict_match.format_decision_report(_minimal_no_bet_output(predict_match))
    assert "NO_BET" in report
    assert "MARKET_DATA_UNAVAILABLE" in report
    assert "poisson_simple" in report
    assert "lambda=1.5000" in report


def test_format_decision_report_handles_no_market(predict_match) -> None:
    report = predict_match.format_decision_report(_minimal_no_bet_output(predict_match))
    assert "Aucune cote de marche" in report
