from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (
    RealMatchRecord,
    RealModelConfig,
    _goals_train_df,
    _xg_train_df,
    run_real_data_walk_forward,
)

_T0 = datetime(2024, 1, 1)


def _record(
    match_id: str,
    kickoff: datetime,
    goals_delay_hours: float = 2.0,
    xg_delay_hours: float = 48.0,
    home_team_id: int = 0,
    away_team_id: int = 1,
) -> RealMatchRecord:
    return RealMatchRecord(
        match_id=match_id,
        league="TEST",
        kickoff_utc=kickoff,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_goals=1,
        away_goals=0,
        home_xg=1.2,
        away_xg=0.8,
        goals_knowledge_time=kickoff + timedelta(hours=goals_delay_hours),
        xg_knowledge_time=kickoff + timedelta(hours=xg_delay_hours),
    )


def test_goals_train_df_excludes_matches_not_yet_known() -> None:
    records = [
        _record("A", _T0),
        _record("B", _T0 + timedelta(days=1)),
    ]
    # decision_time juste avant que le score de B ne soit connu (B+2h)
    decision_time = _T0 + timedelta(days=1, hours=1)
    df = _goals_train_df(records, decision_time, exclude_match_id="C")
    assert list(df["home_goals"]) == [1]  # seul A est connu
    assert len(df) == 1


def test_goals_train_df_never_includes_the_evaluated_match_itself() -> None:
    records = [_record("A", _T0)]
    decision_time = _T0 + timedelta(days=10)  # tres largement apres, score connu
    df = _goals_train_df(records, decision_time, exclude_match_id="A")
    assert df.empty


def test_xg_train_df_never_includes_the_evaluated_match_itself() -> None:
    records = [_record("A", _T0)]
    decision_time = _T0 + timedelta(days=10)
    df = _xg_train_df(records, decision_time, exclude_match_id="A")
    assert df.empty


def test_goals_and_xg_knowledge_times_are_independent() -> None:
    """Le coeur de la garantie PIT specifique a B3 : le xG et les buts
    reels d'un MEME match anterieur ne deviennent pas connus au meme
    instant. A un decision_time situe entre les deux delais, le match doit
    apparaitre dans goals_train_df mais PAS dans xg_train_df."""
    kickoff = _T0
    records = [_record("A", kickoff, goals_delay_hours=2.0, xg_delay_hours=48.0)]
    decision_time = kickoff + timedelta(hours=10)  # apres +2h (buts) mais avant +48h (xG)

    goals_df = _goals_train_df(records, decision_time, exclude_match_id="Z")
    xg_df = _xg_train_df(records, decision_time, exclude_match_id="Z")

    assert len(goals_df) == 1
    assert len(xg_df) == 0


def test_run_real_data_walk_forward_never_leaks_future_matches() -> None:
    records = [_record(str(i), _T0 + timedelta(days=i)) for i in range(10)]

    captured_goals_lens: list[int] = []
    captured_xg_lens: list[int] = []

    def _fit(goals_df, xg_df, decision_time):
        captured_goals_lens.append(len(goals_df))
        captured_xg_lens.append(len(xg_df))

        class _Stub:
            def predict(self, h, a):
                return (0.4, 0.3, 0.3)

        return _Stub()

    eval_ids = [str(i) for i in range(5, 10)]
    configs = [RealModelConfig(name="stub", fit=_fit, min_train_matches=0)]
    evaluations = run_real_data_walk_forward(
        records, eval_match_ids=eval_ids, decision_offset_hours=2.0, model_configs=configs
    )

    assert len(evaluations) == 5
    # Pour le match d'indice i (i>=5), au plus i matchs anterieurs peuvent
    # avoir leur score connu (les matchs 0..i-1) - jamais i ou plus.
    for idx, ev in enumerate(evaluations):
        match_index = int(ev.match_id)
        assert captured_goals_lens[idx] <= match_index
        assert captured_xg_lens[idx] <= match_index


def test_evaluations_are_sorted_chronologically_regardless_of_input_order() -> None:
    records = [_record(str(i), _T0 + timedelta(days=i)) for i in range(5)]
    shuffled_ids = ["3", "0", "4", "1", "2"]

    def _fit(goals_df, xg_df, decision_time):
        class _Stub:
            def predict(self, h, a):
                return (0.4, 0.3, 0.3)

        return _Stub()

    configs = [RealModelConfig(name="stub", fit=_fit, min_train_matches=0)]
    evaluations = run_real_data_walk_forward(
        records, eval_match_ids=shuffled_ids, decision_offset_hours=2.0, model_configs=configs
    )
    kickoffs = [ev.decision_time for ev in evaluations]
    assert kickoffs == sorted(kickoffs)


@given(
    n_records=st.integers(2, 30),
    decision_offset_hours=st.floats(0.0, 72.0),
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
    target_index = n_records - 1
    decision_time = records[target_index].kickoff_utc - timedelta(hours=decision_offset_hours)

    goals_df = _goals_train_df(records, decision_time, exclude_match_id=str(target_index))
    xg_df = _xg_train_df(records, decision_time, exclude_match_id=str(target_index))

    kickoff_by_index = {i: records[i].kickoff_utc for i in range(n_records)}
    # Aucune ligne de train_df ne doit correspondre a un match dont le
    # coup d'envoi est >= decision_time (invariant structurel, independant
    # des delais de connaissance choisis).
    for df in (goals_df, xg_df):
        for kt in df["kickoff_time"]:
            assert kt < decision_time
