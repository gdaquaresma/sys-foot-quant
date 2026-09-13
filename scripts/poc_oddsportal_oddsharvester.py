"""POC/test isole de validation empirique d'OddsPortal + OddsHarvester
(fournisseur candidat gratuit de cotes pre-match, piste explorée après
l'abandon provisoire de TheStatsAPI - voir
``research/thestatsapi_validation.md``).

CE N'EST PAS UN MODULE DE PRODUCTION. Jamais importe par
``final_engine/``, ``scripts/predict_match.py``, R1/R2/R3/R4 ou
``shadow_mode/``. Aucune integration au moteur a ce stade - ce script
repond uniquement a la question posee dans
``research/oddsportal_validation.md`` : est-ce qu'OddsPortal/OddsHarvester
fournit gratuitement un historique de cotes suffisamment horodate pour
respecter notre regle PIT (``odds_timestamp < decision_time < kickoff``) ?

CE QUI A ETE VERIFIE EMPIRIQUEMENT DANS CETTE SESSION (voir
``check_oddsportal_network_access`` et le rapport pour le detail) :
1. L'acces reseau a ``oddsportal.com`` depuis CET environnement est
   BLOQUE par la politique d'egress obligatoire de la session (meme
   mecanisme, meme preuve via ``$HTTPS_PROXY/__agentproxy/status``, que
   pour TheStatsAPI/The Odds API/Polymarket/Understat/Football-Data -
   voir les rapports precedents). AUCUNE tentative de contournement n'a
   ete faite (consigne explicite de l'environnement et de l'utilisateur).
2. Le paquet ``oddsharvester`` (PyPI, MIT, Jordan TETE) EXISTE reellement
   et est activement maintenu (CI, tests, codecov) - verifie via
   ``pypi.org`` (accessible, contrairement a oddsportal.com lui-meme) et
   par extraction reelle du wheel ``oddsharvester-0.12.0-py3-none-any.whl``.
   Il requiert Python >=3.12 (cet environnement/venv est en 3.11) et
   Playwright - deux contraintes supplementaires, INDEPENDANTES du
   blocage reseau, qui empecheraient de toute facon une execution
   complete ici meme si oddsportal.com etait joignable.
3. Par LECTURE DIRECTE du code source reel d'OddsHarvester 0.12.0
   (``core/market_extraction/odds_parser.py::parse_odds_history_modal``,
   ``core/market_extraction/odds_history_extractor.py``), sans aucune
   execution reseau : l'outil est structurellement concu pour extraire,
   pour chaque cellule de cote (Over / Under separement) et chaque
   bookmaker, une liste ``odds_history`` de points ``{"timestamp":
   ISO8601, "odds": float}`` PLUS un ``opening_odds`` distinct - via un
   survol (hover) Playwright qui declenche une modale sur la page
   OddsPortal reelle. C'est un mecanisme reel documente par le CODE, pas
   seulement par une page marketing - mais son comportement sur une VRAIE
   page n'a jamais pu etre observe (reseau bloque) : le nombre reel de
   points renvoyes par OddsPortal pour un match donne reste NON VERIFIE.
4. DEUX DEFAUTS REELS, CONFIRMES PAR LE CODE (independants du reseau) :
   a) ``parse_odds_history_modal`` lit un texte affiche par OddsPortal au
      format ``"DD Mon, HH:MM"`` - SANS ANNEE - et complete l'annee avec
      ``datetime.now(UTC).year``, c'est-a-dire l'annee a laquelle le
      SCRAPING est execute, jamais l'annee reelle du mouvement de cote.
      Pour un match historique (notre cas d'usage exact), ceci produit
      une date FAUSSE des que l'annee de scraping differe de l'annee
      reelle du match. Demontre ici de facon reproductible en rejouant
      une version reproduite fidelement de leur fonction sur une entree
      HTML synthetique CONSTRUITE POUR RESPECTER EXACTEMENT LEURS PROPRES
      SELECTEURS CSS (jamais pour conclure quoi que ce soit sur les
      donnees reelles d'OddsPortal - uniquement pour verifier le
      comportement du CODE d'OddsHarvester lui-meme, un test unitaire du
      logiciel tiers, pas une fabrication de donnees sur la source).
   b) Les timestamps produits sont NAIFS (aucun fuseau horaire) -
      ``datetime.strptime(...).isoformat()`` sans tzinfo. Le fuseau reel
      dans lequel OddsPortal affiche ses heures n'a jamais ete confirme
      empiriquement (reseau bloque) - risque de fuite/decalage PIT si un
      futur connecteur suppose silencieusement UTC (le meme garde-fou que
      ``polymarket/trades.py::_parse_timestamp`` et
      ``validate_thestatsapi.py::_require_aware`` s'applique ici).

Ces deux defauts sont CORRIGIBLES cote appelant (voir
``correct_oddsharvester_year`` et ``attach_assumed_timezone``
ci-dessous) mais ne doivent JAMAIS etre ignores silencieusement par un
futur connecteur de production.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# 1. Verification reseau reelle (DNS / TCP brut / HTTPS via le proxy
#    obligatoire) - meme methode, deja utilisee et documentee, que pour
#    TheStatsAPI/The Odds API dans cette session. Ne contourne jamais le
#    proxy - se contente de le diagnostiquer.
# ---------------------------------------------------------------------------

ODDSPORTAL_HOST = "www.oddsportal.com"
_REQUEST_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class NetworkCheckResult:
    host: str
    dns_resolved: bool
    dns_detail: str
    raw_tcp_connect_ok: bool
    raw_tcp_detail: str
    https_via_proxy_ok: bool
    https_via_proxy_detail: str

    @property
    def blocked_at_proxy_only(self) -> bool:
        """DNS et TCP fonctionnent mais le HTTPS applicatif (via le proxy
        obligatoire de cette session) echoue - signature exacte d'un
        refus de politique d'organisation, pas d'un probleme reseau bas
        niveau ni d'un probleme cote serveur cible."""
        return self.dns_resolved and self.raw_tcp_connect_ok and not self.https_via_proxy_ok


