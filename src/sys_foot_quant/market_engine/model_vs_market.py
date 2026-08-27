"""Interface economique generique modele <-> marche (etape 6, phase
economique - docs/decisions/0006-football-data-point-in-time.md).

Ne calcule NI ROI, NI yield, NI CLV, NI staking, NI selection de paris -
uniquement la comparaison probabiliste modele/marche pour UN match et UN
marche a la fois. Reutilise SANS MODIFICATION
``market_engine.overround.hold_percentage`` et
``.remove_overround_proportional`` (deja testees, etape 2). Generique par
construction : ``model_probs``/``market_odds`` sont de simples
``dict[str, float]`` indexes par selection - fonctionne pour le 1X2
aujourd'hui, pour tout autre marche (Over/Under, BTTS, ...) sans
modification de ce module, le jour ou l'un d'eux serait construit.
"""

from __future__ import annotations

from sys_foot_quant.market_engine.overround import hold_percentage, remove_overround_proportional


def compare_model_to_market(model_probs: dict[str, float], market_odds: dict[str, float]) -> dict:
    """Pour un match et un marche donnes :
    1. probabilite du modele (passee telle quelle) ;
    2. cote de marche (passee telle quelle) ;
    3. probabilite implicite brute = 1 / cote ;
    4. overround du marche (marge du bookmaker) ;
    5. probabilite implicite normalisee (marge retiree, proportionnelle) ;
    6. difference modele - marche normalise, par selection.

    Aucune decision de pari, aucun seuil, aucun ROI - uniquement le
    calcul comparatif brut."""
    if set(model_probs) != set(market_odds):
        raise ValueError(
            f"model_probs et market_odds doivent porter exactement les memes selections "
            f"(recu {sorted(model_probs)} vs {sorted(market_odds)})."
        )

    implied_raw = {selection: 1.0 / o for selection, o in market_odds.items()}
    overround = hold_percentage(market_odds)
    implied_normalized = remove_overround_proportional(market_odds)
    diff = {selection: model_probs[selection] - implied_normalized[selection] for selection in model_probs}

    return {
        "model_probs": dict(model_probs),
        "market_odds": dict(market_odds),
        "implied_prob_raw": implied_raw,
        "overround": overround,
        "implied_prob_normalized": implied_normalized,
        "model_minus_market": diff,
    }
