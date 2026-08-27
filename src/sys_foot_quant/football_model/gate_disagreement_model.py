"""GateDisagreementModel - hypothese B3.3 (docs/research_framework.md
section B3.3), suite a B3 (XGModel seul, INDETERMINE) et B3.2 (melange
lineaire inconditionnel HybridXGModel, INDETERMINE).

Question testee : le DESACCORD pre-match entre `PoissonModel` (buts reels)
et `XGModel` (xG historique) constitue-t-il un signal ex-ante exploitable
de la fiabilite relative des deux modeles sur CE match precis ?

Melange a POIDS ZERO PARAMETRE LIBRE, fixe avant tout calcul (voir
specification B3.3 validee) :

    w = TVD(p_poisson, p_xg)      (distance de variation totale, [0,1])
    p_final = (1 - w) * p_poisson + w * p_xg

Quand les deux modeles sont d'accord (TVD=0), le systeme est EXACTEMENT
`poisson_simple`. Aucun coefficient, seuil ou fonction de calibration
n'est ajuste - `w` est directement la mesure de desaccord elle-meme,
sans transformation. Extension isolee de plus : n'importe ni ne modifie
ni `PoissonModel` ni `XGModel`.
"""

from __future__ import annotations

import pandas as pd

from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.scoring import total_variation_distance
from sys_foot_quant.football_model.xg_model import XGModel


class GateDisagreementModel:
    def __init__(self, max_goals: int = 20) -> None:
        self.max_goals = max_goals

        self._poisson: PoissonModel | None = None
        self._xg: XGModel | None = None

    def fit(self, goals_df: pd.DataFrame, xg_df: pd.DataFrame) -> "GateDisagreementModel":
        """``goals_df`` et ``xg_df`` sont deux DataFrames INDEPENDANTS
        (memes colonnes qu'attendues respectivement par
        ``PoissonModel.fit`` et ``XGModel.fit``), typiquement issus de
        deux flux de connaissance point-in-time distincts (voir
        ``backtesting_engine/real_data_walk_forward.py``)."""
        self._poisson = PoissonModel(use_team_hfa=False).fit(goals_df)
        self._xg = XGModel(max_goals=self.max_goals).fit(xg_df)
        return self

    def predict_outcome_probabilities(
        self, home_team_id: int, away_team_id: int
    ) -> tuple[float, float, float]:
        if self._poisson is None or self._xg is None:
            raise RuntimeError("Le modele doit etre entraine (fit) avant predict_outcome_probabilities().")

        p_poisson = self._poisson.predict_outcome_probabilities(
            home_team_id, away_team_id, max_goals=self.max_goals
        )
        p_xg = self._xg.predict_outcome_probabilities(home_team_id, away_team_id, max_goals=self.max_goals)

        w = total_variation_distance(p_poisson, p_xg)
        return tuple((1.0 - w) * p + w * x for p, x in zip(p_poisson, p_xg))  # type: ignore[return-value]

    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]:
        """Alias pour une interface uniforme avec les autres modeles
        (``RealFittedPredictor.predict``)."""
        return self.predict_outcome_probabilities(home_team_id, away_team_id)