def check_oddsportal_network_access(host: str = ODDSPORTAL_HOST) -> NetworkCheckResult:
    """Diagnostic reseau reel, couche par couche - jamais un contournement
    du proxy obligatoire de cette session (pas de handshake TLS manuel sur
    socket brut)."""
    try:
        addrinfo = socket.getaddrinfo(host, 443)
        dns_resolved = True
        dns_detail = f"{len(addrinfo)} enregistrement(s) resolu(s)."
    except OSError as exc:
        dns_resolved = False
        dns_detail = f"echec resolution DNS : {exc}"

    try:
        sock = socket.create_connection((host, 443), timeout=5)
        sock.close()
        raw_tcp_connect_ok = True
        raw_tcp_detail = "connexion TCP brute reussie (hors proxy)."
    except OSError as exc:
        raw_tcp_connect_ok = False
        raw_tcp_detail = f"echec connexion TCP brute : {exc}"

    try:
        request = Request(f"https://{host}/", headers={"Accept": "text/html"})
        with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS):  # nosec B310 - HTTPS uniquement, via le proxy obligatoire
            https_via_proxy_ok = True
            https_via_proxy_detail = "reponse HTTP recue via le proxy obligatoire."
    except HTTPError as exc:
        https_via_proxy_ok = False
        https_via_proxy_detail = f"HTTP {exc.code} via le proxy obligatoire (reponse serveur ou refus de politique)."
    except URLError as exc:
        https_via_proxy_ok = False
        https_via_proxy_detail = f"echec de connexion via le proxy obligatoire : {exc.reason}."

    return NetworkCheckResult(
        host=host,
        dns_resolved=dns_resolved,
        dns_detail=dns_detail,
        raw_tcp_connect_ok=raw_tcp_connect_ok,
        raw_tcp_detail=raw_tcp_detail,
        https_via_proxy_ok=https_via_proxy_ok,
        https_via_proxy_detail=https_via_proxy_detail,
    )


# ---------------------------------------------------------------------------
# 2. Reproduction fidele (MIT, attribuee) de la logique de parsing reelle
#    d'OddsHarvester 0.12.0, pour DEMONTRER (pas supposer) le bug d'annee
#    - jamais utilisee pour fabriquer une conclusion sur des donnees
#    OddsPortal reelles, uniquement pour tester le CODE tiers lui-meme
#    avec une entree HTML synthetique qui respecte exactement ses propres
#    selecteurs CSS.
#
# Source : oddsharvester 0.12.0, fichier
# ``oddsharvester/core/market_extraction/odds_parser.py``, methode
# ``OddsParser.parse_odds_history_modal`` (lignes 105-159 du wheel PyPI
# ``oddsharvester-0.12.0-py3-none-any.whl``).
# Copyright (c) 2024 Jordan TETE - MIT License.
# https://github.com/jordantete/OddsHarvester
# ---------------------------------------------------------------------------

import re as _re  # noqa: E402

from bs4 import BeautifulSoup  # noqa: E402

_FRACTIONAL_RE = _re.compile(r"^(\d+)/(\d+)$")
_MONTH_ABBR_RE = _re.compile(r"\bSept\b")


def _parse_odds_value_oddsharvester(text: str) -> float:
    m = _FRACTIONAL_RE.match(text)
    if m:
        return int(m.group(1)) / int(m.group(2)) + 1
    return float(text)


