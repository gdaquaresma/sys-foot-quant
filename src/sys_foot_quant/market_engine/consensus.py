"""Consensus multi-bookmaker (E9, phase economique - couche marche).

Prend en entree des probabilites DEJA normalisees (marge retiree,
``overround.remove_overround_proportional`` reutilise sans modification,
UNE FOIS PAR BOOKMAKER avant tout agregat - jamais une moyenne de cotes
brutes) et calcule des statistiques descriptives simples entre
bookmakers pour UNE selection d'UN marche. Aucun poids optimise entre
bookmakers (protocole E9, point 5) - chaque bookmaker reste identifiable
individuellement dans le detail retourne."""

from __future__ import annotations

import statistics


def compute_consensus(normalized_probs_by_bookmaker: dict[str, float]) -> dict:
    """Moyenne, mediane, min, max, dispersion (ecart-type d'echantillon,
    NaN si n<2) des probabilites normalisees, plus le detail brut par
    bookmaker - jamais de poids optimise, jamais de bookmaker masque."""
    if not normalized_probs_by_bookmaker:
        raise ValueError("Aucun bookmaker fourni - le consensus ne peut pas etre calcule.")

    values = list(normalized_probs_by_bookmaker.values())
    n = len(values)
    return {
        "n_bookmakers": n,
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "std": statistics.stdev(values) if n > 1 else float("nan"),
        "by_bookmaker": dict(normalized_probs_by_bookmaker),
    }


def bookmaker_rank(bookmaker: str, odds_by_bookmaker: dict[str, float]) -> dict:
    """Position d'un bookmaker dans la distribution des COTES (pas des
    probabilites) offertes sur cette selection : rang 1 = cote la plus
    elevee (le prix le plus favorable a l'acheteur), n = la plus basse.
    Retourne aussi le nombre total de bookmakers compares."""
    if bookmaker not in odds_by_bookmaker:
        raise ValueError(f"'{bookmaker}' absent de odds_by_bookmaker.")
    ordered = sorted(odds_by_bookmaker.items(), key=lambda kv: kv[1], reverse=True)
    rank = next(i for i, (bk, _) in enumerate(ordered, start=1) if bk == bookmaker)
    return {"bookmaker": bookmaker, "rank": rank, "n_bookmakers": len(odds_by_bookmaker)}
