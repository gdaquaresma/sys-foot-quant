"""Boucle de simulation chronologique minimale.

Ce moteur n'implemente ni modele ni strategie de pari : a chaque point de
decision, il construit un ``DecisionSnapshot`` (les donnees visibles a
cet instant, via le Repository) et delegue a un callback ``on_decision``
fourni par l'appelant. Pour l'etape 1, ce callback est un stub de
diagnostic (voir scripts/run_backtest.py), jamais une logique de
prediction.

Garantie structurelle : le moteur refuse d'executer une sequence de
decision times non strictement croissante, et re-verifie l'ordre a
chaque iteration (defense en profondeur vis-a-vis d'un appelant qui
muterait la sequence pendant l'iteration).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from sys_foot_quant.common.time_utils import assert_strictly_sorted, to_utc
from sys_foot_quant.data_engine.storage.repository import (
    DuckDBRepository,
    PointInTimeEntity,
)


@dataclass(frozen=True)
class DecisionSnapshot:
    """Ce qu'un consommateur du backtest peut legitimement voir a ``decision_time``."""

    decision_time: datetime
    visible: dict[str, pd.DataFrame] = field(default_factory=dict)


class ChronologicalBacktestEngine:
    def __init__(
        self,
        repository: DuckDBRepository,
        entities: Sequence[PointInTimeEntity],
    ):
        self.repository = repository
        self.entities = tuple(entities)

    def run(
        self,
        decision_times: Sequence[datetime],
        on_decision: Callable[[DecisionSnapshot], Any],
    ) -> list[Any]:
        normalized = [to_utc(t) for t in decision_times]
        assert_strictly_sorted(normalized)

        outputs: list[Any] = []
        last_seen: datetime | None = None
        for t in normalized:
            if last_seen is not None and t < last_seen:
                # Defense en profondeur : ne devrait jamais se produire
                # apres assert_strictly_sorted ci-dessus, sauf mutation
                # concurrente de l'appelant.
                raise RuntimeError(
                    f"Ordre chronologique viole pendant l'execution : {t!r} < {last_seen!r}."
                )
            visible = {entity: self.repository.get_as_of(entity, t) for entity in self.entities}
            snapshot = DecisionSnapshot(decision_time=t, visible=visible)
            outputs.append(on_decision(snapshot))
            last_seen = t
        return outputs
