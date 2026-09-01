"""Statistiques de wallet PIT-sures et preparation de la selection future
de traders (Phase L, etapes 5 et 8).

Modele de reglement (``_settlement_pnl_per_share``) : marche binaire,
redemption a 1$/0$ par part selon l'issue gagnante - mecanique
publiquement documentee des marches de prediction Polymarket (jetons
conditionnels de type Gnosis CTF), PAS une hypothese propre a ce module.
Le traitement du cote ``SELL`` (symetrique de ``BUY``, signe invers) est
une CONVENTION explicite de ce module, non verifiee contre un reglement
reel (acces reseau bloque) - a confirmer avant toute utilisation dans une
future experience."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sys_foot_quant.polymarket.positions import derive_positions_as_of
from sys_foot_quant.polymarket.schemas import Market, Trade, TraderStatsAsOf

_SIGN = {"BUY": 1.0, "SELL": -1.0}


def _settlement_pnl_per_share(trade: Trade, winning_outcome: str) -> float:
    sign = _SIGN[trade.side]
    settlement = 1.0 if trade.outcome == winning_outcome else 0.0
    return sign * (settlement - trade.price)


def _index_markets_for_join(markets: dict[str, Market]) -> dict[str, Market]:
    """Construit l'index utilise pour retrouver un ``Market`` a partir de
    ``Trade.market_id``, a partir des VALEURS de ``markets`` (jamais des
    cles du dict fourni par l'appelant - un appelant metier n'a jamais
    besoin de re-cleer son dict lui-meme).

    Sur un vrai payload Data API, ``Trade.market_id`` contient en realite
    le ``conditionId`` on-chain, jamais l'``id`` Gamma numerique que porte
    ``Market.market_id`` (verifie sur donnees reelles, ex. trade
    ``market_id="0xfe0e..."`` face a un marche Gamma ``id="3872870"``/
    ``conditionId="0xfe0e..."``). Chaque marche est donc indexee a la fois
    par son ``market_id`` (retro-compatibilite : anciennes fixtures/tests
    ou les deux identifiants coincident deliberement) et par son
    ``condition_id`` quand il est connu - un ``Trade.market_id`` egal a
    l'un ou l'autre retrouve le meme ``Market``."""
    index: dict[str, Market] = {}
    for market in markets.values():
        index[market.market_id] = market
        if market.condition_id is not None:
            index[market.condition_id] = market
    return index


def token_id_consistent_with_market(trade: Trade, market: Market) -> bool | None:
    """Verification de coherence best-effort entre le token effectivement
    trade (``Trade.token_id``) et les tokens du marche retrouve
    (``Market.token_ids``) - ``None`` (non verifiable) des que l'une des
    deux informations manque, jamais une condition bloquante faute de
    donnee (la plupart des exports n'auront ni l'un ni l'autre)."""
    if trade.token_id is None or market.token_ids is None:
        return None
    return trade.token_id in market.token_ids


def compute_trader_stats_as_of(
    wallet_id: str,
    decision_time: datetime,
    trades: list[Trade],
    markets: dict[str, Market] | None = None,
) -> TraderStatsAsOf:
    """Calcule les statistiques d'un wallet EXCLUSIVEMENT a partir des
    trades dont ``timestamp_utc < decision_time`` et des marches dont
    ``resolution_time`` est CONNU et lui-meme ``< decision_time`` (etape 5 :
    jamais une resolution non encore connue a `decision_time`). Sans
    ``markets`` fourni, ou si aucun ``Market`` ne correspond au
    ``Trade.market_id`` (``_index_markets_for_join``), aucun trade ne peut
    etre considere resolu - ``realized_pnl``/``win_rate`` restent
    ``None``, jamais une valeur par defaut optimiste ni une exception pour
    une jointure simplement absente (donnee reelle intrinsequement
    incomplete, pas une erreur de programmation)."""
    trades_before = [t for t in trades if t.wallet_id == wallet_id and t.timestamp_utc < decision_time]
    volume = sum(t.notional or 0.0 for t in trades_before)

    market_index = _index_markets_for_join(markets) if markets is not None else None

    resolved_pnls: list[float] = []
    if market_index is not None:
        for t in trades_before:
            market = market_index.get(t.market_id)
            if market is None or market.resolution_time is None or market.resolution_time >= decision_time:
                continue
            if market.outcome is None or t.outcome is None:
                continue
            pnl_per_share = _settlement_pnl_per_share(t, market.outcome)
            resolved_pnls.append(pnl_per_share * t.size)

    n_resolved = len(resolved_pnls)
    realized_pnl = sum(resolved_pnls) if n_resolved > 0 else None
    win_rate = (sum(1 for p in resolved_pnls if p > 0) / n_resolved) if n_resolved > 0 else None

    positions = derive_positions_as_of(wallet_id, decision_time, trades_before)
    open_position_count = sum(1 for by_outcome in positions.values() for size in by_outcome.values() if size != 0.0)

    return TraderStatsAsOf(
        wallet_id=wallet_id,
        as_of=decision_time,
        n_trades=len(trades_before),
        n_resolved_trades=n_resolved,
        volume_notional=volume,
        realized_pnl=realized_pnl,
        win_rate=win_rate,
        open_position_count=open_position_count,
    )


@dataclass(frozen=True)
class EligibilityRules:
    """Criteres de selection des traders - AUCUN SEUIL PAR DEFAUT
    (etape 8) : chaque champ non ``None`` restreint la selection, tous
    ``None`` (defaut) ne filtre rien. Les valeurs numeriques concretes
    seront fournies plus tard par un protocole pre-enregistre distinct de
    ce module - jamais inventees ici, exactement comme
    ``OperationalThresholds.min_edge_threshold`` dans ``final_engine``."""

    min_trades: int | None = None
    min_volume_notional: float | None = None
    min_resolved_trades: int | None = None
    min_win_rate: float | None = None
    min_realized_pnl: float | None = None
    top_n_by: str | None = None  # nom du champ de tri, ex. "realized_pnl" - None = pas de troncature
    top_n: int | None = None


def eligible_traders_as_of(
    decision_time: datetime,
    trades_by_wallet: dict[str, list[Trade]],
    markets: dict[str, Market] | None,
    rules: EligibilityRules,
) -> list[TraderStatsAsOf]:
    """« Quels traders etaient historiquement performants A CETTE DATE ? »
    (etape 8) - jamais un classement recalcule avec des donnees futures :
    chaque wallet est evalue via ``compute_trader_stats_as_of`` (PIT-sur),
    puis filtre selon ``rules``. Avec ``EligibilityRules()`` par defaut
    (tout ``None``), retourne tous les wallets ayant au moins un trade
    avant ``decision_time``, sans aucun filtre - ne prejuge d'aucun seuil
    futur."""
    stats = [
        compute_trader_stats_as_of(wallet_id, decision_time, wallet_trades, markets)
        for wallet_id, wallet_trades in trades_by_wallet.items()
    ]
    stats = [s for s in stats if s.n_trades > 0]

    if rules.min_trades is not None:
        stats = [s for s in stats if s.n_trades >= rules.min_trades]
    if rules.min_volume_notional is not None:
        stats = [s for s in stats if s.volume_notional >= rules.min_volume_notional]
    if rules.min_resolved_trades is not None:
        stats = [s for s in stats if s.n_resolved_trades >= rules.min_resolved_trades]
    if rules.min_win_rate is not None:
        stats = [s for s in stats if s.win_rate is not None and s.win_rate >= rules.min_win_rate]
    if rules.min_realized_pnl is not None:
        stats = [s for s in stats if s.realized_pnl is not None and s.realized_pnl >= rules.min_realized_pnl]

    if rules.top_n_by is not None:
        stats = [s for s in stats if getattr(s, rules.top_n_by) is not None]
        stats = sorted(stats, key=lambda s: getattr(s, rules.top_n_by), reverse=True)
        if rules.top_n is not None:
            stats = stats[: rules.top_n]

    return stats
