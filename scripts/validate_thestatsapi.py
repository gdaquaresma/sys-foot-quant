"""Outil de VALIDATION EMPIRIQUE de TheStatsAPI (et The Odds API en
repli) pour l'automatisation des cotes pre-match du Shadow Mode.

CE N'EST PAS UN MODULE DE PRODUCTION. Jamais importe par
``final_engine/``, ``scripts/predict_match.py``, R1/R2/R3/R4 ou
``shadow_mode/``. Ce script existe uniquement pour repondre, avec une
VRAIE reponse API, aux questions A-L de
``research/thestatsapi_validation.md`` - il ne doit jamais etre execute
avec une cle fabriquee, et ne doit jamais presenter une donnee
synthetique comme une observation reelle.

PRECONDITION UNIQUE : la variable d'environnement ``THESTATSAPI_API_KEY``
(et optionnellement ``THE_ODDS_API_KEY`` pour le controle de repli) doit
etre definie dans l'environnement d'execution - JAMAIS en dur dans ce
fichier, jamais dans un fichier commite, jamais affichee dans la sortie
de ce script (voir ``_load_api_key`` : la cle n'est jamais loguee, meme
partiellement).

Si la cle est absente, ce script s'arrete IMMEDIATEMENT avec un message
explicite - il ne fabrique JAMAIS de reponse pour compenser, conformement
a la discipline deja appliquee dans tout ce projet (voir
``research/thestatsapi_validation.md``, deux tentatives precedentes,
commits ``dbef697``/``df73664``/``5bc2781``).

RESERVE IMPORTANTE SUR LES ENDPOINTS CI-DESSOUS (meme discipline que
``research/xg_feasibility/understat_source.py``, qui documente une
reserve identique pour Understat) : le chemin exact de l'API REST
TheStatsAPI (base URL, nom d'en-tete d'authentification, structure de
l'endpoint de recherche de match) n'a PAS pu etre verifie contre une
reponse HTTP reelle avant l'ecriture de ce script - l'acces reseau a
thestatsapi.com est bloque par la politique reseau de cette session
(403, confirme independamment, voir
``research/thestatsapi_validation.md`` section 4). Les constantes
``THESTATSAPI_BASE_URL``/``_search_fixture_url``/``_historical_odds_url``
ci-dessous sont donc un MEILLEUR EFFORT fonde sur la documentation
publique (pages produit, jamais une specification OpenAPI complete) -
PAS confirme. Lors de la premiere execution reelle (compte TheStatsAPI
+ acces reseau), verifiez ces constantes contre la documentation
exacte fournie a votre compte (souvent un exemple curl direct sur le
tableau de bord) et corrigez-les ICI plutot que dans le code appelant si
elles sont fausses - exactement la meme consigne que
``understat_source.py::parse_matches_from_html``.

La logique de PARSING/PIT (``parse_thestatsapi_odds_response``,
``select_last_snapshot_before``) est en revanche PURE et deja testee
(``tests/unit/test_validate_thestatsapi.py``) - c'est elle qui repond
reellement aux questions PIT, independamment de l'exactitude des
endpoints HTTP ci-dessus.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Config reseau - MEILLEUR EFFORT, NON CONFIRME (voir reserve du docstring).
# A corriger ICI apres la premiere execution reelle si les valeurs sont fausses.
# ---------------------------------------------------------------------------

THESTATSAPI_BASE_URL = "https://api.thestatsapi.com/v1"
THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"

_REQUEST_TIMEOUT_SECONDS = 15.0

_TARGET_BOOKMAKERS = ("Bet365", "Pinnacle")
_TARGET_LINE = 2.5


class ValidationBlockedError(RuntimeError):
    """Levee quand le test ne peut PAS avoir lieu (cle absente, reseau
    inaccessible, endpoint introuvable) - jamais confondue avec un
    resultat de test negatif sur les donnees elles-memes."""


def _load_api_key(var_name: str) -> str | None:
    """Lit une cle depuis l'environnement UNIQUEMENT - jamais un fichier,
    jamais une valeur par defaut. Ne loggue, n'imprime et ne renvoie
    JAMAIS la cle elle-meme dans un message d'erreur ou un rapport."""
    return os.environ.get(var_name) or None


