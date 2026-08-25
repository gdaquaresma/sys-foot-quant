from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.bayesian_sequential import (
    DEFAULT_PRIOR_STRENGTH,
    BayesianSequentialModel,
)

_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _matches(rows: list[tuple[int, int, int, int, datetime]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"]
    )


def test_rejects_empty_training_set() -> None:
    with pytest.raises(ValueError):
        BayesianSequentialModel().fit(_matches([]))


def test_rejects_non_positive_prior_strength() -> None:
    with pytest.raises(ValueError):
        BayesianSequentialModel(prior_strength=0.0)
    with pytest.raises(ValueError):
        BayesianSequentialModel(prior_strength=-1.0)


def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        BayesianSequentialModel().predict_lambda_mu(0, 1)


def test_fit_accepts_and_ignores_decision_time() -> None:
    df = _matches([(0, 1, 3, 1, _T0)])
    model = BayesianSequentialModel().fit(df, decision_time=_T0 + timedelta(days=30))
    assert model.attack_alpha_ is not None


def test_single_match_matches_hand_computation() -> None:
    # league_base=(3+1)/2=2.0, hfa_global=3.0/1.0=3.0 ; prior par defaut k0=10.
    df = _matches([(0, 1, 3, 1, _T0)])
    model = BayesianSequentialModel(prior_strength=10.0).fit(df)

    assert model.league_base_ == pytest.approx(2.0)
    assert model.hfa_global_ == pytest.approx(3.0)

    assert model.attack_alpha_[0] == pytest.approx(13.0)
    assert model.attack_beta_[0] == pytest.approx(16.0)
    assert model.defense_alpha_[1] == pytest.approx(13.0)
    assert model.defense_beta_[1] == pytest.approx(16.0)

    assert model.attack_alpha_[1] == pytest.approx(11.0)
    assert model.attack_beta_[1] == pytest.approx(12.0)
    assert model.defense_alpha_[0] == pytest.approx(11.0)
    assert model.defense_beta_[0] == pytest.approx(12.0)

    lam, mu = model.predict_lambda_mu(0, 1)
    assert lam == pytest.approx(2.0 * (13 / 16) * (13 / 16) * 3.0)
    assert mu == pytest.approx(2.0 * (11 / 12) * (11 / 12))


def test_unknown_team_falls_back_to_neutral_ratio() -> None:
    df = _matches([(0, 1, 2, 1, _T0), (1, 0, 1, 1, _T0 + timedelta(days=1))])
    model = BayesianSequentialModel().fit(df)
    lam, mu = model.predict_lambda_mu(999, 998)
    assert lam == pytest.approx(model.league_base_ * model.hfa_global_)
    assert mu == pytest.approx(model.league_base_)


def test_predict_outcome_probabilities_sum_to_one() -> None:
    df = _matches([(0, 1, 2, 1, _T0), (1, 0, 1, 1, _T0 + timedelta(days=1))])
    model = BayesianSequentialModel().fit(df)
    home, draw, away = model.predict_outcome_probabilities(0, 1)
    assert home + draw + away == pytest.approx(1.0, abs=1e-6)


def test_row_order_in_dataframe_does_not_affect_result() -> None:
    # La mise a jour doit suivre l'ordre chronologique (kickoff_time), pas
    # l'ordre d'arrivee des lignes - le Repository ne garantit aucun ordre.
    rows = [
        (0, 1, 2, 1, _T0),
        (1, 2, 0, 0, _T0 + timedelta(days=1)),
        (2, 0, 3, 2, _T0 + timedelta(days=2)),
        (0, 2, 1, 1, _T0 + timedelta(days=3)),
    ]
    df_sorted = _matches(rows)
    df_shuffled = _matches([rows[2], rows[0], rows[3], rows[1]])

    model_sorted = BayesianSequentialModel().fit(df_sorted)
    model_shuffled = BayesianSequentialModel().fit(df_shuffled)

    assert model_sorted.attack_alpha_ == pytest.approx(model_shuffled.attack_alpha_)
    assert model_sorted.attack_beta_ == pytest.approx(model_shuffled.attack_beta_)
    assert model_sorted.defense_alpha_ == pytest.approx(model_shuffled.defense_alpha_)
    assert model_sorted.defense_beta_ == pytest.approx(model_shuffled.defense_beta_)


def _reference_fit(rows: list[tuple[int, int, int, int, int]], k0: float) -> dict[str, dict[int, float]]:
    """Reimplementation independante (mais volontairement naive/lisible) de
    la meme recursion, utilisee comme oracle dans le test property-based."""
    rows_sorted = sorted(rows, key=lambda r: r[4])
    home_goals = [r[2] for r in rows_sorted]
    away_goals = [r[3] for r in rows_sorted]
    n = len(rows_sorted)
    league_base = max(sum(home_goals[i] + away_goals[i] for i in range(n)) / (2.0 * n), 1e-9)
    mean_home = sum(home_goals) / n
    mean_away = sum(away_goals) / n
    hfa_global = max(mean_home / mean_away, 1e-9) if mean_away > 0 else 1.0

    teams = sorted({r[0] for r in rows_sorted} | {r[1] for r in rows_sorted})
    aa = {t: k0 for t in teams}
    ab = {t: k0 for t in teams}
    da = {t: k0 for t in teams}
    db = {t: k0 for t in teams}

    for h, a, hg, ag, _ in rows_sorted:
        am_h, dm_h = aa[h] / ab[h], da[h] / db[h]
        am_a, dm_a = aa[a] / ab[a], da[a] / db[a]

        exp_h_att = league_base * dm_a * hfa_global
        exp_a_def = league_base * am_h * hfa_global
        exp_a_att = league_base * dm_h
        exp_h_def = league_base * am_a

        aa[h] += hg
        ab[h] += exp_h_att
        da[a] += hg
        db[a] += exp_a_def

        aa[a] += ag
        ab[a] += exp_a_att
        da[h] += ag
        db[h] += exp_h_def

    return {"attack_alpha": aa, "attack_beta": ab, "defense_alpha": da, "defense_beta": db}


@given(
    rows=st.lists(
        st.tuples(
            st.integers(0, 4),
            st.integers(0, 4),
            st.integers(0, 6),
            st.integers(0, 6),
            st.integers(0, 100),  # decalage en jours, encode l'ordre chronologique
        ).filter(lambda t: t[0] != t[1]),
        min_size=1,
        max_size=25,
    )
)
@settings(max_examples=60)
def test_sequential_update_matches_independent_reference_implementation(rows) -> None:
    k0 = 10.0
    df_rows = [(h, a, hg, ag, _T0 + timedelta(days=offset)) for h, a, hg, ag, offset in rows]
    model = BayesianSequentialModel(prior_strength=k0).fit(_matches(df_rows))
    expected = _reference_fit(rows, k0)

    assert model.attack_alpha_ == pytest.approx(expected["attack_alpha"])
    assert model.attack_beta_ == pytest.approx(expected["attack_beta"])
    assert model.defense_alpha_ == pytest.approx(expected["defense_alpha"])
    assert model.defense_beta_ == pytest.approx(expected["defense_beta"])


@given(
    rows=st.lists(
        st.tuples(
            st.integers(0, 3),
            st.integers(0, 3),
            st.integers(0, 6),
            st.integers(0, 6),
        ).filter(lambda t: t[0] != t[1]),
        min_size=1,
        max_size=40,
    )
)
@settings(max_examples=50)
def test_fitted_parameters_always_finite_and_positive(rows) -> None:
    df_rows = [(h, a, hg, ag, _T0 + timedelta(days=i)) for i, (h, a, hg, ag) in enumerate(rows)]
    model = BayesianSequentialModel().fit(_matches(df_rows))
    for d in (model.attack_alpha_, model.attack_beta_, model.defense_alpha_, model.defense_beta_):
        for v in d.values():
            assert v > 0
            import math

            assert math.isfinite(v)
    assert model.league_base_ > 0
    assert model.hfa_global_ > 0


def test_default_prior_strength_matches_hfa_shrinkage_k_convention() -> None:
    # Documente explicitement le choix (pre-enregistre, non optimise) : voir
    # docstring du module.
    assert DEFAULT_PRIOR_STRENGTH == 10.0
