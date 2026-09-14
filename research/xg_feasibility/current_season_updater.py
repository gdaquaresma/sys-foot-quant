"""Connecteur d'auto-alimentation de la saison courante (etape suivant
``current_season_merge.py``) - orchestre :

    FETCH (understat_source, INCHANGE)
        -> VALIDATE (current_season_contract, INCHANGE)
        -> DIFF/MERGE (current_season_merge, INCHANGE)
        -> ECRITURE ATOMIQUE (current_season_merge.write_current_season_atomic, INCHANGE)

FAIL-CLOSED strict : toute anomalie a n'importe quelle etape (reseau,
format, contrat, coherence avec l'existant) produit un ``SyncReport``
avec ``action`` explicite ("error"/"refused") et **le fichier canonique
n'est jamais modifie**. Jamais de "dernier fichier recu remplace le
fichier local".

ISOLATION D'ARCHITECTURE (a respecter strictement) : ce module vit dans
``research/`` (jamais dans ``src/sys_foot_quant``) car il depend de
``research.xg_feasibility.understat_source`` - respecte la meme regle
que le reste de ``research/xg_feasibility`` ("N'est JAMAIS importe par
``src/sys_foot_quant``"). Il IMPORTE en revanche depuis
``sys_foot_quant.data_engine.market_odds`` (sens autorise, deja le
principe de tous les scripts de recherche du depot).

CE QUI EST REELLEMENT REUTILISE SANS MODIFICATION :
- ``current_season_contract.validate_current_season_understat_raw`` ;
- ``current_season_merge.merge_current_season``/``write_current_season_atomic``.

ENDPOINT REEL CONFIRME (capture navigateur reelle, session en cours - PAS
une hypothese) : Understat n'expose plus ``datesData`` dans le HTML de
``understat.com/league/{league}/{season}`` (verifie manuellement : marqueur
absent, recherche 0/0 sur la page reelle). Les donnees sont desormais
servies par un endpoint JSON XHR distinct :

    GET https://understat.com/getLeagueData/{league_encoded}/{season}
    Accept: application/json, text/javascript, */*; q=0.01
    X-Requested-With: XMLHttpRequest

    -> corps : {"teams": {...}, "players": [...], "dates": [...]}

Point capital confirme par capture reelle : le nom de ligue utilise dans
CET endpoint est ``"Ligue 1"`` (ESPACE), encode URL en ``Ligue%201`` -
**JAMAIS** ``"Ligue_1"`` (underscore), qui etait la convention de l'ancienne
page HTML et n'est PAS celle de ``getLeagueData``. ``build_get_league_data_url``
applique ``urllib.parse.quote`` sur le nom de ligue tel que fourni ; c'est
a l'appelant de passer ``"Ligue 1"`` (jamais ``"Ligue_1"``) pour Ligue 1.

Le point d'echec reseau/format reste isole a UNE seule fonction
(``fetch_understat_raw_played_matches``, parametre ``http_get`` injectable) :
validation/diff/fusion en aval INCHANGEES."""

from __future__ import annotations

import gzip
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from sys_foot_quant.data_engine.market_odds.current_season_contract import (
    CurrentSeasonContractError,
    validate_current_season_understat_raw,
)
from sys_foot_quant.data_engine.market_odds.current_season_merge import (
    CurrentSeasonSourceInconsistencyError,
    MergeDiff,
    merge_current_season,
    write_current_season_atomic,
)

GETLEAGUEDATA_URL_TEMPLATE = "https://understat.com/getLeagueData/{league}/{season}"

_JSON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


class UnderstatFetchError(RuntimeError):
    """Reponse Understat inexploitable (JSON invalide, cle ``dates``
    absente/mal typee, structure inattendue) - fail-closed, jamais un
    remplacement silencieux par une liste vide."""


JsonHttpGet = Callable[[str], str]  # (url) -> corps de reponse brut (texte JSON attendu)
HttpGet = JsonHttpGet  # alias conserve pour compatibilite du point d'injection existant


@dataclass(frozen=True)
class SourceInfo:
    """Metadonnees de LA tentative de recuperation - toujours produites
    des que le reseau a repondu, meme si la suite echoue."""

    competition: str
    league_id: str
    season: str
    fetched_at: datetime
    n_matches_received_raw: int  # avant filtrage isResult=true
    n_matches_played: int  # apres filtrage isResult=true (isResult=false toujours exclus, jamais promus)


