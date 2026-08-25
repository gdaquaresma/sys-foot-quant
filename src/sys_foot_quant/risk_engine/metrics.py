"""Metriques de risque calculees a partir d'une courbe de bankroll
(``BankrollHistory.balance_curve()``) : drawdown, volatilite, evolution
globale du solde.

Ces metriques sont purement DESCRIPTIVES - elles ne pilotent aucune
decision de mise (pas de "stop-loss auto", pas de recalibrage dynamique
a ce stade) : le cahier des charges de l'etape 4 demande de les
calculer/afficher, pas de les utiliser pour modifier le comportement du
systeme.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def drawdown_curve(balance_curve: pd.DataFrame) -> pd.DataFrame:
    """Ajoute une colonne ``running_max`` et ``drawdown`` (fraction, <= 0)
    a la courbe de bankroll. ``drawdown`` = ``balance / running_max - 1``."""
    if balance_curve.empty:
        raise ValueError("balance_curve ne peut pas etre vide.")
    out = balance_curve.copy()
    out["running_max"] = out["balance"].cummax()
    out["drawdown"] = out["balance"] / out["running_max"] - 1.0
    return out


def max_drawdown(balance_curve: pd.DataFrame) -> float:
    """Drawdown maximal (fraction negative ou nulle, ex: -0.23 = -23%)."""
    return float(drawdown_curve(balance_curve)["drawdown"].min())


def stepwise_returns(balance_curve: pd.DataFrame) -> np.ndarray:
    """Rendements simples entre pas consecutifs de la courbe de bankroll
    (``balance[t] / balance[t-1] - 1``). Necessite au moins deux points
    (le point initial + un pari)."""
    if len(balance_curve) < 2:
        raise ValueError("Au moins deux points (initial + un pari) sont necessaires.")
    balances = balance_curve["balance"].to_numpy(dtype=float)
    if np.any(balances[:-1] <= 0):
        raise ValueError("balance_curve contient un solde nul ou negatif avant le dernier pas.")
    return balances[1:] / balances[:-1] - 1.0


def volatility(balance_curve: pd.DataFrame) -> float:
    """Ecart-type (population, ddof=0) des rendements pas-a-pas. Mesure de
    dispersion descriptive, pas une volatilite annualisee (les paris ne
    surviennent pas a frequence reguliere)."""
    returns = stepwise_returns(balance_curve)
    return float(np.std(returns, ddof=0))


@dataclass(frozen=True)
class RiskMetrics:
    initial_balance: float
    final_balance: float
    total_return_pct: float
    max_drawdown_pct: float
    volatility_pct: float
    n_bets: int
    win_rate: float | None


def compute_risk_metrics(balance_curve: pd.DataFrame, records: pd.DataFrame | None = None) -> RiskMetrics:
    """Synthese des metriques de risque a partir d'une courbe de bankroll
    (et, optionnellement, du detail des paris pour le taux de reussite)."""
    if balance_curve.empty:
        raise ValueError("balance_curve ne peut pas etre vide.")

    initial_balance = float(balance_curve["balance"].iloc[0])
    final_balance = float(balance_curve["balance"].iloc[-1])
    total_return_pct = (final_balance / initial_balance - 1.0) * 100.0
    max_dd_pct = max_drawdown(balance_curve) * 100.0

    n_bets = len(balance_curve) - 1
    vol_pct = volatility(balance_curve) * 100.0 if n_bets >= 1 else 0.0

    win_rate: float | None = None
    if records is not None and len(records) > 0 and "won" in records.columns:
        win_rate = float(records["won"].mean())

    return RiskMetrics(
        initial_balance=initial_balance,
        final_balance=final_balance,
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_dd_pct,
        volatility_pct=vol_pct,
        n_bets=n_bets,
        win_rate=win_rate,
    )
