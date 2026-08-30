"""Normalisation d'un trade Polymarket brut vers ``schemas.Trade`` (Phase
L, etape 4), et deduplication (etape 9, point 9).

Meme reserve que ``markets.py`` : mapping de cles non verifie contre un
appel reel (acces reseau bloque). ``parse_trade`` leve explicitement si un
champ veritablement indispensable a l'usage (wallet, marche, timestamp,
side, prix, taille) est absent - jamais une valeur de repli inventee pour
ces champs precis, contrairement aux champs purement descriptifs."""

from __future__ import annotations

from datetime import datetime, timezone

from sys_foot_quant.polymarket.schemas import Trade

_WALLET_KEYS = ("proxyWallet", "wallet", "wallet_id", "user")
_MARKET_KEYS = ("market", "market_id", "conditionId")
_TIMESTAMP_KEYS = ("timestamp", "timestamp_utc", "matchTime")
_TRADE_ID_KEYS = ("id", "trade_id", "transactionHash")
_EVENT_ID_KEYS = ("eventId", "event_id")


def _first_present(raw: dict, keys: tuple[str, ...]) -> object | None:
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    return None


def _parse_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # Convention Polygon/on-chain frequente : timestamp Unix en secondes,
        # toujours interprete en UTC (jamais le fuseau local du serveur
        # d'execution - reproductibilite, docs/final_preproduction_audit.md
        # section 12 pour la meme exigence sur le moteur final).
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(
                f"Timestamp de trade sans fuseau horaire explicite : {value!r} - "
                "jamais suppose UTC silencieusement (risque de fuite PIT)."
            )
        return parsed
    raise ValueError(f"Timestamp de trade non interpretable : {value!r}")


def parse_trade(raw: dict, source: str) -> Trade:
    wallet = _first_present(raw, _WALLET_KEYS)
    market_id = _first_present(raw, _MARKET_KEYS)
    timestamp_raw = _first_present(raw, _TIMESTAMP_KEYS)
    side = raw.get("side")
    price = raw.get("price")
    size = raw.get("size")

    missing = [
        name
        for name, value in (
            ("wallet", wallet),
            ("market_id", market_id),
            ("timestamp", timestamp_raw),
            ("side", side),
            ("price", price),
            ("size", size),
        )
        if value is None
    ]
    if missing:
        raise ValueError(f"Trade brut incomplet, champs indispensables manquants {missing} : {raw!r}")

    price_f = float(price)
    size_f = float(size)

    return Trade(
        wallet_id=str(wallet),
        market_id=str(market_id),
        timestamp_utc=_parse_timestamp(timestamp_raw),
        side=str(side).upper(),
        price=price_f,
        size=size_f,
        source=source,
        trade_id=(str(v) if (v := _first_present(raw, _TRADE_ID_KEYS)) is not None else None),
        event_id=(str(v) if (v := _first_present(raw, _EVENT_ID_KEYS)) is not None else None),
        outcome=raw.get("outcome"),
        notional=price_f * size_f,
    )


def parse_trades(raws: list[dict], source: str) -> list[Trade]:
    return [parse_trade(r, source) for r in raws]


def deduplicate_trades(trades: list[Trade]) -> list[Trade]:
    """Supprime les doublons (etape 9, point 9). Cle de deduplication :
    ``trade_id`` quand il est connu (identifiant stable) ; a defaut, le
    n-uplet complet des champs observables (aucun ``trade_id`` disponible
    ne permet pas de distinguer deux trades strictement identiques sur
    tous les champs - ils sont alors traites comme un seul et meme trade,
    jamais compte deux fois)."""
    seen: set[tuple] = set()
    result: list[Trade] = []
    for t in trades:
        key = (t.trade_id,) if t.trade_id is not None else (
            None,
            t.wallet_id,
            t.market_id,
            t.timestamp_utc,
            t.side,
            t.price,
            t.size,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(t)
    return result
