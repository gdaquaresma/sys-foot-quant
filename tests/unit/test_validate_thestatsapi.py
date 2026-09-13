"""Tests unitaires de la logique PURE de ``scripts/validate_thestatsapi.py``
(parsing des reponses TheStatsAPI/The Odds API, selection PIT,
diagnostic de granularite) - AUCUN de ces tests n'appelle un reseau reel
ni ne suppose une cle API presente : toutes les entrees sont des fixtures
JSON synthetiques ecrites a la main a partir de la documentation publique
(explicitement NON confirmees contre une reponse HTTP reelle, voir le
docstring du module teste), utilisees uniquement pour verifier que le
CODE DE PARSING/PIT lui-meme est correct - jamais pour affirmer une
propriete du fournisseur reel.

``main()`` (le seul point du script qui appelle reellement le reseau)
n'est PAS teste ici pour son comportement reseau : seul son chemin
"aucune cle" est verifie (test 11), car c'est le seul chemin
deterministe et sans acces reseau."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "validate_thestatsapi.py"


def _load_validate_thestatsapi():
    spec = importlib.util.spec_from_file_location("validate_thestatsapi_for_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vts():
    return _load_validate_thestatsapi()


_KICKOFF = datetime(2024, 11, 10, 16, 30, 0, tzinfo=timezone.utc)


# --- 1. parse_thestatsapi_odds_response -------------------------------------


def test_parse_thestatsapi_extracts_target_bookmaker_and_line(vts) -> None:
    raw = {
        "odds": [
            {
                "bookmaker": "Bet365",
                "market": "total_goals",
                "line": 2.5,
                "over": 1.73,
                "under": 2.10,
                "timestamp": "2024-11-10T10:00:00+00:00",
            }
        ]
    }
    snapshots = vts.parse_thestatsapi_odds_response(raw)
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.bookmaker == "Bet365"
    assert snap.line == 2.5
    assert snap.over_price == 1.73
    assert snap.under_price == 2.10
    assert snap.timestamp == datetime(2024, 11, 10, 10, 0, 0, tzinfo=timezone.utc)


def test_parse_thestatsapi_ignores_non_target_bookmaker(vts) -> None:
    raw = {
        "odds": [
            {
                "bookmaker": "Some Other Book",
                "market": "total_goals",
                "line": 2.5,
                "over": 1.80,
                "under": 2.00,
                "timestamp": "2024-11-10T10:00:00+00:00",
            }
        ]
    }
    assert vts.parse_thestatsapi_odds_response(raw) == []


def test_parse_thestatsapi_ignores_non_target_line(vts) -> None:
    raw = {
        "odds": [
            {
                "bookmaker": "Bet365",
                "market": "total_goals",
                "line": 3.5,
                "over": 2.50,
                "under": 1.50,
                "timestamp": "2024-11-10T10:00:00+00:00",
            }
        ]
    }
    assert vts.parse_thestatsapi_odds_response(raw) == []


def test_parse_thestatsapi_excludes_entry_without_timestamp(vts) -> None:
    """Une observation sans horodatage est structurellement inutilisable
    pour le PIT - exclue explicitement, jamais un timestamp invente."""
    raw = {
        "odds": [
            {
                "bookmaker": "Bet365",
                "market": "total_goals",
                "line": 2.5,
                "over": 1.73,
                "under": 2.10,
            }
        ]
    }
    assert vts.parse_thestatsapi_odds_response(raw) == []


def test_parse_thestatsapi_rejects_naive_timestamp(vts) -> None:
    raw = {
        "odds": [
            {
                "bookmaker": "Bet365",
                "market": "total_goals",
                "line": 2.5,
                "over": 1.73,
                "under": 2.10,
                "timestamp": "2024-11-10T10:00:00",
            }
        ]
    }
    with pytest.raises(ValueError, match="fuseau"):
        vts.parse_thestatsapi_odds_response(raw)


def test_parse_thestatsapi_accepts_alternate_field_names(vts) -> None:
    """``book``/``market_name``/``updated_at``/``over_price`` sont des
    alias documentes en meilleur effort - verifie qu'ils sont bien lus
    quand les noms primaires sont absents."""
    raw = {
        "data": [
            {
                "book": "Pinnacle",
                "market_name": "totals",
                "line": 2.5,
                "over_price": 1.72,
                "under_price": 2.21,
                "updated_at": "2024-11-10T09:00:00+00:00",
            }
        ]
    }
    snapshots = vts.parse_thestatsapi_odds_response(raw)
    assert len(snapshots) == 1
    assert snapshots[0].bookmaker == "Pinnacle"
    assert snapshots[0].over_price == 1.72


# --- 2. parse_the_odds_api_historical_response ------------------------------


def test_parse_the_odds_api_extracts_totals_at_2_5(vts) -> None:
    raw = {
        "timestamp": "2024-11-10T08:00:00+00:00",
        "data": {
            "bookmakers": [
                {
                    "title": "Pinnacle",
                    "markets": [
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "point": 2.5, "price": 1.72},
                                {"name": "Under", "point": 2.5, "price": 2.21},
                            ],
                        }
                    ],
                }
            ]
        },
    }
    snapshots = vts.parse_the_odds_api_historical_response(raw)
    assert len(snapshots) == 1
    assert snapshots[0].bookmaker == "Pinnacle"
    assert snapshots[0].over_price == 1.72
    assert snapshots[0].under_price == 2.21
    assert snapshots[0].timestamp == datetime(2024, 11, 10, 8, 0, 0, tzinfo=timezone.utc)


def test_parse_the_odds_api_without_root_timestamp_returns_empty(vts) -> None:
    assert vts.parse_the_odds_api_historical_response({"data": {"bookmakers": []}}) == []


def test_parse_the_odds_api_ignores_non_target_bookmaker(vts) -> None:
    raw = {
        "timestamp": "2024-11-10T08:00:00+00:00",
        "data": {
            "bookmakers": [
                {
                    "title": "Some Other Book",
                    "markets": [
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "point": 2.5, "price": 1.80},
                                {"name": "Under", "point": 2.5, "price": 2.00},
                            ],
                        }
                    ],
                }
            ]
        },
    }
    assert vts.parse_the_odds_api_historical_response(raw) == []


# --- 3. select_last_snapshot_before (regle PIT centrale) --------------------


def test_select_last_snapshot_before_returns_most_recent_eligible(vts) -> None:
    early = vts.OddsSnapshot(
        bookmaker="Bet365", market="totals", line=2.5, over_price=1.80, under_price=2.00,
        timestamp=datetime(2024, 11, 9, 8, 0, 0, tzinfo=timezone.utc), source="test",
    )
    late = vts.OddsSnapshot(
        bookmaker="Bet365", market="totals", line=2.5, over_price=1.73, under_price=2.10,
        timestamp=datetime(2024, 11, 10, 10, 0, 0, tzinfo=timezone.utc), source="test",
    )
    decision_time = datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc)
    result = vts.select_last_snapshot_before([early, late], decision_time)
    assert result is late


def test_select_last_snapshot_before_excludes_snapshot_at_exact_decision_time(vts) -> None:
    """Regle stricte ``<``, jamais ``<=`` - un snapshot horodate
    exactement a ``decision_time`` n'est PAS considere disponible."""
    at_decision_time = vts.OddsSnapshot(
        bookmaker="Bet365", market="totals", line=2.5, over_price=1.73, under_price=2.10,
        timestamp=datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc), source="test",
    )
    decision_time = datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc)
    assert vts.select_last_snapshot_before([at_decision_time], decision_time) is None


