"""Tests de research.temporal_weighting_experiment.weighted_walkforward -
donnees SYNTHETIQUES uniquement. Couvre la SEULE logique nouvelle de ce
module (calcul de l'age/poids, boucle walk-forward) - football_model.weighting
(deja teste ailleurs, INCHANGE) et PoissonModel/score_matrix/over_under_probs
(INCHANGES) ne sont pas re-testes ici pour eux-memes."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from sys_foot_quant.backtesting_engine.real_data_walk_forward import RealMatchRecord
from research.temporal_weighting_experiment.weighted_walkforward import (
    DECAY_SCHEMES,
    FLAT_SCHEME,
    WeightingScheme,
    binary_brier_score,
    binary_log_loss,
    compute_weights_for_scheme,
    run_walkforward,
)

_T0 = datetime(2020, 1, 1)


def _record(match_id: str, kickoff: datetime, home_id: int, away_id: int, home_goals: int, away_goals: int) -> RealMatchRecord:
    return RealMatchRecord(
        match_id=match_id,
        league="TEST",
        kickoff_utc=kickoff,
        home_team_id=home_id,
        away_team_id=away_id,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=float(home_goals) + 0.2,
        away_xg=float(away_goals) + 0.2,
        goals_knowledge_time=kickoff + timedelta(hours=2.0),
        xg_knowledge_time=kickoff + timedelta(hours=48.0),
    )


# --- compute_weights_for_scheme ---------------------------------------------


def test_flat_scheme_gives_weight_one_to_everyone() -> None:
    kickoffs = pd.Series([_T0, _T0 + timedelta(days=10), _T0 + timedelta(days=400)])
    w = compute_weights_for_scheme(kickoffs, _T0 + timedelta(days=401), FLAT_SCHEME)
    assert np.allclose(w, 1.0)


def test_weight_is_one_at_age_zero_for_decay_schemes() -> None:
    decision_time = _T0 + timedelta(days=100)
    kickoffs = pd.Series([decision_time])  # age = 0 exactement
    for scheme in DECAY_SCHEMES:
        w = compute_weights_for_scheme(kickoffs, decision_time, scheme)
        assert w[0] == pytest.approx(1.0)


def test_weight_at_exactly_one_half_life_is_half() -> None:
    scheme = WeightingScheme(name="test_30d", half_life_days=30.0)
    decision_time = _T0 + timedelta(days=30)
    kickoffs = pd.Series([_T0])  # age = exactement 30 jours = 1 demi-vie
    w = compute_weights_for_scheme(kickoffs, decision_time, scheme)
    assert w[0] == pytest.approx(0.5)


def test_weight_at_two_half_lives_is_quarter() -> None:
    scheme = WeightingScheme(name="test_30d", half_life_days=30.0)
    decision_time = _T0 + timedelta(days=60)
    kickoffs = pd.Series([_T0])
    w = compute_weights_for_scheme(kickoffs, decision_time, scheme)
    assert w[0] == pytest.approx(0.25)


def test_older_match_always_has_lower_or_equal_weight_than_newer_match() -> None:
    """Monotonie : plus un match est ancien (age plus grand), plus son poids
    est faible ou egal - jamais l'inverse."""
    decision_time = _T0 + timedelta(days=500)
    kickoffs = pd.Series(
        [_T0, _T0 + timedelta(days=100), _T0 + timedelta(days=300), _T0 + timedelta(days=499)]
    )
    for scheme in DECAY_SCHEMES:
        w = compute_weights_for_scheme(kickoffs, decision_time, scheme)
        assert list(w) == sorted(w), f"non-monotone pour {scheme.name}"


def test_shorter_half_life_decays_faster_than_longer_half_life() -> None:
    decision_time = _T0 + timedelta(days=200)
    kickoffs = pd.Series([_T0])  # age = 200 jours pour toutes les demi-vies
    weights_by_scheme = {
        s.name: compute_weights_for_scheme(kickoffs, decision_time, s)[0] for s in DECAY_SCHEMES
    }
    ordered = [weights_by_scheme[s.name] for s in DECAY_SCHEMES]
    assert ordered == sorted(ordered), "une demi-vie plus courte doit donner un poids plus faible a age egal"


def test_negative_age_raises_never_silently_tolerated() -> None:
    """Aucune date future : un match d'entrainement dont le kickoff est
    POSTERIEUR a decision_time doit lever une erreur explicite, jamais un
    poids invente ou une acceptation silencieuse."""
    decision_time = _T0
    kickoffs = pd.Series([_T0 + timedelta(days=1)])  # dans le futur par rapport a decision_time
    with pytest.raises(ValueError, match="age negatif"):
        compute_weights_for_scheme(kickoffs, decision_time, DECAY_SCHEMES[0])


def test_deterministic_same_inputs_same_weights() -> None:
    decision_time = _T0 + timedelta(days=123)
    kickoffs = pd.Series([_T0, _T0 + timedelta(days=50)])
    scheme = DECAY_SCHEMES[2]
    w1 = compute_weights_for_scheme(kickoffs, decision_time, scheme)
    w2 = compute_weights_for_scheme(kickoffs, decision_time, scheme)
    assert np.array_equal(w1, w2)


