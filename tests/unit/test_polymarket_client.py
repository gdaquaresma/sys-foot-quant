from __future__ import annotations

import json

import pytest

from sys_foot_quant.polymarket.client import (
    load_clob_prices_history_json,
    load_data_api_positions_json,
    load_data_api_trades_json,
    load_gamma_events_json,
    load_gamma_markets_json,
)


def test_load_gamma_markets_json_reads_local_file(tmp_path) -> None:
    p = tmp_path / "markets.json"
    p.write_text(json.dumps([{"id": "m1"}, {"id": "m2"}]))
    records = load_gamma_markets_json(p)
    assert records == [{"id": "m1"}, {"id": "m2"}]


def test_load_gamma_events_json_reads_local_file(tmp_path) -> None:
    p = tmp_path / "events.json"
    p.write_text(json.dumps([{"id": "e1"}]))
    assert load_gamma_events_json(p) == [{"id": "e1"}]


def test_load_data_api_trades_json_reads_local_file(tmp_path) -> None:
    p = tmp_path / "trades.json"
    p.write_text(json.dumps([{"id": "t1"}]))
    assert load_data_api_trades_json(p) == [{"id": "t1"}]


def test_load_data_api_positions_json_reads_local_file(tmp_path) -> None:
    p = tmp_path / "positions.json"
    p.write_text(json.dumps([{"market": "m1"}]))
    assert load_data_api_positions_json(p) == [{"market": "m1"}]


def test_load_clob_prices_history_json_reads_local_file(tmp_path) -> None:
    p = tmp_path / "prices.json"
    p.write_text(json.dumps([{"t": 1735689600, "p": 0.5}]))
    assert load_clob_prices_history_json(p) == [{"t": 1735689600, "p": 0.5}]


def test_missing_file_raises_explicit_error(tmp_path) -> None:
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        load_gamma_markets_json(missing)


def test_non_list_root_raises_explicit_error(tmp_path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"not": "a list"}))
    with pytest.raises(ValueError):
        load_gamma_markets_json(p)


def test_malformed_json_propagates_a_clear_error(tmp_path) -> None:
    p = tmp_path / "malformed.json"
    p.write_text("{not valid json")
    with pytest.raises(json.JSONDecodeError):
        load_data_api_trades_json(p)


def test_no_network_call_is_ever_made() -> None:
    """Verification structurelle (etape 3/13) : ce module ne doit
    reference aucune bibliotheque de requetes reseau."""
    import inspect

    from sys_foot_quant.polymarket import client

    source = inspect.getsource(client)
    for forbidden in ("import requests", "import httpx", "urllib.request", "urlopen("):
        assert forbidden not in source, f"Appel reseau potentiel trouve dans client.py : {forbidden!r}"