@dataclass(frozen=True)
class ReferenceMatch:
    """Un match deja present dans notre corpus, avec ses cotes B365/
    Pinnacle DEJA connues (Football-Data.co.uk, lecture seule) - utilise
    comme temoin de comparaison, jamais comme une preuve sur le
    fournisseur teste (voir research/thestatsapi_validation.md section 8)."""

    label: str
    competition: str
    home_team: str
    away_team: str
    kickoff_utc: datetime
    known_b365_over_2_5: float
    known_b365_under_2_5: float
    known_pinnacle_over_2_5: float
    known_pinnacle_under_2_5: float


REFERENCE_MATCHES: tuple[ReferenceMatch, ...] = (
    ReferenceMatch(
        label="Chelsea vs Arsenal (Premier League 2024/25)",
        competition="premier_league",
        home_team="Chelsea",
        away_team="Arsenal",
        kickoff_utc=datetime(2024, 11, 10, 16, 30, 0, tzinfo=timezone.utc),
        known_b365_over_2_5=1.73,
        known_b365_under_2_5=2.10,
        known_pinnacle_over_2_5=1.72,
        known_pinnacle_under_2_5=2.21,
    ),
    ReferenceMatch(
        label="Real Madrid vs Barcelona (La Liga 2024/25)",
        competition="liga",
        home_team="Real Madrid",
        away_team="Barcelona",
        kickoff_utc=datetime(2024, 10, 26, 20, 0, 0, tzinfo=timezone.utc),
        known_b365_over_2_5=1.40,
        known_b365_under_2_5=3.00,
        known_pinnacle_over_2_5=1.43,
        known_pinnacle_under_2_5=2.96,
    ),
    ReferenceMatch(
        label="Paris SG vs Marseille (Ligue 1 2024/25)",
        competition="ligue1",
        home_team="Paris SG",
        away_team="Marseille",
        kickoff_utc=datetime(2025, 3, 16, 19, 45, 0, tzinfo=timezone.utc),
        known_b365_over_2_5=1.37,
        known_b365_under_2_5=3.00,
        known_pinnacle_over_2_5=1.40,
        known_pinnacle_under_2_5=3.07,
    ),
)

# Points de controle PIT demandes (etape 4) - toujours relatifs au kickoff
# du match, jamais a l'heure d'execution de ce script.
_PIT_CHECKPOINTS_BEFORE_KICKOFF = (
    timedelta(hours=24),
    timedelta(hours=12),
    timedelta(hours=6),
    timedelta(hours=1),
)


@dataclass(frozen=True)
class OddsSnapshot:
    """Un point d'observation normalise - INDEPENDANT du fournisseur,
    construit uniquement a partir de champs REELLEMENT presents dans une
    reponse (jamais une valeur de repli inventee pour un champ absent)."""

    bookmaker: str
    market: str
    line: float
    over_price: float | None
    under_price: float | None
    timestamp: datetime  # toujours timezone-aware, jamais suppose UTC silencieusement
    source: str
    raw_field_names: tuple[str, ...] = field(default_factory=tuple)


def _require_aware(ts_raw: object, source: str) -> datetime:
    """Meme garde-fou que ``polymarket/trades.py::_parse_timestamp`` :
    un timestamp sans fuseau explicite est un risque de fuite PIT, jamais
    suppose UTC silencieusement."""
    if isinstance(ts_raw, (int, float)):
        return datetime.fromtimestamp(float(ts_raw), tz=timezone.utc)
    if isinstance(ts_raw, str):
        parsed = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(
                f"[{source}] timestamp sans fuseau horaire explicite : {ts_raw!r} - "
                "jamais suppose UTC silencieusement (risque de fuite PIT)."
            )
        return parsed
    raise ValueError(f"[{source}] timestamp non interpretable : {ts_raw!r}")


