"""Niveau F - Decision (docs/final_engine_specification.md sections 3, 14).

``NO_BET`` est une sortie de PREMIER ORDRE, jamais une erreur - c'est la
sortie attendue par defaut du moteur minimal viable
(docs/research_synthesis_e1_e16.md section 13 : "aucune regle positive de
conversion edge->pari n'est implementee dans le MVP"). Ce module reste
generiquement correct (``BET`` est un chemin de code atteignable) ; ce
sont les valeurs PAR DEFAUT des ``OperationalThresholds`` (``gates.py``,
notamment ``min_edge_threshold=None``) qui garantissent que le MVP ne
produit jamais ``BET`` tant qu'aucune regle n'a ete validee - jamais un
codage en dur de cette impossibilite."""

from __future__ import annotations

from sys_foot_quant.final_engine.types import DecisionResult, GateResult


def decide(scientific_gates: list[GateResult], operational_gates: list[GateResult]) -> DecisionResult:
    """Un gate scientifique OU operationnel declenche => NO_BET, jamais une
    modification retroactive de la probabilite modele. Si aucun gate ne se
    declenche, BET est retourne - dans la configuration par defaut du MVP
    (``edge_threshold_gate`` toujours declenche tant que
    ``min_edge_threshold`` reste None), ce chemin n'est jamais emprunte."""
    triggered = [g for g in scientific_gates + operational_gates if g.triggered]
    if not triggered:
        return DecisionResult(decision="BET", decision_reason=[])

    codes = sorted({g.failure_code for g in triggered if g.failure_code})
    return DecisionResult(decision="NO_BET", decision_reason=codes)
