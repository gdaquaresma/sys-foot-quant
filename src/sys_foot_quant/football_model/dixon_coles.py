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

    def fit(
        self,
        matches_df: pd.DataFrame,
        weights: np.ndarray | None = None,
        poisson_fit: "PoissonModel | None" = None,
    ) -> "DixonColesModel":
        """Optimisation d'execution (Phase P3, aucun changement scientifique) :
        si ``poisson_fit`` est fourni, reutilise ses parametres
        attaque/defense/HFA deja calcules plutot que de les recalculer via
        ``super().fit()`` - demontre strictement identiques (Phase P2,
        egalite exacte, jamais une approximation) des lors que
        ``poisson_fit`` provient reellement du MEME ``matches_df`` et de la
        MEME configuration (``use_team_hfa``/``hfa_shrinkage_k``). Verifie
        explicitement les deux plutot que de les supposer silencieusement -
        refuse (``ValueError``) en cas d'incoherence, jamais un resultat
        approximatif.

        Sans ``poisson_fit`` (valeur par defaut), comportement RIGOUREUSEMENT
        INCHANGE : delegue integralement a ``PoissonModel.fit()`` comme
        avant cette optimisation.

        Dans les DEUX cas, ``_estimate_rho`` est appelee exactement de la
        meme facon, sur le meme ``matches_df`` - l'estimation de rho n'est
        en rien affectee par cette optimisation, qui ne porte que sur la
        partie attaque/defense/HFA deja demontree redondante."""
        if poisson_fit is not None:
            if weights is not None:
                raise ValueError(
                    "poisson_fit et weights sont mutuellement exclusifs : le fit Poisson reutilise "
                    "a deja sa propre ponderation, fournir les deux serait ambigu plutot que d'en "
                    "ignorer un silencieusement."
                )
            if poisson_fit.use_team_hfa != self.use_team_hfa or poisson_fit.hfa_shrinkage_k != self.hfa_shrinkage_k:
                raise ValueError(
                    "poisson_fit incompatible : configuration differente "
                    f"(use_team_hfa={poisson_fit.use_team_hfa!r} vs {self.use_team_hfa!r}, "
                    f"hfa_shrinkage_k={poisson_fit.hfa_shrinkage_k!r} vs {self.hfa_shrinkage_k!r}) - "
                    "jamais une reutilisation entre configurations distinctes."
                )
            if poisson_fit.attack_ is None or poisson_fit._fit_input_df is None:
                raise ValueError("poisson_fit doit deja etre entraine (fit() appele) avant reutilisation.")
            if not poisson_fit._fit_input_df.equals(matches_df):
                raise ValueError(
                    "poisson_fit a ete entraine sur un jeu de donnees different de matches_df - "
                    "refus explicite plutot qu'une reutilisation non verifiee."
                )
            self.attack_ = poisson_fit.attack_
            self.defense_ = poisson_fit.defense_
            self.league_base_ = poisson_fit.league_base_
            self.hfa_global_ = poisson_fit.hfa_global_
            self.hfa_team_ = poisson_fit.hfa_team_
            self.raw_hfa_ = poisson_fit.raw_hfa_
            self.n_home_ = poisson_fit.n_home_
            self._fit_input_df = poisson_fit._fit_input_df
        else:
            # Chemin INCHANGE (comportement d'avant la Phase P3) - delegue
            # integralement a PoissonModel.fit (attaque/defense/HFA).
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

        # Optimisation d'execution (Phase P6, aucun changement scientifique) :
        # lambda/mu et l'appartenance de chaque match a l'une des quatre
        # cellules bas-score de dixon_coles_tau() sont INVARIANTS pendant
        # toute l'optimisation de rho (ne dependent que des donnees, jamais
        # de rho) - precalcules ICI, une seule fois par appel a
        # _estimate_rho, plutot qu'a chaque evaluation de neg_log_lik comme
        # le ferait un appel repete a dixon_coles_tau(). dixon_coles_tau()
        # elle-meme reste inchangee et continue d'etre utilisee telle
        # quelle ailleurs (apply_dixon_coles_correction).
        lam_arr = np.array([lm[0] for lm in lam_mu], dtype=float)
        mu_arr = np.array([lm[1] for lm in lam_mu], dtype=float)
        mask_00 = (home_goals == 0) & (away_goals == 0)
        mask_10 = (home_goals == 1) & (away_goals == 0)
        mask_01 = (home_goals == 0) & (away_goals == 1)
        mask_11 = (home_goals == 1) & (away_goals == 1)

        def neg_log_lik(rho: float) -> float:
            # Construction vectorisee de tau(x,y;rho) pour les n matchs -
            # memes quatre formules et meme valeur 1.0 pour les autres
            # scores que dixon_coles_tau(), appliquees via les masques
            # invariants ci-dessus plutot que par branchement Python
            # match par match. La SOMMATION reste une boucle Python
            # sequentielle, dans le MEME ordre que la version precedente,
            # pour preserver exactement le resultat flottant (Phase P6 :
            # identite stricte verifiee sur donnees reelles, alors qu'une
            # reduction np.sum() introduit un ecart de l'ordre de l'ULP du
            # a un ordre de sommation different).
            tau = np.ones(n, dtype=float)
            tau[mask_00] = 1.0 - lam_arr[mask_00] * mu_arr[mask_00] * rho
            tau[mask_10] = 1.0 + mu_arr[mask_10] * rho
            tau[mask_01] = 1.0 + lam_arr[mask_01] * rho
            tau[mask_11] = 1.0 - rho
            log_terms = np.log(np.maximum(tau, _LOG_TAU_FLOOR))
            total = 0.0
            for i in range(n):
                total += log_terms[i]
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