def parse_thestatsapi_odds_response(raw: dict, source: str = "thestatsapi") -> list[OddsSnapshot]:
    """Extrait les observations Bet365/Pinnacle Over/Under 2.5 d'une
    reponse TheStatsAPI. Fonction PURE (aucun acces reseau), testable
    sans cle - voir tests/unit/test_validate_thestatsapi.py.

    RESERVE (meme discipline que markets.py/trades.py Polymarket) : le
    nom exact des cles JSON ci-dessous (``bookmaker``/``market``/
    ``line``/``prices``/``timestamp``) est un MEILLEUR EFFORT fonde sur
    la documentation publique, PAS confirme par une reponse reelle -
    a corriger ici, jamais dans le code appelant, des la premiere vraie
    reponse observee."""
    snapshots: list[OddsSnapshot] = []
    for entry in raw.get("odds", raw.get("data", [])):
        bookmaker = entry.get("bookmaker") or entry.get("book")
        if bookmaker not in _TARGET_BOOKMAKERS:
            continue
        market_name = entry.get("market") or entry.get("market_name")
        if market_name not in ("total_goals", "over_under", "totals"):
            continue
        line = entry.get("line")
        try:
            line_value = float(line)
        except (TypeError, ValueError):
            continue
        if line_value != _TARGET_LINE:
            continue
        ts_raw = entry.get("timestamp") or entry.get("updated_at") or entry.get("created_at")
        if ts_raw is None:
            # Jamais un timestamp invente - une observation sans horodatage
            # est structurellement inutilisable pour le PIT, exclue explicitement.
            continue
        timestamp = _require_aware(ts_raw, source)
        over_price = entry.get("over_price") if entry.get("over_price") is not None else entry.get("over")
        under_price = entry.get("under_price") if entry.get("under_price") is not None else entry.get("under")
        snapshots.append(
            OddsSnapshot(
                bookmaker=bookmaker,
                market=str(market_name),
                line=line_value,
                over_price=(float(over_price) if over_price is not None else None),
                under_price=(float(under_price) if under_price is not None else None),
                timestamp=timestamp,
                source=source,
                raw_field_names=tuple(sorted(entry.keys())),
            )
        )
    return snapshots


def parse_the_odds_api_historical_response(raw: dict, source: str = "the-odds-api") -> list[OddsSnapshot]:
    """Meme role que ci-dessus, pour The Odds API (structure documentee :
    ``data.bookmakers[].markets[].outcomes[]``, ``timestamp`` au niveau
    racine de chaque snapshot historique) - MEILLEUR EFFORT NON CONFIRME,
    meme reserve que ci-dessus."""
    snapshots: list[OddsSnapshot] = []
    ts_raw = raw.get("timestamp")
    if ts_raw is None:
        return snapshots
    timestamp = _require_aware(ts_raw, source)
    data = raw.get("data") or {}
    for bookmaker_entry in data.get("bookmakers", []):
        bookmaker = bookmaker_entry.get("title") or bookmaker_entry.get("key")
        if bookmaker not in _TARGET_BOOKMAKERS and str(bookmaker).lower() not in (
            b.lower() for b in _TARGET_BOOKMAKERS
        ):
            continue
        for market in bookmaker_entry.get("markets", []):
            if market.get("key") != "totals":
                continue
            over_price = under_price = None
            for outcome in market.get("outcomes", []):
                if float(outcome.get("point", -1)) != _TARGET_LINE:
                    continue
                name = str(outcome.get("name", "")).lower()
                if name == "over":
                    over_price = outcome.get("price")
                elif name == "under":
                    under_price = outcome.get("price")
            if over_price is None and under_price is None:
                continue
            snapshots.append(
                OddsSnapshot(
                    bookmaker=str(bookmaker),
                    market="totals",
                    line=_TARGET_LINE,
                    over_price=(float(over_price) if over_price is not None else None),
                    under_price=(float(under_price) if under_price is not None else None),
                    timestamp=timestamp,
                    source=source,
                    raw_field_names=tuple(sorted(bookmaker_entry.keys())),
                )
            )
    return snapshots


def select_last_snapshot_before(snapshots: list[OddsSnapshot], decision_time: datetime) -> OddsSnapshot | None:
    """LE coeur de la regle PIT du projet : ``timestamp < decision_time``,
    jamais ``<=``. Retourne le snapshot valide le plus RECENT (celui
    qu'un vrai decideur pre-match aurait effectivement connu), ou
    ``None`` si aucun n'existe - jamais une extrapolation."""
    eligible = [s for s in snapshots if s.timestamp < decision_time]
    if not eligible:
        return None
    return max(eligible, key=lambda s: s.timestamp)


