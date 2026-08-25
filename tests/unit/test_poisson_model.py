from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.football_model.poisson import PoissonModel


def _matches(rows):
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals"])


def _round_robin_equal_strength(n_teams=4, home_goals=2, away_goals=1):
    rows = []
    for i in range(n_teams):
        for j in range(n_teams):
            if i != j:
                rows.append((i, j, home_goals, away_goals))
    return _matches(rows)


def test_predict_before_fit_raises() -> None:
    with pytest.raises(RuntimeError):
        PoissonModel().predict_lambda_mu(1, 2)


def test_rejects_empty_training_set() -> None:
    with pytest.raises(ValueError):
        PoissonModel().fit(_matches([]))


def test_equal_strength_teams_get_attack_defense_of_one() -> None:
    df = _round_robin_equal_strength()
    model = PoissonModel().fit(df)
    for t in range(4):
        assert model.attack_[t] == pytest.approx(1.0, abs=1e-9)
        assert model.defense_[t] == pytest.approx(1.0, abs=1e-9)


def test_equal_strength_hfa_global_matches_manual_ratio() -> None:
    df = _round_robin_equal_strength(home_goals=2, away_goals=1)
    model = PoissonModel().fit(df)
    # hfa_global_ = moyenne des buts domicile / moyenne des buts exterieur.
    assert model.hfa_global_ == pytest.approx(2.0, abs=1e-9)
    # raw_hfa_ est une quantite differente par construction (ratio du but
    # domicile reel a l'"attendu neutre" league_base*attack*defense, PAS
    # au ratio brut domicile/exterieur) : ici league_base=1.5, donc
    # raw_hfa = 2 / 1.5 = 4/3, distinct de hfa_global_=2.0. C'est documente
    # comme limite connue de la formulation (voir docstring de poisson.py).
    for t in range(4):
        assert model.raw_hfa_[t] == pytest.approx(4 / 3, abs=1e-9)


def test_predict_lambda_mu_matches_hand_computation_for_equal_strength() -> None:
    df = _round_robin_equal_strength(home_goals=2, away_goals=1)
    model = PoissonModel(hfa_shrinkage_k=10.0).fit(df)
    lam, mu = model.predict_lambda_mu(0, 1)
    # league_base=1.5, attack=defense=1, raw_hfa=4/3 partout (n_home=3,
    # k=10) => hfa_team = (3*4/3 + 10*2.0) / 13 = 24/13.
    expected_hfa_team = (3 * (4 / 3) + 10 * 2.0) / 13
    assert model.hfa_team_[0] == pytest.approx(expected_hfa_team, abs=1e-9)
    assert lam == pytest.approx(1.5 * 1.0 * 1.0 * expected_hfa_team, abs=1e-6)
    assert mu == pytest.approx(1.5 * 1.0 * 1.0, abs=1e-6)


def test_use_team_hfa_false_gives_every_team_the_global_hfa() -> None:
    rows = [
        (0, 1, 5, 0),
        (0, 2, 5, 0),
        (0, 3, 5, 0),
        (1, 0, 1, 1),
        (2, 0, 1, 1),
        (3, 0, 1, 1),
    ]
    df = _matches(rows)
    model = PoissonModel(use_team_hfa=False).fit(df)
    values = set(round(v, 9) for v in model.hfa_team_.values())
    assert values == {round(model.hfa_global_, 9)}


def test_hfa_shrinkage_formula_matches_exposed_raw_values() -> None:
    df = _round_robin_equal_strength()
    model = PoissonModel(hfa_shrinkage_k=7.0).fit(df)
    for t in model.raw_hfa_:
        n_t = model.n_home_[t]
        expected = (n_t * model.raw_hfa_[t] + 7.0 * model.hfa_global_) / (n_t + 7.0)
        assert model.hfa_team_[t] == pytest.approx(expected, abs=1e-9)


