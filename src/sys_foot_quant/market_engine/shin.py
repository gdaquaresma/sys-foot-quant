"""Retrait de marge par la methode de Shin (1992, 1993).

Modelise une fraction ``z`` de "paris informes" (insiders) comme source
d'une partie de la marge du bookmaker, en plus du partage normal du
risque. Contrairement a la methode proportionnelle (qui suppose la marge
uniformement repartie entre les issues), Shin corrige un biais
empiriquement documente sur de nombreux marches de paris - le
"favorite-longshot bias" : sous la methode proportionnelle, les outsiders
tendent a etre legerement sur-cotes (probabilite juste sous-estimee) et
les favoris legerement sous-cotes, par rapport a leur probabilite reelle.

Reference : Shin, H.S. (1992), "Prices of State Contingent Claims with
Insider Traders, and the Favourite-Longshot Bias", The Economic Journal.

Formule : soit pi_i = 1/cote_i les probabilites implicites brutes,
Total = somme(pi_i) (>1 s'il y a une marge). Pour z dans [0, 1) :

    p_i(z) = (sqrt(z^2 + 4(1-z) pi_i^2 / Total) - z) / (2(1-z))

``z`` est l'unique racine de somme_i p_i(z) = 1 dans [0, 1).

Cas particulier verifie par test : si Total = 1 (aucune marge), z = 0 est
solution triviale et p_i(0) = pi_i - Shin degenere alors exactement vers
la methode proportionnelle.

Limite documentee : cette methode suppose implicitement que la marge
provient uniformement de ce mecanisme d'asymetrie d'information ; elle
n'a pas de raison de mieux refleter la realite qu'une autre methode sur
un marche synthetique dont le bruit ne reproduit pas volontairement de
favorite-longshot bias (voir le rapport de validation de l'etape 3).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from sys_foot_quant.market_engine.overround import (
    hold_percentage,
    remove_overround_proportional,
    validate_odds,
)

_Z_UPPER_BOUND = 0.5  # tres largement suffisant pour des marges realistes (< 30%)


def _shin_probs(z: float, pi: np.ndarray, total: float) -> np.ndarray:
    return (np.sqrt(z**2 + 4.0 * (1.0 - z) * pi**2 / total) - z) / (2.0 * (1.0 - z))


def _validate_for_shin(odds: dict[str, float]) -> None:
    validate_odds(odds)
    total = sum(1.0 / o for o in odds.values())
    if total < 1.0 - 1e-9:  # tolerance flottante symetrique de _solve_z
        raise ValueError(
            "La methode de Shin suppose une marge non negative (somme des "
            f"probabilites implicites >= 1) ; recu {total:.4f} < 1 (marche "
            "d'arbitrage). Le modele de Shin - fraction de paris 'informes' "
            "expliquant la marge - n'a pas d'interpretation pour un marche "
            "sans marge positive."
        )


def _solve_z(pi: np.ndarray, total: float) -> float:
    def f(z: float) -> float:
        return float(_shin_probs(z, pi, total).sum() - 1.0)

    if total <= 1.0 + 1e-9:
        # Aucune marge (au sens numerique) : z=0 resout exactement
        # l'equation, Shin degenere vers le partage proportionnel.
        return 0.0
    if f(_Z_UPPER_BOUND) > 0.0:
        raise ValueError(
            f"Impossible de resoudre z dans [0, {_Z_UPPER_BOUND}] pour ce "
            "marche (marge inhabituellement elevee)."
        )
    return brentq(f, 0.0, _Z_UPPER_BOUND)


def remove_overround_shin(odds: dict[str, float]) -> dict[str, float]:
    """Retourne les probabilites "justes" selon la methode de Shin."""
    _validate_for_shin(odds)
    selections = list(odds.keys())
    pi = np.array([1.0 / odds[s] for s in selections])
    total = float(pi.sum())
    z = _solve_z(pi, total)
    probs = _shin_probs(z, pi, total)
    return dict(zip(selections, probs.tolist()))


def shin_z(odds: dict[str, float]) -> float:
    """Fraction de paris "informes" (z) estimee par le modele de Shin.

    Expose separement de ``remove_overround_shin`` car c'est en soi une
    grandeur diagnostique (plus z est eleve, plus le modele attribue la
    marge a une asymetrie d'information plutot qu'a un partage de risque
    neutre), utile pour comparer des marches entre eux.
    """
    _validate_for_shin(odds)
    pi = np.array([1.0 / o for o in odds.values()])
    total = float(pi.sum())
    return _solve_z(pi, total)


def compare_overround_methods(odds: dict[str, float]) -> dict:
    """Compare le retrait de marge proportionnel et Shin sur le meme marche.

    Ne privilegie aucune des deux methodes : sert a documenter, pour un
    marche donne, l'ampleur de leur desaccord et la valeur de z estimee.
    """
    proportional = remove_overround_proportional(odds)
    shin = remove_overround_shin(odds)
    z = shin_z(odds)
    max_abs_diff = max(abs(proportional[s] - shin[s]) for s in odds)
    return {
        "proportional": proportional,
        "shin": shin,
        "shin_z": z,
        "hold": hold_percentage(odds),
        "max_abs_diff": max_abs_diff,
    }
