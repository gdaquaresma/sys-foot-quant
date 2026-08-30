"""Validation des exports Polymarket fournis manuellement (Phase N,
etapes 4/10).

Ce module est le POINT D'ENTREE OBLIGATOIRE de tout futur export reel
(marches, trades, prix) avant qu'il n'alimente ``markets.py``/
``trades.py``/``pit.py``/``matching.py`` (Phase L, deja testes sur
donnees SYNTHETIQUES uniquement - voir garde-fou de chaque test). Il ne
fait AUCUN appel reseau et ne fabrique AUCUNE donnee - il ne fait que
REJETER explicitement ce qui est incoherent, jamais silencieusement.

N'importe et n'est importe par aucun module de ``final_engine`` (meme
regle d'isolation que le reste de ``polymarket/``, verifiee par
``tests/unit/test_polymarket_no_final_engine_dependency.py``)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Generic, TypeVar

from sys_foot_quant.polymarket.reason_codes import POLYMARKET_MATCH_AMBIGUOUS, POLYMARKET_MATCH_UNMATCHED
from sys_foot_quant.polymarket.schemas import Market, MarketMatchResult, PricePoint, Trade
from sys_foot_quant.polymarket.trades import parse_trade

# ---------------------------------------------------------------------------
# Codes de rejet stables (etape 10) - toute donnee ecartee porte l'un de
# ces codes, jamais une exclusion silencieuse.
# ---------------------------------------------------------------------------

IMPORT_REJECT_INVALID_TIMESTAMP = "IMPORT_REJECT_INVALID_TIMESTAMP"
IMPORT_REJECT_INCONSISTENT_IDENTIFIER = "IMPORT_REJECT_INCONSISTENT_IDENTIFIER"
IMPORT_REJECT_FUTURE_DATA_AS_PREMATCH = "IMPORT_REJECT_FUTURE_DATA_AS_PREMATCH"
IMPORT_REJECT_RESOLUTION_BEFORE_ITS_TIME = "IMPORT_REJECT_RESOLUTION_BEFORE_ITS_TIME"
IMPORT_REJECT_DUPLICATE = "IMPORT_REJECT_DUPLICATE"
IMPORT_REJECT_UNVERIFIED_TEAM_MAPPING = "IMPORT_REJECT_UNVERIFIED_TEAM_MAPPING"

ALL_IMPORT_REJECT_CODES = frozenset(
    {
        IMPORT_REJECT_INVALID_TIMESTAMP,
        IMPORT_REJECT_INCONSISTENT_IDENTIFIER,
        IMPORT_REJECT_FUTURE_DATA_AS_PREMATCH,
        IMPORT_REJECT_RESOLUTION_BEFORE_ITS_TIME,
        IMPORT_REJECT_DUPLICATE,
        IMPORT_REJECT_UNVERIFIED_TEAM_MAPPING,
    }
)

# ---------------------------------------------------------------------------
# Classification PIT a trois voies (etape 4) - vocabulaire explicite exige
# par la consigne, distinct du filtrage silencieux deja fait par
# ``pit.get_trader_information_as_of`` (Phase L).
# ---------------------------------------------------------------------------

INFORMATION_AVAILABLE_AT_DECISION_TIME = "INFORMATION_AVAILABLE_AT_DECISION_TIME"
INFORMATION_AFTER_DECISION_TIME = "INFORMATION_AFTER_DECISION_TIME"
MARKET_RESOLUTION_INFORMATION = "MARKET_RESOLUTION_INFORMATION"


def classify_information_timing(
    observation_timestamp_utc: datetime, decision_time: datetime, is_resolution_information: bool = False
) -> str:
    """Classe UNE observation (trade/prix) selon les trois categories de
    l'etape 4. Une information de resolution est TOUJOURS classee
    ``MARKET_RESOLUTION_INFORMATION``, independamment de son timestamp -
    une resolution ne doit jamais contaminer la prediction pre-match,
    meme si son timestamp brut precederait ``decision_time`` (ex. export
    corrompu, voir ``validate_market_resolution_consistency``)."""
    if is_resolution_information:
        return MARKET_RESOLUTION_INFORMATION
    if observation_timestamp_utc < decision_time:
        return INFORMATION_AVAILABLE_AT_DECISION_TIME
    return INFORMATION_AFTER_DECISION_TIME


# ---------------------------------------------------------------------------
# Rapport de validation generique
# ---------------------------------------------------------------------------

_T = TypeVar("_T")


@dataclass(frozen=True)
class ImportRejection:
    index: int
    raw_record: dict
    reason_code: str
    detail: str


@dataclass(frozen=True)
class ImportValidationReport(Generic[_T]):
    """``accepted`` ne contient QUE des enregistrements normalises et
    valides - ``rejected`` porte un code de raison stable pour chaque
    exclusion, jamais un simple ``None`` silencieux."""

    accepted: tuple[_T, ...]
    rejected: tuple[ImportRejection, ...]

    @property
    def n_accepted(self) -> int:
        return len(self.accepted)

    @property
    def n_rejected(self) -> int:
        return len(self.rejected)


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


def validate_trades_export(raw_records: list[dict], source: str) -> ImportValidationReport[Trade]:
    """Parse et valide un export brut de trades (etape 10) : timestamps
    invalides et identifiants incoherents rejetes explicitement (jamais
    un crash sur l'ensemble du fichier a cause d'une seule ligne
    corrompue), puis doublons detectes et rejetes (jamais silencieusement
    dedupliques comme le fait ``trades.deduplicate_trades`` en production
    - ici, un doublon dans un export MANUEL est un signal d'alerte a
    afficher, pas un non-evenement)."""
    parsed: list[tuple[int, dict, Trade]] = []
    rejected: list[ImportRejection] = []

    for i, raw in enumerate(raw_records):
        try:
            trade = parse_trade(raw, source=source)
        except ValueError as exc:
            message = str(exc)
            # Prefixe precis (jamais une sous-chaine generique comme
            # "timestamp", qui apparaitrait aussi dans le dict brut
            # echoue par le message "Trade brut incomplet... {raw!r}").
            code = (
                IMPORT_REJECT_INVALID_TIMESTAMP
                if message.startswith("Timestamp de trade")
                else IMPORT_REJECT_INCONSISTENT_IDENTIFIER
            )
            rejected.append(ImportRejection(index=i, raw_record=raw, reason_code=code, detail=message))
            continue
        parsed.append((i, raw, trade))

    seen: dict[tuple, int] = {}
    accepted: list[Trade] = []
    for i, raw, trade in parsed:
        key = (
            (trade.trade_id,)
            if trade.trade_id is not None
            else (None, trade.wallet_id, trade.market_id, trade.timestamp_utc, trade.side, trade.price, trade.size)
        )
        if key in seen:
            rejected.append(
                ImportRejection(
                    index=i,
                    raw_record=raw,
                    reason_code=IMPORT_REJECT_DUPLICATE,
                    detail=f"Doublon du trade a l'index {seen[key]} (cle {key!r}).",
                )
            )
            continue
        seen[key] = i
        accepted.append(trade)

    rejected.sort(key=lambda r: r.index)
    return ImportValidationReport(accepted=tuple(accepted), rejected=tuple(rejected))


def validate_premarket_trades_bundle(trades: list[Trade], decision_time: datetime) -> ImportValidationReport[Trade]:
    """Rejette explicitement tout trade presente comme « pre-match »
    (``decision_time`` donne) dont le timestamp est en realite
    ``>= decision_time`` (etape 10 : « donnees posterieures utilisees
    comme pre-match »). A la difference de ``pit.py`` (Phase L), qui
    filtre SILENCIEUSEMENT en production, cette fonction sert a AUDITER
    un export manuel et doit rendre chaque violation visible."""
    accepted: list[Trade] = []
    rejected: list[ImportRejection] = []
    for i, trade in enumerate(trades):
        if trade.timestamp_utc >= decision_time:
            rejected.append(
                ImportRejection(
                    index=i,
                    raw_record=trade.__dict__,
                    reason_code=IMPORT_REJECT_FUTURE_DATA_AS_PREMATCH,
                    detail=f"timestamp_utc={trade.timestamp_utc.isoformat()} >= decision_time={decision_time.isoformat()}.",
                )
            )
            continue
        accepted.append(trade)
    return ImportValidationReport(accepted=tuple(accepted), rejected=tuple(rejected))


# ---------------------------------------------------------------------------
# Prix
# ---------------------------------------------------------------------------

_PRICE_TS_KEYS = ("t", "timestamp", "timestamp_utc")
_PRICE_VALUE_KEYS = ("p", "price")


def _first_present(raw: dict, keys: tuple[str, ...]) -> object | None:
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    return None


def parse_price_point(raw: dict, market_id: str, source: str, token_id: str | None = None) -> PricePoint:
    """Normalise UN point brut de ``/prices-history`` (etape 10). Leve
    explicitement si le timestamp ou le prix est absent/non interpretable
    - jamais une valeur de repli inventee."""
    ts_raw = _first_present(raw, _PRICE_TS_KEYS)
    price_raw = _first_present(raw, _PRICE_VALUE_KEYS)
    if ts_raw is None or price_raw is None:
        raise ValueError(f"Point de prix incomplet (timestamp/prix manquant) : {raw!r}")

    if isinstance(ts_raw, (int, float)):
        timestamp_utc = datetime.fromtimestamp(float(ts_raw), tz=timezone.utc)
    elif isinstance(ts_raw, str):
        parsed = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(f"Timestamp de prix sans fuseau horaire explicite : {ts_raw!r}")
        timestamp_utc = parsed
    else:
        raise ValueError(f"Timestamp de prix non interpretable : {ts_raw!r}")

    return PricePoint(
        market_id=market_id,
        timestamp_utc=timestamp_utc,
        price=float(price_raw),
        source=source,
        token_id=token_id,
    )


def validate_price_history_export(
    raw_records: list[dict], market_id: str, source: str, token_id: str | None = None
) -> ImportValidationReport[PricePoint]:
    """Meme discipline que ``validate_trades_export``, pour une serie de
    prix : timestamps invalides rejetes explicitement, doublons
    (meme timestamp exact) rejetes plutot que silencieusement ecrases."""
    parsed: list[tuple[int, dict, PricePoint]] = []
    rejected: list[ImportRejection] = []

    for i, raw in enumerate(raw_records):
        try:
            point = parse_price_point(raw, market_id=market_id, source=source, token_id=token_id)
        except ValueError as exc:
            rejected.append(
                ImportRejection(index=i, raw_record=raw, reason_code=IMPORT_REJECT_INVALID_TIMESTAMP, detail=str(exc))
            )
            continue
        parsed.append((i, raw, point))

    seen: set[datetime] = set()
    accepted: list[PricePoint] = []
    for i, raw, point in parsed:
        if point.timestamp_utc in seen:
            rejected.append(
                ImportRejection(
                    index=i,
                    raw_record=raw,
                    reason_code=IMPORT_REJECT_DUPLICATE,
                    detail=f"Deuxieme observation de prix au meme timestamp {point.timestamp_utc.isoformat()}.",
                )
            )
            continue
        seen.add(point.timestamp_utc)
        accepted.append(point)

    rejected.sort(key=lambda r: r.index)
    return ImportValidationReport(accepted=tuple(accepted), rejected=tuple(rejected))


# ---------------------------------------------------------------------------
# Coherence resolution de marche (etape 10 : "marches resolus utilises
# avant leur resolution")
# ---------------------------------------------------------------------------


def validate_market_resolution_consistency(market: Market, claimed_snapshot_time: datetime) -> ImportRejection | None:
    """Detecte un export INTERNEMENT incoherent : un ``Market`` qui porte
    deja une ``outcome`` (issue gagnante) alors que ``resolution_time``
    est absent ou posterieur a ``claimed_snapshot_time`` - signe qu'une
    jointure amont a fusionne une information de resolution dans un
    instantane cense la precede (fuite d'export, pas seulement de
    pipeline). Retourne ``None`` si aucune incoherence detectee."""
    if market.outcome is None:
        return None
    if market.resolution_time is None or market.resolution_time > claimed_snapshot_time:
        return ImportRejection(
            index=-1,
            raw_record=market.__dict__,
            reason_code=IMPORT_REJECT_RESOLUTION_BEFORE_ITS_TIME,
            detail=(
                f"Market {market.market_id!r} porte outcome={market.outcome!r} mais "
                f"resolution_time={market.resolution_time!r} n'est pas anterieure ou egale a "
                f"claimed_snapshot_time={claimed_snapshot_time.isoformat()} - resolution utilisee avant son heure."
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Matching football - UNRESOLVED plutot que force (etape 5)
# ---------------------------------------------------------------------------

UNRESOLVED_MATCH_REASON_CODES = frozenset({POLYMARKET_MATCH_UNMATCHED, POLYMARKET_MATCH_AMBIGUOUS})


def is_unresolved_match(result: MarketMatchResult) -> bool:
    """Un ``MarketMatchResult`` portant un ``reason_code`` doit toujours
    etre traite comme UNRESOLVED (etape 5) - jamais force vers un
    ``match_id`` par defaut/best-effort."""
    return result.reason_code in UNRESOLVED_MATCH_REASON_CODES


# ---------------------------------------------------------------------------
# Couverture (etape 6) - outils de mesure, applicables des qu'un export
# reel existe ; aucune valeur numerique n'est produite ici sans donnees.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverageReport:
    n_markets: int
    n_matched: int
    n_unmatched: int
    n_ambiguous: int
    competitions: tuple[str, ...]
    earliest_start_time: datetime | None
    latest_start_time: datetime | None

    @property
    def match_rate(self) -> float:
        return self.n_matched / self.n_markets if self.n_markets > 0 else 0.0


def compute_coverage_report(markets: list[Market], match_results: list[MarketMatchResult]) -> CoverageReport:
    """Mesure de couverture generique (etape 6) - une fois des marches
    reels et leurs resultats de matching disponibles, cette fonction
    calcule le taux de matching et la couverture temporelle/competition.
    Une decomposition plus fine (par championnat, par saison) s'obtient
    en filtrant ``markets``/``match_results`` avant l'appel, plutot que
    par une multiplication de parametres ici."""
    n_matched = sum(1 for r in match_results if r.match_id is not None)
    n_unmatched = sum(1 for r in match_results if r.reason_code == POLYMARKET_MATCH_UNMATCHED)
    n_ambiguous = sum(1 for r in match_results if r.reason_code == POLYMARKET_MATCH_AMBIGUOUS)
    competitions = tuple(sorted({m.league for m in markets if m.league is not None}))
    start_times = [m.start_time for m in markets if m.start_time is not None]

    return CoverageReport(
        n_markets=len(markets),
        n_matched=n_matched,
        n_unmatched=n_unmatched,
        n_ambiguous=n_ambiguous,
        competitions=competitions,
        earliest_start_time=min(start_times) if start_times else None,
        latest_start_time=max(start_times) if start_times else None,
    )
