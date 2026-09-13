"""Tests unitaires du POC de recherche de sources gratuites de cotes
historiques deja telechargeables (``scripts/poc_free_historical_odds_sources.py``).

Aucun de ces tests n'appelle le reseau. La fixture CSV ci-dessous
reprend VERBATIM quelques lignes reellement observees en telechargeant
``eatpizzanot/soccer-dataset`` (GitHub, ``samples/odds.csv``, licence
CC-BY-4.0) dans cette session - jamais une donnee fabriquee. Elle sert a
verifier que le code d'analyse de granularite est correct sur des
donnees reelles, sans dependre de la disponibilite du reseau pour les
tests."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "poc_free_historical_odds_sources.py"

# Extrait REEL (verbatim) de eatpizzanot/soccer-dataset samples/odds.csv,
# telecharge le 2026-09-13 depuis raw.githubusercontent.com. Chaque
# fixture_id n'apparait qu'une seule fois - c'est precisement ce que ce
# test verifie, pas une hypothese construite pour faire passer le test.
_REAL_SAMPLE_CSV_EXTRACT = """fixture_id,home_win,draw,away_win,bookmaker,source,in_csv,in_pq,known_at
542187,2.6,3.37,2.84,Pinnacle,API-Football-closing,true,false,2024-03-16 00:00:00
212466,2.92,3.06,2.77,Pinnacle,API-Football-closing,true,false,2019-01-19 14:00:00
177846,2.71,3.5,2.62,Pinnacle,API-Football-closing,true,false,2018-09-22 14:00:00
140168,2.21,3.61,3.36,Pinnacle,API-Football-closing,true,false,2021-07-09 00:00:00
189588,1.83,3.3,4.75,Bet365,CSV,false,true,2022-03-15 19:45:00
227355,2.3,3.6,2.9,Bet365,CSV,false,true,2023-05-06 13:30:00
"""


def _load_poc():
    spec = importlib.util.spec_from_file_location("poc_free_historical_odds_sources_for_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def poc():
    return _load_poc()


# --- 1. analyze_odds_csv sur un extrait reel ---------------------------


def test_analyze_odds_csv_counts_rows_and_unique_matches(poc) -> None:
    analysis = poc.analyze_odds_csv(_REAL_SAMPLE_CSV_EXTRACT)
    assert analysis.total_rows == 6
    assert analysis.unique_match_keys == 6  # chaque fixture_id est unique dans cet extrait


def test_analyze_odds_csv_detects_single_observation_per_match(poc) -> None:
    """Confirme empiriquement (sur des donnees reelles, pas une
    hypothese) que ce dataset n'a jamais plus d'une ligne par match."""
    analysis = poc.analyze_odds_csv(_REAL_SAMPLE_CSV_EXTRACT)
    assert analysis.max_rows_per_match == 1
    assert analysis.is_single_snapshot_per_match is True
    assert analysis.rows_per_match_distribution == {1: 6}


def test_analyze_odds_csv_extracts_real_bookmakers_and_sources(poc) -> None:
    analysis = poc.analyze_odds_csv(_REAL_SAMPLE_CSV_EXTRACT)
    assert "Pinnacle" in analysis.bookmakers_observed
    assert "Bet365" in analysis.bookmakers_observed
    assert "API-Football-closing" in analysis.sources_observed
    assert "CSV" in analysis.sources_observed


def test_analyze_odds_csv_captures_real_columns(poc) -> None:
    analysis = poc.analyze_odds_csv(_REAL_SAMPLE_CSV_EXTRACT)
    assert analysis.columns == ("fixture_id", "home_win", "draw", "away_win", "bookmaker", "source", "in_csv", "in_pq", "known_at")


def test_analyze_odds_csv_raises_on_empty_file(poc) -> None:
    with pytest.raises(ValueError, match="vide"):
        poc.analyze_odds_csv("")


# --- 2. classify_pit_capability ------------------------------------------


def test_classify_pit_capability_reports_category_c_for_single_snapshot(poc) -> None:
    analysis = poc.analyze_odds_csv(_REAL_SAMPLE_CSV_EXTRACT)
    verdict = poc.classify_pit_capability(analysis)
    assert "CATEGORIE C" in verdict
    assert "PAS de PIT" in verdict


def test_classify_pit_capability_reports_candidate_when_multiple_observations_exist(poc) -> None:
    """Construit un extrait synthetique avec 2 lignes pour le meme
    fixture_id (jamais observe reellement dans ce dataset - sert
    uniquement a verifier que le code de classification distinguerait
    correctement un vrai cas de serie temporelle s'il en rencontrait un)."""
    synthetic_multi_row_csv = (
        "fixture_id,home_win,draw,away_win,bookmaker,source,in_csv,in_pq,known_at\n"
        "999999,2.0,3.0,4.0,Pinnacle,API-Football,true,false,2024-01-01 08:00:00\n"
        "999999,2.1,3.1,3.9,Pinnacle,API-Football,true,false,2024-01-01 18:00:00\n"
    )
    analysis = poc.analyze_odds_csv(synthetic_multi_row_csv)
    verdict = poc.classify_pit_capability(analysis)
    assert "CATEGORIE A/B CANDIDATE" in verdict
    assert analysis.is_single_snapshot_per_match is False


# --- 3. select_last_observation_before (regle PIT, degenere ici) --------


def test_select_last_observation_before_returns_the_single_observation_when_eligible(poc) -> None:
    obs = poc.OddsObservation(
        match_key="542187", bookmaker="Pinnacle", market="1x2",
        price=2.6, timestamp=datetime(2024, 3, 16, 0, 0, 0, tzinfo=timezone.utc),
    )
    decision_time = datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
    assert poc.select_last_observation_before([obs], decision_time) is obs


def test_select_last_observation_before_excludes_observation_after_decision_time(poc) -> None:
    """Avec une seule observation par match (le cas reel de ce dataset),
    si cette unique observation est APRES decision_time, il ne reste
    RIEN d'exploitable pour le PIT - la fonction ne doit jamais
    extrapoler une valeur anterieure inexistante."""
    obs = poc.OddsObservation(
        match_key="542187", bookmaker="Pinnacle", market="1x2",
        price=2.6, timestamp=datetime(2024, 3, 16, 12, 0, 0, tzinfo=timezone.utc),
    )
    decision_time = datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
    assert poc.select_last_observation_before([obs], decision_time) is None


def test_select_last_observation_before_excludes_at_exact_decision_time(poc) -> None:
    obs = poc.OddsObservation(
        match_key="542187", bookmaker="Pinnacle", market="1x2",
        price=2.6, timestamp=datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc),
    )
    decision_time = datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
    assert poc.select_last_observation_before([obs], decision_time) is None


