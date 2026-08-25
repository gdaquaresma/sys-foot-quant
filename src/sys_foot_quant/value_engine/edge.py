"""Calcul d'Expected Value (EV) et d'edge - fonctions pures, PAS de selection.

RAPPEL DE PRINCIPE (deja acte dans docs/research_framework.md, section G,
et repete par le cahier des charges de l'etape 3) : une EV positive
calculee a partir des probabilites d'un modele n'est JAMAIS, a elle
seule, une preuve de rentabilite reelle - elle suppose que le modele est
correctement calibre, hypothese que ce module ne verifie pas. Aucune
fonction ici ne doit etre utilisee comme signal d'achat direct. Voir
``value_engine.selection`` pour l'articulation complete (edge + EV +
seuils explicites), elle-meme explicitement documentee comme insuffisante
pour une decision de mise reelle sans validation Risk Engine et CLV hors
echantillon (etapes ulterieures).
"""

from __future__ import annotations


def expected_value(model_prob: float, odds: float) -> float:
    """EV par unite misee, cote decimale : ``model_prob * odds - 1``.

    >0 signifie un gain espere positif SI ``model_prob`` reflete la
    veritable probabilite - hypothese non verifiee par cette fonction.
    """
    if not (0.0 <= model_prob <= 1.0):
        raise ValueError(f"model_prob doit etre dans [0, 1] (recu {model_prob}).")
    if odds <= 1.0:
        raise ValueError(f"odds doit etre > 1.0 (recu {odds}).")
    return model_prob * odds - 1.0


def edge(model_prob: float, market_fair_prob: float) -> float:
    """Ecart de probabilite (modele - marche juste, marge deja retiree).

    Mesure le desaccord avec le marche independamment de la marge du
    bookmaker (contrairement a l'EV, qui utilise la cote brute et inclut
    donc le cout de la marge). Un edge positif ne dit rien, a lui seul,
    sur la fiabilite de ce desaccord.
    """
    if not (0.0 <= model_prob <= 1.0):
        raise ValueError(f"model_prob doit etre dans [0, 1] (recu {model_prob}).")
    if not (0.0 <= market_fair_prob <= 1.0):
        raise ValueError(f"market_fair_prob doit etre dans [0, 1] (recu {market_fair_prob}).")
    return model_prob - market_fair_prob
