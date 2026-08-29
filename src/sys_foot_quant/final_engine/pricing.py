"""Niveau C - Pricing (docs/final_engine_specification.md sections 3, 6).

Transformation deterministe de la probabilite modele en cote juste -
aucune donnee externe, aucune comparaison au marche (role du Niveau D)."""

from __future__ import annotations


def compute_fair_price(probabilities: dict[float, float]) -> dict[float, float]:
    """``fair_price = 1 / p_model`` pour chaque seuil - la cote qu'impliquerait
    la probabilite du modele, JAMAIS derivee du marche. ``p=0`` produit une
    cote infinie (limite mathematique bien definie, jamais rencontree en
    pratique sur ce corpus mais non masquee)."""
    return {threshold: (1.0 / p if p > 0.0 else float("inf")) for threshold, p in probabilities.items()}
