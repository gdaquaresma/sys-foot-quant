"""Objets de sortie du moteur final - docs/final_engine_specification.md
section 15. Dataclasses immuables (``frozen=True``) : chaque niveau du
pipeline produit une sortie qui n'est plus modifiee par les niveaux
suivants (section 3 - aucune etape ne se substitue a une autre).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ModelPrediction:
    """Sortie du Niveau A (Prediction) pour un modele donne."""

    model: str
    lam: float
    mu: float
    rho: float | None  # non None uniquement pour dixon_coles
    n_train_matches: int


@dataclass(frozen=True)
class CalibratedGoalDistribution:
    """Sortie du Niveau B (Calibration, E7/E8) pour un modele donne.

    ``goal_distribution``/``probabilities`` sont None si l'historique de
    calibration etait insuffisant (``scale_c`` non estimable) - jamais une
    valeur de repli inventee (docs/final_engine_specification.md section 7)."""

    model: str
    scale_c: float | None
    n_calibration_used: int
    goal_distribution: tuple[float, ...] | None
    probabilities: dict[float, float] | None


@dataclass(frozen=True)
class PricingResult:
    """Sortie du Niveau C (Pricing) : cote juste par seuil, derivee
    directement des probabilites du Niveau B - aucune donnee de marche."""

    fair_price: dict[float, float]


@dataclass(frozen=True)
class MarketComparisonResult:
    """Sortie du Niveau D (Market comparison). Le marche n'est jamais un
    adversaire ni un oracle - uniquement un benchmark de prix
    (docs/final_engine_specification.md section 10)."""

    market_odds: dict[str, float]
    market_implied_probability_raw: dict[str, float]
    market_implied_probability_normalized: dict[str, float]
    market_overround: float
    raw_edge: dict[str, float]
    price_edge: dict[str, float]


@dataclass(frozen=True)
class GateResult:
    """Un controle en LECTURE SEULE : qualifie une prediction deja
    produite, ne la modifie jamais (docs/final_engine_specification.md
    section 12). ``failure_code`` est None si le gate n'est pas declenche,
    ou si le gate declenche n'est pas rattache a un code NO_BET direct."""

    name: str
    triggered: bool
    reason: str
    metric: str
    observed_value: object
    threshold: object
    failure_code: str | None = None


@dataclass(frozen=True)
class QualificationResult:
    """Sortie du Niveau E (Qualification)."""

    calibration_status: dict[float, str]
    discrimination_status: str
    data_quality: list[str]
    scientific_gates: list[GateResult]
    operational_gates: list[GateResult]


@dataclass(frozen=True)
class DecisionResult:
    """Sortie du Niveau F (Decision). ``decision_reason`` est une liste de
    codes stables (docs/final_engine_specification.md section 14) - vide
    uniquement si ``decision == "BET"``."""

    decision: str  # "BET" | "NO_BET"
    decision_reason: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MatchDecisionOutput:
    """Objet de sortie complet du moteur pour un match, un modele
    principal et un marche (docs/final_engine_specification.md section
    15/17) - auditable : toute decision doit pouvoir etre reconstruite a
    partir de ce seul objet."""

    match_id: str
    timestamp_decision: datetime
    competition: str
    season: str
    primary_model: str

    models: dict[str, ModelPrediction | None]
    calibration: dict[str, CalibratedGoalDistribution]
    pricing: dict[str, PricingResult | None]
    market: MarketComparisonResult | None

    qualification: QualificationResult
    decision: DecisionResult

    engine_version: str
    parameters_snapshot: dict
