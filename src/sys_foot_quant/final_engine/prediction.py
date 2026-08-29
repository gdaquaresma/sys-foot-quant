"""Niveau A - Prediction (docs/final_engine_specification.md sections 3, 5).

Reutilise SANS MODIFICATION ``PoissonModel``/``DixonColesModel``/``XGModel``
(``football_model/poisson.py``, ``dixon_coles.py``, ``xg_model.py``) et la
convention deja figee depuis E1 : ``poisson_simple`` = ``PoissonModel
(use_team_hfa=False)``, ``dixon_coles`` = ``DixonColesModel
(use_team_hfa=False)`` (voir ``scripts/run_stage15_e7_total_goals_distribution.
build_lambda_mu_dataframe``, dont ce module reproduit exactement le calcul
par-match).

``poisson_simple`` est le modele PRINCIPAL - CHOIX ARCHITECTURAL, NON
VALIDE COMME SOURCE D'EDGE (aucune superiorite demontree, E11 : les trois
modeles sont statistiquement indiscernables en Brier apres correction
E7/E8). ``dixon_coles``/``xg_model`` restent calcules comme modeles de
CONTROLE, jamais fusionnes ou pondereis entre eux - NE PAS construire
d'ensemble, NE PAS apprendre de poids entre modeles (HYPOTHESE FUTURE,
docs/research_synthesis_e1_e16.md section 8)."""

from __future__ import annotations

import pandas as pd

from sys_foot_quant.data_engine.market_odds.economic_dataset import MIN_TRAIN_MATCHES
from sys_foot_quant.final_engine.types import ModelPrediction
from sys_foot_quant.football_model.dixon_coles import DixonColesModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.xg_model import XGModel

# CHOIX ARCHITECTURAL - NON VALIDE COMME SOURCE D'EDGE (docs/final_engine_specification.md
# section 5) : reference historique du projet depuis E1, dependance de
# donnees minimale, aucune preuve de superiorite d'un autre modele (E11).
PRIMARY_MODEL = "poisson_simple"

CONTROL_MODELS = ("dixon_coles", "xg_model")

_DEFAULT_MAX_GOALS = 20


def predict_match(
    home_team_id: int,
    away_team_id: int,
    goals_train_df: pd.DataFrame,
    xg_train_df: pd.DataFrame | None,
    min_train_matches: int = MIN_TRAIN_MATCHES,
    max_goals: int = _DEFAULT_MAX_GOALS,
) -> dict[str, ModelPrediction | None]:
    """Produit la prediction brute (lambda, mu, [rho]) des trois modeles
    pour UN match, a partir d'un historique DEJA filtre point-in-time par
    l'appelant (``goals_train_df``/``xg_train_df`` ne doivent contenir que
    des matchs dont le resultat etait connu avant ``decision_time`` -
    delegue entierement a l'appelant, jamais refiltre ici, voir
    ``orchestrator.py`` et docs/final_engine_specification.md section 16).

    Retourne ``None`` pour un modele dont l'historique disponible est
    strictement inferieur a ``min_train_matches`` - jamais une prediction
    de repli inventee (``insufficient_data_gate``, section 12)."""
    predictions: dict[str, ModelPrediction | None] = {
        "poisson_simple": None,
        "dixon_coles": None,
        "xg_model": None,
    }

    n_goals = len(goals_train_df)
    if n_goals >= min_train_matches:
        poisson = PoissonModel(use_team_hfa=False).fit(goals_train_df)
        lam, mu = poisson.predict_lambda_mu(home_team_id, away_team_id)
        predictions["poisson_simple"] = ModelPrediction(
            model="poisson_simple", lam=lam, mu=mu, rho=None, n_train_matches=n_goals
        )

        dixon_coles = DixonColesModel(use_team_hfa=False).fit(goals_train_df)
        dc_lam, dc_mu = dixon_coles.predict_lambda_mu(home_team_id, away_team_id)
        predictions["dixon_coles"] = ModelPrediction(
            model="dixon_coles", lam=dc_lam, mu=dc_mu, rho=dixon_coles.rho_, n_train_matches=n_goals
        )

    n_xg = len(xg_train_df) if xg_train_df is not None else 0
    if xg_train_df is not None and n_xg >= min_train_matches:
        xg_model = XGModel(max_goals=max_goals).fit(xg_train_df)
        xg_lam, xg_mu = xg_model.predict_lambda_mu(home_team_id, away_team_id)
        predictions["xg_model"] = ModelPrediction(
            model="xg_model", lam=xg_lam, mu=xg_mu, rho=None, n_train_matches=n_xg
        )

    return predictions