@dataclass(frozen=True)
class SyncReport:
    """Rapport explicite d'UNE synchronisation, TOUJOURS retourne (jamais
    une exception non geree qui masquerait le contexte) :

    - ``action="updated"``            : fichier canonique reecrit (nouveaux matchs ajoutes) ;
    - ``action="no_change"``          : aucun nouveau match, fichier canonique intact (deja a jour) ;
    - ``action="dry_run_would_update"``/``"dry_run_no_change"`` : ``dry_run=True``, jamais d'ecriture ;
    - ``action="refused"``            : la source contredit l'etat local (modification/disparition
                                         detectee par current_season_merge) - fichier intact ;
    - ``action="error"``              : echec reseau/format/contrat/coherence AVANT meme le diff -
                                         fichier intact."""

    source: SourceInfo | None
    diff: MergeDiff | None
    action: str
    error_message: str | None = None


def build_get_league_data_url(league_name: str, season: str) -> str:
    """Construit l'URL reelle ``getLeagueData`` a partir du nom de ligue
    TEL QUEL (ex. ``"Ligue 1"``, avec espace) et de la saison. Encode
    UNIQUEMENT via ``urllib.parse.quote`` (``"Ligue 1"`` -> ``"Ligue%201"``) -
    n'applique JAMAIS de substitution espace->underscore (l'ancienne
    convention ``"Ligue_1"`` de la page HTML, confirmee DIFFERENTE et
    INCOMPATIBLE avec cet endpoint par capture navigateur reelle)."""
    return GETLEAGUEDATA_URL_TEMPLATE.format(league=quote(league_name, safe=""), season=quote(season, safe=""))


def _decode_http_body(raw_bytes: bytes, content_encoding: str) -> str:
    """Decode un corps HTTP brut en texte UTF-8, en decompressant
    d'abord un corps gzip. Constat empirique reel (validation externe,
    Mac avec acces reseau reel) : Understat peut repondre avec un corps
    gzip (magic bytes ``1f 8b``) meme sans que ce module ne l'ait
    demande via ``Accept-Encoding`` - la seule inspection du header
    ``Content-Encoding`` ne suffit donc pas a elle seule, on detecte
    aussi les magic bytes en secours. FAIL-CLOSED : une decompression
    gzip invalide (``gzip.BadGzipFile``, sous-classe ``OSError``) ou un
    decodage UTF-8 invalide remontent tels quels, jamais de contenu
    partiel/tronque accepte silencieusement."""
    if content_encoding.strip().lower() == "gzip" or raw_bytes[:2] == b"\x1f\x8b":
        raw_bytes = gzip.decompress(raw_bytes)
    return raw_bytes.decode("utf-8")


