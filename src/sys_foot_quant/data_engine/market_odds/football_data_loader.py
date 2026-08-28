"""Import des cotes reelles Football-Data.co.uk, marche 1X2 (Bet365, Bet&Win,
Pinnacle) ET Over/Under 2.5 (Bet365 uniquement) - etape 4, phase economique
(docs/decisions/0006-football-data-point-in-time.md) ; extension Over/Under
2.5 - E5 ; extension multi-bookmaker 1X2 (BW, PS) - E9, meme decision,
section "Extension future".

Perimetre strictement respecte : seules les colonnes ``Date``, ``Time``,
``HomeTeam``, ``AwayTeam``, ``FTHG``, ``FTAG``, ``FTR``, ``B365H/D/A``,
``BWH/D/A``, ``PSH/D/A``, ``B365>2.5``, ``B365<2.5`` sont lues. AUCUNE
colonne de cloture (suffixe ``C``, ex. ``B365CH``, ``BWCH``, ``PSCH``,
``B365C>2.5``), AUCUN agregat de marche (``Max``/``Avg``), AUCUN bookmaker
au-dela de ceux listes (notamment PAS ``BFE`` - nature d'exchange non
clarifiee, voir E9) n'est touche - meme si present dans le fichier source.
La liste ``_ALLOWED_COLUMNS`` ci-dessous est la SEULE surface de lecture
autorisee, verifiee par test (aucune colonne de cloture ne peut y figurer,
pour aucun marche). ``B365>2.5``/``B365<2.5`` et ``B365H/D/A`` sont
completes a 100% sur les six fichiers reels. ``BW``/``PS`` sont chacun
PARTIELLEMENT complets (couverture variable par saison - constate, jamais
suppose - un bookmaker absent sur un match donne est simplement absent du
snapshot multi-bookmaker, jamais invente ni impute) : aucun O/U 2.5 n'existe
pour BW/PS dans les fichiers sources (colonnes absentes), seul B365 porte
ce marche - perimetre volontairement limite a ce qui existe reellement.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

SOURCE = "football_data"
BOOKMAKER = "B365"
MARKET = "1x2"
OVER_UNDER_25_MARKET = "over_under_2.5"
BOOKMAKERS_1X2 = ("B365", "BW", "PS")

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
    "BWH",
    "BWD",
    "BWA",
    "PSH",
    "PSD",
    "PSA",
    "B365>2.5",
    "B365<2.5",
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
    b365_over_2_5: float | None = None
    b365_under_2_5: float | None = None
    bw_home: float | None = None
    bw_draw: float | None = None
    bw_away: float | None = None
    ps_home: float | None = None
    ps_draw: float | None = None
    ps_away: float | None = None

    @property
    def has_complete_odds(self) -> bool:
        return self.b365_home is not None and self.b365_draw is not None and self.b365_away is not None

    @property
    def has_complete_over_under_2_5_odds(self) -> bool:
        return self.b365_over_2_5 is not None and self.b365_under_2_5 is not None

    @property
    def has_complete_bw_odds(self) -> bool:
        return self.bw_home is not None and self.bw_draw is not None and self.bw_away is not None

    @property
    def has_complete_ps_odds(self) -> bool:
        return self.ps_home is not None and self.ps_draw is not None and self.ps_away is not None

    def odds_1x2_by_bookmaker(self) -> dict[str, dict[str, float]]:
        """{bookmaker: {"H":.., "D":.., "A":..}} pour chaque bookmaker
        1X2 COMPLET sur ce match - un bookmaker absent ou partiel sur ce
        match n'apparait simplement pas (jamais invente ni impute)."""
        out: dict[str, dict[str, float]] = {}
        if self.has_complete_odds:
            out["B365"] = {"H": self.b365_home, "D": self.b365_draw, "A": self.b365_away}
        if self.has_complete_bw_odds:
            out["BW"] = {"H": self.bw_home, "D": self.bw_draw, "A": self.bw_away}
        if self.has_complete_ps_odds:
            out["PS"] = {"H": self.ps_home, "D": self.ps_draw, "A": self.ps_away}
        return out


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
                    b365_over_2_5=_parse_optional_float(row["B365>2.5"]),
                    b365_under_2_5=_parse_optional_float(row["B365<2.5"]),
                    bw_home=_parse_optional_float(row["BWH"]),
                    bw_draw=_parse_optional_float(row["BWD"]),
                    bw_away=_parse_optional_float(row["BWA"]),
                    ps_home=_parse_optional_float(row["PSH"]),
                    ps_draw=_parse_optional_float(row["PSD"]),
                    ps_away=_parse_optional_float(row["PSA"]),
                )
            )
    return records
