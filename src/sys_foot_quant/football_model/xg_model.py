"""Modele Poisson dont l'attaque/defense par equipe est estimee a partir du
xG historique plutot que des buts reels marques/encaisses (hypothese B3,
docs/research_framework.md section B3).

Hypothese testee, isolee et unique (rien d'autre) : le xG historique
d'une equipe est-il un meilleur signal de sa force sous-jacente que ses
buts reels, pour predire ses PROCHAINS matchs ?

Extension isolee de la meme famille que ``DixonColesModel``/
``RecentFormModel`` : classe entierement nouvelle, n'importe ni ne modifie
``PoissonModel``. La formulation mathematique est deliberement identique
a la configuration "poisson_simple" deja utilisee comme reference dans
tout le projet (pas de HFA par equipe, pas de shrinkage, aucun
hyperparametre libre) - seule la source des "buts" utilisee pour calculer
les ratios attaque/defense change (xG au lieu de buts reels). C'est ce qui
garantit une comparaison XGModel vs poisson_simple qui isole strictement
la question posee, sans introduire une deuxieme variable non controlee.

``fit`` attend un DataFrame avec les colonnes ``home_team_id``,
``away_team_id``, ``home_xg``, ``away_xg`` (pas de colonne de buts reels -
ce modele n'en a par construction pas besoin pour s'entrainer, meme s'il
predit ensuite une distribution de buts via Poisson(lambda, mu)).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sys_foot_quant.football_model.scoring import outcome_probabilities, score_matrix
from sys_foot_quant.football_model.weighting import flat_weights

_EPS = 1e-9


class XGModel:
    def __init__(self, max_goals: int = 20) -> None:
        self.max_goals = max_goals

        self.attack_: dict[int, float] | None = None
        self.defense_: dict[int, float] | None = None
        self.league_base_: float | None = None
        self.hfa_global_: float | None = None

    def fit(self, matches_df: pd.DataFrame, weights: np.ndarray | None = None) -> "XGModel":
        if matches_df.empty:
            raise ValueError("Impossible d'entrainer sur un ensemble de matchs vide.")

        n = len(matches_df)
        w = flat_weights(n) if weights is None else np.asarray(weights, dtype=float)
        if w.shape[0] != n:
            raise ValueError(f"weights doit avoir {n} elements, recu {w.shape[0]}.")
        total_weight = float(w.sum())
        if total_weight <= 0:
            raise ValueError("La somme des ponderations doit etre strictement positive.")

        home_ids = matches_df["home_team_id"].to_numpy()
        away_ids = matches_df["away_team_id"].to_numpy()
        home_xg = matches_df["home_xg"].to_numpy(dtype=float)
        away_xg = matches_df["away_xg"].to_numpy(dtype=float)

        league_base = max(float((w * (home_xg + away_xg)).sum()) / (2.0 * total_weight), _EPS)
        mean_home = float((w * home_xg).sum()) / total_weight
        mean_away = float((w * away_xg).sum()) / total_weight
        hfa_global = max(mean_home / mean_away, _EPS) if mean_away > 0 else 1.0

        teams = sorted(set(home_ids.tolist()) | set(away_ids.tolist()))
        scored_sum = {t: 0.0 for t in teams}
        conceded_sum = {t: 0.0 for t in teams}
        weight_total = {t: 0.0 for t in teams}
        for i in range(n):
            h, a, wi = home_ids[i], away_ids[i], w[i]
            scored_sum[h] += wi * home_xg[i]
            scored_sum[a] += wi * away_xg[i]
            conceded_sum[h] += wi * away_xg[i]
            conceded_sum[a] += wi * home_xg[i]
            weight_total[h] += wi
            weight_total[a] += wi

        attack: dict[int, float] = {}
        defense: dict[int, float] = {}
        for t in teams:
            if weight_total[t] <= 0:
                attack[t] = 1.0
                defense[t] = 1.0
            else:
                scored_rate = scored_sum[t] / weight_total[t]
                conceded_rate = conceded_sum[t] / weight_total[t]
                attack[t] = max(scored_rate / league_base, _EPS)
                defense[t] = max(conceded_rate / league_base, _EPS)

        self.attack_ = attack
        self.defense_ = defense
        self.league_base_ = league_base
        self.hfa_global_ = hfa_global
        return self

    def predict_lambda_mu(self, home_team_id: int, away_team_id: int) -> tuple[float, float]:
        if self.attack_ is None:
            raise RuntimeError("Le modele doit etre entraine (fit) avant predict_lambda_mu().")
        assert self.defense_ is not None
        assert self.league_base_ is not None
        assert self.hfa_global_ is not None

        attack_h = self.attack_.get(home_team_id, 1.0)
        defense_h = self.defense_.get(home_team_id, 1.0)
        attack_a = self.attack_.get(away_team_id, 1.0)
        defense_a = self.defense_.get(away_team_id, 1.0)

        lam = self.league_base_ * attack_h * defense_a * self.hfa_global_
        mu = self.league_base_ * attack_a * defense_h
        return lam, mu

    def predict_outcome_probabilities(
        self, home_team_id: int, away_team_id: int, max_goals: int | None = None
    ) -> tuple[float, float, float]:
        lam, mu = self.predict_lambda_mu(home_team_id, away_team_id)
        matrix = score_matrix(lam, mu, max_goals=max_goals or self.max_goals)
        home_win, draw, away_win = outcome_probabilities(matrix)
        total = home_win + draw + away_win
        return (home_win / total, draw / total, away_win / total)

    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]:
        """Alias pour une interface uniforme avec les autres modeles
        (``FittedPredictor.predict``)."""
        return self.predict_outcome_probabilities(home_team_id, away_team_id)
