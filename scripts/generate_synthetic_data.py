"""CLI : genere le dataset synthetique deterministe et l'ecrit en Parquet.

Usage:
    python scripts/generate_synthetic_data.py --config configs/backtest_stage1.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.common.config import load_config  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.storage.writer import write_dataset  # noqa: E402
from sys_foot_quant.data_engine.synthetic.generator import (  # noqa: E402
    generate_synthetic_dataset,
)

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)


@app.command()
def main(
    config: Path = typer.Option(
        Path("configs/backtest_stage1.yaml"), help="Chemin du fichier de configuration YAML."
    ),
    out_dir: Path = typer.Option(
        Path("data/raw"), help="Repertoire de sortie des fichiers Parquet."
    ),
) -> None:
    cfg = load_config(config)
    dataset = generate_synthetic_dataset(cfg.synthetic_data)
    written = write_dataset(dataset, out_dir)

    logger.info(
        f"Dataset synthetique genere (seed={cfg.synthetic_data.seed}) : "
        f"{len(dataset.teams)} equipes, {len(dataset.matches)} matchs, "
        f"{len(dataset.match_results)} resultats, "
        f"{len(dataset.odds_snapshots)} cotes."
    )
    for name, path in written.items():
        typer.echo(f"  {name:16s} -> {path}")


if __name__ == "__main__":
    app()
