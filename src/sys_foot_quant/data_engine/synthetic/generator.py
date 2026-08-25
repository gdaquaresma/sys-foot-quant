"""Generateur de donnees synthetiques deterministe.

Aucune source de donnees reelle n'est encore configuree pour ce projet.
Ce generateur produit un jeu de matchs/resultats/cotes purement
synthetique, mais avec une structure temporelle realiste :

- une fixture (``Match``) est "connue" (``knowledge_time``) bien avant le
  coup d'envoi (publication du calendrier) ;
- un resultat (``MatchResult``) n'est "connu" qu'apres le coup d'envoi
  (delai de confirmation) ;
- une cote (``OddsSnapshot``) n'est connue qu'a l'instant ou elle est
  observee, generalement a plusieurs echeances avant le coup d'envoi.

Cette asymetrie structurelle du ``knowledge_time`` est precisement ce que
les tests anti-look-ahead (``tests/leakage``) verifient via le
Repository : interroger le systeme avant le coup d'envoi ne doit jamais
exposer un resultat.

Determinisme : pour un ``seed`` donne, la sortie est entierement
reproductible (meme table logique), independamment de l'environnement
d'execution. Voir docs/decisions/0004-reproductibilite-deterministe.md
pour la distinction avec une reproductibilite "bit-a-bit".

Force d'equipe et derive temporelle (etape 2, correction) : chaque equipe
a une force d'attaque/defense de base (log-normale, comme a l'etape 2
initiale), et optionnellement un TAUX DE DERIVE propre (log-lineaire dans
le temps). Avec un taux de derive nul (defaut), le comportement est
strictement identique a l'etape 2 initiale (force constante). Avec un
taux non nul, la force "effective" d'une equipe au jour ``d`` depuis le
debut du dataset est ``force_base * exp(taux_derive * d)`` - une derive
connue, deterministe et reproductible pour un seed donne, precisement
pour tester si une ponderation temporelle (A1) capture reellement un
signal de forme evolutive quand ce signal existe (voir
docs/research_framework.md et le rapport de correction de l'etape 2).

Marche synthetique : les cotes sont desormais generees a partir des
VRAIES probabilites d'issue du match (calculees a partir des memes lambda
utilises pour generer les buts), perturbees par un bruit de Dirichlet
controle (marche "informe mais imparfait"), puis une marge (overround)
connue est appliquee. C'est la correction du defaut de l'etape 2 initiale
ou les cotes etaient generees independamment de la force des equipes.

Correlation basse-score (hypothese B1, Dixon-Coles) : ``config.dixon_coles_rho``
(defaut 0.0) controle une correlation controlee entre les buts domicile et
exterieur sur les quatre cellules de score bas (0-0, 1-0, 0-1, 1-1), via le
facteur correctif tau(x,y;rho) de Dixon & Coles (1997). A 0.0, le
comportement est RIGOUREUSEMENT IDENTIQUE aux etapes 1-5 (deux tirages
``rng.poisson()`` independants) - aucune nouvelle branche de code n'est
empruntee. Voir docs/decisions/0005-protocole-generateur-dixon-coles.md
pour le protocole complet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from scipy.stats import poisson as scipy_poisson

from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.common.time_utils import to_utc
from sys_foot_quant.data_engine.schemas.entities import (
    Match,
    MatchResult,
    OddsSnapshot,
    Team,
)

_SELECTIONS = ("home", "draw", "away")

_BASE_HOME_LAMBDA = 1.35
_BASE_AWAY_LAMBDA = 1.10

# Troncature pour le calcul des vraies probabilites d'issue (utilisees
# uniquement pour generer le marche synthetique, PAS pour generer les
# buts eux-memes qui restent tires directement d'un Poisson exact).
# Duplique volontairement le calcul de football_model.scoring plutot que
# d'importer ce module depuis data_engine : le Data Engine ne doit pas
# dependre du Football Model (respect du sens de dependance de
# l'architecture, voir docs/architecture.md). Le calcul est trivial
# (produit de deux Poisson independants) et teste separement des deux
# cotes.
_TRUE_PROB_MAX_GOALS = 15

# --- Dixon-Coles (hypothese B1) ----------------------------------------
#
# Correction de correlation basse-score (Dixon & Coles, 1997) : les lois
# MARGINALES de buts restent Poisson(lambda)/Poisson(mu) - seule la loi
# JOINTE est reponderee par tau(x,y;rho) sur les quatre cellules 0-0,
# 1-0, 0-1, 1-1 (tau=1 partout ailleurs). Voir
# docs/decisions/0005-protocole-generateur-dixon-coles.md pour le
# protocole complet et le choix de rho.
#
# Ces fonctions sont volontairement dupliquees plutot qu'importees de
# football_model.dixon_coles : le Data Engine ne doit pas dependre du
# Football Model (meme principe deja applique a
# ``_true_outcome_probabilities`` ci-dessus, voir son commentaire).
_DIXON_COLES_MAX_GOALS = 15
_DIXON_COLES_RHO_EPS = 1e-9


def _dixon_coles_tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Facteur correctif tau(x,y), defini uniquement sur les quatre
    cellules bas-score - vaut 1 ailleurs (aucune correction)."""
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def _dixon_coles_rho_bounds(lam: float, mu: float) -> tuple[float, float]:
    """Intervalle de rho garantissant tau(x,y) >= 0 sur les quatre
    cellules bas-score pour ce couple (lam, mu) precis."""
    lo = max(-1.0 / lam, -1.0 / mu)
    hi = min(1.0, 1.0 / (lam * mu))
    return lo, hi


