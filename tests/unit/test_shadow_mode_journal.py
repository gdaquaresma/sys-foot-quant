"""Tests unitaires du journal Shadow Mode V1
(``sys_foot_quant.shadow_mode.journal``) : creation d'une observation,
conservation exacte des champs produits par ``run_match_decision``,
deduplication, statut PENDING/SETTLED, settlement post-match,
immutabilite des champs pre-match, et reproductibilite du
``prediction_id``."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from sys_foot_quant.final_engine.types import (
    CalibratedGoalDistribution,
    DecisionResult,
    GateResult,
    MatchDecisionOutput,
    MarketComparisonResult,
    ModelPrediction,
    PricingResult,
    QualificationResult,
)
from sys_foot_quant.shadow_mode.journal import (
    STATUS_PENDING,
    STATUS_SETTLED,
    ShadowModeError,
    compute_prediction_id,
    find_prediction,
    load_journal,
    record_prediction,
    settle_prediction,
)

_KICKOFF = datetime(2026, 6, 20, 20, 0, 0)


def _output(
    decision: str = "NO_BET",
    decision_reason: list[str] | None = None,
    p_over_2_5: float = 0.6,
    market_odds_over_2_5: float | None = 1.9,
    market_odds_under_2_5: float | None = 1.9,
) -> MatchDecisionOutput:
    pred = ModelPrediction(model="poisson_simple", lam=1.5, mu=1.1, rho=None, n_train_matches=50)
    calib = CalibratedGoalDistribution(
        model="poisson_simple", scale_c=0.9, n_calibration_used=40,
        goal_distribution=(0.1,) * 7, probabilities={0.5: 0.9, 1.5: 0.75, 2.5: p_over_2_5, 3.5: 0.3, 4.5: 0.15},
    )
    market = None
    if market_odds_over_2_5 is not None:
        market = MarketComparisonResult(
            market_odds={"Over": market_odds_over_2_5, "Under": market_odds_under_2_5},
            market_implied_probability_raw={"Over": 0.5, "Under": 0.5},
            market_implied_probability_normalized={"Over": 0.5, "Under": 0.5},
            market_overround=0.05,
            raw_edge={"Over": p_over_2_5 - 0.5, "Under": 0.5 - p_over_2_5},
            price_edge={"Over": 0.1, "Under": -0.1},
        )
    gates = [] if decision == "BET" else [
        GateResult(
            name="edge_threshold_gate", triggered=True, reason="Aucun seuil valide.",
            metric="raw_edge", observed_value=0.1, threshold=None, failure_code="EDGE_BELOW_THRESHOLD",
        )
    ]
    return MatchDecisionOutput(
        match_id="test-match",
        timestamp_decision=_KICKOFF,
        competition="liga",
        season="2025_26",
        primary_model="poisson_simple",
        models={"poisson_simple": pred, "dixon_coles": None, "xg_model": None},
        calibration={"poisson_simple": calib},
        pricing={"poisson_simple": PricingResult(fair_price={2.5: 1.0 / p_over_2_5})},
        market=market,
        qualification=QualificationResult(
            calibration_status={2.5: "OK"},
            discrimination_status="DEMONTREE",
            data_quality=["OK"],
            scientific_gates=gates,
            operational_gates=[],
        ),
        decision=DecisionResult(decision=decision, decision_reason=decision_reason or []),
        engine_version="test-version",
        parameters_snapshot={},
    )


def _record_kwargs(**overrides) -> dict:
    base = dict(
        competition="liga", season="2025_26", home_team="Barcelona", away_team="Atletico Madrid",
        kickoff_utc=_KICKOFF, decision_offset_hours=2.0,
        market_odds_over_2_5=1.9, market_odds_under_2_5=1.9,
    )
    base.update(overrides)
    return base


# --- 1. creation correcte d'une observation ---------------------------------


def test_record_prediction_creates_a_pending_observation(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output(decision="NO_BET", decision_reason=["EDGE_BELOW_THRESHOLD"])
    record, already_existed = record_prediction(output, journal_path=journal_path, **_record_kwargs())

    assert already_existed is False
    assert record["status"] == STATUS_PENDING
    assert record["settlement"] is None
    assert journal_path.exists()
    assert len(journal_path.read_text().strip().splitlines()) == 1


# --- 2. conservation exacte de la decision produite par R3 ------------------


def test_record_prediction_preserves_exact_engine_output(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output(decision="NO_BET", decision_reason=["EDGE_BELOW_THRESHOLD"], p_over_2_5=0.6483)
    record, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs())

    assert record["decision"] == "NO_BET"
    assert record["decision_reason"] == ["EDGE_BELOW_THRESHOLD"]
    assert record["models"]["poisson_simple"]["lambda"] == pytest.approx(1.5)
    assert record["models"]["poisson_simple"]["mu"] == pytest.approx(1.1)
    assert record["models"]["poisson_simple"]["probabilities"]["2.5"] == pytest.approx(0.6483)
    assert record["market_comparison"]["implied_prob_over_2_5"] == pytest.approx(0.5)
    assert record["decision_time"] == _KICKOFF.isoformat()
    assert record["competition"] == "liga"
    assert record["home_team"] == "Barcelona"
    assert record["away_team"] == "Atletico Madrid"


# --- 3. deduplication d'une prediction identique ----------------------------


def test_record_prediction_deduplicates_identical_inputs(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output()
    kwargs = _record_kwargs()

    record_1, existed_1 = record_prediction(output, journal_path=journal_path, **kwargs)
    record_2, existed_2 = record_prediction(output, journal_path=journal_path, **kwargs)

    assert existed_1 is False
    assert existed_2 is True
    assert record_1["prediction_id"] == record_2["prediction_id"]
    assert len(journal_path.read_text().strip().splitlines()) == 1  # jamais un doublon silencieux


def test_record_prediction_distinguishes_different_odds_as_new_observations(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output()
    record_prediction(output, journal_path=journal_path, **_record_kwargs(market_odds_over_2_5=1.9, market_odds_under_2_5=1.9))
    record_prediction(output, journal_path=journal_path, **_record_kwargs(market_odds_over_2_5=2.1, market_odds_under_2_5=1.75))

    assert len(journal_path.read_text().strip().splitlines()) == 2


# --- 4. statut PENDING initial ----------------------------------------------


def test_status_is_pending_before_settlement(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output()
    record, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs())
    reloaded = find_prediction(journal_path, record["prediction_id"])
    assert reloaded["status"] == STATUS_PENDING


# --- 5. settlement post-match ------------------------------------------------


def test_settle_prediction_adds_settlement_fields(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output()
    record, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs())

    settled = settle_prediction(record["prediction_id"], home_goals=2, away_goals=1, journal_path=journal_path)

    assert settled["status"] == STATUS_SETTLED
    assert settled["settlement"]["home_goals_actual"] == 2
    assert settled["settlement"]["away_goals_actual"] == 1
    assert settled["settlement"]["total_goals_actual"] == 3
    assert settled["settlement"]["market_result_over_2_5"] == "Over"


def test_settle_prediction_raises_for_unknown_id(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    with pytest.raises(ShadowModeError, match="Aucune observation"):
        settle_prediction("does-not-exist", home_goals=1, away_goals=0, journal_path=journal_path)


def test_settle_prediction_raises_on_double_settlement(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output()
    record, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs())
    settle_prediction(record["prediction_id"], home_goals=2, away_goals=1, journal_path=journal_path)

    with pytest.raises(ShadowModeError, match="deja reglee"):
        settle_prediction(record["prediction_id"], home_goals=0, away_goals=0, journal_path=journal_path)


# --- 6. impossibilite de modifier la prediction originale lors du settlement


def test_settlement_never_alters_prediction_fields(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output(decision="NO_BET", decision_reason=["EDGE_BELOW_THRESHOLD"], p_over_2_5=0.6483)
    record_before, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs())

    raw_lines_before = journal_path.read_text().strip().splitlines()
    assert len(raw_lines_before) == 1
    prediction_line_before = json.loads(raw_lines_before[0])

    settle_prediction(record_before["prediction_id"], home_goals=2, away_goals=1, journal_path=journal_path)

    raw_lines_after = journal_path.read_text().strip().splitlines()
    assert len(raw_lines_after) == 2  # une ligne "prediction" + une ligne "settlement", jamais une reecriture
    prediction_line_after = json.loads(raw_lines_after[0])

    # La ligne "prediction" d'origine est BYTE-A-BYTE identique.
    assert raw_lines_before[0] == raw_lines_after[0]
    assert prediction_line_before == prediction_line_after

    resolved = find_prediction(journal_path, record_before["prediction_id"])
    for key in (
        "decision", "decision_reason", "models", "market_comparison",
        "calibration_status_over_2_5", "competition", "home_team", "away_team", "kickoff_utc",
    ):
        assert resolved[key] == record_before[key]


# --- reproductibilite du prediction_id --------------------------------------


def test_compute_prediction_id_is_deterministic() -> None:
    kwargs = dict(
        competition="liga", season="2025_26", home_team="Barcelona", away_team="Atletico Madrid",
        kickoff_utc=_KICKOFF, decision_offset_hours=2.0,
        market_odds_over_2_5=1.9, market_odds_under_2_5=1.9,
    )
    assert compute_prediction_id(**kwargs) == compute_prediction_id(**kwargs)


def test_compute_prediction_id_differs_for_different_odds() -> None:
    base = dict(
        competition="liga", season="2025_26", home_team="Barcelona", away_team="Atletico Madrid",
        kickoff_utc=_KICKOFF, decision_offset_hours=2.0,
    )
    id_a = compute_prediction_id(**base, market_odds_over_2_5=1.9, market_odds_under_2_5=1.9)
    id_b = compute_prediction_id(**base, market_odds_over_2_5=2.1, market_odds_under_2_5=1.75)
    assert id_a != id_b


def test_compute_prediction_id_handles_missing_odds() -> None:
    kwargs = dict(
        competition="liga", season="2025_26", home_team="Barcelona", away_team="Atletico Madrid",
        kickoff_utc=_KICKOFF, decision_offset_hours=2.0,
        market_odds_over_2_5=None, market_odds_under_2_5=None,
    )
    assert compute_prediction_id(**kwargs) == compute_prediction_id(**kwargs)


# --- 9. comportement correct avec NO_BET ------------------------------------


def test_no_bet_never_produces_a_pnl_even_after_settlement(tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    output = _output(decision="NO_BET", decision_reason=["EDGE_BELOW_THRESHOLD"])
    record, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs())

    settled = settle_prediction(record["prediction_id"], home_goals=3, away_goals=2, journal_path=journal_path)
    assert settled["settlement"]["pnl_theoretical"] is None


def test_synthetic_bet_record_computes_pnl_correctly(tmp_path) -> None:
    """Le moteur ne produit actuellement jamais BET (min_edge_threshold=None) -
    ce test utilise une sortie SYNTHETIQUE avec decision="BET" pour verifier
    uniquement l'arithmetique du P&L theorique (convention flat 1 unite deja
    etablie par scripts/run_stage6_economic_b365_ev.py), jamais pour
    pretendre que le moteur produit reellement un BET."""
    journal_path = tmp_path / "predictions.jsonl"
    output = _output(decision="BET", decision_reason=[], market_odds_over_2_5=2.5, market_odds_under_2_5=1.6)
    record, _ = record_prediction(output, journal_path=journal_path, **_record_kwargs(market_odds_over_2_5=2.5, market_odds_under_2_5=1.6))

    settled_win = settle_prediction(record["prediction_id"], home_goals=2, away_goals=1, journal_path=journal_path)
    assert settled_win["settlement"]["pnl_theoretical"] == pytest.approx(1.5)  # Over gagnant : cote - 1

    journal_path_2 = tmp_path / "predictions_2.jsonl"
    record_2, _ = record_prediction(output, journal_path=journal_path_2, **_record_kwargs(market_odds_over_2_5=2.5, market_odds_under_2_5=1.6))
    settled_lose = settle_prediction(record_2["prediction_id"], home_goals=1, away_goals=0, journal_path=journal_path_2)
    assert settled_lose["settlement"]["pnl_theoretical"] == pytest.approx(-1.0)  # Under realise : perte flat
