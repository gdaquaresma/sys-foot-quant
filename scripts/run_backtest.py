"""CLI : execute le backtester chronologique minimal sur le dataset synthetique.

Aucune strategie n'est implementee ici : le callback ``on_decision`` est
un stub de diagnostic qui se contente de compter les lignes visibles a
chaque instant de decision, pour demontrer que le volume de donnees
visibles croit de facon monotone et chronologiquement correcte.

Usage:
    python scripts/generate_synthetic_data.py --config configs/backtest_stage1.yaml
    python scripts/run_backtest.py --config configs/backtest_stage1.yaml
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.engine import (  # noqa: E402
    ChronologicalBacktestEngine,
    DecisionSnapshot,
)
from sys_foot_quant.common.config import load_config  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)


def _diagnostic_stub(snapshot: DecisionSnapshot) -> dict[str, int]:
    """Stub de diagnostic : PAS une strategie de pari.

    Se contente de compter les lignes visibles par table a l'instant de
    decision, pour prouver que le backtester respecte le contrat
    point-in-time (aucun modele, aucune decision de pari ici).
    """
    return {entity: len(df) for entity, df in snapshot.visible.items()}


@app.command()
def main(
    config: Path = typer.Option(Path("configs/backtest_stage1.yaml")),
    data_dir: Path = typer.Option(Path("data/raw")),
) -> None:
    cfg = load_config(config)

    with DuckDBRepository(data_dir) as repo:
        matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
        decision_times = [
            kt - timedelta(hours=cfg.decision_offset_hours_before_kickoff)
            for kt in matches["kickoff_time"]
        ]

        engine = ChronologicalBacktestEngine(
            repository=repo, entities=("matches", "match_results", "odds_snapshots")
        )
        trace = engine.run(decision_times, on_decision=_diagnostic_stub)

    logger.info(f"Backtest execute sur {len(trace)} points de decision.")
    first, last = trace[0], trace[-1]
    typer.echo(f"Premier point de decision : {decision_times[0]} -> {first}")
    typer.echo(f"Dernier point de decision  : {decision_times[-1]} -> {last}")
    typer.echo(
        "Note : au dernier point de decision (T-"
        f"{cfg.decision_offset_hours_before_kickoff}h avant le dernier coup d'envoi), "
        "le nombre de resultats visibles doit rester 0 pour CE match "
        "(les resultats des matchs precedents, eux, sont deja connus)."
    )


if __name__ == "__main__":
    app()
