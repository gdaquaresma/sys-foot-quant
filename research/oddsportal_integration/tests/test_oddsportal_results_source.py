"""Tests du connecteur de recherche OddsPortal (``oddsportal_results_source.py``)
- AUCUN reseau reel : soit ``http_get`` est injecte (meme convention que
``research/xg_feasibility/tests/test_current_season_updater.py``), soit le
HTML teste est le fixture ``fixtures/results_page_sample.html`` - extrait
VERBATIM (2 objets de match reels, encore echappes puis re-echappes a
l'identique, voir le commentaire en tete du fixture) d'une vraie reponse
HTTP 200 capturee le 2026-10-10 contre
``https://www.oddsportal.com/football/france/ligue-1/results/``. Le fixture
contient deliberement un bloc ``__next_f.push`` "decoy" (sans donnees de
match) avant le bloc porteur de donnees, pour verifier que la selection du
bon bloc n'est pas un simple "premier bloc trouve"."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.oddsportal_integration.oddsportal_results_source import (
    OddsPortalFetchError,
    OddsPortalMatch,
    OddsPortalParsingError,
    _extract_balanced_json_object,
    _find_next_f_string_literals,
    _parse_goals,
    _select_match_bearing_chunk,
    extract_match_objects,
    fetch_and_parse_results,
    fetch_results_page,
    parse_oddsportal_match,
    parse_results_page,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REAL_RESULTS_PAGE_HTML = (FIXTURES_DIR / "results_page_sample.html").read_text(encoding="utf-8")


def _minimal_match_object(**overrides: object) -> dict:
    """Un objet de match minimal mais structurellement complet (tous les
    champs obligatoires de ``parse_oddsportal_match`` presents) - PAS une
    copie du fixture reel, utilise pour les tests unitaires cibles
    (``parse_oddsportal_match`` seul, independamment de l'extraction HTML)."""
    base = {
        "id": 999001,
        "is-double": False,
        "tournament-name": "Ligue 1",
        "home-name": "Lens",
        "away-name": "Lyon",
        "date-start-timestamp": 1760035500,  # 2025-10-09T18:45:00Z
        "event-stage-name": "Finished",
        "homeResult": "2",
        "awayResult": "1",
        "venue": "Stade Bollaert-Delelis",
        "partialresult": "1:0, 1:1",
        "odds": [
            {"bettingTypeId": 1, "scopeId": 2, "outcomeResultId": 1, "outcomeId": "a1", "avgOdds": 2.61, "maxOdds": 2.72},
            {"bettingTypeId": 1, "scopeId": 2, "outcomeResultId": 2, "outcomeId": "a2", "avgOdds": 3.6, "maxOdds": 3.75},
            {"bettingTypeId": 1, "scopeId": 2, "outcomeResultId": 2, "outcomeId": "a3", "avgOdds": 2.57, "maxOdds": 2.7},
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# fetch_results_page
# ---------------------------------------------------------------------------


def test_fetch_results_page_uses_the_injected_http_get_without_touching_the_network():
    captured_urls = []

    def fake_http_get(url: str) -> str:
        captured_urls.append(url)
        return "<html>stub</html>"

    body = fetch_results_page("https://example.test/results/", http_get=fake_http_get)

    assert body == "<html>stub</html>"
    assert captured_urls == ["https://example.test/results/"]


def test_fetch_results_page_propagates_a_failure_raised_by_the_injected_http_get():
    def failing_http_get(url: str) -> str:
        raise OddsPortalFetchError("injected failure, simulates a real urllib.error.URLError")

    with pytest.raises(OddsPortalFetchError):
        fetch_results_page("https://example.test/results/", http_get=failing_http_get)


def test_fetch_results_page_wraps_a_real_network_failure_as_oddsportal_fetch_error(monkeypatch):
    """Chemin par defaut (pas d'``http_get`` injecte) : une vraie
    ``OSError`` levee par ``urlopen`` (timeout, DNS, etc.) doit ressortir
    comme ``OddsPortalFetchError``, jamais une page vide silencieuse."""
    import research.oddsportal_integration.oddsportal_results_source as module

    def raising_urlopen(*args, **kwargs):
        raise OSError("simulated DNS failure")

    monkeypatch.setattr(module, "urlopen", raising_urlopen)

    with pytest.raises(OddsPortalFetchError):
        fetch_results_page("https://example.test/results/")


# ---------------------------------------------------------------------------
# _find_next_f_string_literals - l'analyseur respectant les echappements
# ---------------------------------------------------------------------------


def test_find_next_f_string_literals_respects_backslash_escaped_quotes():
    """Cas critique : un ``.*?`` naif s'arreterait au premier ``\\"``
    rencontre (le tout premier caractere du contenu ici), tronquant le
    litteral - le scanner doit traverser l'echappement et ne s'arreter
    qu'au guillemet de fermeture NON echappe reel."""
    html = r'''<script>self.__next_f.push([1,"a\"b\\c\"d"])</script>'''

    literals = _find_next_f_string_literals(html)

    assert literals == [r'a\"b\\c\"d']


def test_find_next_f_string_literals_finds_every_occurrence_in_order():
    html = (
        'self.__next_f.push([1,"first"])'
        'some other markup in between'
        'self.__next_f.push([1,"second"])'
    )

    literals = _find_next_f_string_literals(html)

    assert literals == ["first", "second"]


def test_find_next_f_string_literals_returns_empty_list_when_marker_absent():
    assert _find_next_f_string_literals("<html><body>no RSC push here</body></html>") == []


# ---------------------------------------------------------------------------
# _select_match_bearing_chunk
# ---------------------------------------------------------------------------


def test_select_match_bearing_chunk_skips_decoy_blocks_without_match_markers():
    literals = _find_next_f_string_literals(REAL_RESULTS_PAGE_HTML)
    assert len(literals) == 2, "le fixture doit contenir exactement 1 bloc decoy + 1 bloc porteur de matchs"

    chunk = _select_match_bearing_chunk(literals)

    assert chunk is not None
    assert chunk == literals[1], "le bloc decoy (premier) ne doit jamais etre choisi"


def test_select_match_bearing_chunk_returns_none_when_no_literal_qualifies():
    assert _select_match_bearing_chunk(["totally unrelated navigation payload"]) is None
    assert _select_match_bearing_chunk([]) is None


# ---------------------------------------------------------------------------
# _extract_balanced_json_object / extract_match_objects
# ---------------------------------------------------------------------------


def test_extract_balanced_json_object_stops_at_the_matching_closing_brace_not_the_first_one():
    text = '{"id":1,"is-double":false,"nested":{"a":1}}TRAILING_GARBAGE'

    extracted = _extract_balanced_json_object(text, 0)

    assert extracted == '{"id":1,"is-double":false,"nested":{"a":1}}'
    assert json.loads(extracted)["nested"] == {"a": 1}


def test_extract_balanced_json_object_ignores_braces_inside_json_strings():
    text = '{"id":1,"is-double":false,"note":"looks like a brace } but is just text"}TAIL'

    extracted = _extract_balanced_json_object(text, 0)

    parsed = json.loads(extracted)
    assert parsed["note"] == "looks like a brace } but is just text"


def test_extract_balanced_json_object_raises_parsing_error_when_truncated():
    text = '{"id":1,"is-double":false,"incomplete":'  # pas de fermeture

    with pytest.raises(OddsPortalParsingError):
        _extract_balanced_json_object(text, 0)


def test_extract_match_objects_skips_a_corrupted_object_without_failing_the_whole_batch():
    # separators=(",", ":") : format compact SANS espace, celui reellement
    # observe dans le flux RSC (``{"id":10722097,"is-double":...}``) et
    # celui attendu par ``_MATCH_OBJECT_START`` - json.dumps par defaut
    # inserait des espaces et ne matcherait pas le motif de debut d'objet.
    good_object = json.dumps(_minimal_match_object(id=1), separators=(",", ":"))
    corrupted_object = '{"id":2,"is-double":not_valid_json_here}'
    other_good_object = json.dumps(
        _minimal_match_object(id=3, **{"home-name": "Monaco", "away-name": "Toulouse"}),
        separators=(",", ":"),
    )
    chunk = f'NOISE {good_object} NOISE {corrupted_object} NOISE {other_good_object} NOISE'

    objects = extract_match_objects(chunk)

    assert len(objects) == 2
    assert {obj["id"] for obj in objects} == {1, 3}


def test_extract_match_objects_returns_empty_list_when_nothing_matches():
    assert extract_match_objects("no match-shaped objects in this text at all") == []


def test_extract_match_objects_on_the_real_fixture_finds_exactly_the_two_embedded_matches():
    literals = _find_next_f_string_literals(REAL_RESULTS_PAGE_HTML)
    chunk = _select_match_bearing_chunk(literals)
    unescaped = json.loads('"' + chunk + '"')

    objects = extract_match_objects(unescaped)

    names = {(obj["home-name"], obj["away-name"]) for obj in objects}
    assert names == {("Brest", "Angers"), ("Lens", "Lyon")}


# ---------------------------------------------------------------------------
# parse_oddsportal_match
# ---------------------------------------------------------------------------


def test_parse_oddsportal_match_converts_a_complete_finished_match_object():
    match = parse_oddsportal_match(_minimal_match_object(), source_url="https://example.test/results/")

    assert isinstance(match, OddsPortalMatch)
    assert match.event_id == 999001
    assert match.home_team == "Lens"
    assert match.away_team == "Lyon"
    assert match.is_finished is True
    assert match.home_goals == 2
    assert match.away_goals == 1
    assert match.venue == "Stade Bollaert-Delelis"
    assert match.raw_partial_result == "1:0, 1:1"
    assert match.source_url == "https://example.test/results/"
    assert len(match.odds) == 3
    # Les cotes restent BRUTES - aucun label home/draw/away fabrique ici.
    assert match.odds[0].outcome_result_id == 1
    assert match.odds[1].outcome_result_id == 2
    assert match.odds[2].outcome_result_id == 2


def test_parse_oddsportal_match_on_a_not_yet_played_match_leaves_goals_as_none():
    not_played = _minimal_match_object(
        **{"event-stage-name": "Scheduled", "homeResult": "", "awayResult": ""}
    )

    match = parse_oddsportal_match(not_played, source_url="https://example.test/results/")

    assert match.is_finished is False
    assert match.home_goals is None
    assert match.away_goals is None


def test_parse_oddsportal_match_raises_parsing_error_when_a_required_field_is_missing():
    incomplete = _minimal_match_object()
    del incomplete["home-name"]

    with pytest.raises(OddsPortalParsingError):
        parse_oddsportal_match(incomplete, source_url="https://example.test/results/")


def test_parse_oddsportal_match_tolerates_missing_optional_fields():
    minimal = _minimal_match_object(venue=None, partialresult=None, odds=[])
    del minimal["tournament-name"]

    match = parse_oddsportal_match(minimal, source_url="https://example.test/results/")

    assert match.tournament_name == ""
    assert match.venue is None
    assert match.raw_partial_result is None
    assert match.odds == ()


@pytest.mark.parametrize(
    ("raw_result", "expected"),
    [
        ("2", 2),
        ("0", 0),
        ("", None),
        (None, None),
        ("not-a-number", None),
    ],
)
def test_parse_goals_never_guesses_a_default_value(raw_result, expected):
    assert _parse_goals(raw_result) == expected


# ---------------------------------------------------------------------------
# parse_results_page - orchestration complete, fail-closed
# ---------------------------------------------------------------------------


def test_parse_results_page_on_the_real_fixture_returns_the_two_expected_matches():
    matches = parse_results_page(REAL_RESULTS_PAGE_HTML, source_url="https://example.test/results/")

    assert len(matches) == 2
    by_teams = {(m.home_team, m.away_team): m for m in matches}

    scheduled = by_teams[("Brest", "Angers")]
    assert scheduled.is_finished is False
    assert scheduled.home_goals is None and scheduled.away_goals is None

    finished = by_teams[("Lens", "Lyon")]
    assert finished.is_finished is True
    assert finished.home_goals == 2
    assert finished.away_goals == 1
    assert finished.event_id == 10722097
    assert all(m.source_url == "https://example.test/results/" for m in matches)


def test_parse_results_page_raises_parsing_error_when_no_next_f_block_at_all():
    with pytest.raises(OddsPortalParsingError):
        parse_results_page("<html><body>CAPTCHA or error page, no RSC data</body></html>", source_url="https://example.test/")


def test_parse_results_page_raises_parsing_error_when_blocks_exist_but_none_carries_match_data():
    html = 'self.__next_f.push([1,"just some unrelated navigation JSON payload"])'

    with pytest.raises(OddsPortalParsingError):
        parse_results_page(html, source_url="https://example.test/")


def test_parse_results_page_raises_parsing_error_when_the_chunk_is_not_a_decodable_js_string():
    # Guillemet non echappe au milieu du contenu -> ne desescape pas comme
    # une chaine JSON valide d'un seul tenant.
    html = r'self.__next_f.push([1,"home-name is-double but "broken" escaping"])'

    with pytest.raises(OddsPortalParsingError):
        parse_results_page(html, source_url="https://example.test/")


def test_parse_results_page_raises_parsing_error_when_chunk_found_but_zero_valid_match_objects():
    # Contient les marqueurs de selection ("home-name"/"is-double") mais
    # aucun objet JSON valide ne matche le motif de debut d'objet attendu.
    escaped_payload = json.dumps('mentions home-name and is-double but no real object here').replace('"', '\\"')[1:-1]
    html = f'self.__next_f.push([1,"{escaped_payload}"])'

    with pytest.raises(OddsPortalParsingError):
        parse_results_page(html, source_url="https://example.test/")


# ---------------------------------------------------------------------------
# fetch_and_parse_results - point d'entree pratique
# ---------------------------------------------------------------------------


def test_fetch_and_parse_results_raises_key_error_for_an_unknown_competition():
    with pytest.raises(KeyError):
        fetch_and_parse_results("bundesliga")


def test_fetch_and_parse_results_wires_fetch_and_parse_together_via_injected_http_get():
    def fake_http_get(url: str) -> str:
        assert url == "https://www.oddsportal.com/football/france/ligue-1/results/"
        return REAL_RESULTS_PAGE_HTML

    matches = fetch_and_parse_results("ligue1", http_get=fake_http_get)

    assert len(matches) == 2
    assert {(m.home_team, m.away_team) for m in matches} == {("Brest", "Angers"), ("Lens", "Lyon")}
