"""Garde-fous anti-fuite pour
``data_engine.market_odds.future_match_dataset.build_match_train_dataframes``
- point d'entree walk-forward pour un match CIBLE (passe ou futur),
construit en reutilisant SANS MODIFICATION
``backtesting_engine.real_data_walk_forward._goals_train_df``/
``._xg_train_df`` (deja testees en leakage,
``tests/leakage/test_real_data_walk_forward_point_in_time.py``).

Les garanties verifiees ici sont donc, par construction, HERITEES de ces
fonctions - ce module verifie qu'aucune fuite n'est introduite par le fin
point d'entree ajoute (resolution du sentinel ``exclude_match_id``, absence
de tri prealable requis), pas que le mecanisme point-in-time lui-meme est
correct (deja prouve ailleurs)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.backtesting_engine.real_data_walk_forward import RealMatchRecord
from sys_foot_quant.data_engine.market_odds.future_match_dataset import build_match_train_dataframes

_T0 = datetime(2024, 1, 1)


def _record(
    match_id: str,
    kickoff: datetime,
    home_team_id: int = 0,
    away_team_id: int = 1,
    home_goals: int = 1,
    away_goals: int = 0,
    goals_delay_hours: float = 2.0,
    xg_delay_hours: float = 48.0,
) -> RealMatchRecord:
    return RealMatchRecord(
        match_id=match_id,
        league="TEST",
        kickoff_utc=kickoff,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=1.2,
        away_xg=0.8,
        goals_knowledge_time=kickoff + timedelta(hours=goals_delay_hours),
        xg_knowledge_time=kickoff + timedelta(hours=xg_delay_hours),
    )


# --- 1. un match futur ajoute a l'historique ne fuite jamais dans le passe -


def test_adding_a_future_match_never_changes_the_target_train_dataframes() -> None:
    records = [_record(str(i), _T0 + timedelta(days=i)) for i in range(10)]
    decision_time = _T0 + timedelta(days=20)

    goals_before, xg_before = build_match_train_dataframes(records, home_team_id=0, away_team_id=1, decision_time=decision_time)

    future = _record("future", _T0 + timedelta(days=1000))
    goals_after, xg_after = build_match_train_dataframes(
        records + [future], home_team_id=0, away_team_id=1, decision_time=decision_time
    )

    pd_testing_assert_frame_equal(goals_before, goals_after)
    pd_testing_assert_frame_equal(xg_before, xg_after)


def pd_testing_assert_frame_equal(a, b) -> None:
    import pandas as pd

    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))


# --- 2. insertion d'un match entre deux observations existantes -----------


def test_inserting_a_match_before_decision_time_is_included() -> None:
    records = [_record("0", _T0), _record("2", _T0 + timedelta(days=2))]
    decision_time = _T0 + timedelta(days=10)
    goals_before, _ = build_match_train_dataframes(records, home_team_id=0, away_team_id=1, decision_time=decision_time)

    inserted = _record("1", _T0 + timedelta(days=1))  # intercale chronologiquement, connu avant decision_time
    goals_after, _ = build_match_train_dataframes(records + [inserted], home_team_id=0, away_team_id=1, decision_time=decision_time)

    assert len(goals_before) == 2
    assert len(goals_after) == 3


def test_inserting_a_match_after_decision_time_is_never_included() -> None:
    records = [_record("0", _T0), _record("2", _T0 + timedelta(days=2))]
    decision_time = _T0 + timedelta(days=1, hours=1)  # entre le match 0 (+2h connu) et le match 2

    inserted_after = _record("1_5", _T0 + timedelta(days=1, hours=12))  # kickoff APRES decision_time
    goals_after, _ = build_match_train_dataframes(
        records + [inserted_after], home_team_id=0, away_team_id=1, decision_time=decision_time
    )
    assert len(goals_after) == 1  # seul le match "0" (deja connu a decision_time) est eligible


# --- 3. l'historique retourne est toujours strictement anterieur a decision_time


@given(
    n_records=st.integers(2, 30),
    decision_offset_hours=st.floats(0.0, 240.0),
    goals_delay=st.floats(0.5, 24.0),
    xg_delay=st.floats(0.5, 96.0),
)
@settings(max_examples=50)
def test_property_no_train_row_ever_has_kickoff_at_or_after_decision_time(
    n_records, decision_offset_hours, goals_delay, xg_delay
) -> None:
    records = [
        _record(str(i), _T0 + timedelta(days=i), goals_delay_hours=goals_delay, xg_delay_hours=xg_delay)
        for i in range(n_records)
    ]
    decision_time = records[-1].kickoff_utc - timedelta(hours=decision_offset_hours)

    goals_df, xg_df = build_match_train_dataframes(records, home_team_id=0, away_team_id=1, decision_time=decision_time)

    for df in (goals_df, xg_df):
        for kt in df["kickoff_time"]:
            assert kt < decision_time


# --- 4. corpus reel : au moins un match connu, coherent avec re-evaluation -


_UNDERSTAT_DIR = Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs"
_STAGE8_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage8_diagnostic_total_goals_over_under.py"


def _load_stage8():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "run_stage8_diagnostic_total_goals_over_under_for_future_match_dataset_test", _STAGE8_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not _UNDERSTAT_DIR.exists(), reason="Fichiers Understat reels non presents.")
def test_real_corpus_matches_a_known_historical_match_exactly() -> None:
    stage8 = _load_stage8()
    records = stage8._load_records("liga", "2024_25")
    ordered = sorted(records, key=lambda r: r.kickoff_utc)

    # Un match reellement connu du corpus (ni le premier ni le dernier, pour
    # garantir un historique anterieur non trivial).
    target = ordered[100]
    decision_time = target.kickoff_utc - timedelta(hours=2.0)

    goals_df, xg_df = build_match_train_dataframes(
        records,
        home_team_id=target.home_team_id,
        away_team_id=target.away_team_id,
        decision_time=decision_time,
        exclude_match_id=target.match_id,
    )

    expected_goals_df = stage8._goals_train_df(records, decision_time, exclude_match_id=target.match_id)
    expected_xg_df = stage8._xg_train_df(records, decision_time, exclude_match_id=target.match_id)

    assert len(goals_df) == len(expected_goals_df) > 0
    assert len(xg_df) == len(expected_xg_df) > 0
    np.testing.assert_array_equal(goals_df["home_goals"].to_numpy(), expected_goals_df["home_goals"].to_numpy())
    np.testing.assert_array_equal(goals_df["away_goals"].to_numpy(), expected_goals_df["away_goals"].to_numpy())
    np.testing.assert_array_equal(xg_df["home_xg"].to_numpy(), expected_xg_df["home_xg"].to_numpy())
    np.testing.assert_array_equal(xg_df["away_xg"].to_numpy(), expected_xg_df["away_xg"].to_numpy())
    for kt in goals_df["kickoff_time"]:
        assert kt < decision_time
