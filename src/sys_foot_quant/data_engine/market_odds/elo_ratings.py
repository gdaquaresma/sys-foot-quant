"""Ratings Elo pre-match (ClubElo, Phase K -
docs/elo_experiment_specification.md).

Parseur du format CSV ClubElo (``Rank, Club, Country, Level, Elo, From,
To``) et fonction de lookup point-in-time pure ``elo_as_of``. AUCUNE cote
de marche, AUCUN champ de cloture - source totalement independante des
bookmakers deja lus par ce projet.

Format confirme par des sources secondaires publiques uniquement (cet
environnement ne peut pas atteindre clubelo.com/api.clubelo.com - voir
docs/elo_experiment_specification.md section 0bis) : chaque ligne
delimite une fenetre de validite [``From``, ``To``] contigue pendant
laquelle le rating est constant, ``From`` correspondant au LENDEMAIN du
match ayant produit le changement - propriete qui garantit, par
construction du format lui-meme, qu'une date ``D`` ne reflete jamais un
match dispute ce jour ``D``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class EloRatingRow:
    club: str
    country: str
    level: int
    elo: float
    valid_from: date
    valid_to: date


class AmbiguousEloWindowError(Exception):
    """Levee si plus d'une ligne satisfait valid_from <= date <= valid_to
    pour un meme club a une meme date - anomalie de donnees, jamais
    resolue en choisissant arbitrairement l'une des lignes."""


def _parse_date(raw: object) -> date:
    if isinstance(raw, date):
        return raw
    return datetime.strptime(str(raw), "%Y-%m-%d").date()


def parse_clubelo_csv_rows(raw_rows: list[dict]) -> list[EloRatingRow]:
    """Convertit des lignes brutes (un dict par ligne CSV, cles
    'Rank'/'Club'/'Country'/'Level'/'Elo'/'From'/'To') en ``EloRatingRow``.
    Conversion de type stricte uniquement - aucune interpretation, aucun
    tri, aucune deduplication (a la charge de l'appelant)."""
    return [
        EloRatingRow(
            club=str(r["Club"]),
            country=str(r["Country"]),
            level=int(r["Level"]),
            elo=float(r["Elo"]),
            valid_from=_parse_date(r["From"]),
            valid_to=_parse_date(r["To"]),
        )
        for r in raw_rows
    ]


def elo_as_of(rows: list[EloRatingRow], as_of_date: date) -> float | None:
    """Retourne le rating Elo valide a ``as_of_date`` (``valid_from <=
    as_of_date <= valid_to``), ou ``None`` si aucune ligne ne correspond
    - jamais une interpolation, jamais la ligne la plus proche. Leve
    ``AmbiguousEloWindowError`` si plusieurs lignes correspondent
    simultanement (docs/elo_experiment_specification.md section 2)."""
    matches = [r for r in rows if r.valid_from <= as_of_date <= r.valid_to]
    if not matches:
        return None
    if len(matches) > 1:
        raise AmbiguousEloWindowError(
            f"{len(matches)} lignes ClubElo valides simultanement pour {as_of_date} : {matches!r}"
        )
    return matches[0].elo
