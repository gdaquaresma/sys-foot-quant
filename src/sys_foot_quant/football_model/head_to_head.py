"""Derniere confrontation directe (H2H) entre deux equipes, testee comme
hypothese INDEPENDANTE (docs/research_framework.md, re-test A1-recence) -
ne doit jamais etre suppose utile a priori, ni combine avec la forme
recente (``recent_form.py``) tant qu'il n'a pas demontre un benefice
hors echantillon propre.

Mecanisme retenu, deliberement minimal : un modele Poisson simple
(``PoissonModel(use_team_hfa=False)``, meme reference que
``poisson_simple`` partout ailleurs dans le projet) sert de base ; si les
deux equipes se sont deja rencontrees (dans n'importe quel sens,
domicile ou exterieur) dans l'historique disponible, l'issue de LEUR
DERNIERE rencontre (traduite dans le sens domicile/exterieur du match a
predire) est ajoutee comme un vecteur one-hot [1,0,0]/[0,1,0]/[0,0,1], et
melangee lineairement a la prediction Poisson simple avec un poids fixe
``weight`` (petit, fixe AVANT tout test - voir echange de validation du
protocole). Aucune rencontre anterieure disponible -> retour EXACT a la
prediction Poisson simple (aucun biais introduit par absence
d'information), pas une valeur par defaut arbitraire.
"""

from __future__ import annotations

import pandas as pd

from sys_foot_quant.football_model.poisson import PoissonModel

_H2H_COLUMNS = ["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]


class HeadToHeadModel:
    def __init__(self, weight: float = 0.10, max_goals: int = 20) -> None:
        if not (0.0 <= weight <= 1.0):
            raise ValueError(f"weight doit etre dans [0, 1] (recu {weight}).")
        self.weight = weight
        self.max_goals = max_goals

        self._base: PoissonModel | None = None
        self._train_df: pd.DataFrame | None = None

    def fit(self, matches_df: pd.DataFrame, decision_time: object = None) -> "HeadToHeadModel":
        """``decision_time`` non utilise directement, meme raison que dans
        ``RecentFormModel``/``BayesianSequentialModel`` (point-in-time deja
        garanti en amont par le Repository)."""
        if matches_df.empty:
            raise ValueError("Impossible d'entrainer sur un ensemble de matchs vide.")

        self._base = PoissonModel(use_team_hfa=False).fit(matches_df)
        # Tri chronologique STABLE explicite : "derniere" rencontre exige
        # un ordre reel, jamais l'ordre d'arrivee des lignes du DataFrame.
        self._train_df = (
            matches_df[_H2H_COLUMNS].sort_values("kickoff_time", kind="mergesort").reset_index(drop=True)
        )
        return self

    def _last_h2h_outcome(
        self, home_team_id: int, away_team_id: int
    ) -> tuple[float, float, float] | None:
        assert self._train_df is not None
        df = self._train_df
        mask = ((df["home_team_id"] == home_team_id) & (df["away_team_id"] == away_team_id)) | (
            (df["home_team_id"] == away_team_id) & (df["away_team_id"] == home_team_id)
        )
        h2h = df.loc[mask]
        if h2h.empty:
            return None

        last = h2h.iloc[-1]  # deja trie chronologiquement -> derniere ligne = derniere rencontre
        if int(last["home_team_id"]) == home_team_id:
            hg, ag = float(last["home_goals"]), float(last["away_goals"])
        else:
            hg, ag = float(last["away_goals"]), float(last["home_goals"])

        if hg > ag:
            return (1.0, 0.0, 0.0)
        if hg == ag:
            return (0.0, 1.0, 0.0)
        return (0.0, 0.0, 1.0)

    def predict_outcome_probabilities(
        self, home_team_id: int, away_team_id: int, max_goals: int | None = None
    ) -> tuple[float, float, float]:
        if self._base is None:
            raise RuntimeError("Le modele doit etre entraine (fit) avant predict_outcome_probabilities().")

        base_probs = self._base.predict_outcome_probabilities(
            home_team_id, away_team_id, max_goals=max_goals or self.max_goals
        )
        h2h_outcome = self._last_h2h_outcome(home_team_id, away_team_id)
        if h2h_outcome is None:
            return base_probs

        w = self.weight
        return tuple((1.0 - w) * b + w * h for b, h in zip(base_probs, h2h_outcome))  # type: ignore[return-value]

    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]:
        """Alias pour une interface uniforme avec les autres modeles du
        walk-forward (``FittedPredictor.predict``)."""
        return self.predict_outcome_probabilities(home_team_id, away_team_id)
