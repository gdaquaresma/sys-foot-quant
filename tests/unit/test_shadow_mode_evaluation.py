"""Tests de ``shadow_mode.journal.evaluate_shadow`` sur des fixtures
controlees : calcul correct des metriques (Brier/log loss), seuil
d'affichage de la calibration, comportement NO_BET (jamais de BET
invente), et journal vide."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from sys_foot_quant.final_engine.types import (
    CalibratedGoalDistribution,
    DecisionResult,
    MatchDecisionOutput,
    ModelPrediction,
    PricingResult,
    QualificationResult,
)
from sys_foot_quant.shadow_mode.journal import (
    MIN_OBSERVATIONS_FOR_CALIBRATION_DISPLAY,
    evaluate_shadow,
    record_prediction,
    settle_prediction,
)

_T0 = datetime(2026, 1, 1)


def _output(p_over_2_5: float | None) -> MatchDecisionOutput:
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.1, rho=None, n_train_matches=50)
    probabilities = None if p_over_2_5 is None else {2.5: p_over_2_5}
    calib = CalibratedGoalDistribution(
        model="poisson_simple", scale_c=0.9 if p_over_2_5 else None,
        n_calibration_used=40 if p_over_2_5 else 5,
        goal_distribution=(0.1,) * 7 if p_over_2_5 else None,
        probabilities=probabilities,
    )
    return MatchDecisionOutput(
        match_id="test-match", timestamp_decision=_T0, competition="liga", season="2025_26",
        primary_model="poisson_simple",
        models={"poisson_simple": pred, "dixon_coles": None, "xg_model": None},
        calibration={"poisson_simple": calib},
        pricing={"poisson_simple": PricingResult(fair_price={})},
        market=None,
        qualification=QualificationResult(
            calibration_status={2.5: "OK"}, discrimination_status="DEMONTREE",
            data_quality=["OK"], scientific_gates=[], operational_gates=[],
        ),
        decision=DecisionResult(decision="NO_BET", decision_reason=["MARKET_DATA_UNAVAILABLE"]),
        engine_version="test-version", parameters_snapshot={},
    )


def _record_and_settle(journal_path, i: int, p_over_2_5: float, total_goals_actual: int) -> None:
    kickoff = _T0 + timedelta(days=i)
    output = _output(p_over_2_5)
    record, _ = record_prediction(
        output, competition="liga", season="2025_26",
        home_team=f"Home{i}", away_team=f"Away{i}", kickoff_utc=kickoff,
        decision_offset_hours=2.0, market_odds_over_2_5=None, market_odds_under_2_5=None,
        journal_path=journal_path,
    )
    home_goals = total_goals_actual // 2
    away_goals = total_goals_actual - home_goals
    settle_prediction(record["prediction_id"], home_goals=home_goals, away_goals=away_goals, journal_path=journal_path)


def test_evaluate_empty_journal_does_not_crash(tmp_path) -> None:
    report = evaluate_shadow(tmp_path / "empty.jsonl")
    assert report["n_total"] == 0
    assert report["n_settled"] == 0
    assert report["betting"]["n_bet"] == 0
    assert "insuffisant" in report["betting"]["message"]


def test_brier_and_log_loss_match_manual_computation(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    # 4 observations controlees : (p_predite, total_buts_reel)
    fixtures = [(0.8, 3), (0.3, 1), (0.6, 4), (0.4, 1)]  # totals: Over,Under,Over,Under
    for i, (p, total) in enumerate(fixtures):
        _record_and_settle(journal_path, i, p, total)

    report = evaluate_shadow(journal_path)
    probs = np.array([p for p, _ in fixtures])
    outcomes = np.array([1.0 if total > 2.5 else 0.0 for _, total in fixtures])
    expected_brier = float(np.mean((probs - outcomes) ** 2))
    expected_logloss = float(-np.mean(outcomes * np.log(probs) + (1 - outcomes) * np.log(1 - probs)))

    m = report["models"]["poisson_simple"]
    assert m["n"] == 4
    assert m["brier"] == pytest.approx(expected_brier)
    assert m["log_loss"] == pytest.approx(expected_logloss)


def test_calibration_bins_hidden_below_display_threshold(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    n = MIN_OBSERVATIONS_FOR_CALIBRATION_DISPLAY - 1
    for i in range(n):
        _record_and_settle(journal_path, i, 0.5, total_goals_actual=3 if i % 2 == 0 else 1)

    report = evaluate_shadow(journal_path)
    assert report["models"]["poisson_simple"]["n"] == n
    assert report["models"]["poisson_simple"]["calibration_bins"] is None


def test_calibration_bins_shown_at_or_above_display_threshold(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    n = MIN_OBSERVATIONS_FOR_CALIBRATION_DISPLAY
    for i in range(n):
        _record_and_settle(journal_path, i, 0.5, total_goals_actual=3 if i % 2 == 0 else 1)

    report = evaluate_shadow(journal_path)
    assert report["models"]["poisson_simple"]["n"] == n
    assert report["models"]["poisson_simple"]["calibration_bins"] is not None


def test_model_with_no_available_probability_reports_zero(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    _record_and_settle(journal_path, 0, p_over_2_5=0.5, total_goals_actual=3)
    report = evaluate_shadow(journal_path)
    # dixon_coles/xg_model n'ont jamais de prediction dans cette fixture (None).
    assert report["models"]["dixon_coles"]["n"] == 0
    assert report["models"]["dixon_coles"]["brier"] is None
    assert report["models"]["xg_model"]["n"] == 0


def test_zero_bet_returns_the_exact_required_message(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    _record_and_settle(journal_path, 0, 0.6, total_goals_actual=3)
    report = evaluate_shadow(journal_path)
    assert report["betting"]["n_bet"] == 0
    assert report["betting"]["message"] == "0 BET — echantillon insuffisant pour evaluer une strategie de mise."


def test_decision_distribution_counts_all_observations_including_pending(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output(0.6)
    record_prediction(
        output, competition="liga", season="2025_26", home_team="A", away_team="B",
        kickoff_utc=_T0, decision_offset_hours=2.0, market_odds_over_2_5=None, market_odds_under_2_5=None,
        journal_path=journal_path,
    )
    _record_and_settle(journal_path, 1, 0.6, total_goals_actual=3)

    report = evaluate_shadow(journal_path)
    assert report["n_total"] == 2
    assert report["decision_distribution"] == {"NO_BET": 2}
