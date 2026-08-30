"""Schemas normalises Polymarket/Pomet (Phase L, etape 4).

AUCUN champ n'est presume toujours renseigne par une source brute reelle
(Gamma API / CLOB API / Data API / Pomet) : l'audit reseau de cette phase
n'a pas pu verifier directement la forme exacte d'une reponse reelle
(environnement bloque, voir docs/polymarket_pomet_data_audit.md section 9)
- seuls les identifiants strictement necessaires a l'usage interne
(identite, timestamp de decision) sont obligatoires ; tout le reste reste
``Optional`` et n'est jamais rempli par une valeur inventee lors du
parsing (``markets.py``/``trades.py``).

``Market.outcome`` est une CONVENTION INTERNE explicite (non verifiee
contre la structure reelle de la Gamma API) : l'issue gagnante une fois le
marche resolu, ``None`` tant qu'il ne l'est pas ou si l'information n'est
pas disponible. A confirmer lors du prochain audit avec acces reseau."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Market:
    """Un marche Polymarket (typiquement un cote binaire Yes/No d'un
    evenement). ``event_id`` regroupe plusieurs marches lies (ex. les
    differentes lignes O/U d'un meme match) - convention Polymarket
    documentee publiquement (Gamma API : un ``event`` regroupe des
    ``markets``), pas une invention de ce module."""

    market_id: str
    source: str  # ex. "polymarket_gamma_api", "pomet" - tracabilite de provenance
    event_id: str | None = None
    title: str | None = None
    sport: str | None = None
    league: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    market_type: str | None = None  # ex. "moneyline", "over_under", "handicap" - non fige, voir etape 7
    outcome: str | None = None  # issue gagnante si resolu, cf. docstring module
    start_time: datetime | None = None
    end_time: datetime | None = None
    resolution_time: datetime | None = None


@dataclass(frozen=True)
class Trade:
    """Un trade individuel d'un wallet sur un marche. ``notional`` est
    toujours ``price * size`` si les deux sont connus - calcule au
    parsing (``trades.py``), jamais lu tel quel d'une source qui ne le
    fournirait pas explicitement."""

    wallet_id: str
    market_id: str
    timestamp_utc: datetime
    side: str  # "BUY" | "SELL"
    price: float
    size: float
    source: str
    trade_id: str | None = None
    event_id: str | None = None
    outcome: str | None = None
    notional: float | None = None


@dataclass(frozen=True)
class Trader:
    """Metadonnee statique d'un wallet. Ne porte JAMAIS de statistique
    (ROI, win rate, ranking, volume) - toute statistique est une fonction
    d'un ``decision_time`` donne (risque de fuite sinon, voir
    ``TraderStatsAsOf``/``pit.py``, etape 5)."""

    wallet_id: str
    source: str
    first_seen_time: datetime | None = None


@dataclass(frozen=True)
class TraderStatsAsOf:
    """Statistiques d'un wallet calculees EXCLUSIVEMENT a partir de
    l'information disponible avant ``as_of`` (etape 5). Objet immuable et
    horodate explicitement - ne doit jamais etre reutilise pour un autre
    ``decision_time`` que celui pour lequel il a ete calcule."""

    wallet_id: str
    as_of: datetime
    n_trades: int
    n_resolved_trades: int  # trades dont le marche est resolu avant `as_of`
    volume_notional: float
    realized_pnl: float | None  # None si n_resolved_trades == 0
    win_rate: float | None  # None si n_resolved_trades == 0
    open_position_count: int


@dataclass(frozen=True)
class TraderInformationAsOf:
    """Sortie complete de ``pit.get_trader_information_as_of`` - le seul
    point d'entree destine a alimenter une future analyse (etape 5/8)."""

    wallet_id: str
    as_of: datetime
    trades_as_of: tuple[Trade, ...]
    positions_as_of: dict[str, dict[str, float]]  # market_id -> outcome -> taille nette
    stats_as_of: TraderStatsAsOf


@dataclass(frozen=True)
class MarketMatchResult:
    """Resultat du rattachement etape 6 - jamais une correspondance
    forcee : soit un ``match_id`` unique, soit un code de raison explicite
    (``reason_codes.POLYMARKET_MATCH_UNMATCHED``/``_AMBIGUOUS``)."""

    polymarket_market_id: str
    match_id: str | None
    reason_code: str | None
    candidates: tuple[str, ...] = ()  # match_id candidats en cas d'ambiguite
