"""Critere de Kelly : calcul theorique INFORMATIF uniquement.

``kelly_fraction`` est une fonction pure, jamais bridee - elle sert a
afficher/journaliser la recommandation theorique, y compris a des fins
pedagogiques (comparaison a Flat Betting, section D1 de
docs/research_framework.md). Pour produire une VRAIE mise, il faut passer
par ``kelly_stake``, qui refuse de s'executer tant que le quality gate
(``KellyQualityGateResult.unlocked``) n'est pas explicitement leve.

Aucun gate n'est leve par ce projet a ce stade (aucune donnee reelle,
aucune validation CLV hors echantillon, aucune approbation humaine) : le
systeme reste donc, par construction, en Flat Betting uniquement en
production - conformement au cahier des charges de l'etape 4.

Full Kelly n'est JAMAIS accessible via ``kelly_stake`` (multiplicateur
plafonne a 0.5 = Half-Kelly) : voir docs/research_framework.md, section
F2 ("Full Kelly - a rejeter... conduisant mathematiquement a la ruine").
Il reste calculable via ``kelly_fraction`` a titre de reference theorique
(ex: dans les simulations Monte Carlo comparatives).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test

# Fractions pre-enregistrees (Epstein ; Half-Kelly ~75% de la croissance
# pour une volatilite bien moindre que Full Kelly - voir research
# framework D1). Valeurs citees dans la litterature, PAS optimisees sur
# nos donnees.
QUARTER_KELLY = 0.25
HALF_KELLY = 0.50
_MAX_ALLOWED_KELLY_MULTIPLIER = HALF_KELLY  # Full Kelly structurellement inaccessible via kelly_stake()


def kelly_fraction(model_prob: float, odds: float) -> float:
    """Fraction theorique de Kelly complet : ``(p*cote - 1) / (cote - 1)``.

    PUREMENT INFORMATIF. Peut etre negative (absence d'edge) : par
    convention, une valeur negative signifie "ne pas parier", jamais une
    mise negative - c'est a l'appelant de l'ecreter a 0 si necessaire
    (fait automatiquement par ``kelly_stake``).
    """
    if not (0.0 <= model_prob <= 1.0):
        raise ValueError(f"model_prob doit etre dans [0, 1] (recu {model_prob}).")
    if odds <= 1.0:
        raise ValueError(f"odds doit etre > 1.0 (recu {odds}).")
    return (model_prob * odds - 1.0) / (odds - 1.0)


@dataclass(frozen=True)
class KellyGateThresholds:
    """Seuils du quality gate, PRE-ENREGISTRES et non optimises sur aucun
    dataset de test (cahier des charges etape 4). A revalider
    explicitement avant tout usage reel - jamais ajustes pour faire
    passer un cas particulier."""

    min_observations: int = 200
    min_clv_ci_low: float = 0.0  # la borne basse de l'IC95% du CLV doit depasser strictement ce seuil


@dataclass(frozen=True)
class KellyQualityGateResult:
    unlocked: bool
    reasons_blocked: tuple[str, ...] = field(default_factory=tuple)


def evaluate_kelly_quality_gate(
    n_clv_observations: int,
    clv_bootstrap_result: dict | None,
    manual_human_approval: bool,
    thresholds: KellyGateThresholds = KellyGateThresholds(),
) -> KellyQualityGateResult:
    """Trois conditions, TOUTES necessaires :
    1. Echantillon de CLV suffisant (``min_observations``) ;
    2. CLV significativement positif hors echantillon (IC95% bas > seuil) ;
    3. Approbation humaine explicite (``manual_human_approval=True``) -
       jamais mise a True automatiquement par ce code.
    """
    reasons: list[str] = []
    if n_clv_observations < thresholds.min_observations:
        reasons.append(
            f"Echantillon CLV insuffisant : {n_clv_observations} < {thresholds.min_observations}."
        )
    if clv_bootstrap_result is None:
        reasons.append("Aucun test de significativite CLV fourni.")
    elif clv_bootstrap_result["ci_low"] <= thresholds.min_clv_ci_low:
        reasons.append(
            "CLV non significativement positif hors echantillon (IC95% bas = "
            f"{clv_bootstrap_result['ci_low']:.4f} <= {thresholds.min_clv_ci_low})."
        )
    if not manual_human_approval:
        reasons.append("Approbation humaine explicite manquante (manual_human_approval=False).")
    return KellyQualityGateResult(unlocked=(len(reasons) == 0), reasons_blocked=tuple(reasons))


def evaluate_kelly_quality_gate_from_value_log(
    value_log: pd.DataFrame,
    as_of: datetime,
    manual_human_approval: bool,
    thresholds: KellyGateThresholds = KellyGateThresholds(),
    n_resamples: int = 2000,
    seed: int = 0,
) -> KellyQualityGateResult:
    """Variante point-in-time : ne prend en compte que les lignes de
    ``value_log`` dont ``decision_time <= as_of`` - garde-fou
    anti-look-ahead explicite. Evaluer ce gate avec des observations de
    CLV futures invaliderait completement sa raison d'etre (voir ADR 0003)."""
    visible = value_log[value_log["decision_time"] <= as_of]
    clv_values = visible["clv_pct"].dropna().to_numpy()
    if len(clv_values) < 2:
        return evaluate_kelly_quality_gate(
            n_clv_observations=len(clv_values),
            clv_bootstrap_result=None,
            manual_human_approval=manual_human_approval,
            thresholds=thresholds,
        )
    boot = paired_bootstrap_test(clv_values, n_resamples=n_resamples, seed=seed)
    return evaluate_kelly_quality_gate(
        n_clv_observations=len(clv_values),
        clv_bootstrap_result=boot,
        manual_human_approval=manual_human_approval,
        thresholds=thresholds,
    )


class KellyGateLockedError(RuntimeError):
    """Levee par ``kelly_stake`` quand le quality gate n'est pas leve."""


def kelly_stake(
    bankroll: float,
    model_prob: float,
    odds: float,
    kelly_multiplier: float,
    gate_result: KellyQualityGateResult,
) -> float:
    """Mise Kelly fractionnaire REELLE - refuse de s'executer tant que
    ``gate_result.unlocked`` n'est pas True (leve ``KellyGateLockedError``).

    ``kelly_multiplier`` est plafonne a 0.5 (Half-Kelly) : Full Kelly
    n'est jamais accessible par cette fonction (voir docstring du module).
    """
    if not gate_result.unlocked:
        raise KellyGateLockedError(
            "Kelly fractionnaire verrouille - raison(s) : " + "; ".join(gate_result.reasons_blocked)
        )
    if not (0.0 < kelly_multiplier <= _MAX_ALLOWED_KELLY_MULTIPLIER):
        raise ValueError(
            f"kelly_multiplier doit etre dans ]0, {_MAX_ALLOWED_KELLY_MULTIPLIER}] "
            f"(Full Kelly est structurellement interdit) - recu {kelly_multiplier}."
        )
    if bankroll <= 0:
        raise ValueError(f"bankroll doit etre strictement positif (recu {bankroll}).")

    f = max(kelly_fraction(model_prob, odds), 0.0)
    return bankroll * f * kelly_multiplier