def test_select_last_observation_before_returns_none_for_empty_input(poc) -> None:
    assert poc.select_last_observation_before([], datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc)) is None


# --- 4. download_text_file : chemin d'echec reseau, jamais de fabrication ---


def test_download_text_file_reports_failure_without_fabricating_data(poc, monkeypatch) -> None:
    def _raise_urlerror(*args, **kwargs):
        from urllib.error import URLError

        raise URLError("simulated network failure")

    monkeypatch.setattr(poc, "urlopen", _raise_urlerror)
    with pytest.raises(poc.DownloadBlockedError, match="Connexion impossible"):
        poc.download_text_file("https://example.invalid/data.csv")


# --- 5. attempt_download_beatthebookie_sample : jamais de fabrication ------


def test_attempt_download_beatthebookie_sample_reports_failure_as_structured_result(poc, monkeypatch) -> None:
    """Meme discipline que download_text_file, mais retourne un resultat
    structure au lieu de lever - verifie que l'echec (le cas reel observe
    dans cette session, Dropbox bloque) est rapporte tel quel, sans
    donnee de repli fabriquee."""

    def _raise_urlerror(*args, **kwargs):
        from urllib.error import URLError

        raise URLError("simulated network failure")

    monkeypatch.setattr(poc, "urlopen", _raise_urlerror)
    result = poc.attempt_download_beatthebookie_sample()
    assert result.succeeded is False
    assert "Connexion impossible" in result.detail
    assert result.url == poc.BEATTHEBOOKIE_ODDS_SERIES_DROPBOX_URL


def test_attempt_download_beatthebookie_sample_reports_http_error(poc, monkeypatch) -> None:
    def _raise_httperror(*args, **kwargs):
        from urllib.error import HTTPError

        raise HTTPError("https://www.dropbox.com/x", 403, "Forbidden", {}, None)

    monkeypatch.setattr(poc, "urlopen", _raise_httperror)
    result = poc.attempt_download_beatthebookie_sample()
    assert result.succeeded is False
    assert "403" in result.detail


# --- 6. check_beatthebookie_mirrors_for_real_data --------------------------


def test_check_mirrors_reports_nothing_when_all_paths_404(poc, monkeypatch) -> None:
    """Cas reellement observe dans cette session : les 72 combinaisons
    depot x chemin renvoient 404 - aucune anomalie a rapporter, jamais un
    resultat fabrique pour combler l'absence."""

    def _raise_404(*args, **kwargs):
        from urllib.error import HTTPError

        raise HTTPError("https://raw.githubusercontent.com/x", 404, "Not Found", {}, None)

    monkeypatch.setattr(poc, "urlopen", _raise_404)
    results = poc.check_beatthebookie_mirrors_for_real_data(repos=("owner/repo",), paths=("data/x.csv",), branches=("master",))
    assert results == []


def test_check_mirrors_reports_a_real_file_when_found(poc, monkeypatch) -> None:
    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(poc, "urlopen", lambda *args, **kwargs: _FakeResponse())
    results = poc.check_beatthebookie_mirrors_for_real_data(repos=("owner/repo",), paths=("data/x.csv",), branches=("master",))
    assert len(results) == 1
    assert results[0].succeeded is True


def test_check_mirrors_reports_non_404_anomalies(poc, monkeypatch) -> None:
    def _raise_500(*args, **kwargs):
        from urllib.error import HTTPError

        raise HTTPError("https://raw.githubusercontent.com/x", 500, "Server Error", {}, None)

    monkeypatch.setattr(poc, "urlopen", _raise_500)
    results = poc.check_beatthebookie_mirrors_for_real_data(repos=("owner/repo",), paths=("data/x.csv",), branches=("master",))
    assert len(results) == 1
    assert results[0].succeeded is False
    assert "500" in results[0].detail
