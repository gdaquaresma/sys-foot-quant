"""Tests du connecteur d'auto-alimentation (current_season_updater.py) -
AUCUN reseau reel : ``http_get`` est systematiquement mocke, reproduisant
le format JSON reel de l'endpoint ``getLeagueData`` (confirme par capture
navigateur reelle : ``{"teams": {...}, "players": [...], "dates": [...]}``)
ou des pannes explicites (reseau, JSON invalide, structure inattendue)."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

import pytest

from research.xg_feasibility.current_season_updater import (
    _JSON_HEADERS,
    _decode_http_body,
    _default_json_http_get,
    build_get_league_data_url,
    fetch_league_data_payload,
    fetch_understat_raw_played_matches,
    format_report,
    sync_current_season,
)
from sys_foot_quant.data_engine.market_odds.current_season_contract import (
    CurrentSeasonContractError,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_2026_FILE = REPO_ROOT / "research/xg_feasibility/runs/ligue1_2026_datesData.json"

_FIXED_NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)

LEAGUE_NAME = "Ligue 1"  # nom reel attendu par getLeagueData (avec espace, jamais underscore)


def _fixture_payload(raw_matches: list[dict]) -> str:
    return json.dumps({"teams": {}, "players": [], "dates": raw_matches})


def _match(
    match_id: str,
    dt: str,
    home_id: str = "279",
    home_title: str = "Brest",
    away_id: str = "296",
    away_title: str = "Marseille",
    home_goals: str = "1",
    away_goals: str = "2",
    home_xg: str = "1.32",
    away_xg: str = "1.87",
    is_result: bool = True,
) -> dict:
    return {
        "id": match_id,
        "isResult": is_result,
        "datetime": dt,
        "h": {"id": home_id, "title": home_title},
        "a": {"id": away_id, "title": away_title},
        "goals": {"h": home_goals, "a": away_goals} if is_result else {"h": None, "a": None},
        "xG": {"h": home_xg, "a": away_xg} if is_result else {"h": None, "a": None},
    }


def _mock_http_get(body: str):
    def _fn(url: str) -> str:
        return body

    return _fn


def _mock_http_get_raising(exc: Exception):
    def _fn(url: str) -> str:
        raise exc

    return _fn


def _now_fn():
    return _FIXED_NOW


# --- build_get_league_data_url : construction/encodage de l'URL -------------


def test_url_encodes_space_as_percent_20() -> None:
    url = build_get_league_data_url("Ligue 1", "2026")
    assert url == "https://understat.com/getLeagueData/Ligue%201/2026"


def test_url_never_contains_ligue_underscore() -> None:
    # Non-regression explicite : l'ancienne convention "Ligue_1" (page HTML)
    # est CONFIRMEE DIFFERENTE de "Ligue 1" (endpoint getLeagueData reel) -
    # construire l'URL a partir de "Ligue 1" ne doit jamais produire "Ligue_1".
    url = build_get_league_data_url("Ligue 1", "2026")
    assert "Ligue_1" not in url
    assert "Ligue%201" in url


def test_url_uses_https_getleaguedata_path() -> None:
    url = build_get_league_data_url("Ligue 1", "2026")
    assert url.startswith("https://understat.com/getLeagueData/")
    assert url.endswith("/2026")


# --- headers HTTP reels confirmes ---------------------------------------------


def test_json_headers_match_confirmed_browser_capture() -> None:
    assert _JSON_HEADERS["Accept"] == "application/json, text/javascript, */*; q=0.01"
    assert _JSON_HEADERS["X-Requested-With"] == "XMLHttpRequest"


class _FakeHeaders:
    def __init__(self, content_encoding: str | None = None) -> None:
        self._content_encoding = content_encoding

    def get(self, name: str, default=None):
        if name.lower() == "content-encoding":
            return self._content_encoding if self._content_encoding is not None else default
        return default


class _FakeResponse:
    def __init__(self, body: bytes, content_encoding: str | None = None) -> None:
        self._body = body
        self.headers = _FakeHeaders(content_encoding)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._body


def test_default_json_http_get_sends_confirmed_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def _fake_urlopen(request, timeout=None):
        captured["headers"] = dict(request.header_items())
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return _FakeResponse(b'{"teams": {}, "players": [], "dates": []}')

    import urllib.request as urllib_request

    monkeypatch.setattr(urllib_request, "urlopen", _fake_urlopen)
    body = _default_json_http_get("https://understat.com/getLeagueData/Ligue%201/2026")
    assert body == '{"teams": {}, "players": [], "dates": []}'
    assert captured["method"] == "GET"
    assert captured["headers"]["Accept"] == "application/json, text/javascript, */*; q=0.01"
    assert captured["headers"]["X-requested-with"] == "XMLHttpRequest"


# --- _decode_http_body / _default_json_http_get : reponse gzip reelle -------
# Constat empirique (validation externe reelle, machine avec acces reseau) :
# Understat peut repondre en gzip (magic bytes 1f 8b) - UnicodeDecodeError si
# on tente de decoder le corps brut en UTF-8 sans decompresser d'abord.


def test_decode_http_body_plain_uncompressed_response() -> None:
    raw = '{"teams": {}, "players": [], "dates": []}'.encode("utf-8")
    assert _decode_http_body(raw, "") == raw.decode("utf-8")


def test_decode_http_body_gzip_with_content_encoding_header() -> None:
    original = '{"teams": {"1": {"title": "Brest"}}, "players": [], "dates": []}'
    compressed = gzip.compress(original.encode("utf-8"))
    assert _decode_http_body(compressed, "gzip") == original


def test_decode_http_body_gzip_content_encoding_header_case_insensitive() -> None:
    original = '{"teams": {}, "players": [], "dates": []}'
    compressed = gzip.compress(original.encode("utf-8"))
    assert _decode_http_body(compressed, "GZIP") == original


def test_decode_http_body_gzip_magic_bytes_without_header() -> None:
    # Reproduit exactement le cas reel rencontre en validation externe :
    # corps gzip (1f 8b) recu sans Content-Encoding fiable/present.
    original = '{"teams": {}, "players": [], "dates": []}'
    compressed = gzip.compress(original.encode("utf-8"))
    assert compressed[:2] == b"\x1f\x8b"
    assert _decode_http_body(compressed, "") == original


def test_decode_http_body_invalid_gzip_fails_closed() -> None:
    corrupted = b"\x1f\x8bnot actually valid gzip data"
    with pytest.raises(OSError):
        _decode_http_body(corrupted, "gzip")


def test_default_json_http_get_decompresses_gzip_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload_text = '{"teams": {}, "players": [], "dates": [{"id": "1", "isResult": true}]}'
    compressed = gzip.compress(payload_text.encode("utf-8"))

    def _fake_urlopen(request, timeout=None):
        return _FakeResponse(compressed, content_encoding="gzip")

    import urllib.request as urllib_request

    monkeypatch.setattr(urllib_request, "urlopen", _fake_urlopen)
    body = _default_json_http_get("https://understat.com/getLeagueData/Ligue%201/2026")
    assert body == payload_text
    assert json.loads(body)["dates"][0]["id"] == "1"


def test_default_json_http_get_plain_response_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    payload_text = '{"teams": {}, "players": [], "dates": []}'

    def _fake_urlopen(request, timeout=None):
        return _FakeResponse(payload_text.encode("utf-8"), content_encoding=None)

    import urllib.request as urllib_request

    monkeypatch.setattr(urllib_request, "urlopen", _fake_urlopen)
    body = _default_json_http_get("https://understat.com/getLeagueData/Ligue%201/2026")
    assert body == payload_text


# --- fetch_league_data_payload : parsing fail-closed du payload JSON --------


def test_payload_real_representative_response_is_parsed() -> None:
    matches = [_match("1", "2026-08-15 19:45:00")]
    payload_text = json.dumps({"teams": {"279": {"title": "Brest"}}, "players": [], "dates": matches})
    payload = fetch_league_data_payload(LEAGUE_NAME, "2026", http_get=_mock_http_get(payload_text))
    assert payload["dates"] == matches
    assert "teams" in payload


def test_payload_invalid_json_raises_understat_fetch_error() -> None:
    from research.xg_feasibility.current_season_updater import UnderstatFetchError

    with pytest.raises(UnderstatFetchError):
        fetch_league_data_payload(LEAGUE_NAME, "2026", http_get=_mock_http_get("not valid json"))


def test_payload_missing_dates_key_raises_understat_fetch_error() -> None:
    from research.xg_feasibility.current_season_updater import UnderstatFetchError

    body = json.dumps({"teams": {}, "players": []})
    with pytest.raises(UnderstatFetchError, match="dates"):
        fetch_league_data_payload(LEAGUE_NAME, "2026", http_get=_mock_http_get(body))


def test_payload_dates_wrong_type_raises_understat_fetch_error() -> None:
    from research.xg_feasibility.current_season_updater import UnderstatFetchError

    body = json.dumps({"teams": {}, "players": [], "dates": "not-a-list"})
    with pytest.raises(UnderstatFetchError, match="dates"):
        fetch_league_data_payload(LEAGUE_NAME, "2026", http_get=_mock_http_get(body))


def test_payload_non_object_root_raises_understat_fetch_error() -> None:
    from research.xg_feasibility.current_season_updater import UnderstatFetchError

    body = json.dumps([1, 2, 3])
    with pytest.raises(UnderstatFetchError):
        fetch_league_data_payload(LEAGUE_NAME, "2026", http_get=_mock_http_get(body))


# --- fetch_understat_raw_played_matches : extraction + filtrage isResult ----


def test_fetch_filters_isresult_true_only() -> None:
    payload_text = _fixture_payload(
        [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-09-01 19:45:00", is_result=False)]
    )
    played, n_raw = fetch_understat_raw_played_matches(LEAGUE_NAME, "2026", http_get=_mock_http_get(payload_text))
    assert n_raw == 2
    assert [m["id"] for m in played] == ["1"]


def test_fetch_mixed_played_and_unplayed_extracts_only_dates_key() -> None:
    payload_text = json.dumps(
        {
            "teams": {"ignored": True},
            "players": [{"ignored": True}],
            "dates": [
                _match("1", "2026-08-15 19:45:00"),
                _match("2", "2026-08-22 19:45:00", is_result=False),
                _match("3", "2026-08-29 19:45:00"),
            ],
        }
    )
    played, n_raw = fetch_understat_raw_played_matches(LEAGUE_NAME, "2026", http_get=_mock_http_get(payload_text))
    assert n_raw == 3
    assert {m["id"] for m in played} == {"1", "3"}


def test_fetch_http_error_propagates_as_oserror() -> None:
    with pytest.raises(URLError):
        fetch_understat_raw_played_matches(
            LEAGUE_NAME, "2026", http_get=_mock_http_get_raising(URLError("connection refused"))
        )


# --- 1. premiere ingestion (fichier vide/inexistant) -------------------------


def test_1_first_ingestion_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "ligue1_2026_datesData.json"
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00")])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "updated"
    assert path.exists()
    assert len(json.loads(path.read_text())) == 1


# --- 2/3. ajout de nouveaux matchs / nouvelle journee ------------------------


def test_2_new_matches_are_added(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text(json.dumps([_match("1", "2026-08-15 19:45:00")]), encoding="utf-8")
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "updated"
    assert report.diff is not None
    assert len(report.diff.new_matches) == 1
    assert {m["id"] for m in json.loads(path.read_text())} == {"1", "2"}


def test_3_one_full_matchday_added_at_once(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text(json.dumps([_match("1", "2026-08-15 19:45:00")]), encoding="utf-8")
    new_matchday = [
        _match("1", "2026-08-15 19:45:00"),
        _match("2", "2026-08-22 15:00:00", home_id="1", home_title="Lille", away_id="2", away_title="Lens"),
        _match("3", "2026-08-22 17:00:00", home_id="3", home_title="Nice", away_id="4", away_title="Lyon"),
        _match("4", "2026-08-22 19:45:00", home_id="5", home_title="Monaco", away_id="6", away_title="Rennes"),
    ]
    payload_text = _fixture_payload(new_matchday)
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "updated"
    assert len(report.diff.new_matches) == 3
    assert len(json.loads(path.read_text())) == 4


# --- 4. plusieurs journees ajoutees d'un coup --------------------------------


def test_4_multiple_matchdays_added_at_once(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text(json.dumps([_match("1", "2026-08-15 19:45:00")]), encoding="utf-8")
    new_source = [
        _match("1", "2026-08-15 19:45:00"),
        _match("2", "2026-08-22 19:45:00"),
        _match("3", "2026-08-29 19:45:00"),
        _match("4", "2026-09-05 19:45:00"),
    ]
    payload_text = _fixture_payload(new_source)
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "updated"
    assert len(report.diff.new_matches) == 3
    assert len(json.loads(path.read_text())) == 4


# --- 5. resynchronisation identique -----------------------------------------


def test_5_identical_resync_makes_no_change(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    matches = [_match("1", "2026-08-15 19:45:00")]
    path.write_text(json.dumps(matches), encoding="utf-8")
    payload_text = _fixture_payload(matches)
    content_before = path.read_bytes()
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "no_change"
    assert path.read_bytes() == content_before


# --- 6. match modifie ---------------------------------------------------------


def test_6_modified_match_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text(json.dumps([_match("1", "2026-08-15 19:45:00", home_goals="1")]), encoding="utf-8")
    content_before = path.read_bytes()
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00", home_goals="9")])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "refused"
    assert path.read_bytes() == content_before


# --- 7. match disparu ----------------------------------------------------------


def test_7_missing_match_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text(
        json.dumps([_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")]), encoding="utf-8"
    )
    content_before = path.read_bytes()
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00")])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "refused"
    assert path.read_bytes() == content_before


# --- 8. doublon ------------------------------------------------------------


def test_8_internal_duplicate_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00"), _match("1", "2026-08-22 19:45:00")])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "error"
    assert not path.exists()


# --- 9. xG manquant ----------------------------------------------------------


def test_9_missing_xg_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    bad = _match("1", "2026-08-15 19:45:00")
    del bad["xG"]
    payload_text = _fixture_payload([bad])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "error"
    assert not path.exists()


# --- 10. score invalide -------------------------------------------------------


def test_10_invalid_score_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00", home_goals="-1")])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "error"
    assert not path.exists()


# --- 11. isResult=false (dans les donnees destinees au fichier courant) -----


def test_11_unplayed_matches_are_filtered_out_before_validation(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload(
        [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-09-01 19:45:00", is_result=False)]
    )
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "updated"
    written = json.loads(path.read_text())
    assert [m["id"] for m in written] == ["1"]
    assert all(m["isResult"] is True for m in written)


# --- 12. JSON invalide ---------------------------------------------------------


def test_12_invalid_json_response_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get("not valid json"), now_fn=_now_fn)
    assert report.action == "error"
    assert not path.exists()


# --- 13. reponse JSON sans cle "dates" -----------------------------------------


def test_13_response_without_dates_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    body = json.dumps({"teams": {}, "players": []})
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(body), now_fn=_now_fn)
    assert report.action == "error"
    assert "Extraction Understat" in report.error_message
    assert not path.exists()


def test_13b_dates_wrong_type_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    body = json.dumps({"teams": {}, "players": [], "dates": {"not": "a list"}})
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(body), now_fn=_now_fn)
    assert report.action == "error"
    assert not path.exists()


# --- 14. reponse reseau en erreur ----------------------------------------------


def test_14_network_error_is_reported_and_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    path.write_text(json.dumps([_match("1", "2026-08-15 19:45:00")]), encoding="utf-8")
    content_before = path.read_bytes()
    report = sync_current_season(
        "ligue1", LEAGUE_NAME, "2026", path,
        http_get=_mock_http_get_raising(URLError("connection refused")),
        now_fn=_now_fn,
    )
    assert report.action == "error"
    assert "reseau" in report.error_message.lower()
    assert path.read_bytes() == content_before


# --- 15. reponse vide -----------------------------------------------------------


def test_15_empty_response_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload([])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "error"
    assert not path.exists()


# --- 16. equipe inconnue ---------------------------------------------------------


def test_16_unknown_team_is_rejected_when_known_team_ids_provided(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00", home_id="999", home_title="Equipe Fantome")])
    report = sync_current_season(
        "ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text),
        known_team_ids={"296"}, now_fn=_now_fn,
    )
    assert report.action == "error"
    assert "inconnue" in report.error_message.lower()
    assert not path.exists()


def test_16_known_team_check_is_opt_in_and_skipped_by_default(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00", home_id="999", home_title="Equipe Fantome")])
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "updated"


# --- 17. collision avec l'historique -------------------------------------------


def test_17_collision_with_historical_match_id_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload([_match("500", "2026-08-15 19:45:00")])
    report = sync_current_season(
        "ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text),
        historical_match_ids={"500"}, now_fn=_now_fn,
    )
    assert report.action == "error"
    assert "collision" in report.error_message.lower()
    assert not path.exists()


# --- 18/19. ecriture atomique / echec d'ecriture ------------------------------


def test_18_atomic_write_produces_valid_final_file(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00")])
    sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert json.loads(path.read_text())  # fichier final valide, parsable


def test_19_write_failure_leaves_local_file_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "f.json"
    original = [_match("1", "2026-08-15 19:45:00")]
    path.write_text(json.dumps(original), encoding="utf-8")
    content_before = path.read_bytes()

    import sys_foot_quant.data_engine.market_odds.current_season_merge as merge_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated disk failure")

    monkeypatch.setattr(merge_module.json, "dump", _boom)

    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")])
    with pytest.raises(RuntimeError, match="simulated disk failure"):
        sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert path.read_bytes() == content_before


# --- 20. dry-run ne modifie rien ------------------------------------------------


def test_20_dry_run_never_writes_but_reports_diff(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00")])
    report = sync_current_season(
        "ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), dry_run=True, now_fn=_now_fn
    )
    assert report.action == "dry_run_would_update"
    assert not path.exists()
    assert len(report.diff.new_matches) == 1


def test_20_dry_run_reports_no_change_when_nothing_new(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    matches = [_match("1", "2026-08-15 19:45:00")]
    path.write_text(json.dumps(matches), encoding="utf-8")
    payload_text = _fixture_payload(matches)
    report = sync_current_season(
        "ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), dry_run=True, now_fn=_now_fn
    )
    assert report.action == "dry_run_no_change"


# --- 21. aucun match futur dans le fichier final -----------------------------


def test_21_future_matches_never_enter_the_final_file(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    payload_text = _fixture_payload(
        [
            _match("1", "2026-08-15 19:45:00"),  # ancien, deja joue
            _match("2", "2026-08-22 19:45:00"),  # nouveau, deja joue
            _match("3", "2026-12-25 19:45:00", is_result=False),  # futur
        ]
    )
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)
    assert report.action == "updated"
    written = json.loads(path.read_text())
    assert {m["id"] for m in written} == {"1", "2"}
    assert "3" not in {m["id"] for m in written}


# --- Test explicite demande : anciens + nouveaux + futurs, resultat exact ----


def test_old_new_and_future_matches_are_classified_exactly(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    old_match = _match("1", "2026-08-15 19:45:00")
    path.write_text(json.dumps([old_match]), encoding="utf-8")

    new_match = _match("2", "2026-08-22 19:45:00")
    future_match = _match("3", "2026-12-25 19:45:00", is_result=False)
    payload_text = _fixture_payload([old_match, new_match, future_match])

    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)

    assert report.action == "updated"
    assert {m["id"] for m in report.diff.unchanged_matches} == {"1"}
    assert {m["id"] for m in report.diff.new_matches} == {"2"}
    assert not report.diff.modified_matches
    assert not report.diff.missing_from_source

    written_ids = {m["id"] for m in json.loads(path.read_text())}
    assert written_ids == {"1", "2"}  # exactement anciens+nouveaux, jamais le futur


# --- 22. fichier reel 2026/27 accepte sans modification parasite ------------


def test_22_real_2026_file_is_accepted_unchanged_when_resynced_with_itself(tmp_path: Path) -> None:
    with open(REAL_2026_FILE, encoding="utf-8") as f:
        real_matches = json.load(f)
    path = tmp_path / "ligue1_2026_datesData.json"
    path.write_text(json.dumps(real_matches), encoding="utf-8")
    content_before = path.read_bytes()

    payload_text = _fixture_payload(real_matches)
    report = sync_current_season("ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), now_fn=_now_fn)

    assert report.action == "no_change"
    assert path.read_bytes() == content_before
    assert len(report.diff.unchanged_matches) == 35


def test_format_report_contains_required_sections() -> None:
    path = Path("/nonexistent/does-not-matter.json")
    payload_text = _fixture_payload([_match("1", "2026-08-15 19:45:00")])
    report = sync_current_season(
        "ligue1", LEAGUE_NAME, "2026", path, http_get=_mock_http_get(payload_text), dry_run=True, now_fn=_now_fn
    )
    text = format_report(report)
    for section in ("SOURCE", "DIFF", "ACTION"):
        assert section in text
