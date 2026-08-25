"""Retrait de marge (overround) par normalisation proportionnelle.

Methode la plus simple et la plus standard : chaque probabilite implicite
brute (1/cote) est divisee par la somme des probabilites implicites de
toutes les issues du marche. D'autres methodes (Shin, logarithmique) sont
plus sophistiquees mais explicitement hors perimetre de l'etape 2 (le
cahier des charges ne demande que le benchmark "marche sans marge", pas
un Market Engine complet).
"""

from __future__ import annotations


def hold_percentage(odds: dict[str, float]) -> float:
    """Marge du bookmaker : somme des probabilites implicites brutes - 1."""
    _validate_odds(odds)
    return sum(1.0 / o for o in odds.values()) - 1.0


def remove_overround_proportional(odds: dict[str, float]) -> dict[str, float]:
    """Retourne les probabilites "justes" (sans marge), normalisees a somme 1."""
    _validate_odds(odds)
    implied = {selection: 1.0 / o for selection, o in odds.items()}
    total = sum(implied.values())
    return {selection: p / total for selection, p in implied.items()}


def _validate_odds(odds: dict[str, float]) -> None:
    if not odds:
        raise ValueError("Le marche ne peut pas etre vide.")
    for selection, o in odds.items():
        if o <= 1.0:
            raise ValueError(f"Cote invalide pour '{selection}' : {o} (doit etre > 1.0).")
