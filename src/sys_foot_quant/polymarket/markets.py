"""Normalisation d'un marche Polymarket brut vers ``schemas.Market``
(Phase L, etape 4).

Le mapping exact des cles JSON ci-dessous (``id``/``question``/``slug``/
``endDate``...) suit les noms couramment documentes par des sources
publiques tierces pour la Gamma API, mais n'a PAS ete verifie contre un
appel reel dans cet environnement (acces reseau bloque, voir
docs/polymarket_pomet_data_audit.md). ``parse_market`` est donc
deliberement tolerant (cles alternatives, ``.get()`` partout) et ne leve
que si l'identifiant du marche lui-meme est absent - jamais une hypothese
de champ obligatoire non confirmee."""

from __future__ import annotations

import json
from datetime import datetime

from sys_foot_quant.polymarket.schemas import Market

_ID_KEYS = ("id", "market_id", "conditionId")
_TITLE_KEYS = ("question", "title")
_START_KEYS = ("startDate", "start_time", "gameStartTime")
_END_KEYS = ("endDate", "end_time")
_RESOLUTION_KEYS = ("resolvedDate", "resolution_time", "closedTime")
_EVENT_ID_KEYS = ("eventId", "event_id")
_OUTCOME_KEYS = ("outcome", "resolved_outcome", "winning_outcome")


def _first_present(raw: dict, keys: tuple[str, ...]) -> object | None:
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    return None


def _parse_datetime(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_json_string_list(value: object | None) -> list | None:
    """Decode une liste eventuellement encodee en JSON-dans-une-chaine,
    forme observee sur les champs ``outcomes``/``outcomePrices`` de la
    Gamma API reelle (ex. ``'["Yes", "No"]'``). Retourne ``None`` sans
    lever si la valeur est absente ou non interpretable comme liste -
    jamais de valeur inventee."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _resolve_outcome_from_prices(raw: dict) -> str | None:
    """Deduit l'issue gagnante des couples ``outcomes``/``outcomePrices``
    de la Gamma API (ex. ``outcomes=["Yes","No"]``,
    ``outcomePrices=["1","0"]`` -> ``"Yes"``). Ne retourne une issue que
    si un seul libelle a un prix de 1.0 exactement - un marche encore
    ouvert n'a jamais de prix a 1.0 exact, donc ceci ne peut pas
    confondre une simple probabilite elevee avec une resolution."""
    outcomes = _parse_json_string_list(raw.get("outcomes"))
    prices = _parse_json_string_list(raw.get("outcomePrices"))
    if outcomes is None or prices is None or len(outcomes) != len(prices):
        return None

    winners = []
    for label, price in zip(outcomes, prices):
        try:
            price_value = float(price)
        except (TypeError, ValueError):
            continue
        if price_value == 1.0:
            winners.append(label)

    return str(winners[0]) if len(winners) == 1 else None


def parse_market(raw: dict, source: str) -> Market:
    """Normalise un dictionnaire brut de marche vers ``Market``. Ne
    devine ni ``home_team``/``away_team``/``league``/``sport`` a partir du
    titre libre - cette extraction est le role explicite de
    ``matching.py`` (etape 6), jamais fait silencieusement ici."""
    market_id = _first_present(raw, _ID_KEYS)
    if market_id is None:
        raise ValueError(f"Marche brut sans identifiant reconnu (cles testees : {_ID_KEYS}) : {raw!r}")

    outcome = _first_present(raw, _OUTCOME_KEYS)
    if outcome is None:
        outcome = _resolve_outcome_from_prices(raw)

    return Market(
        market_id=str(market_id),
        source=source,
        event_id=(str(v) if (v := _first_present(raw, _EVENT_ID_KEYS)) is not None else None),
        title=_first_present(raw, _TITLE_KEYS),
        sport=raw.get("sport"),
        league=raw.get("league"),
        home_team=raw.get("home_team"),
        away_team=raw.get("away_team"),
        market_type=raw.get("market_type"),
        outcome=outcome,
        start_time=_parse_datetime(_first_present(raw, _START_KEYS)),
        end_time=_parse_datetime(_first_present(raw, _END_KEYS)),
        resolution_time=_parse_datetime(_first_present(raw, _RESOLUTION_KEYS)),
    )


def parse_markets(raws: list[dict], source: str) -> list[Market]:
    return [parse_market(r, source) for r in raws]
