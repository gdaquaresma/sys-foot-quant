from __future__ import annotations

import pytest

from sys_foot_quant.final_engine.reference_tables import (
    CALIBRATION_OK,
    CALIBRATION_ZONE_BIASED,
    CALIBRATION_INSUFFICIENT_VALIDATION,
    DISCRIMINATION_DEMONTREE,
    DISCRIMINATION_NON_DEMONTREE,
    DISCRIMINATION_NON_EVALUEE,
    calibration_status_for,
    discrimination_status,
)


@pytest.mark.parametrize(
    "competition,expected",
    [
        ("Liga", DISCRIMINATION_DEMONTREE),
        ("liga", DISCRIMINATION_DEMONTREE),
        ("Ligue 1", DISCRIMINATION_DEMONTREE),
        ("ligue_1", DISCRIMINATION_DEMONTREE),
        ("Premier League", DISCRIMINATION_NON_DEMONTREE),
        ("premier_league", DISCRIMINATION_NON_DEMONTREE),
        ("Bundesliga", DISCRIMINATION_NON_EVALUEE),
        ("Serie A", DISCRIMINATION_NON_EVALUEE),
    ],
)
def test_discrimination_status_matches_e4_e11_e15(competition: str, expected: str) -> None:
    assert discrimination_status(competition) == expected


def test_unaudited_competition_defaults_to_non_evaluee_never_demontree() -> None:
    """Position par defaut prudente (docs/final_engine_specification.md
    section 9) - un championnat jamais audite ne doit JAMAIS heriter d'une
    discrimination demontree par defaut."""
    assert discrimination_status("championnat_totalement_inconnu") == DISCRIMINATION_NON_EVALUEE


@pytest.mark.parametrize("threshold", [0.5, 4.5])
def test_unvalidated_thresholds_always_insufficient_validation(threshold: float) -> None:
    assert calibration_status_for(threshold, 0.5) == CALIBRATION_INSUFFICIENT_VALIDATION
    assert calibration_status_for(threshold, 0.99) == CALIBRATION_INSUFFICIENT_VALIDATION


def test_over_2_5_in_biased_zone_is_flagged() -> None:
    assert calibration_status_for(2.5, 0.6) == CALIBRATION_ZONE_BIASED
    assert calibration_status_for(2.5, 0.65) == CALIBRATION_ZONE_BIASED
    assert calibration_status_for(2.5, 0.6999) == CALIBRATION_ZONE_BIASED


def test_over_2_5_outside_biased_zone_is_ok() -> None:
    assert calibration_status_for(2.5, 0.5999) == CALIBRATION_OK
    assert calibration_status_for(2.5, 0.7) == CALIBRATION_OK
    assert calibration_status_for(2.5, 0.1) == CALIBRATION_OK


@pytest.mark.parametrize("threshold", [1.5, 3.5])
def test_1_5_and_3_5_never_flagged_by_the_2_5_specific_zone(threshold: float) -> None:
    """La zone biaisee est specifique a Over 2.5 (E11) - elle ne doit
    jamais deteindre sur 1.5/3.5 meme a la meme valeur de probabilite."""
    assert calibration_status_for(threshold, 0.65) == CALIBRATION_OK


def test_unsupported_threshold_raises() -> None:
    with pytest.raises(ValueError):
        calibration_status_for(2.0, 0.5)
