"""Extraction de resultats de matchs (+ cotes consensus brutes) depuis les
pages "results" publiques d'oddsportal.com - connecteur de RECHERCHE isole
(jamais importe par ``src/sys_foot_quant``), PAS un chemin de production.

CONTEXTE - CONTREDIT UN AUDIT PRECEDENT DE CE DEPOT (``research/
oddsportal_validation.md``, verdict "refuse pour cette session" car l'acces
reseau a oddsportal.com etait bloque par la politique d'egress de
l'environnement d'execution de cette session-la). Verifie reellement
(requete HTTP reelle, reponse HTTP 200, 2026-10-10) depuis la session
courante : oddsportal.com est accessible, ET - contrairement a l'hypothese
du POC vendorise precedent (``scripts/poc_oddsportal_oddsharvester.py``,
qui ciblait un "modal" d'historique de cotes necessitant un navigateur
pilote via Playwright) - au MOINS UNE FOIS (capture reelle du 2026-10-10,
voir ``tests/fixtures/results_page_sample.html``, extrait VERBATIM de
cette capture), la page "results" a expose les donnees necessaires
(equipes, score, cotes 1X2 consensus multi-bookmaker) directement dans le
HTML servi par le serveur (rendu Next.js App Router, streaming RSC - voir
``_find_next_f_string_literals``), sans execution JavaScript apparente.

CORRECTIF IMPORTANT (meme journee, 2026-10-10/11, DECOUVERT APRES avoir
ecrit ce qui precede) - CETTE RECUPERATION N'EST PAS FIABLE EN L'ETAT :
plusieurs tentatives ulterieures de ``fetch_results_page`` (``curl``
simple, plusieurs jeux d'en-tetes essayes, avec et sans cookies) contre
cette MEME URL ont systematiquement renvoye une page HTTP 200 PLUS PETITE
(~329 Ko contre ~1.4 Mo pour la capture reussie) qui ne contient PAS les
donnees de match : inspection du contenu confirme qu'il s'agit du
fallback React Suspense de chargement (``"aria-busy":true``,
``"aria-label":"Loading page"``, ~120 occurrences de la classe
``animate-pulse``) - PAS une page d'erreur/CAPTCHA, mais le tableau de
resultats n'est, dans CE cas, resolu que cote client (JavaScript execute
dans un vrai navigateur), le flux RSC serveur n'ayant pas eu le temps/la
decision de le resoudre avant de clore la reponse. ``parse_results_page``
leve correctement ``OddsPortalParsingError`` dans ce cas (fail-closed,
comportement voulu), mais cela signifie concretement que **la fiabilite de
la recuperation en direct (donc d'un rafraichissement automatise/planifie)
n'est PAS etablie** : on sait que le format de donnees existe et est
parsable (d'ou les tests, bases sur la capture reelle reussie), mais pas
qu'une requete HTTP simple le recupere de facon repetable. Deux pistes non
explorees par manque de temps a ce stade : (a) identifier l'appel
fetch/XHR reel que le navigateur declenche cote client pour resoudre ce
Suspense (probablement un point de terminaison JSON plus propre qu'un
scraping HTML, mais nécessite d'analyser les bundles JS minifies
references, ex. ``/_next/static/chunks/1129vlj2svyid.js``) ; (b) repasser
par un navigateur pilote (Playwright/CDP) comme le POC precedent le
faisait pour une raison differente - ce qui annule l'argument "pas besoin
de Playwright" avance plus haut. A NE PAS CONSIDERER COMME UN CONNECTEUR
PRET POUR UNE AUTOMATISATION PLANIFIEE avant resolution de ce point.

FORMAT SOURCE (reverse-engineering direct depuis une reponse HTTP reelle,
PAS depuis une documentation officielle - OddsPortal n'en publie aucune) :
chaque page embarque plusieurs appels ``self.__next_f.push([1,"<chaine JS
echappee>"])`` (protocole de streaming "React Server Components"). Un de
ces blocs, une fois de-echappe comme une chaine JSON standard, contient un
grand nombre d'objets JSON `{"id": <int>, "is-double": ..., ...}` - un par
match - inclus en texte brut dans le flux. ``extract_match_objects``
localise chaque objet par un marqueur de debut non ambigu puis par
equilibrage d'accolades (PAS un regex par champ fragile) avant de le
valider par ``json.loads`` individuellement - un objet corrompu/tronque est
ignore et compte, jamais fabrique ni devine.

LIMITES CONNUES, DOCUMENTEES (pas masquees) :

1. **Semantique des cotes NON CONFIRMEE.** Chaque match expose un tableau
   ``odds`` de 3 lignes (``bettingTypeId=1``, marche 1X2) portant chacune un
   ``outcomeResultId``/``outcomeId`` opaques - aucune des deux cles
   n'encode de facon fiable "domicile/nul/exterieur" (observe sur un cas
   reel : ``outcomeResultId`` vaut 1, 2, 2 - PAS 1/2/3 - pour les 3 lignes
   home/nul/exterieur attendues). ``OddsPortalOddsQuote`` expose donc les
   cotes BRUTES, sans label home/draw/away invente - toute utilisation en
   aval doit d'abord etablir empiriquement la correspondance (ex. en
   comparant a des cotes Football-Data.co.uk connues pour les memes
   matchs) avant de pretendre labelliser une cote comme "domicile".
2. **``partialresult`` non interprete.** Le champ brut (ex. ``"1:0, 1:1"``)
   n'est PAS un score mi-temps confirme (format non documente par
   OddsPortal) - expose tel quel (``raw_partial_result``), jamais parse en
   buts mi-temps.
3. **Une seule page "results" recuperee par appel** (pas de pagination
   suivie) - couvre les matchs les plus recents d'une competition (~50
   dans les tests reels), suffisant pour l'usage vise ("resultats a jour
   des que termines"), PAS pour reconstituer un historique complet de
   saison.
4. **CGU/ToS d'oddsportal.com non verifiees.** Aucune lecture de
   ``robots.txt`` ni des conditions d'utilisation n'a ete faite avant
   d'ecrire ce module - risque accepte explicitement par l'utilisateur
   (echange du 2026-10-10), PAS une validation juridique.
5. **Fuseau horaire** : ``date-start-timestamp`` est un epoch Unix (UTC par
   construction) - converti ici en ``datetime`` UTC conscient du fuseau,
   contrairement au calendrier OpenFootball (``openfootball_calendar.py``)
   dont l'heure publiee reste naive par absence de confirmation. Ce point
   PRECIS (que ``date-start-timestamp`` soit bien UTC) repose sur la
   semantique standard d'un timestamp Unix, pas sur une confirmation
   OddsPortal explicite.

Ce module ne fait QUE lire des pages publiques et n'ecrit jamais sur
oddsportal.com. Usage de recherche personnel vise (quelques requetes
ponctuelles ou un rafraichissement periodique raisonnable), jamais un
crawl massif."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.request import Request, urlopen

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# URLs "results" verifiees reellement accessibles (HTTP 200) le 2026-10-10
# depuis cette session - PAS une liste exhaustive, uniquement les 3
# competitions suivies par le reste du depot (voir scripts/predict_match.py).
COMPETITION_RESULTS_URLS: dict[str, str] = {
    "ligue1": "https://www.oddsportal.com/football/france/ligue-1/results/",
    "liga": "https://www.oddsportal.com/football/spain/laliga/results/",
    "premier_league": "https://www.oddsportal.com/football/england/premier-league/results/",
}

_NEXT_F_PUSH_MARKER = "self.__next_f.push([1,"
_MATCH_OBJECT_START = re.compile(r'\{"id":\d+,"is-double"')


class OddsPortalFetchError(RuntimeError):
    """Echec reseau (timeout, DNS, HTTP en erreur) - propage tel quel par
    ``fetch_results_page``, jamais absorbe en page vide."""


class OddsPortalParsingError(RuntimeError):
    """La page recuperee ne contient aucun bloc de donnees reconnu (format
    du site change, page d'erreur/CAPTCHA servie a la place) - FAIL-CLOSED,
    jamais une liste vide silencieuse presentee comme un resultat valide."""


@dataclass(frozen=True)
class OddsPortalOddsQuote:
    """UNE ligne brute du tableau ``odds`` d'un match - voir limite 1 du
    docstring du module : ``outcome_result_id``/``outcome_id`` sont opaques,
    AUCUN label home/draw/away n'est invente ici."""

    betting_type_id: int
    scope_id: int
    outcome_result_id: int
    outcome_id: str
    avg_odds: float | None
    max_odds: float | None


@dataclass(frozen=True)
class OddsPortalMatch:
    """UN match tel qu'expose par une page "results" OddsPortal - champs
    non ambigus uniquement (voir limites 1/2 du docstring du module pour ce
    qui est deliberement exclu/laisse brut)."""

    event_id: int
    tournament_name: str
    home_team: str
    away_team: str
    kickoff_utc: datetime
    status: str  # ex. "Finished" - valeur brute du site, jamais traduite
    is_finished: bool
    home_goals: int | None
    away_goals: int | None
    venue: str | None
    raw_partial_result: str | None
    odds: tuple[OddsPortalOddsQuote, ...]
    source_url: str


def fetch_results_page(
    url: str,
    *,
    http_get: "Callable[[str], str] | None" = None,
    timeout: float = 20.0,
) -> str:
    """Seule fonction de ce module touchant reellement le reseau - point
    d'injection ``http_get`` EXCLUSIVEMENT destine aux tests (meme
    convention que ``current_season_updater.fetch_understat_raw_played_matches``).
    Laisse toute ``OSError``/``urllib.error.*`` remonter transformee en
    ``OddsPortalFetchError`` explicite, jamais une page vide silencieuse."""
    if http_get is not None:
        return http_get(url)
    request = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_bytes = response.read()
    except OSError as exc:
        raise OddsPortalFetchError(f"Recuperation HTTP echouee pour {url} : {exc}") from exc
    return raw_bytes.decode("utf-8", errors="strict")


def _find_next_f_string_literals(html: str) -> list[str]:
    """Localise chaque appel ``self.__next_f.push([1,"..."])`` et retourne
    le contenu TOUJOURS ENCORE ECHAPPE (pas de-echappe ici) de la chaine JS
    entre guillemets, en respectant les echappements ``\\"``/``\\\\`` - PAS
    un regex ``.*?`` naif (qui s'arreterait au premier guillemet echappe
    rencontre, tronquant systematiquement le contenu)."""
    literals: list[str] = []
    search_start = 0
    while True:
        marker_idx = html.find(_NEXT_F_PUSH_MARKER, search_start)
        if marker_idx == -1:
            break
        quote_start = html.find('"', marker_idx + len(_NEXT_F_PUSH_MARKER))
        if quote_start == -1:
            break
        i = quote_start + 1
        escaped = False
        while i < len(html):
            ch = html[i]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                break
            i += 1
        literals.append(html[quote_start + 1 : i])
        search_start = i + 1
    return literals


def _select_match_bearing_chunk(literals: list[str]) -> str | None:
    """Choisit le premier bloc contenant au moins un marqueur de match
    reconnu - plusieurs blocs independants existent par page (navigation,
    scripts divers), seul un sous-ensemble porte les donnees de match.

    IMPORTANT : ``literal`` est encore la chaine JS ECHAPPEE (pas
    de-echappee - voir ``_find_next_f_string_literals``), donc chaque
    guillemet JSON y apparait precede d'un ``\\`` (ex. ``\\"home-name\\"``).
    On cherche donc le marqueur SANS les guillemets qui l'encadrent
    (``home-name`` et pas ``"home-name"``) - une recherche avec guillemets
    ne correspondrait jamais ici."""
    for literal in literals:
        if "home-name" in literal and "is-double" in literal:
            return literal
    return None


def _extract_balanced_json_object(text: str, start_idx: int) -> str:
    """Extrait la sous-chaine ``{...}`` equilibree (accolades, en ignorant
    celles situees a l'interieur de chaines JSON) commencant a
    ``start_idx`` - PAS un regex non-greedy fragile sur un objet dont la
    profondeur/presence de guillemets internes est inconnue a l'avance."""
    depth = 0
    in_string = False
    escaped = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start_idx : i + 1]
    raise OddsPortalParsingError(f"Objet JSON non equilibre a partir de l'index {start_idx} - page tronquee ?")