def _default_json_http_get(url: str, timeout: float = 15.0) -> str:
    """Seule fonction du module touchant reellement le reseau. Envoie les
    deux headers confirmes par capture navigateur reelle
    (``Accept``/``X-Requested-With``) - sans eux Understat peut repondre
    autrement (ex. page HTML) qu'avec le JSON attendu. Laisse
    ``urllib.error.HTTPError``/``URLError`` (sous-classes ``OSError``)
    remonter telles quelles, sans inspection manuelle du code statut -
    meme convention que le reste du module reseau du depot."""
    request = urllib.request.Request(url, headers=_JSON_HEADERS, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw_bytes = response.read()
        content_encoding = response.headers.get("Content-Encoding", "") or ""
        return _decode_http_body(raw_bytes, content_encoding)


def fetch_league_data_payload(
    league_name: str,
    season: str,
    *,
    http_get: JsonHttpGet | None = None,
) -> dict:
    """Recupere et decode le payload JSON ``getLeagueData`` - fail-closed
    sur toute anomalie de forme (corps non-JSON, racine non-objet, cle
    ``dates`` absente ou mal typee) via ``UnderstatFetchError``, JAMAIS
    une liste vide silencieuse.

    ``http_get`` : point d'injection EXCLUSIVEMENT destine aux tests
    (mock d'une reponse Understat), signature ``(url) -> texte`` - par
    defaut ``_default_json_http_get`` reel."""
    fetch = http_get or _default_json_http_get
    url = build_get_league_data_url(league_name, season)
    raw_text = fetch(url)
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise UnderstatFetchError(f"Reponse Understat non-JSON pour {url} : {exc}") from exc
    if not isinstance(payload, dict):
        raise UnderstatFetchError(f"Reponse Understat inattendue pour {url} : racine JSON non-objet ({type(payload).__name__})")
    dates = payload.get("dates")
    if not isinstance(dates, list):
        raise UnderstatFetchError(
            f"Reponse Understat inattendue pour {url} : cle 'dates' absente ou non-liste "
            f"(type recu : {type(dates).__name__ if dates is not None else 'absente'})"
        )
    return payload


def fetch_understat_raw_played_matches(
    league_id: str,
    season: str,
    *,
    http_get: HttpGet | None = None,
) -> tuple[list[dict], int]:
    """Recupere et extrait les matchs Understat pour ``(league_id,
    season)`` via l'endpoint JSON reel ``getLeagueData`` (voir
    ``fetch_league_data_payload``/``build_get_league_data_url``). Le
    filtrage ``isResult=true`` est fait ICI (jamais delegue en amont).

    ``league_id`` doit etre le nom de ligue attendu par ``getLeagueData``
    (ex. ``"Ligue 1"``, avec espace) - PAS l'ancien identifiant
    ``"Ligue_1"`` de la page HTML.

    ``http_get`` : point d'injection EXCLUSIVEMENT destine aux tests (mock
    d'une reponse Understat), signature ``(url) -> texte`` - par defaut
    ``_default_json_http_get`` reel (seule fonction du module touchant
    reseau ici).

    Retourne ``(matchs_isResult_true, nombre_total_recu_avant_filtrage)``.
    Propage telle quelle ``UnderstatFetchError`` (payload JSON invalide ou
    de forme inattendue) et toute ``OSError`` reseau (timeout, DNS, HTTP en
    erreur) - jamais interceptees ici, c'est a l'appelant
    (``sync_current_season``) de les transformer en ``SyncReport``
    explicite plutot que de les laisser remonter nues."""
    payload = fetch_league_data_payload(league_id, season, http_get=http_get)
    raw_matches = payload["dates"]
    played = [m for m in raw_matches if isinstance(m, dict) and m.get("isResult") is True]
    return played, len(raw_matches)


def _find_unknown_teams(matches: list[dict], known_team_ids: set[str]) -> set[str]:
    unknown: set[str] = set()
    for m in matches:
        for side in ("h", "a"):
            team_id = str(m[side]["id"])
            if team_id not in known_team_ids:
                unknown.add(f"{team_id} ({m[side]['title']})")
    return unknown


def _find_historical_id_collisions(matches: list[dict], historical_match_ids: set[str]) -> set[str]:
    return {str(m["id"]) for m in matches if str(m["id"]) in historical_match_ids}


def sync_current_season(
    competition: str,
    league_id: str,
    season: str,
    canonical_path: Path,
    *,
    http_get: HttpGet | None = None,
    known_team_ids: set[str] | None = None,
    historical_match_ids: set[str] | None = None,
    dry_run: bool = False,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> SyncReport:
    """Orchestration complete FETCH -> VALIDATE -> DIFF -> (ACCEPT ->
    ECRITURE ATOMIQUE | REFUS), FAIL-CLOSED a chaque etape : ``canonical_path``
    n'est JAMAIS modifie tant que la totalite de la chaine n'a pas
    reussi. Ce connecteur NE decide PAS quels matchs sont utilisables pour
    une prediction (aucune notion de ``decision_time`` ici) - il maintient
    uniquement le fichier "tous les matchs reellement termines connus a
    la derniere synchronisation" ; le filtrage point-in-time reste
    entierement delegue a R1/R2 en aval (``future_match_dataset``/
    ``calibration_dataset``, INCHANGES), jamais duplique ici.

    ``known_team_ids``/``historical_match_ids`` : controles OPTIONNELS de
    defense en profondeur (equipe jamais vue dans le corpus de cette
    competition ; collision de ``match_id`` avec l'historique long terme
    2024/25+2025/26) - desactives (``None``) par defaut, jamais une regle
    metier implicite non documentee."""
    fetched_at = now_fn()
    try:
        played_matches, n_raw = fetch_understat_raw_played_matches(league_id, season, http_get=http_get)
    except UnderstatFetchError as exc:
        return SyncReport(
            source=None,
            diff=None,
            action="error",
            error_message=f"Extraction Understat echouee (format inattendu, aucune ecriture) : {exc}",
        )
    except OSError as exc:
        return SyncReport(
            source=None,
            diff=None,
            action="error",
            error_message=f"Recuperation reseau Understat echouee (aucune ecriture) : {exc}",
        )

    source_info = SourceInfo(
        competition=competition,
        league_id=league_id,
        season=season,
        fetched_at=fetched_at,
        n_matches_received_raw=n_raw,
        n_matches_played=len(played_matches),
    )

    if known_team_ids is not None:
        unknown = _find_unknown_teams(played_matches, known_team_ids)
        if unknown:
            return SyncReport(
                source=source_info,
                diff=None,
                action="error",
                error_message=(
                    f"Equipe(s) inconnue(s) rencontree(s) - synchronisation refusee, aucune ecriture : "
                    f"{sorted(unknown)}"
                ),
            )

    if historical_match_ids is not None:
        collisions = _find_historical_id_collisions(played_matches, historical_match_ids)
        if collisions:
            return SyncReport(
                source=source_info,
                diff=None,
                action="error",
                error_message=(
                    f"match_id en collision avec l'historique long terme - synchronisation refusee, "
                    f"aucune ecriture : {sorted(collisions)}"
                ),
            )

    try:
        validate_current_season_understat_raw(played_matches)
    except CurrentSeasonContractError as exc:
        return SyncReport(source=source_info, diff=None, action="error", error_message=str(exc))

    local_matches: list[dict] = []
    if canonical_path.exists():
        try:
            with open(canonical_path, encoding="utf-8") as f:
                local_matches = json.load(f)
        except json.JSONDecodeError as exc:
            return SyncReport(
                source=source_info,
                diff=None,
                action="error",
                error_message=f"Fichier local {canonical_path} corrompu (JSON invalide, aucune ecriture) : {exc}",
            )

    try:
        merged, diff = merge_current_season(local_matches, played_matches)
    except (CurrentSeasonContractError, CurrentSeasonSourceInconsistencyError) as exc:
        return SyncReport(source=source_info, diff=None, action="refused", error_message=str(exc))

    if dry_run:
        action = "dry_run_would_update" if diff.new_matches else "dry_run_no_change"
        return SyncReport(source=source_info, diff=diff, action=action)

    if not diff.new_matches:
        return SyncReport(source=source_info, diff=diff, action="no_change")

    write_current_season_atomic(canonical_path, merged)
    return SyncReport(source=source_info, diff=diff, action="updated")


def format_report(report: SyncReport) -> str:
    """Rendu texte du rapport - format explicite demande (SOURCE/DIFF/ACTION/ERREUR)."""
    lines = ["SOURCE"]
    if report.source is None:
        lines.append("  (aucune source recuperee - echec avant reception)")
    else:
        s = report.source
        lines += [
            f"  competition        : {s.competition}",
            f"  league_id          : {s.league_id}",
            f"  saison             : {s.season}",
            f"  recupere le        : {s.fetched_at.isoformat()}",
            f"  matchs recus (brut): {s.n_matches_received_raw}",
            f"  matchs joues       : {s.n_matches_played}",
        ]
    lines.append("")
    lines.append("DIFF")
    if report.diff is None:
        lines.append("  (non calcule)")
    else:
        d = report.diff
        lines += [
            f"  nouveaux matchs    : {len(d.new_matches)}",
            f"  matchs inchanges   : {len(d.unchanged_matches)}",
            f"  matchs modifies    : {len(d.modified_matches)}",
            f"  matchs disparus    : {len(d.missing_from_source)}",
        ]
    lines.append("")
    lines.append(f"ACTION\n  {report.action}")
    if report.error_message:
        lines.append("")
        lines.append(f"ERREUR\n  {report.error_message}")
    return "\n".join(lines)
