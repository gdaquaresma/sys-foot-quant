"""Orchestrateur du moteur final (docs/final_engine_specification.md
sections 2, 3, 15). Assemble les 6 niveaux SANS qu'aucun ne se substitue
a un autre : chaque niveau ne consomme que la sortie IMMUABLE du
precedent.

    Prediction -> Calibration -> Pricing -> Market comparison
        -> Qualification -> Decision

Le marche n'est compare qu'au modele PRINCIPAL (``poisson_simple``,
CHOIX ARCHITECTURAL, ``prediction.PRIMARY_MODEL``) sur le seuil Over 2.5
(le seul pour lequel Football-Data publie une cote, docs/final_engine_specification.md
section 4.3/7) - ``dixon_coles``/``xg_model`` restent calcules pour
tracabilite (section 5, section 19 du MVP) mais n'entrent jamais dans la
decision."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from sys_foot_quant.final_engine.calibration import calibrate_prediction
from sys_foot_quant.final_engine.gates import (
    OperationalThresholds,
    ambiguous_day_gate,
    calibration_confidence_gate,
    calibration_zone_gate,
    discrimination_confidence_gate,
    discrimination_gate,
    distribution_consistency_gate,
    edge_threshold_gate,
    incomplete_market_odds_gate,
    insufficient_calibration_history_gate,
    insufficient_data_gate,
    unknown_team_gate,
)
from sys_foot_quant.final_engine.market import compare_over_under_to_market
from sys_foot_quant.final_engine.decision import decide
from sys_foot_quant.final_engine.pricing import compute_fair_price
from sys_foot_quant.final_engine.prediction import PRIMARY_MODEL, predict_match
from sys_foot_quant.final_engine.reference_tables import calibration_status_for, discrimination_status
from sys_foot_quant.final_engine.types import (
    CalibratedGoalDistribution,
    DecisionResult,
    MatchDecisionOutput,
    PricingResult,
    QualificationResult,
)

ENGINE_VERSION = "final-engine-mvp-0.1.0"

# Seuil de marche disponible dans Football-Data (docs/final_engine_specification.md
# section 4.3, 7) - la seule ligne O/U comparable au marche a ce jour.
MARKET_COMPARISON_THRESHOLD = 2.5

DECISION_OFFSET_HOURS = 2.0  # identique a economic_dataset.DECISION_OFFSET_HOURS


def run_match_decision(
    match_id: str,
    competition: str,
    season: str,
    kickoff_utc: datetime,
    home_team_id: int,
    away_team_id: int,
    goals_train_df: pd.DataFrame,
    xg_train_df: pd.DataFrame | None,
    calibration_df_by_model: dict[str, pd.DataFrame],
    market_odds_over_2_5: float | None = None,
    market_odds_under_2_5: float | None = None,
    operational_thresholds: OperationalThresholds | None = None,
    decision_offset_hours: float = DECISION_OFFSET_HOURS,
) -> MatchDecisionOutput:
    """Execute le pipeline complet A->F pour un match et produit l'objet de
    sortie structure (section 15). ``goals_train_df``/``xg_train_df``
    doivent DEJA etre filtres point-in-time par l'appelant (delegue a
    ``matching.py``/``time_resolution.py``, jamais refiltre ici - section
    16). ``calibration_df_by_model`` porte, par modele, les colonnes
    ``decision_time``/``{model}_lambda``/``{model}_mu``/``total_goals``."""
    thresholds = operational_thresholds or OperationalThresholds()
    decision_time = kickoff_utc - timedelta(hours=decision_offset_hours)

    # --- Niveau A : Prediction --------------------------------------------
    predictions = predict_match(home_team_id, away_team_id, goals_train_df, xg_train_df)

    # --- Niveau B : Calibration (E7/E8, VALIDEE SCIENTIFIQUEMENT) ----------
    calibrated: dict[str, CalibratedGoalDistribution] = {}
    for model_name, pred in predictions.items():
        if pred is None:
            calibrated[model_name] = CalibratedGoalDistribution(
                model=model_name, scale_c=None, n_calibration_used=0, goal_distribution=None, probabilities=None
            )
            continue
        calibration_df = calibration_df_by_model.get(model_name)
        if calibration_df is None:
            calibrated[model_name] = CalibratedGoalDistribution(
                model=model_name, scale_c=None, n_calibration_used=0, goal_distribution=None, probabilities=None
            )
            continue
        calibrated[model_name] = calibrate_prediction(pred, calibration_df, decision_time)

    # --- Niveau C : Pricing --------------------------------------------------
    pricing: dict[str, PricingResult | None] = {
        name: PricingResult(compute_fair_price(c.probabilities)) if c.probabilities is not None else None
        for name, c in calibrated.items()
    }

    # --- Niveau D : Market comparison (modele PRINCIPAL uniquement) --------
    primary_calibration = calibrated[PRIMARY_MODEL]
    market_odds = None
    market = None
    if market_odds_over_2_5 is not None and market_odds_under_2_5 is not None:
        market_odds = {"Over": market_odds_over_2_5, "Under": market_odds_under_2_5}
    # La comparaison n'est calculee que si la cote est structurellement
    # valide (evite de propager une exception hors du pipeline - une cote
    # invalide doit produire NO_BET via incomplete_market_odds_gate,
    # jamais un crash) ET si le Niveau B a produit une probabilite.
    if market_odds is not None and primary_calibration.probabilities is not None and not incomplete_market_odds_gate(market_odds).triggered:
        market = compare_over_under_to_market(
            primary_calibration.probabilities[MARKET_COMPARISON_THRESHOLD],
            market_odds_over_2_5,
            market_odds_under_2_5,
        )

    # --- Niveau E : Qualification -------------------------------------------
    # Sous-ensemble "qualite des donnees" (docs/final_engine_specification.md
    # section 15) - distinct de calibration_status/discrimination_status,
    # qui ont leurs propres champs dedies.
    data_quality_gates = [
        insufficient_data_gate(predictions[PRIMARY_MODEL].n_train_matches if predictions[PRIMARY_MODEL] else 0),
        unknown_team_gate(home_team_id, away_team_id, goals_train_df),
        insufficient_calibration_history_gate(primary_calibration.n_calibration_used),
        ambiguous_day_gate(kickoff_utc),
        incomplete_market_odds_gate(market_odds),
        distribution_consistency_gate(primary_calibration.goal_distribution, primary_calibration.probabilities),
    ]
    calibration_gate = calibration_zone_gate(
        MARKET_COMPARISON_THRESHOLD,
        primary_calibration.probabilities.get(MARKET_COMPARISON_THRESHOLD)
        if primary_calibration.probabilities
        else None,
    )
    discrimination_scientific_gate = discrimination_gate(competition)

    scientific_gates = [*data_quality_gates, calibration_gate, discrimination_scientific_gate]

    calibration_status_by_threshold: dict[float, str] = {}
    if primary_calibration.probabilities is not None:
        for threshold, probability in primary_calibration.probabilities.items():
            calibration_status_by_threshold[threshold] = calibration_status_for(threshold, probability)

    discrimination_status_value = discrimination_status(competition)
    calibration_status_value = calibration_status_by_threshold.get(MARKET_COMPARISON_THRESHOLD, "INSUFFICIENT_VALIDATION")

    operational_gates = [
        calibration_confidence_gate(calibration_status_value, thresholds),
        discrimination_confidence_gate(discrimination_status_value, thresholds),
        edge_threshold_gate(
            market.raw_edge.get("Over") if market is not None else None,
            thresholds,
        ),
    ]

    data_quality = (
        ["OK"]
        if not any(g.triggered for g in data_quality_gates)
        else [g.failure_code for g in data_quality_gates if g.triggered and g.failure_code]
    )

    qualification = QualificationResult(
        calibration_status=calibration_status_by_threshold,
        discrimination_status=discrimination_status_value,
        data_quality=data_quality,
        scientific_gates=scientific_gates,
        operational_gates=operational_gates,
    )

    # --- Niveau F : Decision --------------------------------------------------
    decision_result: DecisionResult = decide(scientific_gates, operational_gates)

    return MatchDecisionOutput(
        match_id=match_id,
        timestamp_decision=decision_time,
        competition=competition,
        season=season,
        primary_model=PRIMARY_MODEL,
        models=predictions,
        calibration=calibrated,
        pricing=pricing,
        market=market,
        qualification=qualification,
        decision=decision_result,
        engine_version=ENGINE_VERSION,
        parameters_snapshot={
            "require_calibration_ok": thresholds.require_calibration_ok,
            "require_discrimination_demontree": thresholds.require_discrimination_demontree,
            "abstain_on_calibration_zone": thresholds.abstain_on_calibration_zone,
            "min_edge_threshold": thresholds.min_edge_threshold,
            "decision_offset_hours": decision_offset_hours,
        },
    )