def diagnose_pit_granularity(snapshots: list[OddsSnapshot], kickoff_utc: datetime) -> str:
    """Classe la granularite historique REELLEMENT observee (jamais
    supposee) - repond explicitement a l'etape 4 : si moins de 3
    observations distinctes existent avant kickoff, la reconstruction
    PIT fine (T-24h/T-12h/T-6h/T-1h) n'est PAS garantie."""
    distinct_before_kickoff = sorted({s.timestamp for s in snapshots if s.timestamp < kickoff_utc})
    if len(distinct_before_kickoff) == 0:
        return "AUCUNE OBSERVATION AVANT KICKOFF - PIT HISTORIQUE INSUFFISAMMENT GARANTI"
    if len(distinct_before_kickoff) <= 2:
        return (
            f"SEULEMENT {len(distinct_before_kickoff)} OBSERVATION(S) DISTINCTE(S) AVANT KICKOFF "
            "(probable opening/last_seen) - PIT HISTORIQUE INSUFFISAMMENT GARANTI pour une "
            "reconstruction fine (T-24h/T-12h/T-6h/T-1h)"
        )
    return f"{len(distinct_before_kickoff)} observations distinctes avant kickoff - serie temporelle exploitable"


@dataclass
class MatchValidationResult:
    match: ReferenceMatch
    provider: str
    error: str | None = None
    snapshots: list[OddsSnapshot] = field(default_factory=list)
    checkpoint_results: dict[str, OddsSnapshot | None] = field(default_factory=dict)
    granularity_diagnosis: str = ""


def _fetch_json(url: str, api_key: str, auth_header: str = "Authorization") -> dict:
    headers = {"Accept": "application/json"}
    if auth_header == "Authorization":
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers[auth_header] = api_key
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:  # nosec B310 - HTTPS uniquement
            raw = response.read()
    except HTTPError as exc:
        # Ne jamais inclure les en-tetes de la requete (contiendraient la cle) dans le message.
        raise ValidationBlockedError(f"HTTP {exc.code} sur {url} (reponse serveur, cle non affichee).") from exc
    except URLError as exc:
        raise ValidationBlockedError(f"Connexion impossible vers {url} : {exc.reason}.") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationBlockedError(f"Reponse non-JSON depuis {url}.") from exc


def validate_match_thestatsapi(match: ReferenceMatch, api_key: str) -> MatchValidationResult:
    """Tente le test empirique reel pour UN match. Ne fabrique JAMAIS de
    donnee en cas d'echec - toute erreur reseau/format est rapportee
    telle quelle dans ``MatchValidationResult.error``."""
    result = MatchValidationResult(match=match, provider="thestatsapi")
    try:
        # Etape A/B/C (identification) - endpoint de recherche, MEILLEUR EFFORT NON CONFIRME.
        search_url = (
            f"{THESTATSAPI_BASE_URL}/fixtures"
            f"?competition={match.competition}"
            f"&home_team={match.home_team}"
            f"&away_team={match.away_team}"
            f"&date={match.kickoff_utc.date().isoformat()}"
        )
        fixture_response = _fetch_json(search_url, api_key)
        fixtures = fixture_response.get("data") or fixture_response.get("fixtures") or []
        if not fixtures:
            raise ValidationBlockedError("Aucun fixture retourne pour ce match (endpoint de recherche a verifier).")
        fixture_id = fixtures[0].get("id") or fixtures[0].get("fixture_id")
        if fixture_id is None:
            raise ValidationBlockedError("Fixture trouve mais sans identifiant exploitable (id/fixture_id absent).")

        # Etape D-K (historique de cotes).
        odds_url = f"{THESTATSAPI_BASE_URL}/odds/historical?fixture_id={fixture_id}"
        odds_response = _fetch_json(odds_url, api_key)
        result.snapshots = parse_thestatsapi_odds_response(odds_response)
    except ValidationBlockedError as exc:
        result.error = str(exc)
        return result

    result.granularity_diagnosis = diagnose_pit_granularity(result.snapshots, match.kickoff_utc)
    for offset in _PIT_CHECKPOINTS_BEFORE_KICKOFF:
        decision_time = match.kickoff_utc - offset
        label = f"T-{int(offset.total_seconds() // 3600)}h"
        result.checkpoint_results[label] = select_last_snapshot_before(result.snapshots, decision_time)
    return result


