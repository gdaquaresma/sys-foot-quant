"""CLI : synchronise le fichier "saison courante" (ex. 2026/27) contre
Understat via ``current_season_updater.sync_current_season`` - connecteur
d'auto-alimentation, PAS un service automatique (aucun cron/scheduler ici,
etape volontairement separee).

A EXECUTER SUR UNE MACHINE AVEC ACCES INTERNET REEL - cet environnement
d'execution bloque l'acces a understat.com. ``current_season_updater.py``
cible desormais l'endpoint JSON reel ``getLeagueData`` (confirme par
capture navigateur reelle), mais ce CLI n'a jamais ete execute en
conditions reseau reelles depuis cette session - uniquement teste avec
des reponses Understat simulees (``tests/test_current_season_updater.py``).

IMPORTANT - ``--league-id`` attend le nom de ligue EXACT utilise par
l'endpoint ``getLeagueData``, ex. ``"Ligue 1"`` (AVEC ESPACE) - PAS
``"Ligue_1"`` (underscore, ancienne convention de la page HTML,
confirmee DIFFERENTE et INCOMPATIBLE avec cet endpoint).

Usage (dry-run, recommande avant toute synchronisation reelle) :
    uv run python -m research.xg_feasibility.cli_sync_current_season \\
        --competition ligue1 --league-id "Ligue 1" --season 2026 \\
        --canonical-path research/xg_feasibility/runs/ligue1_2026_datesData.json \\
        --dry-run

Usage (synchronisation reelle, ecrit le fichier canonique si sur) :
    uv run python -m research.xg_feasibility.cli_sync_current_season \\
        --competition ligue1 --league-id "Ligue 1" --season 2026 \\
        --canonical-path research/xg_feasibility/runs/ligue1_2026_datesData.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from research.xg_feasibility.current_season_updater import (  # noqa: E402
    format_report,
    sync_current_season,
)

app = typer.Typer(add_completion=False)


@app.command()
def main(
    competition: str = typer.Option(..., help="Nom interne de la competition (ex. ligue1) - pour le rapport uniquement."),
    league_id: str = typer.Option(
        ..., help='Nom de ligue exact attendu par getLeagueData (ex. "Ligue 1", AVEC espace - jamais "Ligue_1").'
    ),
    season: str = typer.Option(..., help="Annee de debut de saison Understat (ex. 2026)."),
    canonical_path: Path = typer.Option(..., help="Chemin du fichier saison courante a synchroniser."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Calcule et affiche le diff SANS rien ecrire."),
) -> None:
    report = sync_current_season(
        competition=competition,
        league_id=league_id,
        season=season,
        canonical_path=canonical_path,
        dry_run=dry_run,
    )
    typer.echo(format_report(report))
    if report.action in ("error", "refused"):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
