"""CLI : recupere la page "results" publique d'oddsportal.com pour une
competition suivie et ecrit les matchs extraits (resultats + cotes
consensus BRUTES) dans un fichier JSON local - connecteur de RECHERCHE,
PAS un chemin de production (voir ``oddsportal_results_source.py`` pour le
detail et les 5 limites documentees dans son docstring de module).

Ce CLI ne fait QUE lire oddsportal.com et ecrire un fichier JSON local -
il n'ecrit JAMAIS dans ``research/xg_feasibility/runs/*_datesData.json``
(les fichiers canoniques Understat), ni dans aucun fichier lu par
``src/sys_foot_quant``. Aucune fusion/merge avec les donnees Understat
n'est faite ici - cf. limite 1 du module (semantique des cotes home/
draw/away non confirmee) : fusionner sans verification prealable
risquerait de propager un mauvais mapping de cotes.

Usage :
    uv run python -m research.oddsportal_integration.cli_fetch_oddsportal_results \\
        --competition ligue1

    uv run python -m research.oddsportal_integration.cli_fetch_oddsportal_results \\
        --competition liga --output-path /tmp/liga_oddsportal.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from research.oddsportal_integration.oddsportal_results_source import (  # noqa: E402
    COMPETITION_RESULTS_URLS,
    OddsPortalFetchError,
    OddsPortalMatch,
    OddsPortalParsingError,
    fetch_and_parse_results,
)

app = typer.Typer(add_completion=False)

_DEFAULT_RUNS_DIR = Path(__file__).resolve().parent / "runs"


def _match_to_json_dict(match: OddsPortalMatch) -> dict:
    """``dataclasses.asdict`` ne sait pas serialiser un ``datetime`` -
    conversion ISO 8601 explicite ici, le reste des champs est deja
    JSON-serialisable tel quel (int/str/bool/None/tuple de dataclasses)."""
    raw = asdict(match)
    raw["kickoff_utc"] = match.kickoff_utc.isoformat()
    return raw


@app.command()
def main(
    competition: str = typer.Option(
        ..., help=f"Competition suivie ({', '.join(sorted(COMPETITION_RESULTS_URLS))})."
    ),
    output_path: Path = typer.Option(
        None,
        help=(
            "Chemin du fichier JSON de sortie. Par defaut : "
            "research/oddsportal_integration/runs/<competition>_results.json"
        ),
    ),
) -> None:
    if competition not in COMPETITION_RESULTS_URLS:
        typer.echo(
            f"Competition inconnue : {competition!r}. Valeurs acceptees : "
            f"{sorted(COMPETITION_RESULTS_URLS)}",
            err=True,
        )
        raise typer.Exit(code=1)

    resolved_output_path = output_path or (_DEFAULT_RUNS_DIR / f"{competition}_results.json")

    try:
        matches = fetch_and_parse_results(competition)
    except (OddsPortalFetchError, OddsPortalParsingError) as exc:
        typer.echo(f"Echec de recuperation/parsing OddsPortal pour {competition!r} : {exc}", err=True)
        raise typer.Exit(code=1) from exc

    finished = [m for m in matches if m.is_finished]
    not_finished = [m for m in matches if not m.is_finished]

    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "competition": competition,
        "source_url": COMPETITION_RESULTS_URLS[competition],
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "match_count": len(matches),
        "matches": [_match_to_json_dict(m) for m in matches],
    }
    resolved_output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    typer.echo(
        f"{len(matches)} matchs extraits pour {competition!r} "
        f"({len(finished)} termines, {len(not_finished)} pas encore) -> {resolved_output_path}"
    )


if __name__ == "__main__":
    app()
