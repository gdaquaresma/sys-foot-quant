"""Detection d'anomalies de prix DESCRIPTIVE (E9, phase economique).

Regles PRE-ENREGISTREES, definies AVANT toute execution reelle (protocole
E9, point 7 : "ne pas optimiser les seuils apres observation"). Seuils
choisis par coherence avec la granularite deja utilisee dans ce depot
pour categoriser un ecart de probabilite en points (E5,
``run_stage13_e5_model_market_agreement_over25.gap_bin_table`` - tranches
de 5 points) plutot qu'inventes ad hoc :

    |ecart| < 0.05                -> "proche du consensus"
    0.05 <= |ecart| < 0.10        -> "ecart notable"
    |ecart| >= 0.10               -> "ecart marque"

Un "ecart" n'est PAS une "value" - jamais qualifie ainsi ici (protocole
E9, point 6). Ce module ne calcule aucun ROI, aucune regle de pari."""

from __future__ import annotations

_THRESHOLD_NOTABLE = 0.05
_THRESHOLD_MARKED = 0.10

CLOSE_TO_CONSENSUS = "proche du consensus"
NOTABLE_GAP = "ecart notable"
MARKED_GAP = "ecart marque"
NOT_INTERPRETABLE = "n=1, non interpretable"


def classify_gap(gap: float) -> str:
    """Classe UN ecart (deja calcule) selon la grille pre-enregistree
    ci-dessus - fonction pure, ne sait rien de sa provenance (book vs
    consensus, ou modele vs consensus)."""
    abs_gap = abs(gap)
    if abs_gap >= _THRESHOLD_MARKED:
        return MARKED_GAP
    if abs_gap >= _THRESHOLD_NOTABLE:
        return NOTABLE_GAP
    return CLOSE_TO_CONSENSUS


def book_vs_consensus(bookmaker: str, book_prob: float, consensus: dict) -> dict:
    """Ecart d'UN bookmaker par rapport au consensus (deja calcule par
    ``consensus.compute_consensus``). Si le consensus ne porte qu'UN seul
    bookmaker (celui-la meme), l'ecart est trivialement nul et NON
    INTERPRETABLE comme anomalie - signale explicitement plutot que
    silencieusement classe "proche du consensus"."""
    if consensus["n_bookmakers"] < 2:
        return {
            "bookmaker": bookmaker,
            "gap": 0.0,
            "classification": NOT_INTERPRETABLE,
        }
    gap = book_prob - consensus["mean"]
    return {
        "bookmaker": bookmaker,
        "gap": gap,
        "classification": classify_gap(gap),
        "direction": "au-dessus du consensus" if gap > 0 else ("en-dessous du consensus" if gap < 0 else "egal au consensus"),
    }


def model_vs_consensus(model_prob: float, consensus: dict) -> dict:
    """Ecart entre la probabilite du modele et le consensus de marche -
    meme grille de classification, jamais qualifie de 'value'."""
    gap = model_prob - consensus["mean"]
    return {
        "model_prob": model_prob,
        "consensus_mean": consensus["mean"],
        "gap": gap,
        "classification": classify_gap(gap),
    }
