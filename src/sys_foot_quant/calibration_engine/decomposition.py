"""Decomposition de Murphy (1973) du Brier score en trois termes :
fiabilite (biais de calibration), resolution (pouvoir de discrimination)
et incertitude (variance climatologique de base) - outil de DIAGNOSTIC,
pas un modele predictif : ne produit et ne modifie aucune prediction,
uniquement une mesure derivee d'un ensemble (probabilite predite, resultat
observe) deja existant.

    Brier = Fiabilite - Resolution + Incertitude

- **Incertitude** = ybar * (1 - ybar) : variance de la frequence de base
  observee (Brier d'un pronostiqueur "climatologique" qui prediraitit
  toujours ybar) - INDEPENDANT du modele evalue.
- **Resolution** : a quel point la frequence observee DANS CHAQUE TRANCHE
  de probabilite predite s'ecarte de la frequence de base globale - mesure
  le pouvoir de DISCRIMINATION (separer les cas probables des improbables),
  quel que soit le biais.
- **Fiabilite** : a quel point la probabilite predite MOYENNE de chaque
  tranche s'ecarte de la frequence REELLEMENT observee dans cette meme
  tranche - mesure le biais de CALIBRATION, independamment du pouvoir de
  discrimination.

Reutilise ``reliability_bins`` (INCHANGEE) comme partition en tranches -
aucune nouvelle logique de binning. La decomposition est EXACTE pour le
score de Brier "groupe" (calcule en remplacant chaque probabilite
individuelle par la moyenne de sa tranche), et seulement APPROXIMATIVE
pour le Brier "brut" (probabilites individuelles) - l'ecart entre les deux
(``grouping_error``) est rapporte explicitement, jamais masque (voir Ferro
& Fricker 2012 pour la discussion standard de cette approximation)."""

from __future__ import annotations

import numpy as np

from sys_foot_quant.calibration_engine.reliability import reliability_bins


def brier_decomposition(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> dict:
    """``probs``/``outcomes`` : memes conventions que ``reliability_bins``
    (probabilite predite pour UNE categorie binaire, indicatrice 0/1 de sa
    realisation)."""
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    if probs.shape != outcomes.shape:
        raise ValueError("probs et outcomes doivent avoir la meme forme.")
    n = probs.shape[0]
    if n == 0:
        raise ValueError("probs/outcomes ne peuvent pas etre vides.")

    bins = reliability_bins(probs, outcomes, n_bins=n_bins)
    non_empty = bins[bins["count"] > 0]

    ybar = float(outcomes.mean())
    uncertainty = ybar * (1.0 - ybar)
    reliability = float(
        (non_empty["count"] * (non_empty["mean_predicted"] - non_empty["observed_frequency"]) ** 2).sum() / n
    )
    resolution = float((non_empty["count"] * (non_empty["observed_frequency"] - ybar) ** 2).sum() / n)
    brier_grouped = reliability - resolution + uncertainty
    brier_raw = float(np.mean((probs - outcomes) ** 2))

    return {
        "n": n,
        "n_bins_used": int(len(non_empty)),
        "ybar": ybar,
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "brier_grouped": brier_grouped,
        "brier_raw": brier_raw,
        "grouping_error": brier_grouped - brier_raw,
        # Brier Skill Score par rapport a un pronostic "climatologique"
        # constant (toujours ybar) : >0 signifie une skill nette (au sens
        # groupe) au-dela de la seule base rate ; <=0 signifie aucune skill
        # nette (le biais de fiabilite annule ou depasse la resolution).
        "skill_score_vs_climatology": (
            (resolution - reliability) / uncertainty if uncertainty > 0 else float("nan")
        ),
    }


def bin_monotonicity_violations(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> dict:
    """A quelle frequence la frequence observee DIMINUE d'une tranche de
    probabilite predite a la tranche suivante (plus haute) - une
    discrimination parfaitement monotone ne devrait presenter aucune
    inversion. Diagnostic complementaire a la resolution (celle-ci mesure
    l'AMPLEUR de la separation entre tranches, celui-ci verifie que
    l'ORDRE est respecte, condition necessaire pour qu'une recalibration
    monotone - ex. isotonique - puisse corriger le biais sans rien perdre
    au rang)."""
    bins = reliability_bins(probs, outcomes, n_bins=n_bins).sort_values("bin_lo")
    non_empty = bins[bins["count"] > 0]
    observed = non_empty["observed_frequency"].to_numpy()
    if len(observed) < 2:
        return {"n_transitions": 0, "n_violations": 0, "violation_rate": float("nan")}
    diffs = np.diff(observed)
    n_violations = int((diffs < 0).sum())
    return {
        "n_transitions": int(len(diffs)),
        "n_violations": n_violations,
        "violation_rate": n_violations / len(diffs),
    }
