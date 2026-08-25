"""Verrouille (regression) le diagnostic mene sur le scenario de derive :
``poisson_simple`` (ponderation plate, pas de suivi de la derive) doit
etre rejete par le test de Chi-Deux en walk-forward sur ce scenario, avec
un exces de scores 0-0 parmi les principaux contributeurs - exactement le
diagnostic documente dans le rapport de correction de l'etape 2.

Ce test ne verifie PAS que le modele est "faux" au sens absolu : il
verifie que le pipeline de diagnostic (walk-forward + goodness_of_fit +
contribution_table) continue de detecter, de facon stable et
reproductible, ce phenomene connu et deja explique (sous-dispersion du
modele quand la force reelle des equipes varie plus, a un instant donne,
que ce qu'une estimation a ponderation plate peut capturer). Si ce test
se met a echouer, cela merite un nouvel examen - pas une correction
automatique du seuil.
"""

from __future__ import annotations

from sys_foot_quant.backtesting_engine.walk_forward import (
    ModelConfig,
    run_walk_forward,
    to_lambda_mu_and_goals,
)
from sys_foot_quant.calibration_engine.goodness_of_fit import (
    contribution_table,
    poisson_goodness_of_fit,
)
from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.data_engine.storage.writer import write_dataset
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset
from sys_foot_quant.football_model.poisson import PoissonModel

_CONFIG = SyntheticDataConfig(
    seed=2024,
    n_teams=14,
    n_matches=900,
    start_date="2021-08-01T00:00:00+00:00",
    days_between_matches=1.0,
    team_attack_log_std=0.35,
    team_defense_log_std=0.35,
    team_attack_drift_log_std_per_day=0.0015,
    team_defense_drift_log_std_per_day=0.0015,
)
_DECISION_OFFSET_HOURS = 2.0
_BURN_IN_FRACTION = 0.4


def test_poisson_simple_gof_rejected_on_drift_with_0_0_as_top_contributor(tmp_path) -> None:
    dataset = generate_synthetic_dataset(_CONFIG)
    write_dataset(dataset, tmp_path)

    with DuckDBRepository(tmp_path) as repo:
        all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
        n_burn_in = int(len(all_matches) * _BURN_IN_FRACTION)
        eval_ids = all_matches["match_id"].iloc[n_burn_in:].tolist()

        cfgs = [
            ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df))
        ]
        evaluations = run_walk_forward(
            repository=repo,
            eval_match_ids=eval_ids,
            decision_offset_hours=_DECISION_OFFSET_HOURS,
            model_configs=cfgs,
            include_market_benchmark=False,
        )

    lambdas_mus, home_goals, away_goals = to_lambda_mu_and_goals(evaluations, "poisson_simple")
    result = poisson_goodness_of_fit(lambdas_mus, home_goals, away_goals, max_goals_per_side=3)

    assert result.p_value < 0.01

    top = contribution_table(result).iloc[:2]["category"].tolist()
    assert "0-0" in top
