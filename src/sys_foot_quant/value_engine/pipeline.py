"""Assemble walk-forward (etape 2) + Market/Value Engine (etape 3) en un
journal de candidats value bet, avec CLV, pret a etre persiste.

Reutilise integralement les ``MatchEvaluation`` produits par
``backtesting_engine.walk_forward.run_walk_forward`` (aucune modification
de l'etape 2 requise) : pour chaque match evalue, les cotes disponibles
au ``decision_time`` sont relues via le Market Engine, comparees aux
probabilites du modele choisi, et le CLV est calcule une fois la cloture
(``kickoff_time``) passee.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from sys_foot_quant.backtesting_engine.walk_forward import MatchEvaluation
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.market_engine.snapshot import latest_odds_as_of
from sys_foot_quant.value_engine.clv import compute_clv_for_selection
from sys_foot_quant.value_engine.selection import build_value_candidates

_OUTCOME_TO_SELECTION = {0: "home", 1: "draw", 2: "away"}


def build_value_log(
    repository: DuckDBRepository,
    evaluations: list[MatchEvaluation],
    model_name: str,
    kickoff_by_match_id: dict[int, datetime],
    *,
    min_edge: float,
    min_ev: float,
    compute_clv: bool = True,
) -> pd.DataFrame:
    """Un DataFrame avec une ligne par (match, selection) evaluee pour
    ``model_name``, incluant edge/EV/passes_thresholds et, si disponible,
    le CLV a la cloture (``kickoff_by_match_id[match_id]``).

    Un match est ignore si le modele ou le benchmark marche n'a pas
    produit de prediction, ou si aucune cote n'etait disponible au
    ``decision_time`` (impossible de determiner un prix pris).
    """
    rows: list[dict] = []
    for ev in evaluations:
        model_probs = ev.predictions.get(model_name)
        market_probs = ev.predictions.get("market_no_vig")
        if model_probs is None or market_probs is None:
            continue

        odds = latest_odds_as_of(repository, ev.match_id, ev.decision_time)
        if odds is None:
            continue

        candidates = build_value_candidates(
            ev.match_id,
            ev.decision_time,
            model_probs,
            market_probs,
            odds,
            min_edge=min_edge,
            min_ev=min_ev,
        )

        kickoff = kickoff_by_match_id.get(ev.match_id)
        winning_selection = _OUTCOME_TO_SELECTION[ev.outcome]

        for c in candidates:
            clv_pct = None
            if compute_clv and kickoff is not None and kickoff > ev.decision_time:
                clv_pct = compute_clv_for_selection(
                    repository, c.match_id, c.selection, c.odds_taken, ev.decision_time, kickoff
                )
            rows.append(
                {
                    "match_id": c.match_id,
                    "decision_time": c.decision_time,
                    "model": model_name,
                    "selection": c.selection,
                    "model_prob": c.model_prob,
                    "market_fair_prob": c.market_fair_prob,
                    "odds_taken": c.odds_taken,
                    "edge": c.edge,
                    "ev": c.ev,
                    "passes_thresholds": c.passes_thresholds,
                    "selection_won": c.selection == winning_selection,
                    "clv_pct": clv_pct,
                }
            )

    return pd.DataFrame(rows)
