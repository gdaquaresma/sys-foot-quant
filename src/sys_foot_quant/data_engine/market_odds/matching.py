"""Appariement Understat <-> Football-Data (etape 3, phase economique -
docs/decisions/0006-football-data-point-in-time.md).

Cle de match normalisee : (championnat, saison, equipe domicile Understat,
equipe exterieur Understat, date de coup d'envoi en UTC) - construite via
``team_mapping`` (deterministe) puis ``time_resolution`` (conversion vers
UTC). La granularite JOUR (pas la minute) est utilisee pour la cle de
match elle-meme : le decalage residuel de convention horaire (etape 2) est
verifie separement, pas fondu dans la cle d'appariement.

Duplique volontairement une analyse minimale du schema brut Understat
(comme ``backtesting_engine/real_data_walk_forward.py``) plutot que
d'importer ``research/xg_feasibility`` - meme principe d'isolation deja
applique dans ce projet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord
from sys_foot_quant.data_engine.market_odds.team_mapping import resolve_understat_name


@dataclass(frozen=True)
class UnderstatMatchKey:
    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    home_team_id: int
    away_team_id: int
    home_team_name: str
    away_team_name: str


def build_understat_keys(raw_matches: list[dict], league: str, season: str) -> list[UnderstatMatchKey]:
    """Extrait les cles d'appariement necessaires depuis le schema brut
    Understat. Ne retient que les matchs deja joues (``isResult``)."""
    keys: list[UnderstatMatchKey] = []
    for raw in raw_matches:
        if not raw.get("isResult", False):
            continue
        kickoff = datetime.strptime(raw["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        keys.append(
            UnderstatMatchKey(
                match_id=str(raw["id"]),
                league=league,
                season=season,
                kickoff_utc=kickoff,
                home_team_id=int(raw["h"]["id"]),
                away_team_id=int(raw["a"]["id"]),
                home_team_name=raw["h"]["title"],
                away_team_name=raw["a"]["title"],
            )
        )
    return keys


def _match_key(league: str, season: str, home: str, away: str, kickoff_date_iso: str) -> tuple:
    return (league, season, home, away, kickoff_date_iso)


@dataclass(frozen=True)
class MatchedRecord:
    understat: UnderstatMatchKey
    football_data: FootballDataMatchRecord


@dataclass(frozen=True)
class MatchingReport:
    league: str
    season: str
    n_understat: int
    n_football_data: int
    n_matched: int
    n_unmatched_understat: int
    n_unmatched_football_data: int
    n_duplicate_keys_understat: int
    n_duplicate_keys_football_data: int
    unmatched_understat: tuple[tuple, ...]
    unmatched_football_data: tuple[tuple, ...]
    matched: tuple[MatchedRecord, ...]


def match_league_season(
    understat_keys: list[UnderstatMatchKey],
    football_data_records: list[FootballDataMatchRecord],
    league: str,
    season: str,
) -> MatchingReport:
    """Apparie, pour UN championnat et UNE saison, les matchs Understat et
    Football-Data via la cle normalisee (championnat, saison, equipe
    domicile/exterieur Understat, date). Rapporte explicitement les
    doublons de cle et les elements non apparies de chaque cote - ne
    masque jamais une ambiguite en gardant silencieusement le premier
    match trouve."""
    us_by_key: dict[tuple, list[UnderstatMatchKey]] = {}
    for k in understat_keys:
        if k.league != league or k.season != season:
            continue
        mk = _match_key(k.league, k.season, k.home_team_name, k.away_team_name, k.kickoff_utc.date().isoformat())
        us_by_key.setdefault(mk, []).append(k)

    fd_by_key: dict[tuple, list[FootballDataMatchRecord]] = {}
    for r in football_data_records:
        if r.league != league or r.season != season:
            continue
        home_us = resolve_understat_name(league, r.home_team_fd)
        away_us = resolve_understat_name(league, r.away_team_fd)
        day, month, year = r.date_str.split("/")
        date_iso = f"{year}-{month}-{day}"
        mk = _match_key(league, season, home_us, away_us, date_iso)
        fd_by_key.setdefault(mk, []).append(r)

    n_dup_us = sum(1 for v in us_by_key.values() if len(v) > 1)
    n_dup_fd = sum(1 for v in fd_by_key.values() if len(v) > 1)

    matched: list[MatchedRecord] = []
    unmatched_us: list[tuple] = []
    for mk, us_list in us_by_key.items():
        fd_list = fd_by_key.get(mk)
        if fd_list and len(us_list) == 1 and len(fd_list) == 1:
            matched.append(MatchedRecord(understat=us_list[0], football_data=fd_list[0]))
        elif not fd_list:
            unmatched_us.append(mk)
        # une cle dupliquee d'un cote ou de l'autre n'est JAMAIS appariee
        # automatiquement - comptee dans n_duplicate_keys_*, pas dans matched.

    unmatched_fd = [mk for mk in fd_by_key if mk not in us_by_key]

    return MatchingReport(
        league=league,
        season=season,
        n_understat=sum(len(v) for v in us_by_key.values()),
        n_football_data=sum(len(v) for v in fd_by_key.values()),
        n_matched=len(matched),
        n_unmatched_understat=len(unmatched_us),
        n_unmatched_football_data=len(unmatched_fd),
        n_duplicate_keys_understat=n_dup_us,
        n_duplicate_keys_football_data=n_dup_fd,
        unmatched_understat=tuple(unmatched_us),
        unmatched_football_data=tuple(unmatched_fd),
        matched=tuple(matched),
    )


def opening_over_under_2_5_by_match_id(
    report: MatchingReport, match_id: str, bookmaker: str = "B365"
) -> dict[str, float] | None:
    """Pont vers le moteur de prediction (``run_prediction(market_odds=...)``)
    - AJOUT PUR, aucun nouveau calcul d'appariement : reutilise
    exclusivement ``report.matched`` (deja produit par
    ``match_league_season``, deja valide sur le corpus reel - voir
    ``tests/leakage/test_football_data_point_in_time.py``). Retrouve le
    ``match_id`` Understat demande et retourne sa cote Over/Under 2.5
    D'OUVERTURE pour ``bookmaker`` (``"B365"`` par defaut, couverture 100%
    constatee - voir docstring de ``football_data_loader``), directement
    exploitable par ``run_prediction(market_odds=...)`` (meme forme
    exacte, ``{"Over": .., "Under": ..}``).

    N'extrait JAMAIS une cote de CLOTURE - seule
    ``over_under_2_5_by_bookmaker()`` (ouverture) est lue, jamais
    ``closing_over_under_2_5_by_bookmaker()``. Les cotes d'ouverture sont
    par construction publiees largement avant ``decision_time``
    (``kickoff_utc - DECISION_OFFSET_HOURS``, quelques heures seulement) -
    aucun nouveau delai de connaissance n'est necessaire ni invente ici,
    contrairement a ``goals_knowledge_time``/``xg_knowledge_time``
    (``real_data_walk_forward.py``), qui portent sur des grandeurs connues
    seulement APRES le coup d'envoi.

    Retourne ``None`` (JAMAIS une cote inventee ou approximee) si :
    - ``match_id`` n'apparait pas dans ``report.matched`` (match non
      apparie - residu documente, voir
      ``tests/leakage/test_football_data_point_in_time.py``, ou simplement
      saison/competition sans fichier Football-Data reel) ;
    - ``bookmaker`` n'a pas de cote Over/Under 2.5 complete sur ce match
      precis (bookmaker absent/partiel sur ce match - jamais impute)."""
    for m in report.matched:
        if m.understat.match_id == match_id:
            return m.football_data.over_under_2_5_by_bookmaker().get(bookmaker)
    return None