def extract_match_objects(unescaped_chunk: str) -> list[dict]:
    """Retourne chaque objet JSON de match valide trouve dans
    ``unescaped_chunk`` (texte DEJA de-echappe, voir ``parse_results_page``).
    Un objet dont les accolades sont desequilibrees ou dont le JSON est
    invalide est ignore (pas remonte comme un echec global) - un seul
    objet corrompu ne doit jamais faire echouer l'extraction des 49 autres."""
    objects: list[dict] = []
    for match in _MATCH_OBJECT_START.finditer(unescaped_chunk):
        try:
            obj_text = _extract_balanced_json_object(unescaped_chunk, match.start())
        except OddsPortalParsingError:
            continue
        try:
            obj = json.loads(obj_text)
        except json.JSONDecodeError:
            continue
        if "home-name" in obj and "away-name" in obj:
            objects.append(obj)
    return objects


def _parse_odds_quote(raw: dict) -> OddsPortalOddsQuote:
    return OddsPortalOddsQuote(
        betting_type_id=raw["bettingTypeId"],
        scope_id=raw["scopeId"],
        outcome_result_id=raw["outcomeResultId"],
        outcome_id=raw["outcomeId"],
        avg_odds=raw.get("avgOdds"),
        max_odds=raw.get("maxOdds"),
    )


