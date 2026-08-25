"""Simulation Monte Carlo de trajectoires de bankroll et comparaison
Flat Betting vs Kelly fractionnaire.

Portee et limites (a lire avant toute interpretation des resultats) :
ce module simule le comportement d'une STRATEGIE DE MISE (comment la
mise varie avec le solde et la cote) etant donne un flux hypothetique de
paris caracterises par une probabilite de gain VRAIE et une cote
(``BetScenario``). Il isole donc le risque de gestion de bankroll
(variance, drawdown, probabilite de ruine) de la question, deja traitee
separement (Football Model + Value Engine), de savoir si le modele
detecte un edge reel sur le marche.

Consequence directe : la comparaison Flat vs Kelly produite ici est
THEORIQUE, sur un scenario hypothetique choisi par l'appelant - elle ne
doit JAMAIS etre presentee comme une preuve de performance reelle, y
compris quand ``BetScenario.true_prob`` est derive de donnees
synthetiques du projet.

Contrairement a ``kelly_stake`` (qui plafonne structurellement a
Half-Kelly et exige un quality gate leve), ce module autorise n'importe
quel multiplicateur, y compris Full Kelly (1.0) : c'est precisement ce
qui permet de MONTRER par la simulation pourquoi Full Kelly est exclu de
la production (volatilite/risque de ruine bien plus eleves - voir
docs/research_framework.md, section F2).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from sys_foot_quant.risk_engine.flat import flat_stake
from sys_foot_quant.risk_engine.kelly import kelly_fraction

StakeFn = Callable[[float, "BetScenario"], float]


@dataclass(frozen=True)
class BetScenario:
    """Un pari hypothetique : probabilite de gain VRAIE (utilisee pour
    tirer l'issue simulee) et cote proposee."""

    true_prob: float
    odds: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.true_prob <= 1.0):
            raise ValueError(f"true_prob doit etre dans [0, 1] (recu {self.true_prob}).")
        if self.odds <= 1.0:
            raise ValueError(f"odds doit etre > 1.0 (recu {self.odds}).")


def _generate_outcomes(scenarios: Sequence[BetScenario], n_simulations: int, seed: int) -> np.ndarray:
    """Matrice booleenne (n_simulations x n_bets) des issues tirees selon
    les ``true_prob`` de chaque scenario - generee UNE FOIS pour permettre
    une comparaison appariee entre strategies (memes tirages, mises
    differentes)."""
    if n_simulations <= 0:
        raise ValueError(f"n_simulations doit etre strictement positif (recu {n_simulations}).")
    if len(scenarios) == 0:
        raise ValueError("scenarios ne peut pas etre vide.")
    rng = np.random.default_rng(seed)
    probs = np.array([s.true_prob for s in scenarios])
    draws = rng.random((n_simulations, len(scenarios)))
    return draws < probs[None, :]


def simulate_bankroll_paths(
    initial_bankroll: float,
    scenarios: Sequence[BetScenario],
    stake_fn: StakeFn,
    outcomes: np.ndarray,
) -> np.ndarray:
    """Rejoue ``scenarios`` sur les issues pre-tirees ``outcomes``
    (shape (n_simulations, len(scenarios))), en appliquant ``stake_fn`` a
    chaque pas. Retourne les trajectoires de bankroll, shape
    (n_simulations, len(scenarios) + 1).

    La mise brute renvoyee par ``stake_fn`` est toujours ecretee a
    ``[0, solde_courant]`` : aucune strategie ne peut faire passer le
    solde sous zero ni miser plus que ce qui est disponible.
    """
    if initial_bankroll <= 0:
        raise ValueError(f"initial_bankroll doit etre strictement positif (recu {initial_bankroll}).")
    n_simulations, n_bets = outcomes.shape
    if n_bets != len(scenarios):
        raise ValueError("outcomes.shape[1] doit correspondre a len(scenarios).")

    paths = np.empty((n_simulations, n_bets + 1), dtype=float)
    paths[:, 0] = initial_bankroll
    for i in range(n_simulations):
        balance = initial_bankroll
        for j, scenario in enumerate(scenarios):
            raw_stake = stake_fn(balance, scenario)
            stake = min(max(raw_stake, 0.0), balance)
            won = bool(outcomes[i, j])
            pnl = stake * (scenario.odds - 1.0) if won else -stake
            balance = balance + pnl
            paths[i, j + 1] = balance
    return paths


