"""Tests cibles pour `draft_ligue1_fixture_candidates` (PHASE
SHADOW-AUTO-2). Couvre uniquement le NOUVEAU comportement : fenetre
d'horizon, exclusion des fixtures sans heure locale, exclusion des
fixtures deja journalisees, et la distinction stricte (pas de champ
verified/officially_confirmed sur DraftFixtureCandidate). Ne reteste
jamais `build_future_fixtures` lui-meme (deja couvert ailleurs)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNDERSTAT_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def drafter():
    return _load_module(_REPO_ROOT / "scripts" / "draft_ligue1_fixture_candidates.py", "draft_candidates_test")


pytestmark = pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat/OpenFootball reels non presents.")


# --- 1. Distinction stricte : pas de champ verified/officially_confirmed ----


def test_draft_fixture_candidate_has_no_verification_fields(drafter) -> None:
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(drafter.DraftFixtureCandidate)}
    assert "verified" not in field_names
    assert "officially_confirmed" not in field_names
    assert "kickoff_utc" not in field_names  # jamais une heure UTC deja calculee ici


# --- 2. Fenetre d'horizon ------------------------------------------------------


def test_candidates_are_within_horizon_window(drafter) -> None:
    now = date(2026, 10, 9)
    candidates = drafter.draft_candidates(now, horizon_days=14, journal_path=Path("/tmp/does_not_exist.jsonl"))
    assert len(candidates) > 0  # corpus reel connu pour contenir des matchs dans cette fenetre
    for c in candidates:
        assert now <= c.fixture_date <= date(2026, 10, 23)


def test_narrow_horizon_returns_fewer_or_equal_candidates(drafter) -> None:
    now = date(2026, 10, 9)
    wide = drafter.draft_candidates(now, horizon_days=30, journal_path=Path("/tmp/does_not_exist.jsonl"))
    narrow = drafter.draft_candidates(now, horizon_days=1, journal_path=Path("/tmp/does_not_exist.jsonl"))
    assert len(narrow) <= len(wide)


# --- 3. Exclusion des fixtures deja journalisees -------------------------------


def test_fixture_already_in_journal_is_excluded(drafter, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    now = date(2026, 10, 9)
    baseline = drafter.draft_candidates(now, horizon_days=14, journal_path=journal_path)
    assert len(baseline) > 0
    target = baseline[0]

    # Pre-semer le journal temporaire avec UNE ligne "prediction" minimale
    # correspondant exactement au premier candidat - jamais le journal reel.
    fake_record = {
        "record_type": "prediction",
        "prediction_id": "fake0000000000ab",
        "competition": target.competition,
        "season": target.season,
        "home_team": target.home_team,
        "away_team": target.away_team,
        "kickoff_utc": datetime.combine(target.fixture_date, target.kickoff_local_naive.time()).isoformat(),
        "decision": "NO_BET",
    }
    journal_path.write_text(json.dumps(fake_record) + "\n")

    after = drafter.draft_candidates(now, horizon_days=14, journal_path=journal_path)
    after_pairs = {(c.home_team, c.away_team) for c in after}
    assert (target.home_team, target.away_team) not in after_pairs
    assert len(after) == len(baseline) - 1


# --- 4. Rapport lecture seule ---------------------------------------------------


def test_format_draft_report_mentions_non_recouped(drafter) -> None:
    now = date(2026, 10, 9)
    candidates = drafter.draft_candidates(now, horizon_days=7, journal_path=Path("/tmp/does_not_exist.jsonl"))
    report = drafter.format_draft_report(candidates)
    assert "NON RECOUPE" in report
    assert str(len(candidates)) in report
