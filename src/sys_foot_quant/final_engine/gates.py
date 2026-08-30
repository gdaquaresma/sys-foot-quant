"""Niveau E - Qualification : scientific gates et operational gates
(docs/final_engine_specification.md sections 3, 12, 13).

Chaque gate est un controle EN LECTURE SEULE - il qualifie une prediction
deja produite par les Niveaux A-D, il ne la modifie JAMAIS. Les
`SCIENTIFIC GATE` traduisent un fait etabli par E1-E16 (non negociable) ;
les `OPERATIONAL GATE` traduisent un choix de gestion du risque, toujours
`PARAMETRE OPERATIONNEL A VALIDER`, jamais presente comme scientifiquement
optimal (docs/research_synthesis_e1_e16.md section 5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from sys_foot_quant.data_engine.market_odds.economic_dataset import MIN_TRAIN_MATCHES
from sys_foot_quant.data_engine.market_odds.time_resolution import (
    AmbiguousCollectionWindowError,
    conservative_knowledge_time_utc,
)
from sys_foot_quant.calibration_engine.scalar_correction import MIN_CALIBRATION_MATCHES_FOR_SCALE
from sys_foot_quant.final_engine import reason_codes
from sys_foot_quant.final_engine.reference_tables import (
    CALIBRATION_OK,
    calibration_status_for,
    discrimination_status,
)
from sys_foot_quant.final_engine.types import GateResult
from sys_foot_quant.football_model.goal_distribution import (
    check_distribution_validity,
    check_over_under_matches_distribution,
    check_over_under_monotonic,
)
from sys_foot_quant.market_engine.overround import validate_odds


# ---------------------------------------------------------------------------
# SCIENTIFIC GATES (docs/final_engine_specification.md section 12)
# ---------------------------------------------------------------------------


def insufficient_data_gate(n_train_matches: int, min_train_matches: int = MIN_TRAIN_MATCHES) -> GateResult:
    """E1 (MIN_TRAIN_MATCHES) - historique de modele insuffisant."""
    triggered = n_train_matches < min_train_matches
    return GateResult(
        name="insufficient_data_gate",
        triggered=triggered,
        reason="Historique de modele insuffisant (E1, MIN_TRAIN_MATCHES).",
        metric="n_train_matches",
        observed_value=n_train_matches,
        threshold=min_train_matches,
        failure_code=reason_codes.INSUFFICIENT_HISTORY if triggered else None,
    )


def insufficient_calibration_history_gate(
    n_calibration_used: int, min_matches: int = MIN_CALIBRATION_MATCHES_FOR_SCALE
) -> GateResult:
    """E8 (_MIN_CALIBRATION_MATCHES_FOR_SCALE) - historique de calibration
    E7/E8 insuffisant pour estimer le facteur d'echelle."""
    triggered = n_calibration_used < min_matches
    return GateResult(
        name="insufficient_calibration_history_gate",
        triggered=triggered,
        reason="Historique de calibration E7/E8 insuffisant pour estimer le facteur d'echelle.",
        metric="n_calibration_used",
        observed_value=n_calibration_used,
        threshold=min_matches,
        failure_code=reason_codes.INSUFFICIENT_HISTORY if triggered else None,
    )


def unknown_team_gate(home_team_id: int, away_team_id: int, goals_train_df: pd.DataFrame) -> GateResult:
    """Audit pre-production (2026-08) - une equipe jamais presente dans
    ``goals_train_df`` (ni domicile ni exterieur) recoit, au Niveau A,
    une prediction NEUTRE silencieuse (comportement DELIBERE et deja
    teste de ``PoissonModel``/``DixonColesModel``, inchange ici) -
    ``insufficient_data_gate`` ne verifie que la taille AGREGEE de
    l'historique, jamais la presence de CES deux equipes precises. Ce
    gate comble cet angle mort : sans historique du tout pour l'une des
    deux equipes, la prediction ne peut pas etre distinguee d'une
    prediction de « moyenne de la ligue » et ne doit jamais qualifier une
    decision positive."""
    if len(goals_train_df) == 0:
        known_ids: set = set()
    else:
        known_ids = set(goals_train_df["home_team_id"]) | set(goals_train_df["away_team_id"])
    unknown = [t for t in (home_team_id, away_team_id) if t not in known_ids]
    triggered = bool(unknown)
    return GateResult(
        name="unknown_team_gate",
        triggered=triggered,
        reason="Une des deux equipes n'apparait dans aucun match de l'historique d'entrainement.",
        metric="unknown_team_ids",
        observed_value=unknown,
        threshold="les deux equipes doivent avoir au moins un match dans l'historique",
        failure_code=reason_codes.INSUFFICIENT_HISTORY if triggered else None,
    )


