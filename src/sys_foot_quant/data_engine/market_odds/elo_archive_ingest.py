"""Ingestion de l'archive quotidienne ClubElo (Phase K, option (b) de
l'audit ClubElo - docs/elo_experiment_specification.md, annexe archive).

Source : depot GitHub public ``tonyelhabr/club-rankings``, fichier
``clubelo-club-rankings.csv`` (alimente automatiquement chaque jour par
un robot interrogeant l'API ClubElo en direct), telecharge le
2026-08-30 depuis
https://github.com/tonyelhabr/club-rankings/releases/download/club-rankings/clubelo-club-rankings.csv
puis filtre aux 67 clubs des 3 championnats deja couverts par ce projet
(``research/market_odds/clubelo/runs/clubelo_daily_archive.csv``, 61394
lignes sur 581279). Contournement du site clubelo.com/api.clubelo.com,
indisponibles au moment de cette phase (timeout constate directement par
l'utilisateur ET par cet environnement).

**Le fichier brut est un JOURNAL de scrapes quotidiens** (une ligne par
jour de collecte, pas une table de fenetres deja dedupliquees) - la meme
fenetre logique ``[From, To]`` apparait donc identiquement plusieurs
jours de suite tant qu'aucun nouveau match n'a eu lieu. La colonne
``To`` du fichier brut n'est PAS fiable telle quelle pour la fenetre
encore « en cours » au moment du scrape (elle derive legerement d'un
jour a l'autre, verifie directement) - cette ingestion reconstruit donc
des fenetres PROPRES et NON chevauchantes en utilisant UNIQUEMENT la
sequence des valeurs DISTINCTES de ``From`` par club (verifie stable :
un changement de ``From`` correspond toujours a un match reel), jamais
la colonne ``To`` brute.

**Choix PIT non negociable, mesure sur les donnees reelles (pas une
hypothese)** : pour chaque fenetre (identifiee par sa valeur ``From``),
la valeur d'Elo retenue est la PREMIERE jamais observee dans l'archive
pour cette fenetre (le scrape le plus proche de son ouverture), jamais
une valeur observee plus tard. Audit direct : 19.3% des fenetres
(3213/16644 sur nos 67 clubs) montrent un ecart >1 point entre leur
premiere et leur derniere observation archivee (mediane ~6.2 points,
max 34.5 points) - un effet modeste mais reel de raffinement retroactif
du moteur ClubElo lui-meme sur l'historique recent. Choisir la PREMIERE
observation garantit que la feature n'utilise jamais une information
publiee apres le moment ou elle aurait ete disponible - le choix
strictement correct pour une experience PIT, jamais la valeur « la plus
a jour avec le recul »."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sys_foot_quant.data_engine.market_odds.elo_ratings import EloRatingRow

# Noms utilises par CETTE archive specifiquement, differents des noms du
# site clubelo.com en direct (deja verifies a la main par l'utilisateur,
# elo_team_mapping.py) - trois cas seulement, chacun sans ambiguite
# possible dans ce contexte championnat/pays (un seul club correspondant).
ARCHIVE_NAME_TO_LIVE_NAME: dict[str, str] = {
    "Bilbao": "Athletic Club",
    "Atletico": "Atlético",
    "Sociedad": "Real Sociedad",
}

CONFLICT_THRESHOLD_ELO_POINTS = 1.0


@dataclass(frozen=True)
class EloArchiveIngestReport:
    total_raw_rows: int
    n_clubs: int
    n_windows_reconstructed: int
    n_windows_with_conflict: int
    earliest_date: date
    latest_date: date
    ratings_by_live_name: dict[str, list[EloRatingRow]] = field(default_factory=dict)


def load_daily_archive_rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ingest_daily_archive(raw_rows: list[dict]) -> EloArchiveIngestReport:
    """Reconstruit, a partir du journal brut de scrapes quotidiens, un
    dictionnaire ``{nom_ClubElo_site_en_direct: [EloRatingRow...]}`` pret
    a etre utilise par ``elo_join.build_elo_dataset`` (INCHANGE) - jamais
    de modification du format ``EloRatingRow``/``elo_as_of`` deja testes."""
    by_club: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in raw_rows:
        by_club[(r["Country"], r["Club"])].append(r)

    n_conflict = 0
    n_windows = 0
    ratings_by_live_name: dict[str, list[EloRatingRow]] = {}
    all_dates: list[date] = []

    for (country, archive_club), rows in by_club.items():
        live_name = ARCHIVE_NAME_TO_LIVE_NAME.get(archive_club, archive_club)
        rows_sorted = sorted(rows, key=lambda r: r["date"])

        first_seen: dict[str, dict] = {}
        seen_values: dict[str, list[float]] = defaultdict(list)
        for r in rows_sorted:
            frm = r["From"]
            seen_values[frm].append(float(r["Elo"]))
            if frm not in first_seen:
                first_seen[frm] = r
            all_dates.append(datetime.strptime(r["date"], "%Y-%m-%d").date())

        froms_sorted = sorted(first_seen.keys())
        max_date = max(datetime.strptime(r["date"], "%Y-%m-%d").date() for r in rows_sorted)

        windows: list[EloRatingRow] = []
        for i, frm in enumerate(froms_sorted):
            n_windows += 1
            values = seen_values[frm]
            if max(values) - min(values) > CONFLICT_THRESHOLD_ELO_POINTS:
                n_conflict += 1
            frm_date = datetime.strptime(frm, "%Y-%m-%d").date()
            if i + 1 < len(froms_sorted):
                to_date = datetime.strptime(froms_sorted[i + 1], "%Y-%m-%d").date() - timedelta(days=1)
            else:
                to_date = max_date
            first_row = first_seen[frm]
            windows.append(
                EloRatingRow(
                    club=live_name,
                    country=country,
                    level=int(float(first_row["Level"])),
                    elo=float(first_row["Elo"]),
                    valid_from=frm_date,
                    valid_to=to_date,
                )
            )
        ratings_by_live_name.setdefault(live_name, []).extend(windows)

    return EloArchiveIngestReport(
        total_raw_rows=len(raw_rows),
        n_clubs=len(ratings_by_live_name),
        n_windows_reconstructed=n_windows,
        n_windows_with_conflict=n_conflict,
        earliest_date=min(all_dates),
        latest_date=max(all_dates),
        ratings_by_live_name=ratings_by_live_name,
    )
