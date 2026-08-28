"""Detection MATHEMATIQUE d'arbitrage historique (E9, phase economique).

Purement mathematique : pour un marche a N issues, si le meilleur prix
disponible (toutes bookmakers confondus) sur chaque issue verifie
``somme(1/meilleure_cote_i) < 1``, une couverture theorique existe -
c'est la definition classique de l'arbitrage ("sure bet"), generalisee
d'un marche binaire (protocole E9, point 8, formule ``1/O_best +
1/U_best < 1``) a N issues (le 1X2 en compte 3).

Ce module NE PRETEND JAMAIS qu'un arbitrage detecte ici serait une
"opportunite reelle" : aucune prise en compte des limites de mise, de la
disponibilite simultanee des prix, des regles differentes selon
bookmaker, des annulations/void, des delais d'execution ni de la
variation des prix entre l'instant de decision et l'instant de mise
reelle. Le resultat doit toujours etre presente comme une **detection
mathematique d'arbitrage historique**, jamais davantage."""

from __future__ import annotations


def find_best_prices(odds_by_selection_bookmaker: dict[str, dict[str, float]]) -> dict[str, tuple[str, float]]:
    """selection -> (bookmaker, meilleure cote) - la cote la plus elevee
    disponible pour cette selection, tous bookmakers fournis confondus."""
    if not odds_by_selection_bookmaker:
        raise ValueError("Aucune selection fournie.")
    best: dict[str, tuple[str, float]] = {}
    for selection, by_bookmaker in odds_by_selection_bookmaker.items():
        if not by_bookmaker:
            raise ValueError(f"Selection '{selection}' sans aucune cote de bookmaker.")
        bookmaker, odds = max(by_bookmaker.items(), key=lambda kv: kv[1])
        best[selection] = (bookmaker, odds)
    return best


def detect_mathematical_arbitrage(odds_by_selection_bookmaker: dict[str, dict[str, float]]) -> dict:
    """Calcule la somme des probabilites implicites inverses des
    MEILLEURS prix (par selection, tous bookmakers confondus) et la marge
    d'arbitrage theorique = 1 - cette somme. ``is_mathematical_arbitrage``
    est True si la marge est strictement positive (couverture theorique
    existe) - jamais interprete au-dela de ce constat mathematique."""
    best = find_best_prices(odds_by_selection_bookmaker)
    implied_prob_sum = sum(1.0 / odds for _, odds in best.values())
    margin = 1.0 - implied_prob_sum
    return {
        "best_prices": best,
        "implied_prob_sum": implied_prob_sum,
        "arbitrage_margin": margin,
        "is_mathematical_arbitrage": margin > 0.0,
    }
