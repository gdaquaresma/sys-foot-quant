"""Niveau B - Calibration (docs/final_engine_specification.md sections 3,
6, 7). Applique la correction scalaire walk-forward E7/E8 -
VALIDEE SCIENTIFIQUEMENT, PRINCIPE NON MODIFIE - puis reconstruit la
matrice de score complete et en derive la distribution de buts ET les
probabilites Over/Under EN UN SEUL APPEL (source unique, section 6).

N'INTEGRE PAS E14 : aucune isotonic calibration locale, aucune correction
logistique locale, aucune modification de la zone [0.6,0.7) - cette zone
est uniquement flaguee au Niveau E (``gates.py``/``reference_tables.py``),
jamais corrigee ici (docs/final_engine_specification.md section 8)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from sys_foot_quant.calibration_engine.scalar_correction import (
    MIN_CALIBRATION_MATCHES_FOR_SCALE,
    fit_scale_correction_as_of,
)
from sys_foot_quant.final_engine.types import CalibratedGoalDistribution, ModelPrediction
from sys_foot_quant.football_model.dixon_coles import apply_dixon_coles_correction
from sys_foot_quant.football_model.goal_distribution import (
    DEFAULT_MAX_BUCKET,
    DEFAULT_OU_THRESHOLDS,
    over_under_probs,
    total_goals_distribution,
)
from sys_foot_quant.football_model.scoring import score_matrix

_DEFAULT_MAX_GOALS = 20


def _corrected_matrix(lam: float, mu: float, rho: float | None, max_goals: int):
    """Reconstruit la matrice de score COMPLETE a partir de (lam, mu) DEJA
    corriges par le facteur d'echelle - identique en esprit a
    ``scripts/run_stage15_e7_total_goals_distribution.matrix_for_row``."""
    matrix = score_matrix(lam, mu, max_goals=max_goals)
    matrix = matrix / matrix.sum()
    if rho is not None:
        matrix = apply_dixon_coles_correction(matrix, lam, mu, rho)
    return matrix


def calibrate_prediction(
    model_prediction: ModelPrediction,
    calibration_df: pd.DataFrame,
    as_of_time: datetime,
    thresholds: tuple[float, ...] = DEFAULT_OU_THRESHOLDS,
    max_bucket: int = DEFAULT_MAX_BUCKET,
    max_goals: int = _DEFAULT_MAX_GOALS,
    min_calibration_matches: int = MIN_CALIBRATION_MATCHES_FOR_SCALE,
) -> CalibratedGoalDistribution:
    """Applique la correction E7/E8 a UNE prediction deja produite par le
    Niveau A. ``calibration_df`` doit porter les colonnes ``decision_time``,
    ``{model}_lambda``, ``{model}_mu``, ``total_goals`` (contrat identique a
    ``scalar_correction.fit_scale_correction_as_of``).

    Retourne ``goal_distribution=None``/``probabilities=None`` si
    l'historique de calibration est insuffisant (``scale_c`` non
    estimable) - jamais une distribution non corrigee presentee comme
    equivalente a la distribution corrigee (section 7)."""
    scale_c, n_calibration_used = fit_scale_correction_as_of(
        calibration_df, model_prediction.model, as_of_time, min_matches=min_calibration_matches
    )
    if scale_c is None:
        return CalibratedGoalDistribution(
            model=model_prediction.model,
            scale_c=None,
            n_calibration_used=n_calibration_used,
            goal_distribution=None,
            probabilities=None,
        )

    corrected_lam = scale_c * model_prediction.lam
    corrected_mu = scale_c * model_prediction.mu
    matrix = _corrected_matrix(corrected_lam, corrected_mu, model_prediction.rho, max_goals)

    dist = total_goals_distribution(matrix, max_bucket=max_bucket)
    ou = over_under_probs(matrix, thresholds=thresholds)

    return CalibratedGoalDistribution(
        model=model_prediction.model,
        scale_c=scale_c,
        n_calibration_used=n_calibration_used,
        goal_distribution=tuple(float(x) for x in dist),
        probabilities=ou,
    )
