"""Garde-fous anti-fuite (etape 9, premiere experience economique reelle -
poisson_simple vs marche B365 1X2). Couvre explicitement les neuf
garanties demandees :

1. la cote utilisee est bien B365 ;
2. aucune colonne *C n'est utilisee ;
3. aucune cote future n'est utilisee (knowledge_time <= decision_time) ;
4. aucune information du resultat n'entre dans le calcul de p_model ;
5. EV est calcule uniquement avec p_model et la cote ;
6. la selection EV > 0 ne depend pas du resultat reel ;
7. le resultat reel n'est utilise qu'apres selection pour calculer le profit ;
8. les memes matchs sont utilises pour comparer les differentes metriques ;
9. aucune optimisation post-hoc du seuil n'est possible.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from sys_foot_quant.data_engine.market_odds.economic_dataset import (
    SELECTIONS,
    build_economic_dataset,
)
from sys_foot_quant.data_engine.market_odds.football_data_loader import (
    _ALLOWED_COLUMNS,
    FootballDataMatchRecord,
)

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage6_economic_b365_ev.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage6_economic_b365_ev", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_LEAGUE = "premier_league"
_SEASON = "2024_25"
_T0_SATURDAY = datetime(2024, 8, 3, 15, 0, 0)
_TEAMS = ["Arsenal", "Chelsea", "Liverpool", "Everton"]


def _us(match_id, dt, home, away, home_id, away_id, hg=1, ag=0):
    return {
        "id": match_id,
        "isResult": True,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": home_id, "title": home},
        "a": {"id": away_id, "title": away},
        "goals": {"h": hg, "a": ag},
        "xG": {"h": 1.1, "a": 0.9},
    }


def _fd(date_dt, home, away, b365=(1.8, 3.6, 4.5), league=_LEAGUE, season=_SEASON):
    return FootballDataMatchRecord(
        league=league, season=season, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=1, away_goals=0,
        b365_home=b365[0], b365_draw=b365[1], b365_away=b365[2],
    )


def _burn_in(n: int, start: datetime) -> list[dict]:
    raw = []
    for i in range(n):
        home, away = _TEAMS[i % 2], _TEAMS[2 + (i % 2)]
        raw.append(_us(f"burn{i}", start - timedelta(days=7 * (n - i)), home, away, home_id=i % 2, away_id=2 + (i % 2)))
    return raw


def _dataset_with_eval(kickoff: datetime, hg=1, ag=0, b365=(1.8, 3.6, 4.5)):
    raw = _burn_in(12, kickoff)
    raw.append(_us("eval1", kickoff, "Arsenal", "Everton", home_id=0, away_id=3, hg=hg, ag=ag))
    fd = [_fd(kickoff, "Arsenal", "Everton", b365=b365)]
    return build_economic_dataset(_LEAGUE, _SEASON, raw, fd)


# --- 1. La cote utilisee est bien B365 --------------------------------------


def test_market_odds_are_exactly_the_b365_fields() -> None:
    report = _dataset_with_eval(_T0_SATURDAY)
    rec = report.records[0]
    assert rec.market_odds == {"home": 1.8, "draw": 3.6, "away": 4.5}


# --- 2. Aucune colonne *C n'est utilisee -------------------------------------


def test_allowed_columns_never_contain_a_closing_column() -> None:
    assert not any(col.endswith("C") for col in _ALLOWED_COLUMNS)


# --- 3. Aucune cote future n'est utilisee ------------------------------------


def test_knowledge_time_always_before_or_equal_decision_time_on_exploitable_matches() -> None:
    report = _dataset_with_eval(_T0_SATURDAY)
    assert report.n_exploitable == 1
    rec = report.records[0]
    assert rec.knowledge_time_utc.replace(tzinfo=None) <= rec.decision_time_utc


def test_early_kickoff_that_would_violate_pit_is_excluded_not_silently_accepted() -> None:
    # Coup d'envoi 00:30 UTC un samedi (01:30 BST) -> decision_time =
    # vendredi 22:30 UTC, mais knowledge_time conservateur (vendredi
    # 23:59:59 heure de Londres = 22:59:59 UTC en BST) tombe APRES : le
    # garde-fou explicite (economic_dataset.py) doit exclure ce match
    # plutot que de laisser passer une "cote" reputee connue apres le
    # decision_time.
    early_kickoff = datetime(2024, 8, 3, 0, 30, 0)  # samedi 00:30 UTC
    report = _dataset_with_eval(early_kickoff)
    assert report.n_exploitable == 0
    assert report.n_excluded_pit_violation == 1


# --- 4. Aucune information du resultat n'entre dans le calcul de p_model ----


def test_model_probs_are_independent_of_the_evaluated_match_actual_outcome() -> None:
    report_a = _dataset_with_eval(_T0_SATURDAY, hg=1, ag=0)
    report_b = _dataset_with_eval(_T0_SATURDAY, hg=0, ag=3)
    assert report_a.records[0].model_probs == report_b.records[0].model_probs


def test_model_probs_are_independent_of_future_matches_goals() -> None:
    # Un match POSTERIEUR au match evalue (donc jamais dans l'historique
    # d'entrainement) ne doit avoir strictement aucun effet sur p_model.
    kickoff = _T0_SATURDAY
    raw_a = _burn_in(12, kickoff)
    raw_a.append(_us("eval1", kickoff, "Arsenal", "Everton", home_id=0, away_id=3))
    raw_a.append(_us("future1", kickoff + timedelta(days=7), "Chelsea", "Liverpool", home_id=1, away_id=2, hg=5, ag=0))

    raw_b = _burn_in(12, kickoff)
    raw_b.append(_us("eval1", kickoff, "Arsenal", "Everton", home_id=0, away_id=3))
    raw_b.append(_us("future1", kickoff + timedelta(days=7), "Chelsea", "Liverpool", home_id=1, away_id=2, hg=0, ag=5))

    fd = [_fd(kickoff, "Arsenal", "Everton")]
    report_a = build_economic_dataset(_LEAGUE, _SEASON, raw_a, fd)
    report_b = build_economic_dataset(_LEAGUE, _SEASON, raw_b, fd)
    assert report_a.records[0].model_probs == report_b.records[0].model_probs


# --- 5. EV est calcule uniquement avec p_model et la cote --------------------


def test_ev_uses_only_model_prob_and_odds() -> None:
    report = _dataset_with_eval(_T0_SATURDAY)
    rec = report.records[0]
    for s in SELECTIONS:
        assert rec.ev[s] == pytest.approx(rec.model_probs[s] * rec.market_odds[s] - 1.0)


# --- 6 & 7. Selection EV>0 independante du resultat ; resultat utilise apres --


def _minimal_df() -> pd.DataFrame:
    rows = []
    for i, (mp, odds, outcome_sel) in enumerate(
        [
            ({"home": 0.6, "draw": 0.25, "away": 0.15}, {"home": 2.2, "draw": 3.4, "away": 6.0}, "home"),
            ({"home": 0.2, "draw": 0.3, "away": 0.5}, {"home": 4.0, "draw": 3.0, "away": 1.7}, "away"),
        ]
    ):
        row = {"match_id": f"m{i}", "league": "premier_league", "season": "2024_25", "outcome_selection": outcome_sel}
        for s in SELECTIONS:
            row[f"model_prob_{s}"] = mp[s]
            row[f"odds_{s}"] = odds[s]
            row[f"ev_{s}"] = mp[s] * odds[s] - 1.0
        rows.append(row)
    return pd.DataFrame(rows)


def test_selection_is_identical_regardless_of_actual_outcome() -> None:
    module = _load_script()
    df = _minimal_df()
    df_alt_outcome = df.copy()
    df_alt_outcome["outcome_selection"] = ["draw", "home"]  # resultats reels differents, EV inchange

    bets_1 = module.select_ev_positive_bets(df)
    bets_2 = module.select_ev_positive_bets(df_alt_outcome)
    assert list(zip(bets_1["match_id"], bets_1["selection"])) == list(zip(bets_2["match_id"], bets_2["selection"]))


def test_select_ev_positive_bets_never_reads_outcome_column() -> None:
    import ast

    tree = ast.parse(inspect.getsource(_load_script().select_ev_positive_bets))
    func_def = tree.body[0]
    body = func_def.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # ignore la docstring, qui mentionne "outcome" pour EXPLIQUER l'absence d'usage
    body_source = "\n".join(ast.unparse(stmt) for stmt in body)
    assert "outcome" not in body_source


def test_bets_from_selection_carry_no_result_information_before_realize_profit() -> None:
    module = _load_script()
    df = _minimal_df()
    bets = module.select_ev_positive_bets(df)
    assert "won" not in bets.columns
    assert "profit" not in bets.columns
    assert "outcome_selection" not in bets.columns

    realized = module.realize_profit(bets, df)
    assert "won" in realized.columns
    assert "profit" in realized.columns


def test_realize_profit_result_matches_independently_recomputed_outcome() -> None:
    module = _load_script()
    df = _minimal_df()
    bets = module.select_ev_positive_bets(df)
    realized = module.realize_profit(bets, df)
    expected_outcome = df.set_index("match_id")["outcome_selection"]
    for _, row in realized.iterrows():
        expected_won = expected_outcome.loc[row["match_id"]] == row["selection"]
        assert row["won"] == expected_won
        expected_profit = (row["odds"] - 1.0) if expected_won else -1.0
        assert row["profit"] == pytest.approx(expected_profit)


# --- 8. Memes matchs utilises pour comparer les differentes metriques -------


def test_same_dataframe_backs_every_descriptive_metric_and_the_strategy() -> None:
    module = _load_script()
    report = _dataset_with_eval(_T0_SATURDAY)
    df = module.records_to_dataframe(report.records)
    bets = module.select_ev_positive_bets(df)
    # Tout pari genere provient necessairement d'un match present dans le
    # meme dataframe que celui utilise pour Brier/calibration/edge/EV.
    assert set(bets["match_id"]).issubset(set(df["match_id"]))
    probs, outcomes = module._probs_outcomes(df, "model_prob")
    assert len(probs) == len(df) == len(outcomes)


# --- 9. Aucune optimisation post-hoc du seuil n'est possible ----------------


def test_select_ev_positive_bets_exposes_no_threshold_parameter() -> None:
    sig = inspect.signature(_load_script().select_ev_positive_bets)
    assert list(sig.parameters) == ["df"]


def test_strategy_threshold_is_hardcoded_zero_in_source() -> None:
    source = inspect.getsource(_load_script().select_ev_positive_bets)
    assert "> 0.0" in source
    assert "threshold" not in source.lower()