def _parse_goals(raw_result: object) -> int | None:
    """``homeResult``/``awayResult`` sont des chaines (ex. ``"2"``) pour un
    match termine, ou une chaine vide/absente sinon - jamais devine a 0."""
    if not isinstance(raw_result, str) or raw_result == "":
        return None
    try:
        return int(raw_result)
    except ValueError:
        return None


def parse_oddsportal_match(obj: dict, *, source_url: str) -> OddsPortalMatch:
    """Convertit UN objet JSON brut (voir ``extract_match_objects``) en
    ``OddsPortalMatch`` - fail-closed (``KeyError``/``OddsPortalParsingError``
    propagees) si un champ non-optionnel attendu est absent, jamais une
    valeur par defaut fabriquee."""
    try:
        status = obj["event-stage-name"]
        odds_raw = obj.get("odds") or []
        return OddsPortalMatch(
            event_id=obj["id"],
            tournament_name=obj.get("tournament-name", ""),
            home_team=obj["home-name"],
            away_team=obj["away-name"],
            kickoff_utc=datetime.fromtimestamp(obj["date-start-timestamp"], tz=timezone.utc),
            status=status,
            is_finished=status == "Finished",
            home_goals=_parse_goals(obj.get("homeResult")),
            away_goals=_parse_goals(obj.get("awayResult")),
            venue=obj.get("venue") or None,
            raw_partial_result=obj.get("partialresult") or None,
            odds=tuple(_parse_odds_quote(q) for q in odds_raw),
            source_url=source_url,
        )
    except KeyError as exc:
        raise OddsPortalParsingError(f"Champ obligatoire absent dans l'objet match OddsPortal : {exc}") from exc


