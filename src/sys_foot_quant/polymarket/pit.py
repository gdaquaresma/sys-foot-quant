"""Point d'entree PIT unique pour l'information sur un trader (Phase L,
etape 5 - POINT LE PLUS IMPORTANT DE CETTE PHASE).

``get_trader_information_as_of`` est la SEULE fonction destinee a
alimenter une future analyse : elle ne retourne QUE ce qui etait
disponible avant ``decision_time`` (trades, positions reconstruites,
statistiques - jamais un trade futur, jamais une resolution de marche pas
encore connue, jamais un ROI/win rate/volume/ranking calcule avec des
paris posterieurs)."""

from __future__ import annotations

from datetime import datetime

from sys_foot_quant.polymarket.positions import derive_positions_as_of
from sys_foot_quant.polymarket.schemas import Market, Trade, TraderInformationAsOf
from sys_foot_quant.polymarket.traders import compute_trader_stats_as_of


def get_trader_information_as_of(
    wallet_id: str,
    decision_time: datetime,
    trades: list[Trade],
    markets: dict[str, Market] | None = None,
) -> TraderInformationAsOf:
    """``trades`` peut contenir l'historique COMPLET (passe et futur) du
    wallet - le filtrage point-in-time est fait ICI, une seule fois,
    jamais delegue a l'appelant (a l'inverse de ``final_engine`` qui
    delegue ce filtrage a l'appelant : ici la fonction est precisement LE
    point de filtrage, donc elle le fait elle-meme, par construction, pour
    qu'aucun appelant ne puisse s'en dispenser par erreur)."""
    trades_as_of = tuple(
        sorted(
            (t for t in trades if t.wallet_id == wallet_id and t.timestamp_utc < decision_time),
            key=lambda t: t.timestamp_utc,
        )
    )
    positions_as_of = derive_positions_as_of(wallet_id, decision_time, trades)
    stats_as_of = compute_trader_stats_as_of(wallet_id, decision_time, trades, markets)

    return TraderInformationAsOf(
        wallet_id=wallet_id,
        as_of=decision_time,
        trades_as_of=trades_as_of,
        positions_as_of=positions_as_of,
        stats_as_of=stats_as_of,
    )
