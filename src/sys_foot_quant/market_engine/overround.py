"""Retrait de marge (overround) par normalisation proportionnelle.

Methode la plus simple et la plus standard : chaque probabilite implicite
brute (1/cote) est divisee par la somme des probabilites implicites de
toutes les issues du marche. Voir ``market_engine.shin`` pour une methode
alternative (Shin) et leur comparaison - le benchmark "marche sans marge"
de l'etape 2 (``backtesting_engine.walk_forward``) continue d'utiliser
exclusivement la methode proportionnelle, inchangee, conformement a la
consigne de conserver les validations de l'etape 2.
"""

from __future__ import annotations

import math


def hold_percentage(odds: dict[str, float]) -> float:
    """Marge du bookmaker : somme des probabilites implicites brutes - 1."""
    validate_odds(odds)
    return sum(1.0 / o for o in odds.values()) - 1.0


def remove_overround_proportional(odds: dict[str, float]) -> dict[str, float]:
    """Retourne les probabilites "justes" (sans marge), normalisees a somme 1."""
    validate_odds(odds)
    implied = {selection: 1.0 / o for selection, o in odds.items()}
    total = sum(implied.values())
    return {selection: p / total for selection, p in implied.items()}


def validate_odds(odds: dict[str, float]) -> None:
    if not odds:
        raise ValueError("Le marche ne peut pas etre vide.")
    for selection, o in odds.items():
        # ``not (o > 1.0)`` (plutot que ``o <= 1.0``) capture aussi NaN, dont
        # toute comparaison (y compris ``<=``) vaut False en Python - une
        # cote NaN traversait donc silencieusement ce controle. ``inf`` est
        # rejete separement : ``inf > 1.0`` est True mais ne represente
        # aucune cote reelle.
        if not (o > 1.0) or math.isinf(o):
            raise ValueError(f"Cote invalide pour '{selection}' : {o} (doit etre > 1.0 et finie).")
