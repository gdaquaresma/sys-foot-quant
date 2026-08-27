from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage5_a2_hfa_real.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage5_a2_hfa_real", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bucket_a2_meilleur_requires_ci_entirely_negative() -> None:
    script = _load_script()
    assert script._bucket_verdict(ci_low=-0.02, ci_high=-0.005) == "a2_meilleur"


def test_bucket_poisson_simple_meilleur_requires_ci_entirely_positive() -> None:
    script = _load_script()
    assert script._bucket_verdict(ci_low=0.005, ci_high=0.02) == "poisson_simple_meilleur"


def test_bucket_indetermine_when_ci_crosses_zero() -> None:
    script = _load_script()
    assert script._bucket_verdict(ci_low=-0.01, ci_high=0.01) == "indetermine"


def test_aggregate_valide_requires_all_three_leagues_a2_meilleur() -> None:
    script = _load_script()
    assert script._aggregate_verdict(["a2_meilleur"] * 3) == "VALIDE"


def test_aggregate_rejete_when_no_league_shows_a2_meilleur() -> None:
    script = _load_script()
    assert script._aggregate_verdict(["poisson_simple_meilleur", "indetermine", "poisson_simple_meilleur"]) == (
        "REJETE"
    )
    assert script._aggregate_verdict(["indetermine"] * 3) == "REJETE"


def test_aggregate_indetermine_on_genuine_disagreement() -> None:
    script = _load_script()
    buckets = ["a2_meilleur", "poisson_simple_meilleur", "indetermine"]
    assert script._aggregate_verdict(buckets) == "INDETERMINE"
    buckets2 = ["a2_meilleur", "a2_meilleur", "indetermine"]
    assert script._aggregate_verdict(buckets2) == "INDETERMINE"


def test_split_eval_ids_matches_frozen_b1_b3_convention() -> None:
    from datetime import datetime, timedelta

    script = _load_script()

    class _Rec:
        def __init__(self, match_id: str, kickoff) -> None:
            self.match_id = match_id
            self.kickoff_utc = kickoff

    t0 = datetime(2024, 1, 1)
    records = [_Rec(str(i), t0 + timedelta(days=i)) for i in range(100)]
    validation_ids, test_ids = script._split_eval_ids(records)
    assert set(validation_ids).isdisjoint(set(test_ids))
    assert len(validation_ids) == 30
    assert len(test_ids) == 30
    assert validation_ids == [str(i) for i in range(40, 70)]
    assert test_ids == [str(i) for i in range(70, 100)]


def test_hfa_shrinkage_k_matches_stage2_frozen_value() -> None:
    script = _load_script()
    assert script._HFA_SHRINKAGE_K == 10.0


def test_a2_fit_uses_frozen_shrinkage_and_team_hfa_enabled() -> None:
    import pandas as pd

    from sys_foot_quant.football_model.poisson import PoissonModel

    script = _load_script()
    goals_df = pd.DataFrame(
        [(0, 1, 2, 1, 0), (1, 0, 1, 1, 1), (0, 1, 3, 0, 2)],
        columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"],
    )
    model = script._fit_a2_hfa(goals_df, xg_df=None, decision_time=None)
    assert isinstance(model, PoissonModel)
    assert model.use_team_hfa is True
    assert model.hfa_shrinkage_k == 10.0
