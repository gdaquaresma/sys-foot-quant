from __future__ import annotations

from sys_foot_quant.backtesting_engine.walk_forward import (
    ModelConfig,
    run_walk_forward,
    to_low_score_probs_and_goals,
)
from sys_foot_quant.football_model.dixon_coles import DixonColesModel
from sys_foot_quant.football_model.naive import NaiveModel
from sys_foot_quant.football_model.poisson import PoissonModel


def _configs():
    return [
        ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
        ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df)),
        ModelConfig(
            name="dixon_coles", fit=lambda df, t: DixonColesModel(use_team_hfa=False).fit(df)
        ),
    ]


def test_low_score_probs_captured_only_for_models_exposing_predict_low_score_probs(repo) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-5:].tolist()

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=2.0,
        model_configs=_configs(),
        include_market_benchmark=True,
    )

    for ev in evaluations:
        assert ev.low_score_probs["naive"] is None
        assert ev.low_score_probs["market_no_vig"] is None
        for name in ("poisson_simple", "dixon_coles"):
            probs = ev.low_score_probs[name]
            assert probs is not None
            assert len(probs) == 4
            assert all(p >= 0.0 for p in probs)
            assert sum(probs) <= 1.0 + 1e-9

    probs_list, home_goals, away_goals = to_low_score_probs_and_goals(evaluations, "dixon_coles")
    assert len(probs_list) == len(evaluations)
    assert len(home_goals) == len(evaluations)
    assert len(away_goals) == len(evaluations)

    naive_probs, naive_home, naive_away = to_low_score_probs_and_goals(evaluations, "naive")
    assert naive_probs == []
    assert len(naive_home) == 0
