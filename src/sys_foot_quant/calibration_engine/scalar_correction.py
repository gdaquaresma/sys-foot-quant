"""Correction scalaire walk-forward du total de buts predit - brique
VALIDEE SCIENTIFIQUEMENT (Verdict A, E8, les trois modeles ; section S de
docs/research_framework.md ; voir aussi docs/final_engine_specification.md
section 7). Le PRINCIPE de cette correction n'est PAS modifie ici.

Portage VERBATIM (aucune nouvelle logique) de
``scripts/run_stage16_e8_walk_forward_validation.fit_scale_correction_as_of``
et ``.attach_walk_forward_scale``, promues de ``scripts/`` vers ``src/``
pour etre reutilisables par le moteur de production sans dependre de
l'import dynamique reserve aux scripts de recherche.

Contrat (docs/final_engine_specification.md section 7) :
- ``c = E[total_reel] / E[lambda+mu_predit]``, un seul degre de liberte ;
- estime EXCLUSIVEMENT sur les matchs de ``calibration_df`` dont
  ``decision_time < as_of_time`` - jamais un match de test, jamais un
  match dont ``decision_time >= as_of_time`` (fenetre expansive stricte,
  jamais glissante a taille fixe) ;
- ``min_matches = 30`` (regle d'exclusion PRE-ENREGISTREE, jamais activee
  sur le corpus reel E1-E16 mais validee par construction) - retourne
  ``(None, n)`` si l'historique est insuffisant, jamais une valeur par
  defaut inventee.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

# Regle d'exclusion PRE-ENREGISTREE (E8, jamais activee sur le corpus reel
# mais validee par construction) - identique a
# ``run_stage16_e8_walk_forward_validation._MIN_CALIBRATION_MATCHES_FOR_SCALE``.
MIN_CALIBRATION_MATCHES_FOR_SCALE = 30


def fit_scale_correction_as_of(
    calibration_df: pd.DataFrame,
    model: str,
    as_of_time: datetime,
    min_matches: int = MIN_CALIBRATION_MATCHES_FOR_SCALE,
) -> tuple[float | None, int]:
    """c = E[total reel]/E[lambda+mu predit], estime EXCLUSIVEMENT sur les
    matchs de `calibration_df` dont `decision_time < as_of_time` - jamais
    un match de test, jamais un match dont `decision_time >= as_of_time`.
    Retourne (None, n) si n < min_matches (regle d'exclusion pre-enregistree).

    Identique a
    ``run_stage16_e8_walk_forward_validation.fit_scale_correction_as_of``.
    """
    lam_col, mu_col = f"{model}_lambda", f"{model}_mu"
    sub = calibration_df[calibration_df["decision_time"] < as_of_time].dropna(subset=[lam_col, mu_col])
    n = len(sub)
    if n < min_matches:
        return None, n
    predicted_mean = float((sub[lam_col] + sub[mu_col]).mean())
    actual_mean = float(sub["total_goals"].mean())
    return actual_mean / predicted_mean, n


def attach_walk_forward_scale(calibration_df: pd.DataFrame, test_df: pd.DataFrame, model: str) -> pd.DataFrame:
    """Pour chaque match de `test_df` (trie par `decision_time`), calcule
    `scale_c` walk-forward (None si insuffisant - regle d'exclusion) et
    `n_calibration_used`. `test_df` n'est JAMAIS utilise dans le calcul de
    `scale_c` - seul `calibration_df`, filtre temporellement, l'est.

    Identique a
    ``run_stage16_e8_walk_forward_validation.attach_walk_forward_scale``.
    Fournie pour l'evaluation batch (regression/monitoring) ; le moteur de
    decision temps reel appelle ``fit_scale_correction_as_of`` directement,
    un match a la fois.
    """
    lam_col, mu_col = f"{model}_lambda", f"{model}_mu"
    sub = test_df.dropna(subset=[lam_col, mu_col]).sort_values("decision_time").copy()

    scales: list[float | None] = []
    n_used: list[int] = []
    for as_of in sub["decision_time"]:
        c, n = fit_scale_correction_as_of(calibration_df, model, as_of)
        scales.append(c)
        n_used.append(n)
    sub["scale_c"] = scales
    sub["n_calibration_used"] = n_used
    return sub
