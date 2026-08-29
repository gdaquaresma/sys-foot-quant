from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sys_foot_quant.final_engine import reason_codes
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
)
from sys_foot_quant.football_model.goal_distribution import over_under_probs, total_goals_distribution
from sys_foot_quant.football_model.scoring import score_matrix


def _dt(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, 15, 0, tzinfo=timezone.utc)


# --- insufficient_data_gate --------------------------------------------------


def test_insufficient_data_gate_triggers_below_threshold() -> None:
    gate = insufficient_data_gate(5, min_train_matches=10)
    assert gate.triggered
    assert gate.failure_code == reason_codes.INSUFFICIENT_HISTORY


def test_insufficient_data_gate_does_not_trigger_at_or_above_threshold() -> None:
    assert not insufficient_data_gate(10, min_train_matches=10).triggered
    assert not insufficient_data_gate(50, min_train_matches=10).triggered


# --- insufficient_calibration_history_gate ----------------------------------


def test_insufficient_calibration_history_gate() -> None:
    assert insufficient_calibration_history_gate(29, min_matches=30).triggered
    assert not insufficient_calibration_history_gate(30, min_matches=30).triggered


# --- ambiguous_day_gate -------------------------------------------------------


def test_ambiguous_day_gate_triggers_on_monday_tuesday_friday() -> None:
    # 2025-01-06 = lundi, 2025-01-07 = mardi, 2025-01-10 = vendredi (UTC, Londres = UTC en hiver)
    for d in (6, 7, 10):
        gate = ambiguous_day_gate(_dt(2025, 1, d))
        assert gate.triggered, f"jour {d} janvier 2025 devrait etre ambigu"
        assert gate.failure_code == reason_codes.AMBIGUOUS_COLLECTION_DAY


def test_ambiguous_day_gate_does_not_trigger_on_weekend_or_wed_thu() -> None:
    # 2025-01-11 = samedi, 2025-01-08 = mercredi
    for d in (11, 8):
        gate = ambiguous_day_gate(_dt(2025, 1, d))
        assert not gate.triggered


# --- incomplete_market_odds_gate ---------------------------------------------


def test_incomplete_market_odds_gate_triggers_on_missing_odds() -> None:
    gate = incomplete_market_odds_gate(None)
    assert gate.triggered
    assert gate.failure_code == reason_codes.MARKET_DATA_UNAVAILABLE


def test_incomplete_market_odds_gate_triggers_on_invalid_odds() -> None:
    gate = incomplete_market_odds_gate({"Over": 0.5, "Under": 2.0})  # cote <= 1.0 invalide
    assert gate.triggered


def test_incomplete_market_odds_gate_passes_on_valid_odds() -> None:
    gate = incomplete_market_odds_gate({"Over": 1.9, "Under": 2.0})
    assert not gate.triggered


# --- distribution_consistency_gate -------------------------------------------


def test_distribution_consistency_gate_passes_for_a_valid_distribution() -> None:
    matrix = score_matrix(1.4, 1.1)
    matrix = matrix / matrix.sum()
    dist = tuple(float(x) for x in total_goals_distribution(matrix))
    ou = over_under_probs(matrix, thresholds=(0.5, 1.5, 2.5, 3.5, 4.5))
    gate = distribution_consistency_gate(dist, ou)
    assert not gate.triggered


def test_distribution_consistency_gate_triggers_on_tampered_probability() -> None:
    matrix = score_matrix(1.4, 1.1)
    matrix = matrix / matrix.sum()
    dist = tuple(float(x) for x in total_goals_distribution(matrix))
    ou = over_under_probs(matrix, thresholds=(2.5,))
    tampered = {2.5: ou[2.5] + 0.3}
    gate = distribution_consistency_gate(dist, tampered)
    assert gate.triggered
    assert gate.failure_code == reason_codes.DISTRIBUTION_INCONSISTENT


def test_distribution_consistency_gate_does_not_trigger_when_no_distribution() -> None:
    gate = distribution_consistency_gate(None, None)
    assert not gate.triggered
    assert gate.failure_code is None


# --- calibration_zone_gate ----------------------------------------------------


def test_calibration_zone_gate_triggers_in_biased_zone() -> None:
    gate = calibration_zone_gate(2.5, 0.65)
    assert gate.triggered
    assert gate.failure_code == reason_codes.INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE


def test_calibration_zone_gate_does_not_trigger_outside_biased_zone() -> None:
    gate = calibration_zone_gate(2.5, 0.5)
    assert not gate.triggered


def test_calibration_zone_gate_flags_unvalidated_thresholds() -> None:
    gate = calibration_zone_gate(0.5, 0.9)
    assert gate.triggered  # INSUFFICIENT_VALIDATION != OK


# --- discrimination_gate ------------------------------------------------------


def test_discrimination_gate_triggers_for_premier_league() -> None:
    gate = discrimination_gate("Premier League")
    assert gate.triggered
    assert gate.failure_code == reason_codes.DISCRIMINATION_NOT_DEMONSTRATED


def test_discrimination_gate_does_not_trigger_for_liga() -> None:
    gate = discrimination_gate("Liga")
    assert not gate.triggered


def test_discrimination_gate_triggers_for_unaudited_competition() -> None:
    gate = discrimination_gate("Bundesliga")
    assert gate.triggered


# --- operational gates --------------------------------------------------------


def test_calibration_confidence_gate_respects_configured_requirement() -> None:
    thresholds = OperationalThresholds(require_calibration_ok=True)
    assert calibration_confidence_gate("ZONE_BIAISEE_NON_CORRIGEE", thresholds).triggered
    assert not calibration_confidence_gate("OK", thresholds).triggered

    lenient = OperationalThresholds(require_calibration_ok=False)
    assert not calibration_confidence_gate("ZONE_BIAISEE_NON_CORRIGEE", lenient).triggered


def test_discrimination_confidence_gate_respects_configured_requirement() -> None:
    thresholds = OperationalThresholds(require_discrimination_demontree=True)
    assert discrimination_confidence_gate("NON_DEMONTREE", thresholds).triggered
    assert not discrimination_confidence_gate("DEMONTREE", thresholds).triggered


def test_edge_threshold_gate_always_triggers_when_threshold_unset() -> None:
    """docs/final_engine_specification.md section 13 : min_edge_threshold
    est 'Non fixe' - aucune valeur numerique n'a ete validee par E1-E16, le
    gate doit donc TOUJOURS se declencher par defaut, quel que soit l'edge
    observe (jamais une conclusion positive sans regle validee)."""
    thresholds = OperationalThresholds()  # min_edge_threshold=None par defaut
    assert edge_threshold_gate(0.5, thresholds).triggered
    assert edge_threshold_gate(-0.5, thresholds).triggered
    assert edge_threshold_gate(None, thresholds).triggered
    for gate in (edge_threshold_gate(0.5, thresholds), edge_threshold_gate(-0.5, thresholds)):
        assert gate.failure_code == reason_codes.EDGE_BELOW_THRESHOLD


def test_edge_threshold_gate_uses_configured_threshold_when_set() -> None:
    thresholds = OperationalThresholds(min_edge_threshold=0.1)
    assert not edge_threshold_gate(0.2, thresholds).triggered
    assert edge_threshold_gate(0.05, thresholds).triggered
