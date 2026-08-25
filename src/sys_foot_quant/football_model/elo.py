"""Benchmark Elo (rating de force + calibration empirique par tranche).

L'Elo classique donne un "score de match attendu" (1 = victoire, 0.5 =
nul, 0 = defaite) a partir de l'ecart de rating, mais ne separe pas
nativement victoire/nul/defaite (marche a 3 issues). Plutot que de fixer
arbitrairement une forme parametrique de conversion, ce module estime la
repartition empirique domicile/nul/exterieur observee historiquement pour
chaque tranche de "score attendu" (binning), et l'applique aux nouvelles
predictions - une forme simple de calibration isotonique par tranches.

Voir docs/research_framework.md, section A3 : ce modele sert egalement de
proxy pour le "Power Rating" (Dolan), qui n'est structurellement qu'une
variante d'Elo et ne justifie pas d'implementation separee.

IMPORTANT : ``matches_df`` passe a ``fit`` DOIT etre trie par ordre
chronologique croissant (kickoff_time) - les ratings sont mis a jour
sequentiellement match par match, et l'ordre determine le resultat.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_HOME, _DRAW, _AWAY = 0, 1, 2


class EloModel:
    def __init__(
        self,
        k: float = 20.0,
        home_advantage: float = 100.0,
        initial_rating: float = 1500.0,
        n_calibration_bins: int = 10,
    ) -> None:
        self.k = k
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.n_calibration_bins = n_calibration_bins
        self.ratings_: dict[int, float] | None = None
        self._bins: list[dict] | None = None

    def fit(self, matches_df: pd.DataFrame) -> "EloModel":
        if matches_df.empty:
            raise ValueError("Impossible d'entrainer sur un ensemble de matchs vide.")

        ratings: dict[int, float] = {}
        expected_scores = []
        outcomes = []

        for row in matches_df.itertuples(index=False):
            h, a = int(row.home_team_id), int(row.away_team_id)
            rh = ratings.get(h, self.initial_rating)
            ra = ratings.get(a, self.initial_rating)
            expected_home = self._expected_score(rh, ra)

            if row.home_goals > row.away_goals:
                actual_home, outcome = 1.0, _HOME
            elif row.home_goals == row.away_goals:
                actual_home, outcome = 0.5, _DRAW
            else:
                actual_home, outcome = 0.0, _AWAY

            ratings[h] = rh + self.k * (actual_home - expected_home)
            ratings[a] = ra + self.k * ((1.0 - actual_home) - (1.0 - expected_home))

            expected_scores.append(expected_home)
            outcomes.append(outcome)

        self.ratings_ = ratings
        self._bins = self._fit_calibration_bins(np.array(expected_scores), np.array(outcomes))
        return self

    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]:
        if self.ratings_ is None or self._bins is None:
            raise RuntimeError("Le modele doit etre entraine (fit) avant predict().")
        rh = self.ratings_.get(home_team_id, self.initial_rating)
        ra = self.ratings_.get(away_team_id, self.initial_rating)
        expected_home = self._expected_score(rh, ra)
        return self._lookup_calibration(expected_home)

    def _expected_score(self, rating_home: float, rating_away: float) -> float:
        diff = rating_home + self.home_advantage - rating_away
        return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))

    def _fit_calibration_bins(
        self, expected_scores: np.ndarray, outcomes: np.ndarray
    ) -> list[dict]:
        edges = np.linspace(0.0, 1.0, self.n_calibration_bins + 1)
        bin_idx = np.clip(
            np.digitize(expected_scores, edges[1:-1], right=True), 0, self.n_calibration_bins - 1
        )
        bins = []
        for b in range(self.n_calibration_bins):
            mask = bin_idx == b
            count = int(mask.sum())
            bins.append(
                {
                    "mid": (edges[b] + edges[b + 1]) / 2.0,
                    "count": count,
                    "home": float(np.mean(outcomes[mask] == _HOME)) if count else None,
                    "draw": float(np.mean(outcomes[mask] == _DRAW)) if count else None,
                    "away": float(np.mean(outcomes[mask] == _AWAY)) if count else None,
                }
            )
        return bins

    def _lookup_calibration(self, expected_home: float) -> tuple[float, float, float]:
        assert self._bins is not None
        candidates = [b for b in self._bins if b["count"] > 0]
        if not candidates:
            # Ne devrait jamais arriver (fit() exige un ensemble non vide,
            # donc au moins une tranche est peuplee), mais on se protege
            # avec un repli neutre plutot que de lever une exception ici.
            return (expected_home, 0.0, 1.0 - expected_home)
        nearest = min(candidates, key=lambda b: abs(b["mid"] - expected_home))
        return (nearest["home"], nearest["draw"], nearest["away"])