def parse_odds_history_modal_oddsharvester_v0_12_0(modal_html: str) -> dict:
    """Reproduction verbatim (MIT, voir en-tete de section) de
    ``OddsParser.parse_odds_history_modal`` d'OddsHarvester 0.12.0 -
    INCLUANT son bug d'annee tel quel, pour le demontrer reellement
    plutot que de l'affirmer sans preuve."""
    soup = BeautifulSoup(modal_html, "html.parser")
    odds_history: list[dict] = []
    cols = soup.select("div.flex.flex-row.gap-3 > div.flex.flex-col.gap-1")
    timestamps = cols[0].select("div.font-normal") if cols else []
    odds_values = cols[1].select("div.font-bold") if len(cols) > 1 else []

    for ts, odd in zip(timestamps, odds_values, strict=False):
        time_text = ts.get_text(strip=True)
        try:
            dt = datetime.strptime(_MONTH_ABBR_RE.sub("Sep", time_text), "%d %b, %H:%M")
            formatted_time = dt.replace(year=datetime.now(timezone.utc).year).isoformat()
        except ValueError:
            continue
        odds_history.append({"timestamp": formatted_time, "odds": _parse_odds_value_oddsharvester(odd.get_text(strip=True))})

    opening_odds = None
    opening_odds_block = soup.select_one("div.mt-2.gap-1")
    if opening_odds_block:
        opening_ts_div = opening_odds_block.select_one("div.flex.gap-1 div")
        opening_val_div = opening_odds_block.select_one("div.flex.gap-1 .font-bold")
        if opening_ts_div and opening_val_div:
            try:
                dt = datetime.strptime(_MONTH_ABBR_RE.sub("Sep", opening_ts_div.get_text(strip=True)), "%d %b, %H:%M")
                opening_odds = {
                    "timestamp": dt.replace(year=datetime.now(timezone.utc).year).isoformat(),
                    "odds": _parse_odds_value_oddsharvester(opening_val_div.get_text(strip=True)),
                }
            except ValueError:
                pass

    return {"odds_history": odds_history, "opening_odds": opening_odds}


# ---------------------------------------------------------------------------
# 3. Correctifs cote appelant (jamais silencieux) pour les deux defauts
#    reels ci-dessus - a appliquer systematiquement si ce fournisseur est
#    un jour retenu, jamais integres dans le code d'OddsHarvester lui-meme.
# ---------------------------------------------------------------------------


def correct_oddsharvester_year(naive_dt: datetime, reference_date: date, max_drift_days: int = 5) -> datetime:
    """Corrige le bug d'annee d'OddsHarvester 0.12.0 (voir docstring de
    module) en utilisant la seule information fiable toujours disponible
    pour un match cible : sa date de coup d'envoi. Essaie
    ``reference_date.year - 1``, ``reference_date.year`` et
    ``reference_date.year + 1``, ne garde que les candidats a moins de
    ``max_drift_days`` jours de ``reference_date`` (un mouvement de cote
    se produit toujours dans les jours qui precedent un match, jamais des
    mois avant/apres), et REFUSE (leve ``ValueError``) si zero ou plus
    d'un candidat correspond plutot que de deviner silencieusement."""
    candidates: list[datetime] = []
    for year in (reference_date.year - 1, reference_date.year, reference_date.year + 1):
        try:
            candidate = naive_dt.replace(year=year)
        except ValueError:
            continue  # ex. 29 fevrier sur une annee non bissextile
        if abs((candidate.date() - reference_date).days) <= max_drift_days:
            candidates.append(candidate)

    if len(candidates) != 1:
        raise ValueError(
            f"Correction d'annee ambigue ou impossible pour {naive_dt.isoformat()} avec reference "
            f"{reference_date.isoformat()} ({len(candidates)} candidat(s) valide(s), 1 attendu)."
        )
    return candidates[0]


def attach_assumed_timezone(naive_dt: datetime, assumed_tz: timezone) -> datetime:
    """OddsHarvester produit des timestamps naifs (voir docstring de
    module) - le fuseau reel d'affichage d'OddsPortal n'a jamais ete
    confirme empiriquement dans cette session (reseau bloque). Cette
    fonction force l'appelant a fournir explicitement le fuseau suppose
    plutot que de deduire UTC silencieusement - meme discipline que
    ``polymarket/trades.py::_parse_timestamp`` et
    ``validate_thestatsapi.py::_require_aware``."""
    if naive_dt.tzinfo is not None:
        raise ValueError(f"Timestamp deja timezone-aware, refus d'ecraser : {naive_dt.isoformat()}")
    return naive_dt.replace(tzinfo=assumed_tz)