def _validate_dixon_coles_rho(rho: float, lam: float, mu: float) -> None:
    """Verifie explicitement la validite de ``rho`` pour ce match precis.
    Leve une erreur plutot que d'ecreter silencieusement (voir ADR 0005,
    point 3) : un rho hors bornes sur un cas extreme doit etre traite en
    amont (rho plus modere, ou bornes de derive/force plus resserrees
    pour ce scenario), jamais masque au vol dans la boucle de generation.
    """
    lo, hi = _dixon_coles_rho_bounds(lam, mu)
    if not (lo <= rho <= hi):
        raise ValueError(
            f"dixon_coles_rho={rho} hors de l'intervalle de validite "
            f"[{lo:.6f}, {hi:.6f}] pour lam={lam:.6f}, mu={mu:.6f} "
            f"(tau(x,y) deviendrait negatif sur au moins une cellule "
            f"bas-score). Choisir un rho plus modere ou resserrer les "
            f"bornes de derive/force du scenario - aucun ecretage "
            f"silencieux n'est applique."
        )


def _dixon_coles_score_matrix(
    lam: float, mu: float, rho: float, max_goals: int = _DIXON_COLES_MAX_GOALS
) -> np.ndarray:
    """Matrice de score jointe P(X=x, Y=y) corrigee par tau(x,y;rho),
    RENORMALISEE explicitement pour rester une distribution de probabilite
    exacte (somme = 1 a la precision flottante pres) - voir ADR 0005,
    point 2, pour la justification de cette renormalisation (absente de
    l'article academique original, mais requise ici puisque ce generateur
    doit produire une loi de probabilite exacte, pas une approximation)."""
    goals = np.arange(0, max_goals + 1)
    p_home = scipy_poisson.pmf(goals, lam)
    p_away = scipy_poisson.pmf(goals, mu)
    matrix = np.outer(p_home, p_away)
    matrix = matrix / matrix.sum()  # normalise la base independante avant tau

    corrected = matrix.copy()
    for x, y in ((0, 0), (1, 0), (0, 1), (1, 1)):
        corrected[x, y] = matrix[x, y] * _dixon_coles_tau(x, y, lam, mu, rho)

    total = corrected.sum()
    if total <= 0:
        raise ValueError(
            f"Masse totale non positive apres correction tau (rho={rho}, "
            f"lam={lam}, mu={mu}) - devrait etre impossible si "
            f"_validate_dixon_coles_rho a ete appele avant."
        )
    return corrected / total


def _dixon_coles_outcome_probabilities(
    lam: float, mu: float, rho: float
) -> tuple[float, float, float]:
    """(P(domicile), P(nul), P(exterieur)) sous la correction Dixon-Coles,
    pour le marche synthetique "pleinement informe" (Option A validee -
    voir ADR 0005, point 4)."""
    matrix = _dixon_coles_score_matrix(lam, mu, rho, max_goals=_TRUE_PROB_MAX_GOALS)
    n = matrix.shape[0]
    rows, cols = np.indices((n, n))
    home_win = float(matrix[rows > cols].sum())
    draw = float(matrix[rows == cols].sum())
    away_win = float(matrix[rows < cols].sum())
    total = home_win + draw + away_win
    return (home_win / total, draw / total, away_win / total)


