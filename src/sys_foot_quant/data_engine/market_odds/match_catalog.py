"""Catalogue en LECTURE SEULE des matchs/equipes disponibles par
(competition, saison) - Phase UI-2-A.

Objectif unique : repondre a "quels matchs/equipes existent pour cette
selection ?" pour un futur explorateur (page web), JAMAIS "quelles donnees
d'entrainement le moteur doit-il utiliser ?" (ce dernier reste
integralement le role de ``scripts/predict_match.py``/
``data_engine.market_odds.future_match_dataset``/
``backtesting_engine.real_data_walk_forward``, INCHANGES, jamais
reimplementes ni appeles ici).

Design deliberement separe de ``scripts/predict_match.py`` :

- ``predict_match._SEASONS``/``_CURRENT_SEASON_SOURCES`` decrivent quelles
  SOURCES alimentent l'ENTRAINEMENT d'une prediction pour une saison (pour
  ``"2026_27"``, une AGREGATION de 3 fichiers - voir Etape I-2). Ce module
  repond a une question differente : quels matchs APPARTIENNENT
  reellement a la saison ``"2026_27"`` elle-meme (pour les proposer a la
  selection dans un explorateur) - un seul fichier
  (``ligue1_2026_datesData.json``), jamais les saisons historiques
  agregees comme corpus d'entrainement. Melanger ces deux notions
  afficherait ~650 matchs "dans la saison 2026/27" a l'utilisateur, ce qui
  serait factuellement faux.
- Ce module n'importe ni n'est importe par ``scripts/predict_match.py`` -
  aucun couplage, aucun risque de second chemin de prediction (ce module
  ne construit JAMAIS de DataFrame d'entrainement, ne filtre JAMAIS par
  point-in-time - il n'y a rien a filtrer, une simple lecture descriptive
  ne s'appuie sur aucune notion de ``decision_time``).

Duplique volontairement une analyse minimale du schema brut Understat
(meme principe deja documente dans ``matching.py``/
``backtesting_engine/real_data_walk_forward.py`` - isolation deliberee
plutot qu'un import de ``research/xg_feasibility``), et duplique
volontairement la cartographie (competition, saison) -> fichier deja
utilisee par ``scripts/predict_match.py``/
``scripts/run_stage8_diagnostic_total_goals_over_under.py`` (meme
convention de duplication minimale que le reste du projet pour les
modules/scripts isoles - jamais une nouvelle source de donnees).

Constat verifie sur les 7 fichiers canoniques (README de cette phase) :
aucun ne contient de champ "journee"/matchday exploitable. Un champ
``numbers.week`` existe dans 6 des 7 fichiers (absent de
``ligue1_2026_datesData.json``) mais represente la SEMAINE CALENDAIRE ISO,
pas un numero de journee de championnat garanti (aucune validation de
cette correspondance) - deliberement NON EXPOSE par ce module. Seule la
date de coup d'envoi (``kickoff_utc``, deja fournie par le schema brut) est
exploitee pour un filtrage temporel eventuel cote appelant.

Constat verifie egalement : les 7 fichiers canoniques actuellement presents
ne contiennent QUE des matchs ``isResult=true`` (aucun match a venir non
encore joue). Le champ ``is_played`` ci-dessous est neanmoins expose sans
etre invente : il reflete fidelement ``isResult`` tel que lu, pret a
distinguer un futur match non joue le jour ou un tel fichier existera,
sans qu'aucune modification de ce module ne soit necessaire."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# IDENTIQUE (memes valeurs) au mapping deja utilise par
# scripts/predict_match.py (``_SEASONS``) pour 2024_25/2025_26 - duplication
# volontaire et minimale (voir docstring du module). Pour ``2026_27``,
# UN SEUL fichier (celui de la saison courante elle-meme) est utilise ici
# - deliberement DIFFERENT de predict_match._CURRENT_SEASON_SOURCES (qui
# agrege 3 fichiers pour l'ENTRAINEMENT, jamais pour l'enumeration).
_SEASON_FILES: dict[str, dict[str, tuple[str, Path]]] = {
    "2024_25": {
        "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2024_datesData.json")),
        "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2024_datesData.json")),
        "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2024_datesData.json")),
    },
    "2025_26": {
        "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2025_datesData.json")),
        "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2025_datesData.json")),
        "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2025_datesData.json")),
    },
    "2026_27": {
        "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2026_datesData.json")),
    },
}

COMPETITIONS: tuple[str, ...] = tuple(sorted({c for seasons in _SEASON_FILES.values() for c in seasons}))
SEASONS: tuple[str, ...] = tuple(sorted(_SEASON_FILES))


class MatchCatalogError(ValueError):
    """Refus explicite (competition/saison inconnue, fichier absent,
    donnees malformees) - jamais un catalogue partiel ou un defaut
    silencieux (meme discipline que ``predict_match.PredictMatchError``)."""


@dataclass(frozen=True)
class MatchSummary:
    """Description minimale, en lecture seule, d'UN match - jamais une
    structure d'entrainement (aucun champ de buts/xG, hors du perimetre de
    ce catalogue)."""

    match_id: str
    competition: str
    season: str
    kickoff_utc: datetime
    home_team: str
    away_team: str
    is_played: bool


def list_competitions() -> tuple[str, ...]:
    """Competitions connues de ce catalogue, toutes saisons confondues."""
    return COMPETITIONS


def list_seasons() -> tuple[str, ...]:
    """Saisons connues de ce catalogue."""
    return SEASONS


def _raw_matches_for(competition: str, season: str) -> tuple[list[dict], Path]:
    if season not in _SEASON_FILES:
        raise MatchCatalogError(f"Saison inconnue : {season!r} (saisons disponibles : {SEASONS}).")
    if competition not in _SEASON_FILES[season]:
        raise MatchCatalogError(
            f"Competition inconnue pour la saison {season!r} : {competition!r} "
            f"(competitions disponibles pour cette saison : {tuple(sorted(_SEASON_FILES[season]))})."
        )
    _league_id, path = _SEASON_FILES[season][competition]
    if not path.exists():
        raise MatchCatalogError(
            f"Fichier Understat introuvable : {path} (ce catalogue ne collecte jamais de nouvelle donnee)."
        )
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise MatchCatalogError(f"Fichier Understat corrompu : {path} ({exc}).") from exc
    if not isinstance(raw, list):
        raise MatchCatalogError(f"Format inattendu dans {path} : une liste de matchs est attendue.")
    return raw, path


def _to_match_summary(raw_match: dict, competition: str, season: str, path: Path) -> MatchSummary:
    try:
        match_id = str(raw_match["id"])
        home_team = raw_match["h"]["title"]
        away_team = raw_match["a"]["title"]
        kickoff_utc = datetime.strptime(raw_match["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError) as exc:
        raise MatchCatalogError(
            f"Entree de match invalide dans {path} : {raw_match!r} ({exc}) - "
            "refus plutot qu'un catalogue partiel silencieux."
        ) from exc
    return MatchSummary(
        match_id=match_id,
        competition=competition,
        season=season,
        kickoff_utc=kickoff_utc,
        home_team=home_team,
        away_team=away_team,
        is_played=bool(raw_match.get("isResult", False)),
    )


def list_matches(competition: str, season: str) -> tuple[MatchSummary, ...]:
    """Matchs de ``(competition, season)``, triees de facon deterministe
    par coup d'envoi puis par ``match_id`` (depart egalite) - jamais
    l'ordre d'apparition brut du fichier, qui n'est pas garanti trie.

    Leve ``MatchCatalogError`` explicitement si ``competition``/``season``
    est inconnue ou si le fichier est absent/corrompu/malforme - jamais un
    catalogue vide ou partiel en cas de probleme de donnees."""
    raw_matches, path = _raw_matches_for(competition, season)
    summaries = [_to_match_summary(m, competition, season, path) for m in raw_matches]
    return tuple(sorted(summaries, key=lambda m: (m.kickoff_utc, m.match_id)))


def list_teams(competition: str, season: str) -> tuple[str, ...]:
    """Noms d'equipes REELLEMENT presents dans les matchs de
    ``(competition, season)`` - derives de ``list_matches`` (jamais une
    seconde lecture independante du fichier), triees alphabetiquement,
    sans doublon."""
    matches = list_matches(competition, season)
    teams = {m.home_team for m in matches} | {m.away_team for m in matches}
    return tuple(sorted(teams))