def test_select_last_snapshot_before_excludes_future_snapshot(vts) -> None:
    future = vts.OddsSnapshot(
        bookmaker="Bet365", market="totals", line=2.5, over_price=1.73, under_price=2.10,
        timestamp=datetime(2024, 11, 10, 17, 0, 0, tzinfo=timezone.utc), source="test",
    )
    decision_time = datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc)
    assert vts.select_last_snapshot_before([future], decision_time) is None


def test_select_last_snapshot_before_returns_none_for_empty_input(vts) -> None:
    assert vts.select_last_snapshot_before([], datetime(2024, 11, 10, 14, 30, 0, tzinfo=timezone.utc)) is None


# --- 4. diagnose_pit_granularity --------------------------------------------


def test_diagnose_pit_granularity_reports_no_observation(vts) -> None:
    diagnosis = vts.diagnose_pit_granularity([], _KICKOFF)
    assert "AUCUNE OBSERVATION" in diagnosis
    assert "INSUFFISAMMENT GARANTI" in diagnosis


def test_diagnose_pit_granularity_reports_insufficient_for_one_or_two_observations(vts) -> None:
    snap = vts.OddsSnapshot(
        bookmaker="Bet365", market="totals", line=2.5, over_price=1.73, under_price=2.10,
        timestamp=_KICKOFF, source="test",
    )
    before = vts.OddsSnapshot(
        bookmaker="Bet365", market="totals", line=2.5, over_price=1.75, under_price=2.05,
        timestamp=_KICKOFF.replace(day=9), source="test",
    )
    diagnosis = vts.diagnose_pit_granularity([before, snap], _KICKOFF)
    assert "INSUFFISAMMENT GARANTI" in diagnosis


