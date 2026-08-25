"""DixonColesModel : correction de correlation basse-score (hypothese B1
du Research Framework, docs/research_framework.md section B1).

Le Poisson simple suppose les buts domicile/exterieur INDEPENDANTS. Dixon
& Coles (1997) observent que les scores bas (0-0, 1-0, 0-1, 1-1) sont
sur/sous-representes par rapport a cette hypothese, et corrigent la loi
JOINTE (les lois marginales restent Poisson(lambda)/Poisson(mu)) par un
facteur tau(x,y;rho) defini uniquement sur ces quatre cellules :

    tau(0,0) = 1 - lambda*mu*rho
    tau(1,0) = 1 + mu*rho
    tau(0,1) = 1 + lambda*rho
    tau(1,1) = 1 - rho
    tau(x,y) = 1                    pour x>=2 ou y>=2

Extension ISOLEE de PoissonModel (sous-classe) : herite integralement de
``PoissonModel.fit()`` pour attaque/defense/HFA - AUCUNE ligne de
``football_model/poisson.py`` n'est modifiee ou re-implementee ici, son
comportement reste rigoureusement inchange. La seule etape ajoutee est
l'estimation d'un scalaire unique ``rho`` par maximum de vraisemblance,
les (lambda, mu) de chaque match d'entrainement etant traites comme FIXES
(deja estimes par la methode des ratios de PoissonModel, pas re-estimes
conjointement avec rho). Ce choix delibere evite un MLE joint
multi-parametres (risque de non-convergence) : c'est exactement le meme
principe de simplicite deja documente dans poisson.py ("pas d'optimiseur
numerique... pour rester simple"). Un seul scalaire borne reste toutefois
un probleme d'optimisation 1D bien pose ; une recherche bornee
(``scipy.optimize.minimize_scalar``, ``method="bounded"``) a un risque de
non-convergence sans commune mesure avec un MLE joint a haute dimension.

Voir docs/decisions/0005-protocole-generateur-dixon-coles.md pour le
protocole complet (generateur synthetique dedie, choix de rho, bornes de
validite) et docs/research_framework.md section B1 pour le protocole de
test hors-echantillon (walk-forward, metriques bas-score).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.scoring import (
    low_score_cell_probabilities,
    outcome_probabilities,
    score_matrix,
)

_RHO_BOUND_EPS = 1e-6
_DEFAULT_MAX_GOALS = 20
_LOG_TAU_FLOOR = 1e-300  # evite log(0) exact en cas de tau numeriquement nul


def dixon_coles_tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Facteur correctif tau(x,y) de Dixon & Coles (1997). Vaut 1 partout
    sauf sur les quatre cellules bas-score (0-0, 1-0, 0-1, 1-1)."""
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def rho_valid_bounds(lam: float, mu: float) -> tuple[float, float]:
    """Intervalle de rho garantissant tau(x,y) >= 0 sur les quatre
    cellules bas-score, pour un couple (lam, mu) donne."""
    if lam <= 0 or mu <= 0:
        raise ValueError(f"lam et mu doivent etre strictement positifs (lam={lam}, mu={mu}).")
    lo = max(-1.0 / lam, -1.0 / mu)
    hi = min(1.0, 1.0 / (lam * mu))
    return lo, hi


def apply_dixon_coles_correction(matrix: np.ndarray, lam: float, mu: float, rho: float) -> np.ndarray:
    """Applique tau aux quatre cellules bas-score d'une matrice de score
    deja normalisee (Poisson independant), puis RENORMALISE l'ensemble de
    la matrice pour garantir une distribution de probabilite exacte
    (voir ADR 0005, point 2 : la version academique originale ne
    renormalise pas pour un petit rho, ce projet le fait explicitement)."""
    corrected = matrix.copy()
    for x, y in ((0, 0), (1, 0), (0, 1), (1, 1)):
        corrected[x, y] = matrix[x, y] * dixon_coles_tau(x, y, lam, mu, rho)
    total = corrected.sum()
    if total <= 0:
        raise ValueError(
            f"Masse totale non positive apres correction tau (rho={rho}, lam={lam}, mu={mu})."
        )
    return corrected / total


