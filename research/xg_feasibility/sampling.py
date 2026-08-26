"""Selection d'un echantillon fixe de matchs pour la mesure de revision
xG (protocole B3, priorite 2). Fonctions PURES, aucun acces reseau -
l'echantillon doit etre fige AVANT la premiere extraction et jamais
recalcule au moment de la comparaison (sinon la "mesure" serait biaisee
par un choix fait apres avoir vu les donnees, ce que ce projet interdit
systematiquement - voir la discipline deja appliquee a A1/B1/B2)."""

from __future__ import annotations

import random

from research.xg_feasibility.understat_source import MatchXGRecord


def select_fixed_sample(
    records: list[MatchXGRecord], n: int, seed: int
) -> list[MatchXGRecord]:
    """Tire un sous-ensemble deterministe de taille ``min(n, len(records))``.

    Deterministe a deux niveaux : (1) les enregistrements sont trie par
    ``match_id`` avant tirage, pour ne jamais dependre de l'ordre renvoye
    par la source (non garanti) ; (2) le tirage utilise un ``random.Random``
    local avec ``seed`` explicite, jamais l'etat aleatoire global -
    reproductible a l'identique tant que ``records`` et ``seed`` sont les
    memes, quel que soit le moment ou la fonction est appelee.
    """
    if n < 1:
        raise ValueError(f"n doit etre >= 1 (recu {n}).")
    ordered = sorted(records, key=lambda r: r.match_id)
    if n >= len(ordered):
        return ordered
    rng = random.Random(seed)
    return sorted(rng.sample(ordered, k=n), key=lambda r: r.match_id)