def test_timezone_naive_datetimes_are_handled_consistently() -> None:
    """Les objets datetime naifs (convention deja etablie par
    RealMatchRecord/_goals_train_df) doivent produire un age coherent -
    pas de crash ni de decalage introduit par ce module."""
    decision_time = datetime(2024, 6, 15, 12, 0, 0)
    kickoff = datetime(2024, 5, 16, 12, 0, 0)  # exactement 30 jours avant
    scheme = WeightingScheme(name="test_30d", half_life_days=30.0)
    w = compute_weights_for_scheme(pd.Series([kickoff]), decision_time, scheme)
    assert w[0] == pytest.approx(0.5)


def test_empty_kickoff_series_returns_empty_weights() -> None:
    for scheme in (FLAT_SCHEME, *DECAY_SCHEMES):
        w = compute_weights_for_scheme(pd.Series([], dtype="datetime64[ns]"), _T0, scheme)
        assert len(w) == 0


# --- run_walkforward (garanties PIT / structure) ---------------------------


def _round_robin_history(n_matches: int, start: datetime) -> list[RealMatchRecord]:
    pairs = [(0, 1), (2, 3), (1, 2), (3, 0), (0, 2), (1, 3)]
    return [
        _record(f"m{i}", start + timedelta(days=4 * i), *pairs[i % len(pairs)], home_goals=1 + (i % 3), away_goals=1 + ((i + 1) % 2))
        for i in range(n_matches)
    ]


def test_run_walkforward_produces_one_row_per_match_with_all_scheme_columns() -> None:
    records = _round_robin_history(30, _T0)
    df = run_walkforward(records)
    assert len(df) == 30
    for scheme in (FLAT_SCHEME, *DECAY_SCHEMES):
        assert f"p_over_2_5_{scheme.name}" in df.columns


def test_run_walkforward_leaves_nan_below_min_train_matches() -> None:
    records = _round_robin_history(30, _T0)
    df = run_walkforward(records, min_train_matches=10)
    early_rows = df[df["n_train_matches"] < 10]
    assert len(early_rows) > 0
    for scheme in (FLAT_SCHEME, *DECAY_SCHEMES):
        assert early_rows[f"p_over_2_5_{scheme.name}"].isna().all()


def test_run_walkforward_never_uses_a_match_id_as_its_own_training_data() -> None:
    """Le match cible ne doit jamais entrer dans son propre entrainement -
    verifie indirectement : n_train_matches < nombre total de matchs
    strictement anterieurs + 1 (lui-meme exclu)."""
    records = _round_robin_history(20, _T0)
    df = run_walkforward(records)
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    for i, row in df.iterrows():
        # au plus i matchs anterieurs disponibles (jamais le match lui-meme)
        assert row["n_train_matches"] <= i


def test_run_walkforward_same_eligible_match_set_across_all_schemes() -> None:
    """Critere anti-biais explicite : le meme sous-ensemble de matchs est
    evalue (NaN ou valeur) pour TOUS les schemas simultanement."""
    records = _round_robin_history(25, _T0)
    df = run_walkforward(records)
    cols = [f"p_over_2_5_{s.name}" for s in (FLAT_SCHEME, *DECAY_SCHEMES)]
    na_masks = [df[c].isna() for c in cols]
    for mask in na_masks[1:]:
        assert (mask == na_masks[0]).all()


def test_run_walkforward_different_schemes_produce_different_probabilities_when_history_is_not_symmetric() -> None:
    """Regression minimale : les schemas de decroissance doivent
    reellement produire un resultat different du plat des lors que
    l'historique n'est pas symetrique dans le temps (sinon la ponderation
    ne servirait a rien - verifie que le branchement fonctionne)."""
    records = _round_robin_history(40, _T0)
    # Ajoute un choc recent net pour l'equipe 0 : une serie de large victoires
    # juste avant la derniere date, pour creer une asymetrie temporelle forte.
    shock = [
        _record(f"shock{i}", _T0 + timedelta(days=160 + i), 0, 2, home_goals=5, away_goals=0)
        for i in range(3)
    ]
    records_with_shock = records + shock
    target_kickoff = _T0 + timedelta(days=170)
    target = _record("target", target_kickoff, 0, 1, home_goals=1, away_goals=1)
    df = run_walkforward(records_with_shock + [target])
    row = df[df["match_id"] == "target"].iloc[0]
    assert row["p_over_2_5_A0_flat"] != pytest.approx(row["p_over_2_5_A1_halflife_30d"])


# --- metriques --------------------------------------------------------------


def test_binary_brier_score_perfect_prediction_is_zero() -> None:
    assert binary_brier_score(np.array([1.0, 0.0]), np.array([1.0, 0.0])) == pytest.approx([0.0, 0.0])


def test_binary_brier_score_worst_prediction_is_one() -> None:
    assert binary_brier_score(np.array([0.0]), np.array([1.0]))[0] == pytest.approx(1.0)


def test_binary_log_loss_is_finite_even_at_extreme_probabilities() -> None:
    result = binary_log_loss(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    assert np.all(np.isfinite(result))
    assert np.all(result >= 0)
