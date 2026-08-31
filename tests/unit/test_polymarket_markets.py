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
