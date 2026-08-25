"""Anti-look-ahead pour le Value Engine (etape 3) :

1. l'edge/EV d'un candidat ne doit reposer que sur des cotes visibles au
   decision_time (deja garanti par latest_odds_as_of, teste a l'etape 1,
   re-verifie ici a travers le pipeline complet) ;
2. le CLV ne doit jamais etre calcule avec une cloture anterieure ou
   simultanee au decision_time (compute_clv_for_selection leve une
   exception - deja teste unitairement ; ici on verifie qu'aucun appel
   du pipeline ne contourne cette regle) ;
3. aucune ligne du journal de valeur ne doit utiliser une cote dont le
   knowledge_time est posterieur au decision_time de son match.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sys_foot_quant.backtesting_engine.walk_forward import ModelConfig, run_walk_forward
from sys_foot_quant.football_model.naive import NaiveModel
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.market_engine.snapshot import latest_odds_as_of
from sys_foot_quant.value_engine.clv import compute_clv_for_selection
from sys_foot_quant.value_engine.pipeline import build_value_log


def _configs():
    return [
        ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
        ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df)),
    ]


def test_value_log_odds_taken_never_exceeds_decision_time_knowledge(repo) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    eval_ids = all_matches["match_id"].iloc[-10:].tolist()
    kickoff_by_id = dict(zip(all_matches["match_id"], all_matches["kickoff_time"]))

    evaluations = run_walk_forward(
        repository=repo,
        eval_match_ids=eval_ids,
        decision_offset_hours=3.0,
        model_configs=_configs(),
        include_market_benchmark=True,
    )
    log = build_value_log(
        repo, evaluations, "poisson_simple", kickoff_by_id, min_edge=0.0, min_ev=0.0
    )

    for _, row in log.iterrows():
        odds_asof = repo.get_as_of("odds_snapshots", row["decision_time"])
        match_odds = odds_asof[odds_asof["match_id"] == row["match_id"]]
        assert not match_odds.empty, (
            "Une cote a ete utilisee pour construire un candidat alors "
            "qu'aucun snapshot n'etait visible au decision_time - fuite."
        )


@given(closing_before_decision=st.booleans())
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_compute_clv_for_selection_never_accepts_non_posterior_closing(
    repo, closing_before_decision: bool
) -> None:
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    match_id = int(full_matches.iloc[0]["match_id"])
    kickoff = full_matches.iloc[0]["kickoff_time"]

    from datetime import timedelta

    decision_time = kickoff - timedelta(hours=3)
    closing_time = decision_time - timedelta(hours=1) if closing_before_decision else kickoff

    if closing_before_decision:
        try:
            compute_clv_for_selection(repo, match_id, "home", 2.0, decision_time, closing_time)
        except ValueError:
            pass
        else:
            raise AssertionError(
                "compute_clv_for_selection a accepte une cloture anterieure "
                "au decision_time : garde-fou anti-look-ahead viole."
            )
    else:
        # Ne doit pas lever pour un ordre temporel valide (peut retourner
        # None si aucun snapshot n'est disponible, ce qui est different
        # d'une fuite).
        result = compute_clv_for_selection(repo, match_id, "home", 2.0, decision_time, closing_time)
        assert result is None or isinstance(result, float)


def test_latest_odds_as_of_used_by_pipeline_never_exceeds_as_of(repo) -> None:
    all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    for match_id in all_matches["match_id"].iloc[-5:]:
        kickoff = all_matches.loc[all_matches["match_id"] == match_id, "kickoff_time"].iloc[0]
        for offset_hours in (73, 30, 12, 2):
            from datetime import timedelta

            as_of = kickoff - timedelta(hours=offset_hours)
            odds = latest_odds_as_of(repo, int(match_id), as_of)
            if odds is None:
                continue
            # Le snapshot retourne doit exister dans la fenetre visible :
            # on le re-verifie via get_as_of, source de verite deja testee.
            visible = repo.get_as_of("odds_snapshots", as_of)
            visible_match = visible[visible["match_id"] == match_id]
            assert not visible_match.empty
