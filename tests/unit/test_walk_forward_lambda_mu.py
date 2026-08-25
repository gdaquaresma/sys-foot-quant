from __future__ import annotations

from sys_foot_quant.backtesting_engine.walk_forward import (
    ModelConfig,
    run_walk_forward,
    to_lambda_mu_and_goals,
)
from sys_foot_quant.football_model.naive import NaiveModel
from sys_foot_quant.football_model.poisson import PoissonModel


def _configs():
    return [
        ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
        ModelConfig(name="poisson", fit=lambda df, t: PoissonModel().fit(df)),
    ]


def test_lambda_mu_captured_only_for_models_exposing_predict_lambda_mu(repo) -> None:
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
        assert ev.lambda_mu["naive"] is None
        assert ev.lambda_mu["market_no_vig"] is None
        lm = ev.lambda_mu["poisson"]
        assert lm is not None
        lam, mu = lm
        assert lam > 0
        assert mu > 0

    lambdas_mus, home_goals, away_goals = to_lambda_mu_and_goals(evaluations, "poisson")
    assert len(lambdas_mus) == len(evaluations)
    assert len(home_goals) == len(evaluations)
    assert len(away_goals) == len(evaluations)

    naive_lm, naive_home, naive_away = to_lambda_mu_and_goals(evaluations, "naive")
    assert naive_lm == []
