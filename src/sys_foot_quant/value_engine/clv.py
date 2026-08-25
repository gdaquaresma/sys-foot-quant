"""Closing Line Value (CLV) : metrique de qualite de prix A POSTERIORI.

RAPPEL (ADR 0003, docs/decisions/0003-prudence-benchmark-marche.md) : la
cote de cloture n'est jamais disponible au moment d'une decision
pre-match - elle ne peut donc jamais entrer dans un calcul d'edge ou d'EV
pre-match (voir value_engine.edge). Elle sert UNIQUEMENT, une fois le
match joue (ou du moins une fois la cloture reellement passee), a evaluer
la qualite du prix qui avait ete pris au moment de la decision.

Formule (Dolan, citee dans docs/research_framework.md section C5) :
    CLV(%) = (cote_de_cloture_juste / cote_prise - 1) x 100
Positif = le prix pris etait meilleur que l'estimation la plus informee
du marche (sa cloture) ; negatif = moins bon.
"""

from __future__ import annotations

from datetime import datetime

from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.market_engine.overround import remove_overround_proportional
from sys_foot_quant.market_engine.snapshot import latest_odds_as_of


def closing_line_value(odds_taken: float, closing_fair_odds: float) -> float:
    """CLV en pourcentage. Fonction pure : ``odds_taken`` et
    ``closing_fair_odds`` doivent tous deux avoir ete determines par
    l'appelant - cette fonction ne verifie aucun ordre temporel."""
    if odds_taken <= 1.0:
        raise ValueError(f"odds_taken doit etre > 1.0 (recu {odds_taken}).")
    if closing_fair_odds <= 1.0:
        raise ValueError(f"closing_fair_odds doit etre > 1.0 (recu {closing_fair_odds}).")
    return (closing_fair_odds / odds_taken - 1.0) * 100.0


def compute_clv_for_selection(
    repository: DuckDBRepository,
    match_id: int,
    selection: str,
    odds_taken: float,
    decision_time: datetime,
    closing_reference_time: datetime,
) -> float | None:
    """CLV pour une selection donnee, en lisant le dernier snapshot connu
    a ``closing_reference_time`` (marge retiree par la methode
    proportionnelle, coherente avec le benchmark marche de l'etape 2).

    Garde-fou anti-look-ahead explicite : ``closing_reference_time`` doit
    etre strictement posterieur a ``decision_time`` - sinon ce n'est pas
    un calcul a posteriori et l'appel est refuse. Retourne None si aucun
    snapshot n'est disponible a ``closing_reference_time`` (ex: marche
    pas encore ouvert a cet instant) ou si ``selection`` n'y figure pas.
    """
    if closing_reference_time <= decision_time:
        raise ValueError(
            "closing_reference_time doit etre strictement posterieur a "
            "decision_time : la cloture ne peut pas etre anterieure ou "
            "simultanee a la decision, sinon ce n'est plus un calcul a "
            "posteriori (voir ADR 0003)."
        )
    odds = latest_odds_as_of(repository, match_id, closing_reference_time)
    if odds is None or selection not in odds:
        return None
    fair = remove_overround_proportional(odds)
    closing_fair_prob = fair[selection]
    closing_fair_odds = 1.0 / closing_fair_prob
    return closing_line_value(odds_taken, closing_fair_odds)
