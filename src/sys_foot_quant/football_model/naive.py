"""Benchmark naif : frequence historique des issues, sans aucune information
sur l'identite des equipes.

C'est le plancher absolu que tout modele doit battre hors echantillon pour
justifier sa complexite (voir docs/research_framework.md, section H).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class NaiveModel:
    def __init__(self) -> None:
        self._probs: tuple[float, float, float] | None = None

    def fit(self, matches_df: pd.DataFrame) -> "NaiveModel":
        if matches_df.empty:
            raise ValueError("Impossible d'entrainer sur un ensemble de matchs vide.")
        home_goals = matches_df["home_goals"].to_numpy()
        away_goals = matches_df["away_goals"].to_numpy()
        n = len(matches_df)
        home_win = float(np.sum(home_goals > away_goals)) / n
        draw = float(np.sum(home_goals == away_goals)) / n
        away_win = float(np.sum(home_goals < away_goals)) / n
        self._probs = (home_win, draw, away_win)
        return self

    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]:
        if self._probs is None:
            raise RuntimeError("Le modele doit etre entraine (fit) avant predict().")
        return self._probs
