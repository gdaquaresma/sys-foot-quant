"""Construction de l'historique de calibration walk-forward
(``calibration_df_by_model``) attendu par le moteur final (Niveau B,
``docs/final_engine_specification.md`` sections 4.1/7 ; checklist
d'execution reelle, ``docs/final_preproduction_audit.md`` section 9,
"OBLIGATOIRE" : ``decision_time``, ``{model}_lambda``, ``{model}_mu``,
``total_goals``).

Portage VERBATIM (aucune nouvelle logique de modelisation, aucune nouvelle
methode de calibration, aucun nouveau modele) de
``scripts/run_stage15_e7_total_goals_distribution.build_lambda_mu_dataframe``
(E7) - generalise UNIQUEMENT sur la SOURCE des donnees : ce module accepte
directement une liste de ``RealMatchRecord`` deja chargee plutot que de
dependre du module de recherche charge dynamiquement
(``run_stage8_diagnostic_total_goals_over_under``, chemins de fichiers
codes en dur propres au corpus figu de la campagne E1-E16). Le CALCUL
lui-meme est identique, terme a terme :

- meme tri chronologique (``kickoff_utc`` croissant) ;
- meme ``decision_time = kickoff_utc - DECISION_OFFSET_HOURS`` (reutilise
  ``economic_dataset.DECISION_OFFSET_HOURS``, jamais recalcule
  differemment) ;
- meme filtrage point-in-time du train set, en reutilisant SANS
  MODIFICATION ``backtesting_engine.real_data_walk_forward._goals_train_df``/
  ``._xg_train_df`` (deja la brique testee en leakage,
  ``tests/leakage/test_real_data_walk_forward_point_in_time.py``) - jamais
  redupliquees une troisieme fois ;
- meme ``MIN_TRAIN_MATCHES`` (reutilise ``economic_dataset.MIN_TRAIN_MATCHES``) ;
- memes trois modeles figes (``poisson_simple``, ``dixon_coles``,
  ``xg_model``), fittes SANS MODIFICATION (``PoissonModel``,
  ``DixonColesModel``, ``XGModel`` inchanges).

Ce module ne calcule PAS la correction scalaire elle-meme (deja portee
verbatim dans ``calibration_engine.scalar_correction``, INCHANGE) - il
produit uniquement l'HISTORIQUE dont cette correction a besoin en entree.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (
    RealMatchRecord,
    _goals_train_df,
    _xg_train_df,
)
from sys_foot_quant.data_engine.market_odds.economic_dataset import (
    DECISION_OFFSET_HOURS,
    MIN_TRAIN_MATCHES,
)
from sys_foot_quant.football_model.dixon_coles import DixonColesModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.xg_model import XGModel

# Trois modeles fixes de la campagne E1-E16 - jamais un ensemble, jamais un
# quatrieme modele (docs/final_engine_specification.md section 5).
MODELS = ("poisson_simple", "dixon_coles", "xg_model")

_MAX_GOALS = 20  # identique a build_lambda_mu_dataframe (E7)


def build_calibration_dataframe(
    records: list[RealMatchRecord],
    decision_offset_hours: float = DECISION_OFFSET_HOURS,
    min_train_matches: int = MIN_TRAIN_MATCHES,
    max_goals: int = _MAX_GOALS,
) -> pd.DataFrame:
    """Reproduit EXACTEMENT le mecanisme walk-forward d'E7
    (``build_lambda_mu_dataframe``) : pour chaque match de ``records``,
    trie par ``kickoff_utc``, entraine les trois modeles SANS MODIFICATION
    sur l'historique strictement anterieur (point-in-time, exclusion
    explicite du match evalue lui-meme - meme garde-fou que
    ``_goals_train_df``/``_xg_train_df``) et expose ``(lambda, mu)``
    SEPAREMENT par modele (necessaire pour une correction scalaire qui
    preserve le ratio domicile/exterieur, section 7 de la specification).

    Une ligne par match de ``records``, quel que soit le nombre de
    competitions/saisons representees. ``records`` n'a besoin d'aucun tri
    prealable (trie ici, comme E7) ; si l'appelant doit combiner plusieurs
    competitions/saisons, il doit appeler cette fonction separement PAR
    flux chronologique coherent et concatener les resultats lui-meme -
    exactement le choix deja fait par E7/E8 (jamais un tri global qui
    melangerait des competitions distinctes en un seul historique).

    Colonnes produites : ``match_id``, ``league``, ``decision_time``,
    ``home_goals``, ``away_goals``, ``total_goals``, puis pour chaque
    modele ``{model}_lambda``/``{model}_mu`` (+ ``dixon_coles_rho``) -
    ``NaN`` si l'historique disponible avant ``decision_time`` etait
    strictement inferieur a ``min_train_matches`` (jamais une valeur de
    repli inventee, comportement identique a E7)."""
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    rows: list[dict] = []
    for r in ordered:
        decision_time = r.kickoff_utc - timedelta(hours=decision_offset_hours)
        goals_df = _goals_train_df(ordered, decision_time, exclude_match_id=r.match_id)
        xg_df = _xg_train_df(ordered, decision_time, exclude_match_id=r.match_id)

        row: dict = {
            "match_id": r.match_id,
            "league": r.league,
            "decision_time": decision_time,
            "home_goals": r.home_goals,
            "away_goals": r.away_goals,
            "total_goals": r.home_goals + r.away_goals,
        }

        if len(goals_df) >= min_train_matches:
            poisson = PoissonModel(use_team_hfa=False).fit(goals_df)
            lam, mu = poisson.predict_lambda_mu(r.home_team_id, r.away_team_id)
            row["poisson_simple_lambda"], row["poisson_simple_mu"] = lam, mu

            dc = DixonColesModel(use_team_hfa=False).fit(goals_df)
            dc_lam, dc_mu = dc.predict_lambda_mu(r.home_team_id, r.away_team_id)
            row["dixon_coles_lambda"], row["dixon_coles_mu"], row["dixon_coles_rho"] = dc_lam, dc_mu, dc.rho_
        else:
            row["poisson_simple_lambda"] = row["poisson_simple_mu"] = float("nan")
            row["dixon_coles_lambda"] = row["dixon_coles_mu"] = row["dixon_coles_rho"] = float("nan")

        if len(xg_df) >= min_train_matches:
            xg = XGModel(max_goals=max_goals).fit(xg_df)
            xg_lam, xg_mu = xg.predict_lambda_mu(r.home_team_id, r.away_team_id)
            row["xg_model_lambda"], row["xg_model_mu"] = xg_lam, xg_mu
        else:
            row["xg_model_lambda"] = row["xg_model_mu"] = float("nan")

        rows.append(row)
    return pd.DataFrame(rows)


def split_calibration_df_by_model(df: pd.DataFrame, models: tuple[str, ...] = MODELS) -> dict[str, pd.DataFrame]:
    """Decoupe le DataFrame large (une colonne ``{model}_lambda``/``_mu``
    par modele) produit par ``build_calibration_dataframe`` en un dict par
    modele, au format EXACT attendu par
    ``final_engine.orchestrator.run_match_decision(calibration_df_by_model=...)``
    et consomme directement par
    ``calibration_engine.scalar_correction.fit_scale_correction_as_of``/
    ``.attach_walk_forward_scale`` (INCHANGES) : colonnes ``decision_time``,
    ``{model}_lambda``, ``{model}_mu``, ``total_goals``.

    Aucun pre-filtrage des lignes ``NaN`` ici : ``fit_scale_correction_as_of``
    applique deja son propre ``dropna(subset=[lam_col, mu_col])`` en interne
    (meme comportement que E8, qui passe le DataFrame complet sans
    pre-filtrage)."""
    return {model: df[["decision_time", f"{model}_lambda", f"{model}_mu", "total_goals"]].copy() for model in models}