def validate_match_the_odds_api(match: ReferenceMatch, api_key: str) -> MatchValidationResult:
    """Meme role que ci-dessus, pour The Odds API (controle de repli,
    etape 5) - appele uniquement si demande explicitement."""
    result = MatchValidationResult(match=match, provider="the-odds-api")
    try:
        all_snapshots: list[OddsSnapshot] = []
        for offset in _PIT_CHECKPOINTS_BEFORE_KICKOFF:
            checkpoint_time = match.kickoff_utc - offset
            url = (
                f"{THE_ODDS_API_BASE_URL}/historical/sports/soccer/odds"
                f"?apiKey={api_key}&regions=uk,eu&markets=totals"
                f"&date={checkpoint_time.isoformat()}"
            )
            response = _fetch_json(url, api_key, auth_header="apiKey-in-url")
            all_snapshots.extend(parse_the_odds_api_historical_response(response))
        result.snapshots = all_snapshots
    except ValidationBlockedError as exc:
        result.error = str(exc)
        return result

    result.granularity_diagnosis = diagnose_pit_granularity(result.snapshots, match.kickoff_utc)
    for offset in _PIT_CHECKPOINTS_BEFORE_KICKOFF:
        decision_time = match.kickoff_utc - offset
        label = f"T-{int(offset.total_seconds() // 3600)}h"
        result.checkpoint_results[label] = select_last_snapshot_before(result.snapshots, decision_time)
    return result


def format_report(results: list[MatchValidationResult]) -> str:
    lines: list[str] = []
    for r in results:
        lines.append(f"=== {r.match.label} [{r.provider}] ===")
        if r.error:
            lines.append(f"  TEST BLOQUE (aucune donnee fabriquee) : {r.error}")
            lines.append("")
            continue
        bookmakers_found = sorted({s.bookmaker for s in r.snapshots})
        lines.append(f"  Bookmakers OBSERVES reellement : {bookmakers_found or 'AUCUN'}")
        for bookmaker in _TARGET_BOOKMAKERS:
            present = bookmaker in bookmakers_found
            lines.append(f"  {bookmaker} disponible ? {'OUI (OBSERVE)' if present else 'NON (absent de la reponse reelle)'}")
        lines.append(f"  Granularite PIT : {r.granularity_diagnosis}")
        for label, snap in r.checkpoint_results.items():
            if snap is None:
                lines.append(f"  {label} avant kickoff : AUCUNE observation valide (timestamp < decision_time)")
            else:
                lines.append(
                    f"  {label} avant kickoff : {snap.bookmaker} O/U {snap.line} "
                    f"over={snap.over_price} under={snap.under_price} @ {snap.timestamp.isoformat()}"
                )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    thestatsapi_key = _load_api_key("THESTATSAPI_API_KEY")
    odds_api_key = _load_api_key("THE_ODDS_API_KEY")

    if thestatsapi_key is None and odds_api_key is None:
        sys.stderr.write(
            "ERREUR : aucune cle disponible (variables d'environnement "
            "THESTATSAPI_API_KEY / THE_ODDS_API_KEY absentes toutes les deux).\n"
            "Ce script ne fabrique jamais de donnee : arret immediat, "
            "aucun test execute.\n"
        )
        return 1

    results: list[MatchValidationResult] = []
    if thestatsapi_key is not None:
        for match in REFERENCE_MATCHES:
            results.append(validate_match_thestatsapi(match, thestatsapi_key))
    else:
        sys.stderr.write("THESTATSAPI_API_KEY absente - TheStatsAPI non teste.\n")

    if odds_api_key is not None:
        for match in REFERENCE_MATCHES:
            results.append(validate_match_the_odds_api(match, odds_api_key))
    else:
        sys.stderr.write("THE_ODDS_API_KEY absente - The Odds API non teste (repli non exerce).\n")

    print(format_report(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
