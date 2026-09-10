"""Tests d'integration CLI pour ``predict_match.py --record-shadow`` :
verifie que le flag execute exactement le pipeline R3 existant puis
journalise une copie immuable, sans jamais dupliquer une observation
identique."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "predict_match.py"
_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"


def _load_predict_match():
    spec = importlib.util.spec_from_file_location("predict_match_for_shadow_cli_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def predict_match():
    return _load_predict_match()


runner = CliRunner()

pytestmark = pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat reels non presents.")


def _cli_args(journal_path: Path, **overrides) -> list[str]:
    args = {
        "--competition": "liga",
        "--season": "2024_25",
        "--home-team": "Las Palmas",
        "--away-team": "Real Valladolid",
        "--kickoff-utc": "2024-12-07T13:00:00",
        "--market-odds-over-2-5": "1.9",
        "--market-odds-under-2-5": "1.9",
        "--shadow-journal-path": str(journal_path),
    }
    args.update(overrides)
    flat: list[str] = ["--record-shadow"]
    for k, v in args.items():
        flat += [k, v]
    return flat


def test_record_shadow_flag_writes_one_observation(predict_match, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    result = runner.invoke(predict_match.app, _cli_args(journal_path))

    assert result.exit_code == 0, result.output
    assert "Shadow Mode : observation enregistree" in result.output
    assert journal_path.exists()
    lines = journal_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["record_type"] == "prediction"
    assert record["home_team"] == "Las Palmas"
    assert record["decision"] == "NO_BET"


def test_record_shadow_flag_deduplicates_on_rerun(predict_match, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    runner.invoke(predict_match.app, _cli_args(journal_path))
    result_2 = runner.invoke(predict_match.app, _cli_args(journal_path))

    assert result_2.exit_code == 0, result_2.output
    assert "deja enregistree" in result_2.output
    assert len(journal_path.read_text().strip().splitlines()) == 1


def test_without_record_shadow_flag_nothing_is_written(predict_match, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    args = _cli_args(journal_path)
    args.remove("--record-shadow")
    result = runner.invoke(predict_match.app, args)

    assert result.exit_code == 0, result.output
    assert "Shadow Mode" not in result.output
    assert not journal_path.exists()


def test_recorded_output_matches_run_prediction_exactly(predict_match, tmp_path) -> None:
    journal_path = tmp_path / "predictions.jsonl"
    runner.invoke(predict_match.app, _cli_args(journal_path))

    direct_output = predict_match.run_prediction(
        competition="liga", season="2024_25", home_team="Las Palmas", away_team="Real Valladolid",
        kickoff_utc=datetime(2024, 12, 7, 13, 0, 0), market_odds={"Over": 1.9, "Under": 1.9},
    )
    record = json.loads(journal_path.read_text().strip())
    assert record["decision"] == direct_output.decision.decision
    assert record["decision_reason"] == direct_output.decision.decision_reason
    assert record["models"]["poisson_simple"]["lambda"] == pytest.approx(direct_output.models["poisson_simple"].lam)
