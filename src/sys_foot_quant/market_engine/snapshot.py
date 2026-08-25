"""Lecture de snapshots de marche point-in-time.

Extrait de ``backtesting_engine.walk_forward`` (etape 2) : lire le dernier
snapshot de cotes connu a un instant donne est une responsabilite du
Market Engine, pas de l'orchestrateur de backtest (respect du sens de
dependance de l'architecture, voir docs/architecture.md). Refactor
purement additif - ``walk_forward.market_benchmark_probs`` appelle
desormais cette fonction ; son comportement externe est inchange et
verifie par la suite de tests de l'etape 2.
"""

from __future__ import annotations

from datetime import datetime

from sys_foot_quant.data_engine.storage.repository import DuckDBRepository


def latest_odds_as_of(
    repository: DuckDBRepository, match_id: int, as_of: datetime
) -> dict[str, float] | None:
    """Cotes brutes (marge incluse) du dernier snapshot connu a ``as_of``
    pour ``match_id``. None si aucun snapshot n'est encore visible a cet
    instant (marche pas encore ouvert)."""
    snapshots = repository.get_as_of("odds_snapshots", as_of)
    match_snapshots = snapshots[snapshots["match_id"] == match_id]
    if match_snapshots.empty:
        return None
    latest_time = match_snapshots["knowledge_time"].max()
    latest = match_snapshots[match_snapshots["knowledge_time"] == latest_time]
    return dict(zip(latest["selection"], latest["odds_value"]))