class DixonColesModel(PoissonModel):
    def __init__(
        self,
        hfa_shrinkage_k: float = 10.0,
        use_team_hfa: bool = True,
        max_goals: int = _DEFAULT_MAX_GOALS,
    ) -> None:
        super().__init__(hfa_shrinkage_k=hfa_shrinkage_k, use_team_hfa=use_team_hfa)
        if max_goals < 1:
            raise ValueError("max_goals doit etre >= 1.")
        self.max_goals = max_goals
        self.rho_: float | None = None

    def fit(self, matches_df: pd.DataFrame, weights: np.ndarray | None = None) -> "DixonColesModel":
        # Delegue integralement a PoissonModel.fit (attaque/defense/HFA) -
        # comportement de PoissonModel non modifie, cf. docstring module.
        super().fit(matches_df, weights=weights)
        self.rho_ = self._estimate_rho(matches_df)
        return self

    def _estimate_rho(self, matches_df: pd.DataFrame) -> float:
        home_ids = matches_df["home_team_id"].to_numpy()
        away_ids = matches_df["away_team_id"].to_numpy()
        home_goals = matches_df["home_goals"].to_numpy(dtype=int)
        away_goals = matches_df["away_goals"].to_numpy(dtype=int)
        n = len(matches_df)

        lam_mu = [
            self.predict_lambda_mu(int(home_ids[i]), int(away_ids[i])) for i in range(n)
        ]

        # Bornes COMMUNES = intersection des bornes par-match : garantit
        # tau >= 0 pour CHAQUE match d'entrainement (pas seulement en
        # moyenne), jamais un ecretage silencieux d'un rho hors bornes
        # pour un sous-ensemble de matchs (meme discipline que le
        # generateur, voir ADR 0005 point 3).
        bounds_per_match = [rho_valid_bounds(lam, mu) for lam, mu in lam_mu]
        lo = max(b[0] for b in bounds_per_match) + _RHO_BOUND_EPS
        hi = min(b[1] for b in bounds_per_match) - _RHO_BOUND_EPS
        if lo >= hi:
            # Intervalle vide (cas degenere - jamais rencontre avec des
            # lambda/mu realistes de football dans ce projet) : repli
            # EXPLICITE et documente sur rho=0.0 (equivalent Poisson
            # simple), jamais un ecretage silencieux hors de cet
            # intervalle vide.
            return 0.0

        def neg_log_lik(rho: float) -> float:
            total = 0.0
            for i in range(n):
                lam, mu = lam_mu[i]
                tau = dixon_coles_tau(int(home_goals[i]), int(away_goals[i]), lam, mu, rho)
                total += np.log(max(tau, _LOG_TAU_FLOOR))
            return -total

        result = minimize_scalar(neg_log_lik, bounds=(lo, hi), method="bounded")
        return float(result.x)

    def predict_score_matrix(self, home_team_id: int, away_team_id: int) -> np.ndarray:
        if self.rho_ is None:
            raise RuntimeError("Le modele doit etre entraine (fit) avant predict_score_matrix().")
        lam, mu = self.predict_lambda_mu(home_team_id, away_team_id)
        matrix = score_matrix(lam, mu, max_goals=self.max_goals)
        matrix = matrix / matrix.sum()
        return apply_dixon_coles_correction(matrix, lam, mu, self.rho_)

    def predict_outcome_probabilities(
        self, home_team_id: int, away_team_id: int, max_goals: int | None = None
    ) -> tuple[float, float, float]:
        """``max_goals`` est ignore (conserve uniquement pour compatibilite
        de signature avec ``PoissonModel`` - la grille utilisee est celle
        fixee a la construction du modele, ``self.max_goals``, pour
        garantir que ``predict_low_score_probs`` et ce calcul d'issue
        proviennent toujours EXACTEMENT de la meme matrice)."""
        matrix = self.predict_score_matrix(home_team_id, away_team_id)
        home_win, draw, away_win = outcome_probabilities(matrix)
        total = home_win + draw + away_win
        return (home_win / total, draw / total, away_win / total)

    def predict_low_score_probs(
        self, home_team_id: int, away_team_id: int
    ) -> tuple[float, float, float, float]:
        """(P(0-0), P(1-0), P(0-1), P(1-1)) sous la correction Dixon-Coles
        - point cible du protocole de test B1."""
        matrix = self.predict_score_matrix(home_team_id, away_team_id)
        return low_score_cell_probabilities(matrix)