def ambiguous_day_gate(kickoff_utc: datetime) -> GateResult:
    """E1 - jour de collecte de cote non fiable (lundi/mardi/vendredi).
    Reutilise SANS MODIFICATION ``conservative_knowledge_time_utc``, jamais
    une reimplementation du calcul de jour de la semaine."""
    try:
        conservative_knowledge_time_utc(kickoff_utc)
        triggered = False
        detail = "Jour de collecte non ambigu."
    except AmbiguousCollectionWindowError as exc:
        triggered = True
        detail = str(exc)
    return GateResult(
        name="ambiguous_day_gate",
        triggered=triggered,
        reason=detail,
        metric="kickoff_utc_weekday",
        observed_value=kickoff_utc.isoformat(),
        threshold="lundi/mardi/vendredi exclus",
        failure_code=reason_codes.AMBIGUOUS_COLLECTION_DAY if triggered else None,
    )


def incomplete_market_odds_gate(market_odds: dict[str, float] | None) -> GateResult:
    """E1/E5 - cote de marche incomplete ou absente a decision_time.
    Reutilise SANS MODIFICATION ``market_engine.overround.validate_odds``."""
    if market_odds is None:
        return GateResult(
            name="incomplete_market_odds_gate",
            triggered=True,
            reason="Aucune cote de marche disponible a decision_time.",
            metric="market_odds",
            observed_value=None,
            threshold="cote complete requise",
            failure_code=reason_codes.MARKET_DATA_UNAVAILABLE,
        )
    try:
        validate_odds(market_odds)
        triggered = False
        detail = "Cote de marche valide."
    except ValueError as exc:
        triggered = True
        detail = str(exc)
    return GateResult(
        name="incomplete_market_odds_gate",
        triggered=triggered,
        reason=detail,
        metric="market_odds",
        observed_value=market_odds,
        threshold="cote complete requise",
        failure_code=reason_codes.MARKET_DATA_UNAVAILABLE if triggered else None,
    )


def distribution_consistency_gate(
    goal_distribution: tuple[float, ...] | None, probabilities: dict[float, float] | None
) -> GateResult:
    """E7 section 6 - coherence structurelle de la distribution de buts.
    Ne devrait JAMAIS se declencher en pratique (signalerait un bug amont,
    pas une condition normale d'entree) - alerte technique, pas une
    condition d'abstention ordinaire."""
    if goal_distribution is None or probabilities is None:
        # Rien a verifier - l'absence de distribution est deja couverte par
        # insufficient_calibration_history_gate, jamais un doublon d'echec ici.
        return GateResult(
            name="distribution_consistency_gate",
            triggered=False,
            reason="Aucune distribution a verifier (calibration non estimee).",
            metric="goal_distribution",
            observed_value=None,
            threshold=None,
            failure_code=None,
        )
    dist_array = np.array(goal_distribution)
    validity = check_distribution_validity(dist_array)
    monotonic = check_over_under_monotonic(probabilities)
    matches = check_over_under_matches_distribution(dist_array, probabilities)
    triggered = not (validity["all_non_negative"] and validity["sums_to_one"] and monotonic and matches)
    return GateResult(
        name="distribution_consistency_gate",
        triggered=triggered,
        reason="Incoherence structurelle de la distribution de buts (bug amont, jamais attendu).",
        metric="distribution_checks",
        observed_value={
            "all_non_negative": validity["all_non_negative"],
            "sums_to_one": validity["sums_to_one"],
            "monotonic": monotonic,
            "matches_distribution": matches,
        },
        threshold="toutes les verifications doivent etre vraies",
        failure_code=reason_codes.DISTRIBUTION_INCONSISTENT if triggered else None,
    )


def calibration_zone_gate(threshold: float, probability: float | None) -> GateResult:
    """E11/E14 - zone [0.6,0.7) d'Over 2.5, sur-confiance demontree, JAMAIS
    corrigee (E14 rejetee). Le gate observe, il ne modifie jamais la
    probabilite (docs/final_engine_specification.md section 8)."""
    if probability is None:
        status = None
        triggered = False
    else:
        status = calibration_status_for(threshold, probability)
        triggered = status != CALIBRATION_OK
    return GateResult(
        name="calibration_zone_gate",
        triggered=triggered,
        reason="Zone de calibration non OK pour ce seuil (E11/E14) - probabilite affichee mais non corrigee.",
        metric=f"calibration_status[{threshold}]",
        observed_value=status,
        threshold=CALIBRATION_OK,
        failure_code=reason_codes.INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE if triggered else None,
    )


