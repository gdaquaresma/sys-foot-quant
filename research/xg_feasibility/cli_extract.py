"""CLI : effectue UNE extraction datee d'un echantillon fixe de matchs
Understat (protocole B3, priorite 2).

A EXECUTER SUR UNE MACHINE AVEC ACCES INTERNET REEL - cet environnement
d'execution (bac a sable) bloque l'acces a understat.com par politique
reseau ; ce script n'a donc jamais ete execute en direct depuis la
session qui l'a ecrit (voir avertissement dans understat_source.py).

Usage (deux temps, a plusieurs semaines d'intervalle, MEME echantillon) :
    uv run python -m research.xg_feasibility.cli_extract \\
        --league EPL --season 2024 --n-matches 200 --seed 20260826 \\
        --out research/xg_feasibility/runs/extraction_1.json

    # ... attendre 4-6 semaines ...

    uv run python -m research.xg_feasibility.cli_extract \\
        --league EPL --season 2024 --n-matches 200 --seed 20260826 \\
        --out research/xg_feasibility/runs/extraction_2.json

Le MEME --seed et le meme --n-matches doivent etre reutilises pour la
deuxieme extraction : ils garantissent (avec la meme liste source de
matchs deja joues) un tirage identique, condition necessaire pour que la
comparaison porte sur exactement les memes matchs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from research.xg_feasibility.sampling import select_fixed_sample  # noqa: E402
from research.xg_feasibility.storage import save_extraction  # noqa: E402
from research.xg_feasibility.understat_source import fetch_match_records  # noqa: E402

app = typer.Typer(add_completion=False)


@app.command()
def main(
    league: str = typer.Option(..., help="Identifiant Understat de la ligue, ex. EPL, La_liga."),
    season: str = typer.Option(..., help="Annee de debut de saison, ex. 2024 pour 2024/2025."),
    n_matches: int = typer.Option(200, help="Taille de l'echantillon fixe a tirer."),
    seed: int = typer.Option(..., help="Graine du tirage (fixer AVANT la 1ere extraction, reutiliser a l'identique pour la 2eme)."),
    out: Path = typer.Option(..., help="Fichier JSON de sortie (horodate automatiquement en interne)."),
) -> None:
    typer.echo(f"Recuperation de {league}/{season} depuis understat.com...")
    all_records = fetch_match_records(league, season)
    typer.echo(f"{len(all_records)} matchs deja joues trouves pour cette ligue/saison.")

    sample = select_fixed_sample(all_records, n=n_matches, seed=seed)
    typer.echo(f"Echantillon fixe : {len(sample)} matchs (seed={seed}).")

    out.parent.mkdir(parents=True, exist_ok=True)
    save_extraction(sample, out, league=league, season=season)
    typer.echo(f"Extraction sauvegardee dans {out} (avec horodatage de collecte).")


if __name__ == "__main__":
    app()
