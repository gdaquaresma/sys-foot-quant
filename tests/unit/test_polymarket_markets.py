from __future__ import annotations

import pytest

from sys_foot_quant.polymarket.markets import parse_market, parse_markets


def test_parse_market_with_canonical_key_names() -> None:
    raw = {
        "id": "m1",
        "eventId": "e1",
        "question": "Will Team A beat Team B?",
        "startDate": "2025-01-08T20:00:00Z",
        "endDate": "2025-01-08T22:00:00Z",
        "resolvedDate": "2025-01-08T23:00:00Z",
    }
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.market_id == "m1"
    assert m.event_id == "e1"
    assert m.title == "Will Team A beat Team B?"
    assert m.start_time is not None
    assert m.end_time is not None
    assert m.resolution_time is not None
    assert m.source == "polymarket_gamma_api"


def test_parse_market_accepts_alternate_key_names() -> None:
    raw = {"market_id": "m2", "title": "Match X vs Y", "event_id": "e2"}
    m = parse_market(raw, source="pomet")
    assert m.market_id == "m2"
    assert m.title == "Match X vs Y"
    assert m.event_id == "e2"


def test_parse_market_without_recognized_id_raises() -> None:
    with pytest.raises(ValueError):
        parse_market({"question": "no id here"}, source="polymarket_gamma_api")


def test_parse_market_never_guesses_home_away_team_from_title() -> None:
    raw = {"id": "m1", "question": "Will Real Madrid beat Barcelona?"}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.home_team is None
    assert m.away_team is None


def test_parse_market_unparseable_date_is_none_not_a_crash() -> None:
    raw = {"id": "m1", "startDate": "not-a-date"}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.start_time is None


def test_parse_markets_parses_a_list() -> None:
    raws = [{"id": "m1"}, {"id": "m2"}]
    markets = parse_markets(raws, source="polymarket_gamma_api")
    assert [m.market_id for m in markets] == ["m1", "m2"]


def test_parse_market_reads_direct_outcome_key() -> None:
    raw = {"id": "m1", "outcome": "Yes"}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.outcome == "Yes"


def test_parse_market_derives_outcome_from_resolved_outcome_prices() -> None:
    raw = {"id": "m1", "outcomes": '["Yes", "No"]', "outcomePrices": '["1", "0"]'}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.outcome == "Yes"


def test_parse_market_derives_outcome_from_resolved_outcome_prices_other_side() -> None:
    raw = {"id": "m1", "outcomes": '["Yes", "No"]', "outcomePrices": '["0", "1"]'}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.outcome == "No"


def test_parse_market_outcome_is_none_for_open_market_prices() -> None:
    raw = {"id": "m1", "outcomes": '["Yes", "No"]', "outcomePrices": '["0.575", "0.425"]'}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.outcome is None


def test_parse_market_outcome_is_none_when_outcome_prices_missing() -> None:
    raw = {"id": "m1", "outcomes": '["Yes", "No"]'}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.outcome is None


def test_parse_market_outcome_is_none_when_outcome_prices_malformed() -> None:
    raw = {"id": "m1", "outcomes": '["Yes", "No"]', "outcomePrices": "not-json"}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.outcome is None


def test_parse_market_outcome_accepts_native_json_lists() -> None:
    raw = {"id": "m1", "outcomes": ["Yes", "No"], "outcomePrices": ["1", "0"]}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.outcome == "Yes"


def test_parse_market_condition_id_is_distinct_from_gamma_numeric_id() -> None:
    """Cas reel (Phillies-Diamondbacks) : ``id`` Gamma numerique et
    ``conditionId`` on-chain sont deux identifiants differents -
    ``market_id`` garde la priorite existante (``id``), ``condition_id``
    porte la valeur separee necessaire a la jointure avec les trades."""
    raw = {"id": "3872870", "conditionId": "0xfe0ebcbb0a3de954dcf08c7d1ef0c1333d94a89d7f0effa03591e1f7bb0a0ebc"}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.market_id == "3872870"
    assert m.condition_id == "0xfe0ebcbb0a3de954dcf08c7d1ef0c1333d94a89d7f0effa03591e1f7bb0a0ebc"


def test_parse_market_without_condition_id_key_leaves_it_none() -> None:
    """Ancienne fixture synthetique sans ``conditionId`` distinct - ne doit
    jamais inventer de valeur, ``condition_id`` reste ``None``."""
    raw = {"id": "m1"}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.condition_id is None


def test_parse_market_reads_token_ids_from_json_string() -> None:
    raw = {"id": "3872870", "clobTokenIds": '["1111", "2222"]'}
    m = parse_market(raw, source="polymarket_gamma_api")
    assert m.token_ids == ("1111", "2222")


def test_parse_market_token_ids_is_none_when_absent() -> None:
    m = parse_market({"id": "m1"}, source="polymarket_gamma_api")
    assert m.token_ids is None