def parse_results_page(html: str, *, source_url: str) -> list[OddsPortalMatch]:
    """Orchestration complete HTML -> blocs ``__next_f`` -> bloc porteur de
    matchs -> de-echappement -> objets JSON -> ``OddsPortalMatch``.
    FAIL-CLOSED : leve ``OddsPortalParsingError`` si aucun bloc porteur de
    matchs n'est trouve (format du site change / page CAPTCHA/erreur
    servie) - ne retourne JAMAIS une liste vide comme s'il s'agissait d'un
    jour sans aucun match."""
    literals = _find_next_f_string_literals(html)
    chunk = _select_match_bearing_chunk(literals)
    if chunk is None:
        raise OddsPortalParsingError(
            "Aucun bloc '__next_f.push' porteur de donnees de match trouve - "
            "format de page OddsPortal probablement different de celui attendu "
            "(verifie le 2026-10-10), ou page d'erreur/CAPTCHA servie a la place."
        )
    try:
        unescaped = json.loads('"' + chunk + '"')
    except json.JSONDecodeError as exc:
        raise OddsPortalParsingError(f"Bloc '__next_f.push' non de-echappable comme chaine JSON : {exc}") from exc

    raw_objects = extract_match_objects(unescaped)
    if not raw_objects:
        raise OddsPortalParsingError(
            "Bloc de donnees trouve mais aucun objet de match valide extrait - "
            "format interne probablement different de celui attendu (verifie le 2026-10-10)."
        )
    return [parse_oddsportal_match(obj, source_url=source_url) for obj in raw_objects]


def fetch_and_parse_results(
    competition: str,
    *,
    http_get: "Callable[[str], str] | None" = None,
) -> list[OddsPortalMatch]:
    """Point d'entree pratique : ``competition`` doit etre une cle de
    ``COMPETITION_RESULTS_URLS`` (``ligue1``/``liga``/``premier_league``) -
    toute autre valeur leve ``KeyError`` explicitement (pas de competition
    "par defaut")."""
    url = COMPETITION_RESULTS_URLS[competition]
    html = fetch_results_page(url, http_get=http_get)
    return parse_results_page(html, source_url=url)