def discrimination_gate(competition: str) -> GateResult:
    """E4/E11/E15 - discrimination non demontree pour ce championnat
    (Premier League) ou championnat jamais audite (NON_EVALUEE)."""
    status = discrimination_status(competition)
    triggered = status != "DEMONTREE"
    return GateResult(
        name="discrimination_gate",
        triggered=triggered,
        reason="Discrimination non demontree pour ce championnat (E4/E11/E15).",
        metric="discrimination_status",
        observed_value=status,
        threshold="DEMONTREE",
        failure_code=reason_codes.DISCRIMINATION_NOT_DEMONSTRATED if triggered else None,
    )


# ---------------------------------------------------------------------------
# OPERATIONAL GATES (docs/final_engine_specification.md section 13) -
# PARAMETRE OPERATIONNEL A VALIDER : aucune de ces valeurs par defaut n'est
# presentee comme scientifiquement optimale ou validee par E1-E16.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationalThresholds:
    """PARAMETRE OPERATIONNEL A VALIDER (docs/final_engine_specification.md
    sections 11, 13). Valeurs par defaut reprises TELLES QUELLES de la
    specification - jamais optimisees, jamais choisies pour maximiser une
    rentabilite quelconque."""

    require_calibration_ok: bool = True
    require_discrimination_demontree: bool = True
    abstain_on_calibration_zone: bool = True
    # "Non fixe" dans la specification (section 13) : AUCUNE valeur d'edge
    # minimal n'a ete validee par E1-E16 (E5/E10/E12 : le desaccord n'est
    # jamais fiable, quelle que soit son amplitude). Tant que cette valeur
    # reste None, le gate d'edge se declenche TOUJOURS - consequence director
    # de l'absence de regle validee, jamais une valeur numerique inventee.
    min_edge_threshold: float | None = None


def calibration_confidence_gate(calibration_status_value: str, thresholds: OperationalThresholds) -> GateResult:
    triggered = thresholds.require_calibration_ok and calibration_status_value != CALIBRATION_OK
    return GateResult(
        name="calibration_confidence_gate",
        triggered=triggered,
        reason="Confiance de calibration insuffisante (seuil operationnel : calibration_status == OK requis).",
        metric="calibration_status",
        observed_value=calibration_status_value,
        threshold=CALIBRATION_OK if thresholds.require_calibration_ok else None,
        failure_code=reason_codes.INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE if triggered else None,
    )


def discrimination_confidence_gate(discrimination_status_value: str, thresholds: OperationalThresholds) -> GateResult:
    triggered = thresholds.require_discrimination_demontree and discrimination_status_value != "DEMONTREE"
    return GateResult(
        name="discrimination_confidence_gate",
        triggered=triggered,
        reason="Confiance de discrimination insuffisante (seuil operationnel : discrimination DEMONTREE requise).",
        metric="discrimination_status",
        observed_value=discrimination_status_value,
        threshold="DEMONTREE" if thresholds.require_discrimination_demontree else None,
        failure_code=reason_codes.DISCRIMINATION_NOT_DEMONSTRATED if triggered else None,
    )


def edge_threshold_gate(raw_edge: float | None, thresholds: OperationalThresholds) -> GateResult:
    """PARAMETRE OPERATIONNEL A VALIDER - ``min_edge_threshold`` n'a jamais
    ete fixe par E1-E16 (section 13 : "Non fixe"). Tant qu'il reste
    ``None``, aucun edge ne peut etre confirme suffisant - le gate se
    declenche systematiquement, ce qui traduit fidelement l'absence de
    regle validee plutot que d'inventer un seuil numerique."""
    if thresholds.min_edge_threshold is None:
        return GateResult(
            name="edge_threshold_gate",
            triggered=True,
            reason="Aucun seuil d'edge minimal valide par E1-E16 (PARAMETRE OPERATIONNEL A VALIDER, jamais fixe).",
            metric="raw_edge",
            observed_value=raw_edge,
            threshold=None,
            failure_code=reason_codes.EDGE_BELOW_THRESHOLD,
        )
    triggered = raw_edge is None or raw_edge < thresholds.min_edge_threshold
    return GateResult(
        name="edge_threshold_gate",
        triggered=triggered,
        reason="Edge sous le seuil operationnel configure.",
        metric="raw_edge",
        observed_value=raw_edge,
        threshold=thresholds.min_edge_threshold,
        failure_code=reason_codes.EDGE_BELOW_THRESHOLD if triggered else None,
    )
