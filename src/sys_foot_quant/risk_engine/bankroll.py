"""Bankroll et historique des mises - fondation du Risk Engine.

Regle du cahier des charges (etape 4) : le systeme DOIT commencer et
rester en Flat Betting tant que les quality gates de Kelly fractionnaire
(voir risk_engine.kelly) ne sont pas explicitement leves - jamais avant
(voir risk_engine/__init__.py).

Garantie anti-look-ahead de ce module : ``BankrollHistory`` refuse tout
reglement dont le timestamp precede le dernier reglement enregistre - le
solde disponible pour dimensionner une mise ne peut donc jamais, par
construction, inclure le resultat d'une mise future.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class BetRecord:
    timestamp: datetime
    match_id: int
    selection: str
    stake: float
    odds: float
    won: bool
    pnl: float
    balance_before: float
    balance_after: float


class BankrollHistory:
    """Historique sequentiel d'une bankroll.

    Chaque mise est reglee dans l'ordre chronologique fourni par
    l'appelant - aucun reordonnancement interne. Une mise a decouvert
    (stake > solde disponible) est refusee : le Risk Engine ne pretend
    jamais a un effet de levier implicite.
    """

    def __init__(self, initial_balance: float) -> None:
        if initial_balance <= 0:
            raise ValueError(
                f"initial_balance doit etre strictement positif (recu {initial_balance})."
            )
        self.initial_balance = initial_balance
        self._balance = initial_balance
        self.records: list[BetRecord] = []

    @property
    def current_balance(self) -> float:
        return self._balance

    def settle_bet(
        self,
        timestamp: datetime,
        match_id: int,
        selection: str,
        stake: float,
        odds: float,
        won: bool,
    ) -> BetRecord:
        if stake <= 0:
            raise ValueError(f"stake doit etre strictement positif (recu {stake}).")
        if odds <= 1.0:
            raise ValueError(f"odds doit etre > 1.0 (recu {odds}).")
        if stake > self._balance:
            raise ValueError(
                f"Mise ({stake:.2f}) superieure au solde disponible "
                f"({self._balance:.2f}) - aucune mise a decouvert n'est autorisee."
            )
        if self.records and timestamp < self.records[-1].timestamp:
            raise ValueError(
                "Les mises doivent etre reglees dans l'ordre chronologique "
                f"strict ; {timestamp} est anterieur au dernier reglement "
                f"({self.records[-1].timestamp})."
            )

        balance_before = self._balance
        pnl = stake * (odds - 1.0) if won else -stake
        balance_after = balance_before + pnl

        record = BetRecord(
            timestamp=timestamp,
            match_id=match_id,
            selection=selection,
            stake=stake,
            odds=odds,
            won=won,
            pnl=pnl,
            balance_before=balance_before,
            balance_after=balance_after,
        )
        self.records.append(record)
        self._balance = balance_after
        return record

    def balance_curve(self) -> pd.DataFrame:
        """Evolution du solde, point de depart (step 0, avant toute mise) inclus."""
        rows = [{"step": 0, "timestamp": None, "balance": self.initial_balance}]
        for i, r in enumerate(self.records, start=1):
            rows.append({"step": i, "timestamp": r.timestamp, "balance": r.balance_after})
        return pd.DataFrame(rows)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(r) for r in self.records])
