"""CLI minimal, POST-MATCH UNIQUEMENT : ajoute le score final d'un match
deja enregistre dans le journal Shadow Mode
(``scripts/predict_match.py --record-shadow``). N'ajoute QUE des champs de
settlement (nouvelle ligne ``record_type="settlement"``, voir
``shadow_mode.journal``, INCHANGE ici) - ne modifie JAMAIS un champ
pre-match existant, ne reentraine et ne recalibre jamais rien.

Usage:
    uv run python scripts/settle_shadow.py \\
        --prediction-id 1a2b3c4d5e6f7890 --home-goals 2 --away-goals 1
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.shadow_mode.journal import (  # noqa: E402
    DEFAULT_JOURNAL_PATH,
    ShadowModeError,
    settle_prediction,
)

app = typer.Typer(add_completion=False)


@app.command()
def main(
    prediction_id: str = typer.Option(..., "--prediction-id", help="Identifiant retourne par predict_match.py --record-shadow."),
    home_goals: int = typer.Option(..., "--home-goals", help="Buts marques par l'equipe a domicile (score final)."),
    away_goals: int = typer.Option(..., "--away-goals", help="Buts marques par l'equipe a l'exterieur (score final)."),
    journal_path: Path = typer.Option(DEFAULT_JOURNAL_PATH, "--journal-path", help="Chemin du journal Shadow Mode."),
) -> None:
    if home_goals < 0 or away_goals < 0:
        typer.echo("ERREUR : --home-goals/--away-goals doivent etre >= 0.", err=True)
        raise typer.Exit(code=1)

    try:
        settled = settle_prediction(prediction_id, home_goals, away_goals, journal_path=journal_path)
    except ShadowModeError as exc:
        typer.echo(f"ERREUR : {exc}", err=True)
        raise typer.Exit(code=1) from None

    s = settled["settlement"]
    typer.echo(
        f"Regle : {settled['prediction_id']} - {settled['home_team']} {home_goals}-{away_goals} {settled['away_team']}"
    )
    typer.echo(f"Decision pre-match (jamais modifiee) : {settled['decision']}")
    typer.echo(f"Total buts reel : {s['total_goals_actual']} -> marche O/U 2.5 : {s['market_result_over_2_5']}")
    if s["pnl_theoretical"] is not None:
        typer.echo(f"P&L theorique (flat 1 unite) : {s['pnl_theoretical']:+.4f}")
    else:
        typer.echo("P&L theorique : n/a (decision pre-match = NO_BET, aucun pari a evaluer).")


if __name__ == "__main__":
    app()