@dataclass(frozen=True)
class SyntheticDataset:
    teams: pd.DataFrame
    matches: pd.DataFrame
    match_results: pd.DataFrame
    odds_snapshots: pd.DataFrame
    # Force reellement utilisee pour generer les resultats (attack/defense
    # multiplicatifs par equipe a J+0, base 1.0 = force moyenne, plus le
    # taux de derive log-lineaire par jour). N'est PAS une table de faits
    # point-in-time et n'est jamais ecrite en Parquet : c'est un artefact
    # de validation, utilise uniquement pour verifier qu'un estimateur
    # retrouve un signal connu (voir tests/integration). Un modele de
    # prediction ne doit jamais y avoir acces.
    true_team_strength: pd.DataFrame


def _true_outcome_probabilities(lam: float, mu: float) -> tuple[float, float, float]:
    """(P(domicile), P(nul), P(exterieur)) exactes pour deux Poisson
    independants de parametres lam/mu, renormalisees apres troncature."""
    goals = np.arange(0, _TRUE_PROB_MAX_GOALS + 1)
    p_home_goals = scipy_poisson.pmf(goals, lam)
    p_away_goals = scipy_poisson.pmf(goals, mu)
    matrix = np.outer(p_home_goals, p_away_goals)
    n = matrix.shape[0]
    rows, cols = np.indices((n, n))
    home_win = float(matrix[rows > cols].sum())
    draw = float(matrix[rows == cols].sum())
    away_win = float(matrix[rows < cols].sum())
    total = home_win + draw + away_win
    return (home_win / total, draw / total, away_win / total)


