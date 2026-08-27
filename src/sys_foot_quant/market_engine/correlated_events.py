"""Hypothese C7 - phase 1 uniquement (docs/research_framework.md section
C7) : existence d'une correlation empirique entre deux evenements de match
fixes A PRIORI, condition NECESSAIRE (pas suffisante) au mecanisme de
mauvaise tarification d'un combine par un bookmaker suppose independance.
Ne calcule aucun prix reel de combine (aucune cote de marche combine dans
notre schema actuel) - une eventuelle phase 2 (EV reel) n'est pas traitee
ici et n'est pas commencee.

Evenements figes avant tout calcul, jamais revus a la lecture des
resultats (voir echange de validation du protocole) :
- A ("favori a domicile") : l'equipe a domicile est favorite selon
  `poisson_simple` UNIQUEMENT (jamais `XGModel` ni `HybridXGModel`),
  calcule point-in-time / walk-forward (memes conventions que B3/B3.2) :
  A est vrai si P(victoire domicile) > P(victoire exterieur). Aucun seuil
  de magnitude - simple comparaison de signe, pour eviter le risque de
  seuil ajuste apres coup deja signale dans le corpus pour C3/C4.
- B ("Over 2.5 buts") : home_goals + away_goals >= 3.

Module isole : n'importe que `PoissonModel` (jamais les modeles xG), ne
modifie ni ne recalcule aucun modele officiel.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from sys_foot_quant.calibration_engine.significance import two_by_two_association_test


def label_home_favorite(prob_home_win: float, prob_away_win: float) -> bool:
    """Evenement A. Comparaison stricte, sans seuil : une egalite (favori
    ambigu) est traitee comme "non A", jamais comme favori a domicile."""
    return prob_home_win > prob_away_win


def label_over_2_5(home_goals: int, away_goals: int) -> bool:
    """Evenement B : Over 2.5 buts, ligne canonique de marche (non ajustee)."""
    return (home_goals + away_goals) >= 3


def eligible_match_ids_after_burn_in(
    match_ids_by_kickoff: list[tuple[str, datetime]], burn_in_fraction: float
) -> list[str]:
    """Exclut le rodage necessaire a `poisson_simple` (meme convention que
    B3/B3.2 : les premiers ``burn_in_fraction`` de la saison, tries par
    coup d'envoi, ne sont jamais evalues). Fonction PURE, ne prend que des
    identifiants et des horodatages (pas de dependance au reste du
    pipeline) pour rester testable isolement."""
    ordered = sorted(match_ids_by_kickoff, key=lambda pair: pair[1])
    n_total = len(ordered)
    n_burn_in = int(n_total * burn_in_fraction)
    return [match_id for match_id, _ in ordered[n_burn_in:]]


def association_result_from_predictions(
    rows: list[tuple[float, float, int, int]],
) -> dict[str, float | int | str]:
    """``rows`` : liste de (prob_home_win, prob_away_win, home_goals,
    away_goals), une entree par match eligible. Construit les deux
    vecteurs de labels et delegue le test statistique a
    ``two_by_two_association_test``."""
    labels_a = np.array([label_home_favorite(ph, pa) for ph, pa, _, _ in rows], dtype=bool)
    labels_b = np.array([label_over_2_5(hg, ag) for _, _, hg, ag in rows], dtype=bool)
    return two_by_two_association_test(labels_a, labels_b)


def per_league_bucket(estimation: dict[str, float], confirmation: dict[str, float]) -> str:
    """Classe une ligue en "positif_confirme" seulement si l'ecart
    P(B|A) - P(B|non A) est significativement positif (IC95% > 0) A LA
    FOIS en estimation (2024/25) ET en confirmation (2025/26, jamais
    reajustee) - sinon "non_positif" (couvre absence d'association et
    effet oppose)."""
    est_positive = estimation["ci_low"] > 0.0
    conf_positive = confirmation["ci_low"] > 0.0
    if est_positive and conf_positive:
        return "positif_confirme"
    return "non_positif"


def aggregate_verdict(buckets: list[str]) -> str:
    """Meme regle d'agregation que B1/B2/A1-recence/B3/B3.2 : les trois
    ligues doivent etre coherentes pour VALIDE ou REJETE, sinon INDETERMINE."""
    if all(b == "positif_confirme" for b in buckets):
        return "VALIDE"
    if all(b == "non_positif" for b in buckets):
        return "REJETE"
    return "INDETERMINE"
