"""Flat Betting : mode de mise obligatoire par defaut (cahier des charges
etape 4 - "Debut obligatoire en Flat Betting").

Mise CONSTANTE, calculee comme une fraction fixe de la bankroll INITIALE
(pas de la bankroll courante) : c'est precisement ce qui distingue le
Flat Betting de Kelly (qui, lui, recalcule la mise a chaque pari en
fonction du solde courant, donc compose). Une mise flat ne varie pas avec
les gains/pertes anterieurs - c'est le protocole de controle recommande
avant toute gestion dynamique (voir docs/research_framework.md, section D1).
"""

from __future__ import annotations


def flat_stake(initial_bankroll: float, fraction: float) -> float:
    """Mise constante = ``fraction`` de la bankroll initiale."""
    if initial_bankroll <= 0:
        raise ValueError(f"initial_bankroll doit etre strictement positif (recu {initial_bankroll}).")
    if not (0.0 < fraction <= 1.0):
        raise ValueError(f"fraction doit etre dans ]0, 1] (recu {fraction}).")
    return initial_bankroll * fraction
