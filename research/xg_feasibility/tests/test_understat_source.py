"""Tests des fonctions PURES (aucun reseau) de understat_source.py.

``fetch_league_season_html`` (la seule fonction qui touche le reseau)
n'est PAS testee ici - impossible a verifier depuis ce depot sans acces
reseau reel (voir avertissement dans le module). Ces tests couvrent tout
le reste : decodage, parsing, normalisation - avec un fixture HTML qui
reproduit le format documente (variable ``datesData`` echappee en hexa).
"""

from __future__ import annotations

import json

import pytest

from research.xg_feasibility.understat_source import (
    MatchXGRecord,
    UnderstatParsingError,
    _decode_hex_escaped_json,
    extract_match_records,
    parse_matches_from_html,
)


def _hex_escape(text: str) -> str:
    """Reproduit l'echappement hexadecimal utilise par Understat avant de
    passer la chaine a ``JSON.parse`` cote navigateur - inverse de
    ``_decode_hex_escaped_json``."""
    return "".join(f"\\x{b:02x}" for b in text.encode("utf-8"))


def _fixture_html(raw_matches: list[dict]) -> str:
    encoded = _hex_escape(json.dumps(raw_matches))
    return f"""
    <html><body><script>
    var datesData = JSON.parse('{encoded}');
    </script></body></html>
    """


_SAMPLE_RAW_MATCH_PLAYED = {
    "id": "12345",
    "isResult": True,
    "datetime": "2024-08-17 15:00:00",
    "h": {"id": "1", "title": "Paris Saint Germain"},
    "a": {"id": "2", "title": "Le Havre"},
    "goals": {"h": "3", "a": "0"},
    "xG": {"h": "2.45", "a": "0.31"},
}

_SAMPLE_RAW_MATCH_UPCOMING = {
    "id": "99999",
    "isResult": False,
    "datetime": "2026-09-01 15:00:00",
    "h": {"id": "3", "title": "Lyon"},
    "a": {"id": "4", "title": "Monaco"},
    "goals": {"h": None, "a": None},
    "xG": {"h": "0", "a": "0"},
}


def test_decode_hex_escaped_json_round_trip() -> None:
    original = '{"team":"Oléron Football Club","value":1}'
    assert _decode_hex_escaped_json(_hex_escape(original)) == original


def test_parse_matches_from_html_extracts_list() -> None:
    html = _fixture_html([_SAMPLE_RAW_MATCH_PLAYED, _SAMPLE_RAW_MATCH_UPCOMING])
    parsed = parse_matches_from_html(html)
    assert parsed == [_SAMPLE_RAW_MATCH_PLAYED, _SAMPLE_RAW_MATCH_UPCOMING]


def test_parse_matches_from_html_missing_marker_raises() -> None:
    with pytest.raises(UnderstatParsingError):
        parse_matches_from_html("<html><body>rien ici</body></html>")


def test_parse_matches_from_html_invalid_json_raises() -> None:
    html = f"""<script>var datesData = JSON.parse('{_hex_escape("not json")}');</script>"""
    with pytest.raises(UnderstatParsingError):
        parse_matches_from_html(html)


def test_extract_match_records_skips_unplayed_matches() -> None:
    raw = [_SAMPLE_RAW_MATCH_PLAYED, _SAMPLE_RAW_MATCH_UPCOMING]
    records = extract_match_records(raw, league="Ligue_1", season="2024")
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, MatchXGRecord)
    assert record.match_id == "12345"
    assert record.home_team == "Paris Saint Germain"
    assert record.away_team == "Le Havre"
    assert record.home_goals == 3
    assert record.away_goals == 0
    assert record.home_xg == pytest.approx(2.45)
    assert record.away_xg == pytest.approx(0.31)
    assert record.league == "Ligue_1"
    assert record.season == "2024"


def test_extract_match_records_handles_accented_names() -> None:
    raw_match = dict(_SAMPLE_RAW_MATCH_PLAYED)
    raw_match["h"] = {"id": "1", "title": "Saint-Étienne"}
    records = extract_match_records([raw_match], league="Ligue_1", season="2024")
    assert records[0].home_team == "Saint-Étienne"
