"""Articulation edge + EV -> candidats a examiner.

CE MODULE NE SELECTIONNE PAS DE PARIS. ``passes_thresholds`` est une
condition NECESSAIRE (edge et EV tous deux au-dessus de seuils fournis
explicitement par l'appelant), PAS SUFFISANTE. Avant toute mise reelle,
un candidat doit en plus :

- avoir demontre un CLV positif hors echantillon de facon statistiquement
  significative (voir value_engine.clv et calibration_engine.significance) ;
- passer par le Risk Engine (etape 4, non implemente) pour le
  dimensionnement de la mise (jamais Full Kelly sur la seule confiance du
  modele - voir docs/research_framework.md, section F2) ;
- ne jamais etre decide sur la seule base de donnees synthetiques (voir
  le rapport de validation de l'etape 3 : les resultats synthetiques
  valident la mecanique de calcul, jamais un edge reel sur un marche reel).

``min_edge`` et ``min_ev`` sont des parametres OBLIGATOIRES (aucune
valeur par defaut) : le choix d'un seuil est une decision methodologique
a part entiere, qui doit etre faite consciemment par l'appelant a chaque
usage - jamais un defaut silencieux qui pourrait passer pour "valide".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sys_foot_quant.value_engine.edge import edge as compute_edge
from sys_foot_quant.value_engine.edge import expected_value

_SELECTIONS = ("home", "draw", "away")


@dataclass(frozen=True)
class ValueCandidate:
    match_id: int
    decision_time: datetime
    selection: str  # "home" / "draw" / "away"
    model_prob: float
    market_fair_prob: float
    odds_taken: float
    edge: float
    ev: float
    passes_thresholds: bool  # necessaire, PAS suffisant - voir docstring du module


def build_value_candidates(
    match_id: int,
    decision_time: datetime,
    model_probs: tuple[float, float, float],
    market_fair_probs: tuple[float, float, float],
    odds: dict[str, float],
    *,
    min_edge: float,
    min_ev: float,
) -> list[ValueCandidate]:
    """Construit un ``ValueCandidate`` par selection presente dans ``odds``
    (parmi home/draw/away), sans en filtrer aucun - le filtrage explicite
    se lit sur le champ ``passes_thresholds`` de chaque candidat, jamais
    en supprimant silencieusement les autres."""
    if len(model_probs) != 3 or len(market_fair_probs) != 3:
        raise ValueError("model_probs et market_fair_probs doivent avoir 3 elements (home,draw,away).")

    candidates: list[ValueCandidate] = []
    for i, sel in enumerate(_SELECTIONS):
        if sel not in odds:
            continue
        model_prob = model_probs[i]
        market_fair_prob = market_fair_probs[i]
        odds_taken = odds[sel]
        e = compute_edge(model_prob, market_fair_prob)
        ev = expected_value(model_prob, odds_taken)
        candidates.append(
            ValueCandidate(
                match_id=match_id,
                decision_time=decision_time,
                selection=sel,
                model_prob=model_prob,
                market_fair_prob=market_fair_prob,
                odds_taken=odds_taken,
                edge=e,
                ev=ev,
                passes_thresholds=(e > min_edge and ev > min_ev),
            )
        )
    return candidates