# ---------------------------------------------------------------------------
# 4. Regle PIT centrale - identique, a l'identique, a celle deja etablie
#    et testee dans ``scripts/validate_thestatsapi.py``.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OddsMovement:
    bookmaker: str
    market: str
    outcome: str
    odds: float
    timestamp: datetime  # toujours timezone-aware au moment de la selection PIT
    source: str = "oddsportal_oddsharvester"


def select_last_snapshot_before(movements: list[OddsMovement], decision_time: datetime) -> OddsMovement | None:
    """Regle PIT stricte du projet : ``timestamp < decision_time``, jamais
    ``<=``. Retourne le mouvement valide le plus recent, ou ``None`` si
    aucun n'existe - jamais une extrapolation."""
    eligible = [m for m in movements if m.timestamp < decision_time]
    if not eligible:
        return None
    return max(eligible, key=lambda m: m.timestamp)


# ---------------------------------------------------------------------------
# 5. Matchs de reference (identiques a ceux de
#    ``scripts/validate_thestatsapi.py`` - comparabilite explicitement
#    demandee) et points de controle PIT demandes.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceMatch:
    label: str
    competition: str
    home_team: str
    away_team: str
    kickoff_utc: datetime


REFERENCE_MATCHES: tuple[ReferenceMatch, ...] = (
    ReferenceMatch(
        label="Chelsea vs Arsenal (Premier League 2024/25)",
        competition="england-premier-league",
        home_team="Chelsea",
        away_team="Arsenal",
        kickoff_utc=datetime(2024, 11, 10, 16, 30, 0, tzinfo=timezone.utc),
    ),
    ReferenceMatch(
        label="Real Madrid vs Barcelona (La Liga 2024/25)",
        competition="spain-laliga",
        home_team="Real Madrid",
        away_team="Barcelona",
        kickoff_utc=datetime(2024, 10, 26, 20, 0, 0, tzinfo=timezone.utc),
    ),
    ReferenceMatch(
        label="Paris SG vs Marseille (Ligue 1 2024/25)",
        competition="france-ligue-1",
        home_team="Paris SG",
        away_team="Marseille",
        kickoff_utc=datetime(2025, 3, 16, 19, 45, 0, tzinfo=timezone.utc),
    ),
)

_PIT_CHECKPOINTS_BEFORE_KICKOFF = (
    timedelta(hours=24),
    timedelta(hours=12),
    timedelta(hours=6),
    timedelta(hours=3),
    timedelta(hours=1),
    timedelta(minutes=30),
    timedelta(minutes=10),
)


def format_checkpoint_table(matches: list[ReferenceMatch], blocked_reason: str) -> str:
    """Aucune observation reelle n'existe (acces reseau bloque, voir
    ``check_oddsportal_network_access``) - chaque point de controle est
    rapporte tel quel comme NON VERIFIE, jamais fabrique."""
    lines: list[str] = []
    for match in matches:
        lines.append(f"=== {match.label} ===")
        for offset in _PIT_CHECKPOINTS_BEFORE_KICKOFF:
            total_seconds = int(offset.total_seconds())
            label = f"T-{total_seconds // 3600}h" if total_seconds >= 3600 else f"T-{total_seconds // 60}min"
            lines.append(f"  {label} avant kickoff : NON VERIFIE ({blocked_reason})")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    result = check_oddsportal_network_access()
    print(f"=== Diagnostic reseau reel vers {result.host} ===")
    print(f"  DNS       : {'OK' if result.dns_resolved else 'ECHEC'} - {result.dns_detail}")
    print(f"  TCP brut  : {'OK' if result.raw_tcp_connect_ok else 'ECHEC'} - {result.raw_tcp_detail}")
    print(f"  HTTPS (via le proxy obligatoire) : {'OK' if result.https_via_proxy_ok else 'ECHEC'} - {result.https_via_proxy_detail}")
    print()

    if result.https_via_proxy_ok:
        print(
            "Acces reseau disponible - ce script s'arrete ici volontairement : "
            "l'execution reelle d'OddsHarvester necessite Python >=3.12 et "
            "Playwright, hors du perimetre de ce POC de diagnostic. Voir "
            "research/oddsportal_validation.md pour la suite a donner."
        )
        return 0

    blocked_reason = "acces reseau a oddsportal.com bloque depuis cet environnement"
    print(f"ACCES BLOQUE : {blocked_reason}.")
    print("Aucune tentative de contournement du proxy obligatoire n'a ete faite.")
    print("Aucune donnee n'est fabriquee pour compenser cette absence d'acces reel.")
    print()
    print(format_checkpoint_table(list(REFERENCE_MATCHES), blocked_reason))
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
