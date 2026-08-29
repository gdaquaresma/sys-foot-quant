"""Tests unitaires des fonctions PURES d'E16
(scripts/run_stage25_e16_market_movement_information.py) - avant toute
execution reelle."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sys_foot_quant.data_engine.market_odds.football_data_loader import FootballDataMatchRecord

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage25_e16_market_movement_information.py"

_LEAGUE = "premier_league"
_SEASON = "2024_25"
_T0 = datetime(2024, 8, 3, 15, 0, 0)  # un samedi


def _us(match_id, dt, home, away, is_result=True):
    return {
        "id": match_id,
        "isResult": is_result,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "h": {"id": 1, "title": home},
        "a": {"id": 2, "title": away},
    }


def _fd(
    date_dt,
    home,
    away,
    b365=(1.8, 3.6, 4.5),
    b365_close=(1.75, 3.7, 4.6),
    over=1.85,
    under=1.95,
    over_close=1.80,
    under_close=2.00,
    ps=None,
    ps_close=None,
    league=_LEAGUE,
    season=_SEASON,
):
    return FootballDataMatchRecord(
        league=league, season=season, source="football_data", bookmaker="B365", market="1x2",
        date_str=date_dt.strftime("%d/%m/%Y"), time_str=date_dt.strftime("%H:%M"),
        home_team_fd=home, away_team_fd=away, home_goals=2, away_goals=1,
        b365_home=b365[0], b365_draw=b365[1], b365_away=b365[2],
        b365_close_home=b365_close[0] if b365_close else None,
        b365_close_draw=b365_close[1] if b365_close else None,
        b365_close_away=b365_close[2] if b365_close else None,
        b365_over_2_5=over, b365_under_2_5=under,
        b365_close_over_2_5=over_close, b365_close_under_2_5=under_close,
        ps_home=ps[0] if ps else None, ps_draw=ps[1] if ps else None, ps_away=ps[2] if ps else None,
        ps_close_home=ps_close[0] if ps_close else None, ps_close_draw=ps_close[1] if ps_close else None, ps_close_away=ps_close[2] if ps_close else None,
    )


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage25_e16_market_movement_information", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e16_module():
    return _load_script()


def _dt(day: int) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


# --- compute_market_movement ---------------------------------------------------


def test_compute_market_movement_basic_1x2(e16_module) -> None:
    odds_open = {"H": 2.0, "D": 3.5, "A": 4.0}
    odds_close = {"H": 1.9, "D": 3.6, "A": 4.2}
    out = e16_module.compute_market_movement(odds_open, odds_close)
    assert set(out) == {"H", "D", "A"}
    h = out["H"]
    assert h["odds_open"] == pytest.approx(2.0)
    assert h["odds_close"] == pytest.approx(1.9)
    assert h["movement_abs"] == pytest.approx(-0.1)
    assert h["movement_rel"] == pytest.approx(-0.05)
    assert h["prob_open_raw"] == pytest.approx(0.5)
    assert h["prob_close_raw"] == pytest.approx(1 / 1.9)


def test_compute_market_movement_normalized_sums_to_one(e16_module) -> None:
    odds_open = {"H": 2.0, "D": 3.5, "A": 4.0}
    odds_close = {"H": 1.9, "D": 3.6, "A": 4.2}
    out = e16_module.compute_market_movement(odds_open, odds_close)
    assert sum(v["prob_open_norm"] for v in out.values()) == pytest.approx(1.0)
    assert sum(v["prob_close_norm"] for v in out.values()) == pytest.approx(1.0)


def test_compute_market_movement_prob_movement_matches_diff(e16_module) -> None:
    odds_open = {"Over": 1.90, "Under": 2.00}
    odds_close = {"Over": 1.80, "Under": 2.10}
    out = e16_module.compute_market_movement(odds_open, odds_close)
    over = out["Over"]
    assert over["movement_prob_norm"] == pytest.approx(over["prob_close_norm"] - over["prob_open_norm"])
    assert over["movement_prob_raw"] == pytest.approx(over["prob_close_raw"] - over["prob_open_raw"])


# --- fit_logistic / predict_logistic --------------------------------------------


def test_fit_logistic_recovers_known_relationship(e16_module) -> None:
    rng = np.random.default_rng(0)
    n = 2000
    x = rng.uniform(-3, 3, n)
    true_a, true_b = 0.3, 1.5
    p_true = 1.0 / (1.0 + np.exp(-(true_a + true_b * x)))
    y = rng.binomial(1, p_true)
    X = np.column_stack([np.ones(n), x])
    beta = e16_module.fit_logistic(X, y)
    assert beta[0] == pytest.approx(true_a, abs=0.15)
    assert beta[1] == pytest.approx(true_b, abs=0.15)


def test_predict_logistic_matches_sigmoid_formula(e16_module) -> None:
    beta = np.array([0.5, -1.0])
    X = np.array([[1.0, 0.0], [1.0, 1.0]])
    out = e16_module.predict_logistic(beta, X)
    assert out[0] == pytest.approx(1 / (1 + np.exp(-0.5)))
    assert out[1] == pytest.approx(1 / (1 + np.exp(-(0.5 - 1.0))))


# --- walk_forward_logistic -------------------------------------------------------


def test_walk_forward_logistic_excludes_rows_below_min_train(e16_module) -> None:
    n = 10
    df = pd.DataFrame({"decision_time": [_dt(d) for d in range(1, n + 1)], "movement_prob_norm": np.linspace(-0.1, 0.1, n), "outcome": [0.0, 1.0] * (n // 2)})

    def cov(d):
        X = np.column_stack([np.ones(len(d)), d["movement_prob_norm"].to_numpy()])
        return X, d["outcome"].to_numpy()

    preds = e16_module.walk_forward_logistic(df, cov, min_train=5)
    assert np.all(np.isnan(preds[:5]))
    assert not np.any(np.isnan(preds[5:]))


def test_walk_forward_logistic_never_uses_future_rows(e16_module) -> None:
    """Une ligne FUTURE aberrante ne doit jamais influencer la prediction
    d'une ligne anterieure - preuve directe d'absence de fuite temporelle."""
    n = 40
    rng = np.random.default_rng(0)
    mv = rng.uniform(-0.05, 0.05, n)
    y = rng.binomial(1, 0.5, n).astype(float)
    df = pd.DataFrame({"decision_time": [_dt(d) for d in range(1, n + 1)], "movement_prob_norm": mv, "outcome": y})

    def cov(d):
        X = np.column_stack([np.ones(len(d)), d["movement_prob_norm"].to_numpy()])
        return X, d["outcome"].to_numpy()

    preds_before = e16_module.walk_forward_logistic(df, cov, min_train=10)

    df_corrupted = df.copy()
    df_corrupted.loc[n - 1, "movement_prob_norm"] = 999.0  # valeur aberrante sur la DERNIERE ligne (future)
    df_corrupted.loc[n - 1, "outcome"] = 1.0
    preds_after = e16_module.walk_forward_logistic(df_corrupted, cov, min_train=10)

    # toutes les predictions SAUF la derniere doivent rester identiques -
    # la ligne aberrante est future par rapport a elles.
    np.testing.assert_allclose(preds_before[:-1], preds_after[:-1])


def test_walk_forward_logistic_uses_strictly_prior_rows_only(e16_module) -> None:
    """Verifie directement (sans passer par le fit) que le nombre de
    lignes d'entrainement utilisees a l'etape i est EXACTEMENT i."""
    n = 15
    seen_lengths = []

    df = pd.DataFrame({"decision_time": [_dt(d) for d in range(1, n + 1)], "x": np.linspace(0, 1, n), "outcome": [0.0, 1.0] * (n // 2) + [0.0]})

    def cov(d):
        seen_lengths.append(len(d))
        X = np.column_stack([np.ones(len(d)), d["x"].to_numpy()])
        return X, d["outcome"].to_numpy()

    e16_module.walk_forward_logistic(df, cov, min_train=3)
    # cov() est appele UNE FOIS pour construire (X_all, y_all) sur tout le
    # DataFrame - la troncature `X_all[:i]` se fait ensuite en interne.
    assert seen_lengths == [n]


# --- evaluate_predictions / compare_brier_paired --------------------------------


def test_evaluate_predictions_perfect_predictions_zero_brier(e16_module) -> None:
    p = np.array([1.0, 0.0, 1.0, 0.0])
    y = np.array([1.0, 0.0, 1.0, 0.0])
    out = e16_module.evaluate_predictions(p, y)
    assert out["brier"] == pytest.approx(0.0)
    assert out["biais"] == pytest.approx(0.0)


def test_evaluate_predictions_drops_nan_rows(e16_module) -> None:
    p = np.array([0.5, np.nan, 0.6])
    y = np.array([1.0, 0.0, 1.0])
    out = e16_module.evaluate_predictions(p, y)
    assert out["n"] == 2


def test_compare_brier_paired_zero_when_identical(e16_module) -> None:
    p = np.array([0.5, 0.6, 0.7])
    y = np.array([1.0, 0.0, 1.0])
    out = e16_module.compare_brier_paired(p, p, y)
    assert out["boot"]["mean_diff"] == pytest.approx(0.0, abs=1e-9)


def test_compare_brier_paired_none_when_too_few_common_rows(e16_module) -> None:
    p_a = np.array([0.5, np.nan])
    p_b = np.array([np.nan, 0.6])
    y = np.array([1.0, 0.0])
    assert e16_module.compare_brier_paired(p_a, p_b, y) is None


# --- classify_amplitude / amplitude_table ---------------------------------------


@pytest.mark.parametrize(
    "movement,expected",
    [
        (0.0, "quasi nul (<1pt)"),
        (0.009, "quasi nul (<1pt)"),
        (-0.009, "quasi nul (<1pt)"),
        (0.01, "petit (1-3pt)"),
        (0.029, "petit (1-3pt)"),
        (0.03, "moyen (3-6pt)"),
        (0.059, "moyen (3-6pt)"),
        (0.06, "gros (>=6pt)"),
        (-0.10, "gros (>=6pt)"),
    ],
)
def test_classify_amplitude_boundaries(e16_module, movement, expected) -> None:
    assert e16_module.classify_amplitude(movement) == expected


def test_amplitude_table_reports_all_labels_even_when_empty(e16_module) -> None:
    df = pd.DataFrame({"movement_prob_norm": [0.001, 0.002], "prob_open_norm": [0.5, 0.5], "prob_close_norm": [0.5, 0.5], "outcome": [1.0, 0.0]})
    table = e16_module.amplitude_table(df)
    assert set(table["categorie"]) == set(e16_module._AMPLITUDE_LABELS)
    empty_rows = table[table["categorie"] != "quasi nul (<1pt)"]
    assert (empty_rows["n"] == 0).all()
    assert (empty_rows["insuffisant"]).all()


# --- price_discovery_summary ----------------------------------------------------


def test_price_discovery_summary_basic(e16_module) -> None:
    df = pd.DataFrame(
        {
            "movement_prob_norm": [0.02, -0.02, 0.005, 0.04],
            "outcome": [1.0, 0.0, 1.0, 1.0],
        }
    )
    out = e16_module.price_discovery_summary(df)
    assert out["n"] == 4
    assert out["frac_moved_toward_selection"] == pytest.approx(0.75)  # 0.02, 0.005 et 0.04 > 0
    assert out["mean_abs_movement"] == pytest.approx(np.mean([0.02, 0.02, 0.005, 0.04]))


# --- holm_bonferroni --------------------------------------------------------------


def test_holm_bonferroni_rejects_all_when_all_tiny(e16_module) -> None:
    out = e16_module.holm_bonferroni([0.0001, 0.0002, 0.0003, 0.0004], alpha=0.05)
    assert out == [True, True, True, True]


def test_holm_bonferroni_rejects_none_when_all_large(e16_module) -> None:
    out = e16_module.holm_bonferroni([0.9, 0.8, 0.7, 0.6], alpha=0.05)
    assert out == [False, False, False, False]


def test_holm_bonferroni_more_conservative_than_uncorrected(e16_module) -> None:
    """Une p-value de 0.04 (significative sans correction a 0.05) ne doit
    PAS forcement etre rejetee une fois corrigee parmi plusieurs tests."""
    p_values = [0.04, 0.20, 0.30, 0.40]
    out = e16_module.holm_bonferroni(p_values, alpha=0.05)
    # seuil le plus strict pour le plus petit p : alpha/4 = 0.0125 < 0.04
    assert out[0] is False


def test_holm_bonferroni_sequential_stop(e16_module) -> None:
    """Verifie la procedure SEQUENTIELLE : une fois qu'un rang ne franchit
    plus son seuil, tous les rangs suivants (p plus grands) sont aussi non
    rejetes, meme si leur propre seuil individuel serait technique."""
    p_values = [0.001, 0.5, 0.002]  # trie : 0.001, 0.002, 0.5
    out = e16_module.holm_bonferroni(p_values, alpha=0.05)
    assert out[1] is False  # p=0.5 jamais rejete


# --- build_movement_dataset (mirror des exclusions d'E9) ------------------------


def test_build_movement_dataset_basic_exploitable_match(e16_module) -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton")]
    records, counts = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    assert counts["n_exploitable"] == 1
    r = records[0]
    assert r.match_id == "1"
    assert r.b365_open_1x2 == {"H": pytest.approx(1.8), "D": pytest.approx(3.6), "A": pytest.approx(4.5)}
    assert r.b365_close_1x2 == {"H": pytest.approx(1.75), "D": pytest.approx(3.7), "A": pytest.approx(4.6)}
    assert r.b365_open_ou == {"Over": pytest.approx(1.85), "Under": pytest.approx(1.95)}
    assert r.b365_close_ou == {"Over": pytest.approx(1.80), "Under": pytest.approx(2.00)}


def test_build_movement_dataset_incomplete_b365_opening_excludes_match(e16_module) -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton", b365=(None, 3.6, 4.5))]
    records, counts = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    assert counts["n_exploitable"] == 0
    assert counts["n_excluded_incomplete_b365"] == 1


def test_build_movement_dataset_missing_closing_is_none_never_excludes_match(e16_module) -> None:
    """Une cloture manquante ne doit JAMAIS exclure un match - seule
    l'ouverture B365 1X2 conditionne l'inclusion (meme regle qu'E9)."""
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton", b365_close=None, over_close=None, under_close=None)]
    records, counts = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    assert counts["n_exploitable"] == 1
    r = records[0]
    assert r.b365_close_1x2 is None
    assert r.b365_close_ou is None
    assert r.b365_open_1x2 is not None  # l'ouverture, elle, reste presente


def test_build_movement_dataset_ambiguous_weekday_excluded(e16_module) -> None:
    tuesday = datetime(2024, 8, 6, 20, 0, 0)
    raw = [_us("1", tuesday, "Arsenal", "Everton")]
    fd = [_fd(tuesday, "Arsenal", "Everton")]
    records, counts = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    assert counts["n_exploitable"] == 0
    assert counts["n_excluded_ambiguous_weekday"] == 1


def test_build_movement_dataset_ps_present_and_absent(e16_module) -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton"), _us("2", datetime(2024, 8, 10, 15, 0, 0), "Chelsea", "Liverpool")]
    fd = [
        _fd(_T0, "Arsenal", "Everton", ps=(1.83, 3.55, 4.45), ps_close=(1.80, 3.60, 4.50)),
        _fd(datetime(2024, 8, 10, 15, 0, 0), "Chelsea", "Liverpool", ps=None),
    ]
    records, counts = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    by_id = {r.match_id: r for r in records}
    assert by_id["1"].ps_open_1x2 == {"H": pytest.approx(1.83), "D": pytest.approx(3.55), "A": pytest.approx(4.45)}
    assert by_id["1"].ps_close_1x2 == {"H": pytest.approx(1.80), "D": pytest.approx(3.60), "A": pytest.approx(4.50)}
    assert by_id["2"].ps_open_1x2 is None
    assert by_id["2"].ps_close_1x2 is None


# --- build_selection_dataframe / build_ps_selection_dataframe ------------------


def test_build_selection_dataframe_1x2_home_outcome(e16_module) -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton")]  # home_goals=2, away_goals=1 -> home wins
    records, _ = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    df = e16_module.build_selection_dataframe(records, "1x2", "H")
    assert len(df) == 1
    assert df.iloc[0]["outcome"] == 1.0
    assert df.iloc[0]["odds_open"] == pytest.approx(1.8)


def test_build_selection_dataframe_excludes_rows_without_closing(e16_module) -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton", b365_close=None)]
    records, _ = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    df = e16_module.build_selection_dataframe(records, "1x2", "H")
    assert df.empty  # pas de cloture -> pas de ligne de mouvement exploitable


def test_build_selection_dataframe_over_under_outcome(e16_module) -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton")]
    fd = [_fd(_T0, "Arsenal", "Everton")]  # 2+1=3 buts -> Over 2.5
    records, _ = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    df = e16_module.build_selection_dataframe(records, "ou25", "Over")
    assert len(df) == 1
    assert df.iloc[0]["outcome"] == 1.0


def test_build_ps_selection_dataframe_only_includes_matches_with_ps(e16_module) -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton"), _us("2", datetime(2024, 8, 10, 15, 0, 0), "Chelsea", "Liverpool")]
    fd = [
        _fd(_T0, "Arsenal", "Everton", ps=(1.83, 3.55, 4.45), ps_close=(1.80, 3.60, 4.50)),
        _fd(datetime(2024, 8, 10, 15, 0, 0), "Chelsea", "Liverpool", ps=None),
    ]
    records, _ = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    df = e16_module.build_ps_selection_dataframe(records, "H")
    assert len(df) == 1
    assert df.iloc[0]["match_id"] == "1"


# --- coverage_audit ---------------------------------------------------------------


def test_coverage_audit_basic(e16_module) -> None:
    raw = [_us("1", _T0, "Arsenal", "Everton"), _us("2", datetime(2024, 8, 10, 15, 0, 0), "Chelsea", "Liverpool")]
    fd = [
        _fd(_T0, "Arsenal", "Everton", ps=(1.83, 3.55, 4.45), ps_close=(1.80, 3.60, 4.50)),
        _fd(datetime(2024, 8, 10, 15, 0, 0), "Chelsea", "Liverpool", ps=None, b365_close=None),
    ]
    records, _ = e16_module.build_movement_dataset(_LEAGUE, _SEASON, raw, fd)
    out = e16_module.coverage_audit(records)
    assert out["n_matches"] == 2
    assert out["b365_1x2_open"] == pytest.approx(1.0)
    assert out["b365_1x2_close"] == pytest.approx(0.5)
    assert out["ps_1x2_open"] == pytest.approx(0.5)
