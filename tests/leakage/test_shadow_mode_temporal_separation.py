"""Garde-fou de separation temporelle pour le journal Shadow Mode V1 :
les champs post-match ne doivent JAMAIS pouvoir se retrouver dans la ligne
``prediction`` (pre-match), et l'evaluation ne doit jamais utiliser une
observation non reglee."""

from __future__ import annotations

import json
from datetime import datetime

from sys_foot_quant.final_engine.types import (
    CalibratedGoalDistribution,
    DecisionResult,
    MatchDecisionOutput,
    ModelPrediction,
    PricingResult,
    QualificationResult,
)
from sys_foot_quant.shadow_mode.journal import (
    evaluate_shadow,
    find_prediction,
    record_prediction,
    settle_prediction,
)

_KICKOFF = datetime(2026, 6, 20, 20, 0, 0)

_POST_MATCH_ONLY_FIELDS = {
    "settled_at", "home_goals_actual", "away_goals_actual", "total_goals_actual",
    "market_result_over_2_5", "pnl_theoretical",
}


def _output(p_over_2_5: float = 0.6) -> MatchDecisionOutput:
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.1, rho=None, n_train_matches=50)
    calib = CalibratedGoalDistribution(
        model="poisson_simple", scale_c=0.9, n_calibration_used=40,
        goal_distribution=(0.1,) * 7, probabilities={2.5: p_over_2_5},
    )
    return MatchDecisionOutput(
        match_id="test-match",
        timestamp_decision=_KICKOFF,
        competition="liga",
        season="2025_26",
        primary_model="poisson_simple",
        models={"poisson_simple": pred, "dixon_coles": None, "xg_model": None},
        calibration={"poisson_simple": calib},
        pricing={"poisson_simple": PricingResult(fair_price={2.5: 1.0 / p_over_2_5})},
        market=None,
        qualification=QualificationResult(
            calibration_status={2.5: "OK"}, discrimination_status="DEMONTREE",
            data_quality=["OK"], scientific_gates=[], operational_gates=[],
        ),
        decision=DecisionResult(decision="NO_BET", decision_reason=["MARKET_DATA_UNAVAILABLE"]),
        engine_version="test-version",
        parameters_snapshot={},
    )


def _record_kwargs(**overrides) -> dict:
    base = dict(
        competition="liga", season="2025_26", home_team="Barcelona", away_team="Atletico Madrid",
        kickoff_utc=_KICKOFF, decision_offset_hours=2.0,
        market_odds_over_2_5=None, market_odds_under_2_5=None,
    )
    base.update(overrides)
    return base


def test_prediction_line_never_contains_post_match_fields_even_after_settlement(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output()
    record, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs())
    settle_prediction(record["prediction_id"], home_goals=1, away_goals=0, journal_path=journal_path)

    raw_lines = [json.loads(line) for line in journal_path.read_text().strip().splitlines()]
    prediction_lines = [r for r in raw_lines if r["record_type"] == "prediction"]
    settlement_lines = [r for r in raw_lines if r["record_type"] == "settlement"]

    assert len(prediction_lines) == 1
    assert len(settlement_lines) == 1
    # La ligne pre-match ne porte AUCUN champ post-match, meme apres settlement.
    assert set(prediction_lines[0].keys()).isdisjoint(_POST_MATCH_ONLY_FIELDS)
    # La ligne settlement ne porte AUCUN champ de decision/probabilite pre-match.
    assert "decision" not in settlement_lines[0]
    assert "models" not in settlement_lines[0]
    assert "market_odds_over_2_5" not in settlement_lines[0]


def test_settlement_cannot_alter_decision_or_probabilities(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output(p_over_2_5=0.7123)
    record_before, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs())

    settle_prediction(record_before["prediction_id"], home_goals=4, away_goals=3, journal_path=journal_path)
    record_after = find_prediction(journal_path, record_before["prediction_id"])

    assert record_after["decision"] == record_before["decision"] == "NO_BET"
    assert record_after["models"] == record_before["models"]
    assert record_after["models"]["poisson_simple"]["probabilities"]["2.5"] == 0.7123


def test_evaluate_shadow_never_uses_pending_observations(tmp_path) -> None:
    """Une observation PENDING (jamais reglee) n'a par definition aucun
    resultat reel connu - elle ne doit jamais contribuer au Brier/log_loss
    ni a la distribution des paris theoriques."""
    journal_path = tmp_path / "predictions.jsonl"
    pending_output = _output(p_over_2_5=0.99)  # probabilite extreme : si utilisee par erreur, fausserait fortement le Brier
    record_prediction(pending_output, journal_path=journal_path, **_record_kwargs(home_team="Pending FC", away_team="Never Settled FC"))

    settled_output = _output(p_over_2_5=0.5)
    record, _ = record_prediction(settled_output, journal_path=journal_path, **_record_kwargs(home_team="Settled FC", away_team="Other FC"))
    settle_prediction(record["prediction_id"], home_goals=1, away_goals=1, journal_path=journal_path)

    report = evaluate_shadow(journal_path)
    assert report["n_total"] == 2
    assert report["n_pending"] == 1
    assert report["n_settled"] == 1
    # Seule l'observation reglee (p=0.5) doit contribuer - jamais celle a 0.99.
    assert report["models"]["poisson_simple"]["n"] == 1
