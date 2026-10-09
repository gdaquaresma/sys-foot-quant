"""Tests cibles pour `collect_shadow_predictions` (PHASE SHADOW-AUTO-1).
Couvre uniquement le NOUVEAU comportement d'orchestration : fixture
admissible, doublon, echeance depassee, verification non concordante,
plusieurs fixtures dont une echoue, preservation/absence de doublon dans
le journal, absence de cote inventee. Ne reteste pas
`run_match_decision`/`run_prediction`/`record_prediction` eux-memes (deja
couverts par leurs propres suites)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNDERSTAT_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"

sys.path.insert(0, str(_REPO_ROOT / "src"))
from sys_foot_quant.data_engine.market_odds.ligue1_kickoff_cet_conversion import (  # noqa: E402
    build_cross_checked_kickoff,
)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def collector():
    return _load_module(_REPO_ROOT / "scripts" / "collect_shadow_predictions.py", "collect_shadow_predictions_test")


pytestmark = pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat reels non presents.")


def _verified_kickoff(fixture_date: date, local_time: datetime):
    return build_cross_checked_kickoff(
        fixture_date=fixture_date,
        kickoff_local_naive=local_time,
        source_local_time="test",
        cross_check_source="test",
        cross_check_local_time=local_time,  # concorde -> verified=True
    )


def _unverified_kickoff(fixture_date: date, local_time: datetime):
    diverging = local_time + timedelta(minutes=30)
    return build_cross_checked_kickoff(
        fixture_date=fixture_date,
        kickoff_local_naive=local_time,
        source_local_time="test",
        cross_check_source="test-divergent",
        cross_check_local_time=diverging,  # ne concorde pas -> verified=False
    )


# --- 1. Fixture admissible ----------------------------------------------------


def test_admissible_fixture_is_recorded(collector, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    ck = _verified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 20, 45))
    fixture = collector.FixtureToCollect("ligue1", "2026_27", "Lens", "Lyon", ck)

    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    result = collector.collect_one(fixture, now, journal_path=journal_path)

    assert result.status == "recorded"
    assert result.prediction_id is not None
    assert journal_path.exists()


# --- 2. Doublon ----------------------------------------------------------------


def test_duplicate_fixture_is_not_rewritten(collector, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    ck = _verified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 20, 45))
    fixture = collector.FixtureToCollect("ligue1", "2026_27", "Lens", "Lyon", ck)
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)

    first = collector.collect_one(fixture, now, journal_path=journal_path)
    second = collector.collect_one(fixture, now, journal_path=journal_path)

    assert first.status == "recorded"
    assert second.status == "duplicate"
    assert second.prediction_id == first.prediction_id
    # Une seule ligne "prediction" dans le journal, pas deux.
    lines = journal_path.read_text().strip().splitlines()
    prediction_lines = [json.loads(l) for l in lines if json.loads(l).get("record_type") == "prediction"]
    assert len(prediction_lines) == 1


# --- 3. Echeance depassee -------------------------------------------------------


def test_deadline_passed_fixture_is_excluded_and_nothing_written(collector, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    ck = _verified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 20, 45))  # -> 19:45 UTC (CET)
    fixture = collector.FixtureToCollect("ligue1", "2026_27", "Lens", "Lyon", ck)
    # now APRES decision_time (19:45 - 2h = 17:45 UTC) -> echeance depassee.
    now = datetime(2026, 11, 2, tzinfo=timezone.utc)

    result = collector.collect_one(fixture, now, journal_path=journal_path)

    assert result.status == "deadline_passed"
    assert result.prediction_id is None
    assert not journal_path.exists()


# --- 4. Verification horaire non concordante -----------------------------------


def test_unverified_kickoff_is_excluded_and_nothing_written(collector, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    ck = _unverified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 20, 45))
    fixture = collector.FixtureToCollect("ligue1", "2026_27", "Lens", "Lyon", ck)
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)

    result = collector.collect_one(fixture, now, journal_path=journal_path)

    assert result.status == "unverified"
    assert result.prediction_id is None
    assert not journal_path.exists()


# --- 5. Plusieurs fixtures, une echoue -----------------------------------------


def test_multiple_fixtures_one_failure_does_not_block_others(collector, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    ck_ok = _verified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 20, 45))
    ck_bad = _verified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 17, 15))

    fixtures = [
        collector.FixtureToCollect("ligue1", "2026_27", "EquipeInconnueXYZ", "Lyon", ck_bad),
        collector.FixtureToCollect("ligue1", "2026_27", "Monaco", "Toulouse", ck_ok),
    ]
    results = collector.collect_many(fixtures, now=now, journal_path=journal_path)

    assert results[0].status == "error"
    assert "EquipeInconnueXYZ" in results[0].detail or "inconnue" in results[0].detail.lower()
    assert results[1].status == "recorded"


# --- 6. Preservation du journal / absence de doublon sur un lot --------------


def test_batch_preserves_existing_journal_entries_without_duplication(collector, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    ck1 = _verified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 20, 45))
    ck2 = _verified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 17, 15))

    fixture1 = collector.FixtureToCollect("ligue1", "2026_27", "Lens", "Lyon", ck1)
    fixture2 = collector.FixtureToCollect("ligue1", "2026_27", "Monaco", "Toulouse", ck2)

    first_batch = collector.collect_many([fixture1], now=now, journal_path=journal_path)
    assert first_batch[0].status == "recorded"

    # Second lot : la meme fixture1 (doit etre detectee comme doublon) + une nouvelle (fixture2).
    second_batch = collector.collect_many([fixture1, fixture2], now=now, journal_path=journal_path)
    assert second_batch[0].status == "duplicate"
    assert second_batch[1].status == "recorded"

    lines = journal_path.read_text().strip().splitlines()
    prediction_lines = [json.loads(l) for l in lines if json.loads(l).get("record_type") == "prediction"]
    assert len(prediction_lines) == 2  # jamais 3 - fixture1 non dupliquee


# --- 7. Aucune cote inventee ----------------------------------------------------


def test_no_odds_provided_means_null_in_journal_never_invented(collector, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    ck = _verified_kickoff(date(2026, 11, 1), datetime(2026, 11, 1, 20, 45))
    fixture = collector.FixtureToCollect("ligue1", "2026_27", "Lens", "Lyon", ck)
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)

    collector.collect_one(fixture, now, journal_path=journal_path)

    lines = journal_path.read_text().strip().splitlines()
    rec = json.loads(lines[0])
    assert rec["market_odds_over_2_5"] is None
    assert rec["market_odds_under_2_5"] is None
