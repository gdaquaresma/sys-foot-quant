"""Recalibration isotonique post-hoc des probabilites DEJA PRODUITES par un
modele fige (poisson_simple, xg_model) - une transformation monotone, SANS
PARAMETRE LIBRE, appliquee APRES coup a des probabilites existantes.
Ne modifie, ne remplace et ne reentraine JAMAIS le modele qui les a
produites : c'est une couche de calibration separee, testee par
walk-forward strict (rodage/calibration/test) comme toute autre hypothese
du projet.

CHOIX METHODOLOGIQUE (unique methode testee, justifiee AVANT
implementation - voir aussi
scripts/run_stage10_over_under_recalibration.py) : regression isotonique
via ``scipy.optimize.isotonic_regression`` (Pool Adjacent Violators
Algorithm, PAVA) - DEJA une dependance du projet (``scipy>=1.12.0``),
AUCUNE nouvelle dependance ajoutee. Retenue plutot que toute alternative
(ex. Platt scaling) pour trois raisons :

1. **Monotone par construction** - ne peut donc JAMAIS degrader le
   pouvoir de discrimination (la resolution, au sens de
   ``calibration_engine.decomposition``, ne depend que du RANG des
   probabilites, pas de leur valeur ; une transformation monotone
   preserve ce rang par definition).
2. **Aucune forme parametrique supposee** - le diagnostic prealable
   (docs/research_framework.md, section L) a documente un biais en "S",
   pas une simple sigmoide a 2 parametres (ce que supposerait un Platt
   scaling) : une regression isotonique (fonction en escalier, aussi
   flexible que les donnees le permettent sous la seule contrainte de
   monotonicite) s'adapte a cette forme sans l'imposer a priori.
3. **Aucun hyperparametre a ajuster** - PAVA est deterministe une fois
   les donnees de calibration fixees (pas de taux d'apprentissage, pas de
   nombre de tranches, pas de regularisation a choisir).

Precedent deja present dans le depot (etudie, pas reutilise directement) :
``football_model.elo.EloModel`` applique deja une forme de calibration
empirique par tranches (bins fixes, lookup au plus proche) - la
regression isotonique en est le raffinement standard (tranches
determinees par les donnees elles-memes via PAVA, pas fixees a priori, et
monotonicite formellement garantie)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import isotonic_regression


@dataclass(frozen=True)
class IsotonicCalibrationCurve:
    """Fonction de recalibration ajustee : ``x_calibration`` (probabilites
    brutes de calibration, triees) -> ``fitted_values`` (valeurs
    isotoniques correspondantes, PAVA). ``predict`` interpole lineairement
    entre points de calibration connus (``numpy.interp`` - outil standard,
    aucun parametre de lissage) et clippe aux bornes en dehors de la plage
    observee en calibration (comportement par defaut de ``numpy.interp``,
    pas une extrapolation)."""

    x_calibration: np.ndarray
    fitted_values: np.ndarray

    def predict(self, p: np.ndarray) -> np.ndarray:
        p = np.asarray(p, dtype=float)
        return np.interp(p, self.x_calibration, self.fitted_values)


def fit_isotonic_calibration(p_calibration: np.ndarray, y_calibration: np.ndarray) -> IsotonicCalibrationCurve:
    """Ajuste UNE courbe de recalibration isotonique - a appeler
    UNIQUEMENT sur l'ensemble de CALIBRATION (jamais sur le TEST, jamais
    sur le RODAGE). ``p_calibration`` : probabilites brutes deja produites
    par un modele fige. ``y_calibration`` : indicatrice binaire (0/1) du
    resultat reellement observe pour la meme selection."""
    p_calibration = np.asarray(p_calibration, dtype=float)
    y_calibration = np.asarray(y_calibration, dtype=float)
    if p_calibration.shape != y_calibration.shape:
        raise ValueError("p_calibration et y_calibration doivent avoir la meme forme.")
    if p_calibration.size == 0:
        raise ValueError("L'ensemble de calibration ne peut pas etre vide.")

    order = np.argsort(p_calibration, kind="stable")
    x_sorted = p_calibration[order]
    y_sorted = y_calibration[order]
    result = isotonic_regression(y_sorted, increasing=True)
    return IsotonicCalibrationCurve(x_calibration=x_sorted, fitted_values=np.asarray(result.x, dtype=float))
