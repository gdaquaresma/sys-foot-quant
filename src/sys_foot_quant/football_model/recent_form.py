"""Forme recente par equipe, a fenetre fixe (hypothese A1-bis du Research
Framework, docs/research_framework.md section A1 - re-test avec une
definition football-realiste de la forme recente, remplacant l'ancienne
decroissance exponentielle calendaire deja jugee dominee par
poisson_simple sur les deux scenarios synthetiques).

Difference deliberee avec l'ancienne A1 (``football_model/weighting.py``,
``exponential_decay_weights``) : au lieu d'une decroissance continue en
JOURS calendaires (un match d'il y a 40 jours pese presque autant qu'un
match d'il y a 10 jours des lors que la demi-vie est large), ce module
retient un nombre FIXE des ``window`` derniers matchs de chaque equipe
(poids plat DANS la fenetre, poids nul strictement en dehors) - une
equipe change (joueurs, entraineur, systeme, niveau de forme), donc un
resultat vieux de plusieurs mois ne doit plus peser du tout au-dela d'un
nombre de matchs recents fixe, quel que soit l'ecart calendaire reel.

``prior_k`` (par defaut 0.0 = aucun mecanisme de memoire longue, fenetre
seule) permet de tester separement l'hypothese "faible memoire de la
saison precedente" : le ratio attaque/defense de la fenetre recente est
alors mélange, par shrinkage bayesien empirique (MEME famille
mathematique que le shrinkage HFA deja valide en A2,
``football_model/poisson.py``, formule poids/(poids+k)), vers le ratio
calcule sur TOUT l'historique disponible de l'equipe (long terme). Plus
une equipe a de matchs recents disponibles dans sa fenetre (jusqu'a
``window``), moins l'historique long pese ; au tout debut de
l'historique connu d'une equipe (moins de ``window`` matchs disponibles),
l'historique long agit comme un prior/fondation qui comble
l'echantillon recent insuffisant. Ce generateur synthetique n'a aucune
notion de saison : "l'historique long" est ici, par construction,
l'unique traduction disponible et documentee de "memoire de la saison
precedente" pour ce jeu de donnees (voir echange de validation du
protocole).

Le HFA par equipe (A2) n'est PAS combine ici : conformement a la
pratique deja etablie pour isoler la question testee (A1 vs B2 a l'etape
5), seul le HFA global (moyenne de ligue) est utilise - jamais de
shrinkage HFA par equipe dans ce module.
"""

from __future__ import annotations

import pandas as pd

from sys_foot_quant.football_model.scoring import (
    low_score_cell_probabilities,
    outcome_probabilities,
    score_matrix,
)

_EPS = 1e-9


class RecentFormModel:
    def __init__(self, window: int, prior_k: float = 0.0, max_goals: int = 20) -> None:
        if window < 1:
            raise ValueError(f"window doit etre >= 1 (recu {window}).")
        if prior_k < 0:
            raise ValueError(f"prior_k doit etre >= 0 (recu {prior_k}).")
        self.window = window
        self.prior_k = prior_k
        self.max_goals = max_goals

        self.attack_: dict[int, float] | None = None
        self.defense_: dict[int, float] | None = None
        self.league_base_: float | None = None
        self.hfa_global_: float | None = None

    def fit(self, matches_df: pd.DataFrame, decision_time: object = None) -> "RecentFormModel":
        """``decision_time`` n'est pas utilise directement (le point-in-time
        est deja garanti en amont par le Repository : ``matches_df`` ne
        contient, par construction du walk-forward, que des matchs connus
        a l'instant de decision) - conserve uniquement pour une signature
        uniforme avec les autres configurations du walk-forward."""
        if matches_df.empty:
            raise ValueError("Impossible d'entrainer sur un ensemble de matchs vide.")

        # Tri chronologique STABLE explicite : la notion de "derniers
        # matchs" exige un ordre reel, jamais l'ordre d'arrivee des lignes
        # du DataFrame (non garanti par le Repository) - meme discipline
        # que BayesianSequentialModel (voir bayesian_sequential.py).
        df = matches_df.sort_values("kickoff_time", kind="mergesort").reset_index(drop=True)

        home_ids = df["home_team_id"].to_numpy()
        away_ids = df["away_team_id"].to_numpy()
        home_goals = df["home_goals"].to_numpy(dtype=float)
        away_goals = df["away_goals"].to_numpy(dtype=float)
        n_total = len(df)

        league_base = max(float((home_goals + away_goals).sum()) / (2.0 * n_total), _EPS)
        mean_home = float(home_goals.mean())
        mean_away = float(away_goals.mean())
        hfa_global = max(mean_home / mean_away, _EPS) if mean_away > 0 else 1.0
        self.league_base_ = league_base
        self.hfa_global_ = hfa_global

        teams = sorted(set(home_ids.tolist()) | set(away_ids.tolist()))
        team_history: dict[int, list[tuple[float, float]]] = {t: [] for t in teams}
        for i in range(n_total):
            h, a = home_ids[i], away_ids[i]
            team_history[h].append((home_goals[i], away_goals[i]))
            team_history[a].append((away_goals[i], home_goals[i]))

        attack: dict[int, float] = {}
        defense: dict[int, float] = {}
        for t in teams:
            history = team_history[t]  # deja chronologique (df trie stable)
            n_all = len(history)
            if n_all == 0:
                attack[t] = 1.0
                defense[t] = 1.0
                continue

            scored_all = sum(m[0] for m in history)
            conceded_all = sum(m[1] for m in history)
            long_run_attack = max((scored_all / n_all) / league_base, _EPS)
            long_run_defense = max((conceded_all / n_all) / league_base, _EPS)

            recent = history[-self.window :]
            n_recent = len(recent)
            scored_recent = sum(m[0] for m in recent)
            conceded_recent = sum(m[1] for m in recent)
            recent_attack = max((scored_recent / n_recent) / league_base, _EPS)
            recent_defense = max((conceded_recent / n_recent) / league_base, _EPS)

            if self.prior_k > 0:
                k = self.prior_k
                attack[t] = (n_recent * recent_attack + k * long_run_attack) / (n_recent + k)
                defense[t] = (n_recent * recent_defense + k * long_run_defense) / (n_recent + k)
            else:
                attack[t] = recent_attack
                defense[t] = recent_defense

        self.attack_ = attack
        self.defense_ = defense
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
        """Alias pour une interface uniforme avec les autres modeles du
        walk-forward (``FittedPredictor.predict``)."""
        return self.predict_outcome_probabilities(home_team_id, away_team_id)

    def predict_low_score_probs(
        self, home_team_id: int, away_team_id: int, max_goals: int | None = None
    ) -> tuple[float, float, float, float]:
        """(P(0-0), P(1-0), P(0-1), P(1-1)) - AJOUT PUR pour reutiliser le
        diagnostic bas-score existant si besoin ; n'est pas la metrique de
        decision du protocole A1-recence (Brier/log loss globaux sur le
        walk-forward), mais assure une interface homogene avec
        PoissonModel/DixonColesModel."""
        lam, mu = self.predict_lambda_mu(home_team_id, away_team_id)
        matrix = score_matrix(lam, mu, max_goals=max_goals or self.max_goals)
        matrix = matrix / matrix.sum()
        return low_score_cell_probabilities(matrix)
