"""Import des cotes reelles Football-Data.co.uk, marche 1X2, bookmaker
Bet365 uniquement (etape 4, phase economique -
docs/decisions/0006-football-data-point-in-time.md).

Perimetre strictement respecte : seules les colonnes ``Date``, ``Time``,
``HomeTeam``, ``AwayTeam``, ``FTHG``, ``FTAG``, ``FTR``, ``B365H``,
``B365D``, ``B365A`` sont lues. AUCUNE colonne de cloture (suffixe ``C``,
ex. ``B365CH``), AUCUN agregat de marche (``Max``/``Avg``), AUCUN autre
bookmaker n'est touche - meme si present dans le fichier source. La liste
``_ALLOWED_COLUMNS`` ci-dessous est la SEULE surface de lecture autorisee,
verifiee par test (aucune colonne ``*C`` ne peut y figurer).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

SOURCE = "football_data"
BOOKMAKER = "B365"
MARKET = "1x2"

_ALLOWED_COLUMNS = (
    "Date",
    "Time",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
    "B365H",
    "B365D",
    "B365A",
)


@dataclass(frozen=True)
class FootballDataMatchRecord:
    league: str
    season: str
    source: str
    bookmaker: str
    market: str
    date_str: str
    time_str: str
    home_team_fd: str
    away_team_fd: str
    home_goals: int
    away_goals: int
    b365_home: float | None
    b365_draw: float | None
    b365_away: float | None

    @property
    def has_complete_odds(self) -> bool:
        return self.b365_home is not None and self.b365_draw is not None and self.b365_away is not None


def _parse_optional_float(raw: str) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    return float(raw)


def load_football_data_csv(path: Path, league: str, season: str) -> list[FootballDataMatchRecord]:
    """Lit un fichier Football-Data brut et ne retient QUE les colonnes de
    ``_ALLOWED_COLUMNS``. Leve une erreur explicite si une colonne
    attendue est absente du fichier - jamais une valeur inventee."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in _ALLOWED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: colonnes attendues absentes du fichier : {missing}.")

        records: list[FootballDataMatchRecord] = []
        for row in reader:
            records.append(
                FootballDataMatchRecord(
                    league=league,
                    season=season,
                    source=SOURCE,
                    bookmaker=BOOKMAKER,
                    market=MARKET,
                    date_str=row["Date"],
                    time_str=row["Time"],
                    home_team_fd=row["HomeTeam"],
                    away_team_fd=row["AwayTeam"],
                    home_goals=int(row["FTHG"]),
                    away_goals=int(row["FTAG"]),
                    b365_home=_parse_optional_float(row["B365H"]),
                    b365_draw=_parse_optional_float(row["B365D"]),
                    b365_away=_parse_optional_float(row["B365A"]),
                )
            )
    return records
