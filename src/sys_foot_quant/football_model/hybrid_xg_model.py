"""Combinaison, au niveau des probabilites 1X2, de `PoissonModel` (buts
reels) et `XGModel` (xG historique) - hypothese B3.2, suite a l'analyse de
complementarite de B3 (docs/research_framework.md section B3) qui a
montre que `XGModel` bat significativement `poisson_simple` precisement
quand ce dernier se trompe, sans que `XGModel` seul batte significativement
`poisson_simple` en global.

Extension isolee de plus : n'importe ni ne modifie ni `PoissonModel` ni
`XGModel`, se contente de les faire tourner tous les deux et de melanger
leurs sorties. Un SEUL parametre libre, `w`, fixe A PRIORI (choisi sur une
periode de validation dediee, jamais sur le test final - voir
scripts/run_stage5_b3_2_hybrid_xg.py) :

    p_final = (1 - w) * p_poisson + w * p_xg

Melange lineaire simple : la somme de deux vecteurs de probabilite valides
ponderes par des poids positifs sommant a 1 est elle-meme une distribution
de probabilite valide (aucune renormalisation necessaire). Meme famille de
mecanisme que ``HeadToHeadModel`` (blend lineaire a poids fixe).
"""

from __future__ import annotations

import pandas as pd

from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.xg_model import XGModel


class HybridXGModel:
    def __init__(self, w: float, max_goals: int = 20) -> None:
        if not (0.0 <= w <= 1.0):
            raise ValueError(f"w doit etre dans [0, 1] (recu {w}).")
        self.w = w
        self.max_goals = max_goals

        self._poisson: PoissonModel | None = None
        self._xg: XGModel | None = None

    def fit(self, goals_df: pd.DataFrame, xg_df: pd.DataFrame) -> "HybridXGModel":
        """``goals_df`` et ``xg_df`` sont deux DataFrames INDEPENDANTS
        (memes colonnes que celles attendues respectivement par
        ``PoissonModel.fit`` et ``XGModel.fit``) - typiquement issus de deux
        flux de connaissance point-in-time distincts (voir
        ``backtesting_engine/real_data_walk_forward.py``), pas necessairement
        les memes matchs ni la meme taille."""
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

        w = self.w
        return tuple((1.0 - w) * p + w * x for p, x in zip(p_poisson, p_xg))  # type: ignore[return-value]

    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]:
        """Alias pour une interface uniforme avec les autres modeles
        (``RealFittedPredictor.predict``)."""
        return self.predict_outcome_probabilities(home_team_id, away_team_id)
