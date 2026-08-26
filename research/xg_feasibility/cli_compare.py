"""CLI : compare deux extractions Understat datees et rapporte le risque
de revision mesure (protocole B3, priorite 2).

Usage :
    uv run python -m research.xg_feasibility.cli_compare \\
        --first research/xg_feasibility/runs/extraction_1.json \\
        --second research/xg_feasibility/runs/extraction_2.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from research.xg_feasibility.compare import FieldDiffStats, compare_extractions  # noqa: E402
from research.xg_feasibility.storage import load_extraction  # noqa: E402

app = typer.Typer(add_completion=False)


def _print_field_stats(label: str, stats: FieldDiffStats) -> None:
    typer.echo(f"  {label} :")
    typer.echo(f"    matchs communs           : {stats.n_common}")
    typer.echo(
        f"    matchs modifies (>eps)   : {stats.n_changed} "
        f"({stats.proportion_changed:.1%})"
    )
    typer.echo(f"    ecart absolu moyen       : {stats.mean_abs_diff:.4f}")
    typer.echo(f"    ecart absolu median (p50): {stats.p50_abs_diff:.4f}")
    typer.echo(f"    ecart absolu p90         : {stats.p90_abs_diff:.4f}")
    typer.echo(f"    ecart absolu p99         : {stats.p99_abs_diff:.4f}")
    typer.echo(f"    ecart absolu max         : {stats.max_abs_diff:.4f}")


@app.command()
def main(
    first: Path = typer.Option(..., help="Premiere extraction (la plus ancienne)."),
    second: Path = typer.Option(..., help="Deuxieme extraction (plus recente, memes matchs)."),
) -> None:
    extraction_first = load_extraction(first)
    extraction_second = load_extraction(second)

    typer.echo(f"Premiere extraction  : collectee le {extraction_first.collected_at.isoformat()}")
    typer.echo(f"Deuxieme extraction  : collectee le {extraction_second.collected_at.isoformat()}")

    report = compare_extractions(extraction_first, extraction_second)

    typer.echo(f"\nMatchs presents uniquement dans la 1ere extraction : {report.n_only_in_first}")
    typer.echo(f"Matchs presents uniquement dans la 2eme extraction : {report.n_only_in_second}")
    typer.echo("\n=== Resultat de la mesure de revision (donnees reelles, pas une hypothese) ===")
    _print_field_stats("xG domicile", report.home_xg)
    _print_field_stats("xG exterieur", report.away_xg)


if __name__ == "__main__":
    app()
