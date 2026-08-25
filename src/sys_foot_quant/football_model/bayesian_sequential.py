"""Mise a jour bayesienne sequentielle de la force d'equipe (hypothese B2
du Research Framework, docs/research_framework.md section B2).

Alternative CONCURRENTE a la ponderation temporelle par fenetre glissante
(A1, ``football_model/weighting.py``) - pas une brique cumulative. Les
deux methodes visent le meme objectif (capter l'evolution recente de la
force d'une equipe) par des voies differentes :

- A1 : recalcule un ratio pondere sur une fenetre/decroissance exogene,
  appliquee uniformement a tout l'historique.
- B2 : maintient, pour chaque equipe, une croyance (prior) sur son
  ratio d'attaque et de defense, mise a jour SEQUENTIELLEMENT match par
  match (prior -> observation -> posterior, qui devient le nouveau prior
  pour le match suivant), en suivant l'ordre chronologique des matchs.

Modelisation retenue - conjugaison Gamma-Poisson (choix delibere pour
rester sans optimiseur numerique, coherent avec le reste du Football
Model, voir football_model/poisson.py) :

    buts_marques | ratio_attaque ~ Poisson(ratio_attaque * exposition)
    ratio_attaque ~ Gamma(alpha, beta)  (moyenne = alpha/beta)

``exposition`` est le nombre de buts qu'une equipe MOYENNE (ratio=1.0)
marquerait dans ce contexte precis (force de defense adverse courante,
HFA global), au moment du match. La mise a jour conjuguee est alors :

    posterior = Gamma(alpha + buts_observes, beta + exposition)

Le meme mecanisme est applique symetriquement a la defense (buts
encaisses). ``league_base`` et ``hfa_global`` sont calcules UNE FOIS sur
tout l'historique d'entrainement (comme dans PoissonModel), puis geles
pendant la boucle sequentielle - simplification documentee, pas un
optimiseur cache.

``prior_strength`` (alpha0 = beta0 avant tout match, moyenne 1.0 =
equipe moyenne) est un parametre PRE-ENREGISTRE, choisi par analogie
directe avec la constante de shrinkage HFA deja validee (A2,
``hfa_shrinkage_k=10.0``) pour eviter d'introduire un nouveau magic
number non justifie - PAS optimise sur les donnees de test.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from sys_foot_quant.football_model.scoring import outcome_probabilities, score_matrix

_EPS = 1e-9
DEFAULT_PRIOR_STRENGTH = 10.0  # par analogie avec hfa_shrinkage_k=10.0 (A2), pre-enregistre


class BayesianSequentialModel:
    def __init__(self, prior_strength: float = DEFAULT_PRIOR_STRENGTH) -> None:
        if prior_strength <= 0:
            raise ValueError(f"prior_strength doit etre strictement positif (recu {prior_strength}).")
        self.prior_strength = prior_strength

        self.attack_alpha_: dict[int, float] | None = None
        self.attack_beta_: dict[int, float] | None = None
        self.defense_alpha_: dict[int, float] | None = None
        self.defense_beta_: dict[int, float] | None = None
        self.league_base_: float | None = None
        self.hfa_global_: float | None = None

    def fit(self, matches_df: pd.DataFrame, decision_time: datetime | None = None) -> "BayesianSequentialModel":
        """``decision_time`` n'est pas utilise par la mise a jour elle-meme
        (pas de decroissance exogene en B2, c'est justement ce qui la
        distingue d'A1) - conserve uniquement pour une signature uniforme
        avec les autres configurations du walk-forward."""
        if matches_df.empty:
            raise ValueError("Impossible d'entrainer sur un ensemble de matchs vide.")

        # Tri chronologique explicite : la mise a jour sequentielle doit
        # suivre l'ordre reel des matchs, jamais l'ordre d'arrivee des
        # lignes du DataFrame (qui n'est pas garanti par le Repository).
        # Tri STABLE (mergesort) requis : le tri par defaut de pandas
        # (quicksort) n'est pas stable et rendrait l'ordre de traitement
        # des matchs a kickoff_time strictement identique (meme journee)
        # non-reproductible d'un appel a l'autre - violerait l'exigence de
        # reproductibilite deterministe du projet (ADR 0004). Limite
        # documentee : pour des matchs reellement simultanes, l'ordre
        # relatif retenu est celui du DataFrame d'entree, pas une mise a
        # jour groupee - simplification deliberee, comme les autres choix
        # de modelisation de ce module.
        df = matches_df.sort_values("kickoff_time", kind="mergesort").reset_index(drop=True)

        home_ids = df["home_team_id"].to_numpy()
        away_ids = df["away_team_id"].to_numpy()
        home_goals = df["home_goals"].to_numpy(dtype=float)
        away_goals = df["away_goals"].to_numpy(dtype=float)
        n = len(df)

        league_base = max(float((home_goals + away_goals).sum()) / (2.0 * n), _EPS)
        mean_home = float(home_goals.mean())
        mean_away = float(away_goals.mean())
        hfa_global = max(mean_home / mean_away, _EPS) if mean_away > 0 else 1.0
        self.league_base_ = league_base
        self.hfa_global_ = hfa_global

        teams = sorted(set(home_ids.tolist()) | set(away_ids.tolist()))
        k0 = self.prior_strength
        attack_alpha = {t: k0 for t in teams}
        attack_beta = {t: k0 for t in teams}
        defense_alpha = {t: k0 for t in teams}
        defense_beta = {t: k0 for t in teams}

        for i in range(n):
            h, a = home_ids[i], away_ids[i]
            hg, ag = home_goals[i], away_goals[i]

            attack_h_mean = attack_alpha[h] / attack_beta[h]
            defense_h_mean = defense_alpha[h] / defense_beta[h]
            attack_a_mean = attack_alpha[a] / attack_beta[a]
            defense_a_mean = defense_alpha[a] / defense_beta[a]

            # Exposition = ce qu'une equipe moyenne marquerait dans ce
            # contexte precis, avec les croyances COURANTES (avant ce
            # match) sur la defense adverse - jamais mises a jour avec le
            # resultat du match en cours avant d'avoir servi d'exposition.
            exposure_home_attack = league_base * defense_a_mean * hfa_global
            exposure_away_defense = league_base * attack_h_mean * hfa_global
            exposure_away_attack = league_base * defense_h_mean
            exposure_home_defense = league_base * attack_a_mean

            attack_alpha[h] += hg
            attack_beta[h] += exposure_home_attack
            defense_alpha[a] += hg
            defense_beta[a] += exposure_away_defense

            attack_alpha[a] += ag
            attack_beta[a] += exposure_away_attack
            defense_alpha[h] += ag
            defense_beta[h] += exposure_home_defense

        self.attack_alpha_ = attack_alpha
        self.attack_beta_ = attack_beta
        self.defense_alpha_ = defense_alpha
        self.defense_beta_ = defense_beta
        return self

    def _mean_ratio(self, alphas: dict[int, float], betas: dict[int, float], team_id: int) -> float:
        if team_id not in alphas:
            return 1.0  # equipe inconnue -> prior neutre (alpha0=beta0 => moyenne 1.0)
        return alphas[team_id] / betas[team_id]

    def predict_lambda_mu(self, home_team_id: int, away_team_id: int) -> tuple[float, float]:
        if self.attack_alpha_ is None:
            raise RuntimeError("Le modele doit etre entraine (fit) avant predict_lambda_mu().")
        assert self.defense_alpha_ is not None
        assert self.attack_beta_ is not None
        assert self.defense_beta_ is not None
        assert self.league_base_ is not None
        assert self.hfa_global_ is not None

        attack_h = self._mean_ratio(self.attack_alpha_, self.attack_beta_, home_team_id)
        defense_h = self._mean_ratio(self.defense_alpha_, self.defense_beta_, home_team_id)
        attack_a = self._mean_ratio(self.attack_alpha_, self.attack_beta_, away_team_id)
        defense_a = self._mean_ratio(self.defense_alpha_, self.defense_beta_, away_team_id)

        lam = self.league_base_ * attack_h * defense_a * self.hfa_global_
        mu = self.league_base_ * attack_a * defense_h
        return lam, mu

    def predict_outcome_probabilities(
        self, home_team_id: int, away_team_id: int, max_goals: int = 20
    ) -> tuple[float, float, float]:
        lam, mu = self.predict_lambda_mu(home_team_id, away_team_id)
        matrix = score_matrix(lam, mu, max_goals=max_goals)
        home_win, draw, away_win = outcome_probabilities(matrix)
        total = home_win + draw + away_win
        return (home_win / total, draw / total, away_win / total)

    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float]:
        """Alias pour une interface uniforme avec les autres modeles du
        walk-forward (``FittedPredictor.predict``)."""
        return self.predict_outcome_probabilities(home_team_id, away_team_id)