def test_hfa_shrinkage_limiting_behavior() -> None:
    # Comportement limite du shrinkage, verifie directement sur la formule :
    # k quasi nul => hfa_team quasi egal au ratio brut (aucune confiance
    # dans le prior global) ; k enorme => hfa_team quasi egal a hfa_global
    # (le peu d'observations propres par equipe est totalement ecrase).
    df = _round_robin_equal_strength(home_goals=3, away_goals=1)
    model_low_k = PoissonModel(hfa_shrinkage_k=1e-6).fit(df)
    model_high_k = PoissonModel(hfa_shrinkage_k=1e6).fit(df)
    for t in range(4):
        assert model_low_k.hfa_team_[t] == pytest.approx(model_low_k.raw_hfa_[t], rel=1e-3)
        assert model_high_k.hfa_team_[t] == pytest.approx(model_high_k.hfa_global_, rel=1e-3)


def test_hfa_shrinkage_weight_grows_with_home_sample_size() -> None:
    # Une equipe avec beaucoup de matchs a domicile doit voir son hfa_team_
    # rester plus proche de son propre ratio brut (moins shrink) qu'une
    # equipe avec un seul match a domicile.
    many_home_rows = [(0, 1, 4, 0)] * 20 + [(1, 0, 1, 1)] * 20
    one_home_row = many_home_rows + [(2, 3, 4, 0), (3, 2, 1, 1)] * 1
    df = _matches(one_home_row)
    model = PoissonModel(hfa_shrinkage_k=10.0).fit(df)

    dist_team0 = abs(model.hfa_team_[0] - model.raw_hfa_[0])
    dist_team2 = abs(model.hfa_team_[2] - model.raw_hfa_[2])
    assert model.n_home_[0] > model.n_home_[2]
    assert dist_team0 < dist_team2


def test_unknown_team_falls_back_to_neutral_parameters() -> None:
    df = _round_robin_equal_strength()
    model = PoissonModel().fit(df)
    lam, mu = model.predict_lambda_mu(999, 998)
    # Deux equipes inconnues -> parametres neutres (attack=defense=1),
    # hfa global applique par defaut.
    assert lam == pytest.approx(model.league_base_ * model.hfa_global_, abs=1e-6)
    assert mu == pytest.approx(model.league_base_, abs=1e-6)


def test_predict_outcome_probabilities_sum_to_one() -> None:
    df = _round_robin_equal_strength()
    model = PoissonModel().fit(df)
    home, draw, away = model.predict_outcome_probabilities(0, 1, max_goals=20)
    assert home + draw + away == pytest.approx(1.0, abs=1e-6)


def test_weight_zero_is_equivalent_to_excluding_the_match() -> None:
    df_full = _matches(
        [(0, 1, 3, 0), (1, 0, 0, 3), (0, 1, 0, 0), (1, 0, 1, 1)]
    )
    df_reduced = df_full.iloc[:2].reset_index(drop=True)
    weights_full = np.array([1.0, 1.0, 0.0, 0.0])

    model_full = PoissonModel().fit(df_full, weights=weights_full)
    model_reduced = PoissonModel().fit(df_reduced)

    assert model_full.attack_ == pytest.approx(model_reduced.attack_, abs=1e-9)
    assert model_full.defense_ == pytest.approx(model_reduced.defense_, abs=1e-9)
    assert model_full.hfa_global_ == pytest.approx(model_reduced.hfa_global_, abs=1e-9)


def test_rejects_mismatched_weights_length() -> None:
    df = _round_robin_equal_strength()
    with pytest.raises(ValueError):
        PoissonModel().fit(df, weights=np.array([1.0, 2.0]))


@given(
    rows=st.lists(
        st.tuples(
            st.integers(0, 3),
            st.integers(0, 3),
            st.integers(0, 6),
            st.integers(0, 6),
        ).filter(lambda t: t[0] != t[1]),
        min_size=1,
        max_size=60,
    )
)
@settings(max_examples=50)
def test_fitted_parameters_always_finite_and_positive(rows) -> None:
    df = _matches(rows)
    model = PoissonModel().fit(df)
    for d in (model.attack_, model.defense_, model.hfa_team_):
        for v in d.values():
            assert v > 0
            assert np.isfinite(v)
    assert model.league_base_ > 0
    assert model.hfa_global_ > 0
