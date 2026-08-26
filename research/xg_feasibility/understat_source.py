"""Extraction du xG par match depuis understat.com (source Priorite 2,
protocole B3 - mesure du risque de revision, PAS un connecteur de
production).

AVERTISSEMENT DE TRANSPARENCE (a lire avant toute execution) : le format
interne des pages Understat (variable JavaScript ``datesData`` encodee en
JSON, elle-meme echappee en hexadecimal ``\\xHH`` dans une chaine passee a
``JSON.parse``) est celui documente par plusieurs bibliotheques
communautaires independantes (paquet PyPI ``understat``, projet
``UnderData``, divers scrapers publics) - CE N'EST PAS verifie contre une
reponse HTTP reelle depuis cette session : l'acces reseau a
understat.com est bloque par la politique reseau de l'environnement
d'execution (403, "policy denial", confirme cote proxy - voir echange
precedent). Ce module a donc ete ecrit contre un format documente, pas
teste en direct. Lors de la premiere execution reelle (sur une machine
avec acces internet), verifiez que ``parse_matches_from_html`` retourne
bien des enregistrements non vides avant de faire confiance a
l'extraction - si Understat a change son balisage, corrigez d'abord le
parsing ici plutot que dans le code appelant.

Ce module ne fait QUE lire des pages publiques et n'ecrit jamais sur
understat.com. Il ne doit etre execute qu'a frequence raisonnable
(quelques requetes, pas un crawl massif) - conformement a un usage de
recherche personnel, pas un service en production.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.request import Request, urlopen

_USER_AGENT = (
    "Mozilla/5.0 (compatible; sys-foot-quant-research/0.1; "
    "usage de recherche personnel, mesure de stabilite xG)"
)

# Nom de la variable JS embarquee dans les pages "league season" d'Understat
# qui contient la liste des matchs de la saison (documente par les
# bibliotheques communautaires citees ci-dessus). Isole dans une constante
# pour que la correction, si le format a change, se fasse a un seul endroit.
_DATES_DATA_PATTERN = re.compile(
    r"datesData\s*=\s*JSON\.parse\('(?P<encoded>[^']+)'\)", re.DOTALL
)


class UnderstatParsingError(RuntimeError):
    """Leve quand la page recuperee ne correspond pas au format attendu -
    signal explicite plutot qu'un echec silencieux (meme discipline que le
    reste du projet : jamais de degradation silencieuse d'une garantie)."""


@dataclass(frozen=True)
class MatchXGRecord:
    """Un enregistrement xG normalise, independant du schema brut
    d'Understat - c'est ce format qui est serialise par ``storage.py`` et
    consomme par ``compare.py``."""

    match_id: str
    league: str
    season: str
    kickoff_utc: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_xg: float
    away_xg: float


def fetch_league_season_html(league: str, season: str, timeout: float = 15.0) -> str:
    """SEULE fonction de ce module qui touche le reseau. Isolee
    deliberement pour que tout le reste (parsing, normalisation,
    comparaison) reste testable sans connexion.

    ``league`` : identifiant Understat de la ligue (ex. "EPL", "La_liga",
    "Ligue_1", "Bundesliga", "Serie_A") - a verifier sur le site au moment
    de l'execution reelle, le format exact n'est pas garanti par ce module.
    ``season`` : annee de debut de saison (ex. "2024" pour 2024/2025).
    """
    url = f"https://understat.com/league/{league}/{season}"
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - URL fixe, https uniquement
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def parse_matches_from_html(html: str) -> list[dict]:
    """Extrait la liste brute des matchs (schema natif Understat, non
    normalise) depuis le HTML d'une page "league season". Fonction PURE
    (aucun acces reseau) - directement testable avec un fixture HTML.

    Leve ``UnderstatParsingError`` si le marqueur ``datesData`` est
    introuvable - jamais de retour silencieux d'une liste vide qui
    masquerait un changement de format en amont.
    """
    match = _DATES_DATA_PATTERN.search(html)
    if match is None:
        raise UnderstatParsingError(
            "Marqueur 'datesData = JSON.parse(...)' introuvable dans la page - "
            "le format d'Understat a peut-etre change, ou la page recuperee "
            "n'est pas une page 'league season' valide. Ne pas contourner "
            "silencieusement : corriger _DATES_DATA_PATTERN ci-dessus apres "
            "inspection manuelle d'une vraie page."
        )
    encoded = match.group("encoded")
    decoded_json = _decode_hex_escaped_json(encoded)
    try:
        payload = json.loads(decoded_json)
    except json.JSONDecodeError as exc:
        raise UnderstatParsingError(
            f"Le contenu decode de 'datesData' n'est pas un JSON valide : {exc}"
        ) from exc
    if not isinstance(payload, list):
        raise UnderstatParsingError(
            f"'datesData' decode n'est pas une liste (type recu : {type(payload).__name__})."
        )
    return payload


def _decode_hex_escaped_json(encoded: str) -> str:
    """Understat echappe la chaine JSON en hexadecimal (``\\xHH``) avant de
    la passer a ``JSON.parse`` cote navigateur. Le detour par
    latin1/unicode_escape est necessaire pour restituer correctement les
    caracteres multi-octets (ex. noms d'equipes accentues) - un simple
    ``.encode().decode('unicode_escape')`` seul corromprait l'UTF-8."""
    return encoded.encode("utf-8").decode("unicode_escape").encode("latin1").decode("utf-8")


def extract_match_records(
    raw_matches: list[dict], league: str, season: str
) -> list[MatchXGRecord]:
    """Normalise le schema brut Understat en ``MatchXGRecord``. Fonction
    PURE, testable sans reseau. Ne retient QUE les matchs deja joues
    (``isResult`` vrai) - un match a venir n'a par definition aucun xG
    reel a comparer."""
    records: list[MatchXGRecord] = []
    for raw in raw_matches:
        if not raw.get("isResult", False):
            continue
        kickoff = datetime.strptime(raw["datetime"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        records.append(
            MatchXGRecord(
                match_id=str(raw["id"]),
                league=league,
                season=season,
                kickoff_utc=kickoff,
                home_team=raw["h"]["title"],
                away_team=raw["a"]["title"],
                home_goals=int(raw["goals"]["h"]),
                away_goals=int(raw["goals"]["a"]),
                home_xg=float(raw["xG"]["h"]),
                away_xg=float(raw["xG"]["a"]),
            )
        )
    return records


def fetch_match_records(league: str, season: str, timeout: float = 15.0) -> list[MatchXGRecord]:
    """Enchainement complet fetch -> parse -> normalise, pour un usage
    direct depuis le CLI. Les trois etapes restent appelables separement
    pour les tests (seule ``fetch_league_season_html`` touche le reseau)."""
    html = fetch_league_season_html(league, season, timeout=timeout)
    raw_matches = parse_matches_from_html(html)
    return extract_match_records(raw_matches, league=league, season=season)