def generate_synthetic_dataset(config: SyntheticDataConfig) -> SyntheticDataset:
    rng = np.random.default_rng(config.seed)
    start = to_utc(datetime.fromisoformat(config.start_date))

    teams = [
        Team(team_id=i, name=f"Team_{i:02d}") for i in range(config.n_teams)
    ]

    # Force d'attaque/defense simulee par equipe (echelle log-normale,
    # centree sur 1.0) a J+0. std=0 => toutes les equipes a 1.0.
    team_attack = np.exp(rng.normal(0.0, config.team_attack_log_std, size=config.n_teams))
    team_defense = np.exp(rng.normal(0.0, config.team_defense_log_std, size=config.n_teams))
    # Taux de derive log-lineaire par equipe (par jour). 0 => force
    # constante dans le temps (comportement etape 2 initial, inchange).
    attack_drift_rate = rng.normal(
        0.0, config.team_attack_drift_log_std_per_day, size=config.n_teams
    )
    defense_drift_rate = rng.normal(
        0.0, config.team_defense_drift_log_std_per_day, size=config.n_teams
    )
    true_team_strength = pd.DataFrame(
        {
            "team_id": list(range(config.n_teams)),
            "true_attack": team_attack,
            "true_defense": team_defense,
            "true_attack_drift_rate": attack_drift_rate,
            "true_defense_drift_rate": defense_drift_rate,
        }
    )

    matches: list[Match] = []
    results: list[MatchResult] = []
    odds: list[OddsSnapshot] = []

    for i in range(config.n_matches):
        home_id, away_id = rng.choice(config.n_teams, size=2, replace=False)
        home_id, away_id = int(home_id), int(away_id)
        kickoff = start + timedelta(days=config.days_between_matches * i)
        fixture_known = kickoff - timedelta(
            days=config.fixture_announcement_days_before
        )

        match = Match(
            match_id=i + 1,
            home_team_id=home_id,
            away_team_id=away_id,
            kickoff_time=kickoff,
            knowledge_time=fixture_known,
        )
        matches.append(match)

        days_since_start = config.days_between_matches * i
        attack_h_eff = team_attack[home_id] * np.exp(attack_drift_rate[home_id] * days_since_start)
        defense_h_eff = team_defense[home_id] * np.exp(
            defense_drift_rate[home_id] * days_since_start
        )
        attack_a_eff = team_attack[away_id] * np.exp(attack_drift_rate[away_id] * days_since_start)
        defense_a_eff = team_defense[away_id] * np.exp(
            defense_drift_rate[away_id] * days_since_start
        )

        lam_home = _BASE_HOME_LAMBDA * attack_h_eff * defense_a_eff
        lam_away = _BASE_AWAY_LAMBDA * attack_a_eff * defense_h_eff

        if config.dixon_coles_rho != 0.0:
            # Hypothese B1 (Dixon-Coles) : tirage JOINT via la matrice de
            # score corrigee par tau(x,y;rho), remplace les deux tirages
            # rng.poisson() independants. N'est JAMAIS emprunte quand
            # dixon_coles_rho=0.0 (defaut) - le chemin ci-dessous (branche
            # ``else``) reste rigoureusement identique, ligne pour ligne,
            # au comportement valide aux etapes 1-5.
            _validate_dixon_coles_rho(config.dixon_coles_rho, lam_home, lam_away)
            score_probs = _dixon_coles_score_matrix(lam_home, lam_away, config.dixon_coles_rho)
            flat_index = rng.choice(score_probs.size, p=score_probs.ravel())
            home_goals_idx, away_goals_idx = np.unravel_index(flat_index, score_probs.shape)
            home_goals, away_goals = int(home_goals_idx), int(away_goals_idx)
        else:
            home_goals = int(rng.poisson(lam=lam_home))
            away_goals = int(rng.poisson(lam=lam_away))
        confirmation_delay = config.result_confirmation_delay_hours + float(
            rng.uniform(0.0, 0.5)
        )
        results.append(
            MatchResult(
                match_id=match.match_id,
                home_goals=home_goals,
                away_goals=away_goals,
                knowledge_time=kickoff + timedelta(hours=confirmation_delay),
            )
        )

        # Marche synthetique "informe mais imparfait" : centre sur les
        # VRAIES probabilites d'issue du match (calculees a partir des
        # memes lambda que les buts), perturbe par un bruit de Dirichlet
        # controle, puis une marge connue est appliquee. Voir
        # market_engine.overround.remove_overround_proportional pour la
        # verification mathematique que cette marge est bien reconstructible.
        # Option A (validee, ADR 0005 point 4) : quand une correlation
        # basse-score est simulee, le marche synthetique "vrai" doit lui
        # aussi integrer tau(x,y;rho) - sinon meme le marche "informe"
        # laisserait un edge structurel artificiel sur les scores bas,
        # cree par une INCOHERENCE generateur/marche plutot que par le
        # modele teste. A rho=0.0, chemin inchange (identique aux etapes
        # 1-5).
        if config.dixon_coles_rho != 0.0:
            true_probs = np.array(
                _dixon_coles_outcome_probabilities(lam_home, lam_away, config.dixon_coles_rho)
            )
        else:
            true_probs = np.array(_true_outcome_probabilities(lam_home, lam_away))

        # Plancher realiste applique UNIQUEMENT a la generation du marche
        # (pas aux buts, ni a true_team_strength, ni au diagnostic de
        # Chi-Deux qui reconstruit lam_home/lam_away independamment) :
        # aucun bookmaker reel n'affiche une probabilite implicite en
        # dessous de quelques pourcents sur un marche 1X2 offert. Sans ce
        # plancher, un match tres desequilibre (derive cumulee extreme)
        # peut donner une probabilite vraie quasi nulle sur une issue, ce
        # qui degenere le bruit de Dirichlet (alpha quasi nul) en cotes
        # irrealistes (jusqu'a plusieurs centaines de milliers). Trouve
        # lors de la validation de l'etape 3 (Value Engine, ou l'EV brute
        # amplifie ce probleme) - invisible sur les metriques de
        # probabilite bornees [0,1] de l'etape 2 (Brier/log loss).
        true_probs_for_market = np.clip(true_probs, 0.01, None)
        true_probs_for_market = true_probs_for_market / true_probs_for_market.sum()

        for offset_hours in config.odds_snapshot_offsets_hours:
            snapshot_time = kickoff - timedelta(hours=offset_hours)
            noisy_probs = rng.dirichlet(alpha=true_probs_for_market * config.market_noise_concentration)
            implied_with_margin = noisy_probs * (1.0 + config.market_margin)
            # Garde-fou final (defense en profondeur) : meme avec le
            # plancher ci-dessus, le bruit de Dirichlet peut placer une
            # probabilite tres proche de 1 (ou tres proche de 0), ce qui
            # rendrait la cote decimale invalide ou irrealiste. On ecrete
            # directement la probabilite impliquee finale (sans
            # renormaliser - renormaliser apres ecretage reintroduirait le
            # probleme en gonflant a nouveau la valeur ecretee). Plage
            # choisie pour rester dans des cotes plausibles (~1.005 a 200).
            implied_with_margin = np.clip(implied_with_margin, 0.005, 0.995)
            for selection, prob in zip(_SELECTIONS, implied_with_margin):
                odds.append(
                    OddsSnapshot(
                        match_id=match.match_id,
                        bookmaker="synthetic_book",
                        market_type="1x2",
                        selection=selection,
                        odds_value=round(1.0 / prob, 3),
                        knowledge_time=snapshot_time,
                    )
                )

    return SyntheticDataset(
        teams=pd.DataFrame([t.model_dump() for t in teams]),
        matches=pd.DataFrame([m.model_dump() for m in matches]),
        match_results=pd.DataFrame([r.model_dump() for r in results]),
        odds_snapshots=pd.DataFrame([o.model_dump() for o in odds]),
        true_team_strength=true_team_strength,
    )