def flat_stake_fn(initial_bankroll: float, fraction: float) -> StakeFn:
    """Strategie Flat Betting : mise constante = fraction de la bankroll
    INITIALE, independante du solde courant."""
    fixed = flat_stake(initial_bankroll, fraction)

    def _fn(balance: float, scenario: BetScenario) -> float:
        return fixed

    return _fn


def kelly_stake_fn(kelly_multiplier: float) -> StakeFn:
    """Strategie Kelly fractionnaire THEORIQUE (pas de quality gate ici -
    voir avertissement de portee en tete de module). ``kelly_multiplier``
    n'est pas plafonne : 1.0 = Full Kelly, utilisable pour illustrer son
    risque par comparaison."""
    if kelly_multiplier <= 0.0:
        raise ValueError(f"kelly_multiplier doit etre strictement positif (recu {kelly_multiplier}).")

    def _fn(balance: float, scenario: BetScenario) -> float:
        f = max(kelly_fraction(scenario.true_prob, scenario.odds), 0.0)
        return balance * f * kelly_multiplier

    return _fn


@dataclass(frozen=True)
class MonteCarloSummary:
    strategy_name: str
    n_simulations: int
    median_final_balance: float
    mean_final_balance: float
    prob_ruin: float
    median_max_drawdown_pct: float
    volatility_pct: float  # ecart-type (inter-simulations) du rendement total


def summarize_paths(paths: np.ndarray, strategy_name: str, ruin_threshold_fraction: float = 0.1) -> MonteCarloSummary:
    """Resume descriptif d'un ensemble de trajectoires simulees.
    ``ruin_threshold_fraction`` definit le seuil de "ruine" comme une
    fraction de la bankroll initiale (ex: 0.1 = solde final < 10% du
    depart)."""
    if paths.shape[0] == 0:
        raise ValueError("paths ne peut pas etre vide.")
    initial = float(paths[0, 0])
    finals = paths[:, -1]
    total_returns_pct = (finals / initial - 1.0) * 100.0

    running_max = np.maximum.accumulate(paths, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        drawdowns = np.where(running_max > 0, paths / np.where(running_max > 0, running_max, 1.0) - 1.0, 0.0)
    max_dd_per_sim_pct = drawdowns.min(axis=1) * 100.0

    ruin_level = initial * ruin_threshold_fraction
    prob_ruin = float(np.mean(finals < ruin_level))

    return MonteCarloSummary(
        strategy_name=strategy_name,
        n_simulations=int(paths.shape[0]),
        median_final_balance=float(np.median(finals)),
        mean_final_balance=float(np.mean(finals)),
        prob_ruin=prob_ruin,
        median_max_drawdown_pct=float(np.median(max_dd_per_sim_pct)),
        volatility_pct=float(np.std(total_returns_pct, ddof=0)),
    )


def compare_flat_vs_kelly(
    initial_bankroll: float,
    scenarios: Sequence[BetScenario],
    flat_fraction: float,
    kelly_multiplier: float,
    n_simulations: int,
    seed: int,
    ruin_threshold_fraction: float = 0.1,
) -> dict[str, MonteCarloSummary]:
    """Compare Flat Betting et Kelly fractionnaire sur le MEME jeu de
    tirages d'issues (comparaison appariee, seed partagee) - seule la
    strategie de mise differe entre les deux trajectoires."""
    outcomes = _generate_outcomes(scenarios, n_simulations, seed)

    flat_paths = simulate_bankroll_paths(
        initial_bankroll, scenarios, flat_stake_fn(initial_bankroll, flat_fraction), outcomes
    )
    kelly_paths = simulate_bankroll_paths(
        initial_bankroll, scenarios, kelly_stake_fn(kelly_multiplier), outcomes
    )

    return {
        "flat": summarize_paths(flat_paths, "flat", ruin_threshold_fraction),
        "kelly": summarize_paths(kelly_paths, "kelly", ruin_threshold_fraction),
    }