def test_diagnose_pit_granularity_reports_exploitable_series_for_three_or_more(vts) -> None:
    snapshots = [
        vts.OddsSnapshot(
            bookmaker="Bet365", market="totals", line=2.5, over_price=1.73, under_price=2.10,
            timestamp=_KICKOFF - vts.timedelta(hours=h), source="test",
        )
        for h in (24, 12, 6)
    ]
    diagnosis = vts.diagnose_pit_granularity(snapshots, _KICKOFF)
    assert "serie temporelle exploitable" in diagnosis
    assert "INSUFFISAMMENT" not in diagnosis


def test_diagnose_pit_granularity_ignores_observations_after_kickoff(vts) -> None:
    """Une observation posterieure au coup d'envoi ne compte pas comme
    une observation PIT exploitable (etape 4 : distinguer les
    observations avant/apres kickoff)."""
    after = vts.OddsSnapshot(
        bookmaker="Bet365", market="totals", line=2.5, over_price=1.73, under_price=2.10,
        timestamp=_KICKOFF + vts.timedelta(hours=2), source="test",
    )
    diagnosis = vts.diagnose_pit_granularity([after], _KICKOFF)
    assert "AUCUNE OBSERVATION" in diagnosis


# --- 5. _require_aware -------------------------------------------------------


def test_require_aware_accepts_unix_timestamp(vts) -> None:
    result = vts._require_aware(1731232800, "test")
    assert result.tzinfo is not None


def test_require_aware_rejects_naive_string(vts) -> None:
    with pytest.raises(ValueError, match="fuseau"):
        vts._require_aware("2024-11-10T10:00:00", "test")


def test_require_aware_rejects_unparseable_type(vts) -> None:
    with pytest.raises(ValueError, match="non interpretable"):
        vts._require_aware(object(), "test")


# --- 6. _load_api_key --------------------------------------------------------


def test_load_api_key_returns_none_when_absent(vts, monkeypatch) -> None:
    monkeypatch.delenv("THESTATSAPI_API_KEY", raising=False)
    assert vts._load_api_key("THESTATSAPI_API_KEY") is None


def test_load_api_key_returns_value_when_present(vts, monkeypatch) -> None:
    monkeypatch.setenv("THESTATSAPI_API_KEY", "dummy-for-test-only")
    assert vts._load_api_key("THESTATSAPI_API_KEY") == "dummy-for-test-only"


# --- 7. main() - seul chemin deterministe sans reseau : aucune cle ---------


def test_main_exits_with_error_when_no_key_available(vts, monkeypatch, capsys) -> None:
    """Le seul comportement de ``main()`` verifiable sans reseau ni cle :
    arret immediat, code de sortie 1, message explicite - jamais une
    donnee fabriquee pour compenser l'absence de cle."""
    monkeypatch.delenv("THESTATSAPI_API_KEY", raising=False)
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    exit_code = vts.main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "aucune cle disponible" in captured.err
    assert "ne fabrique jamais de donnee" in captured.err


# --- 8. format_report --------------------------------------------------------


def test_format_report_shows_blocked_test_without_fabricating_data(vts) -> None:
    match = vts.REFERENCE_MATCHES[0]
    result = vts.MatchValidationResult(match=match, provider="thestatsapi", error="HTTP 403 (reponse serveur, cle non affichee).")
    report = vts.format_report([result])
    assert "TEST BLOQUE" in report
    assert "HTTP 403" in report


def test_format_report_shows_bookmaker_presence_from_real_snapshots(vts) -> None:
    match = vts.REFERENCE_MATCHES[0]
    snap = vts.OddsSnapshot(
        bookmaker="Bet365", market="totals", line=2.5, over_price=1.73, under_price=2.10,
        timestamp=_KICKOFF - vts.timedelta(hours=6), source="thestatsapi",
    )
    result = vts.MatchValidationResult(
        match=match, provider="thestatsapi", snapshots=[snap],
        granularity_diagnosis="1 observation - insuffisant",
        checkpoint_results={"T-6h": snap, "T-1h": None},
    )
    report = vts.format_report([result])
    assert "Bet365 disponible ? OUI (OBSERVE)" in report
    assert "Pinnacle disponible ? NON (absent de la reponse reelle)" in report
    assert "T-1h avant kickoff : AUCUNE observation valide" in report
