"""Reconstruction PIT-sure des positions d'un wallet (Phase L, etape 5).

L'endpoint ``/positions`` documente de la Data API ne renvoie que l'etat
COURANT d'un wallet (voir ``client.py``) - inutilisable pour une decision
passee. La seule maniere PIT-sure de connaitre la position d'un wallet a
une date passee est de la RECONSTRUIRE depuis le journal de trades, filtre
strictement avant ``decision_time`` : c'est l'objet de ce module."""

from __future__ import annotations

from datetime import datetime

from sys_foot_quant.polymarket.schemas import Trade

_SIGN = {"BUY": 1.0, "SELL": -1.0}


def derive_positions_as_of(
    wallet_id: str, decision_time: datetime, trades: list[Trade]
) -> dict[str, dict[str, float]]:
    """Position nette (en taille de parts) par marche et par issue, en
    n'utilisant QUE les trades du wallet dont ``timestamp_utc <
    decision_time`` (strict - un trade execute exactement a
    ``decision_time`` n'est pas encore connu, coherent avec la convention
    ``decision_time`` deja utilisee dans ``final_engine``). BUY augmente
    la position, SELL la diminue - hypothese standard des marches de
    prediction binaires, independante de la structure exacte d'une
    reponse API non verifiee."""
    positions: dict[str, dict[str, float]] = {}
    for t in trades:
        if t.wallet_id != wallet_id or t.timestamp_utc >= decision_time:
            continue
        sign = _SIGN.get(t.side)
        if sign is None:
            raise ValueError(f"Side de trade non reconnu (ni BUY ni SELL) : {t.side!r}")
        outcome_key = t.outcome if t.outcome is not None else "UNKNOWN_OUTCOME"
        by_outcome = positions.setdefault(t.market_id, {})
        by_outcome[outcome_key] = by_outcome.get(outcome_key, 0.0) + sign * t.size
    return positions
