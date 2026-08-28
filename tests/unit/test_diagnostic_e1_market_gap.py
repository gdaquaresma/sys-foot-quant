"""Tests unitaires des fonctions PURES du diagnostic post-E1
(scripts/run_stage7_diagnostic_e1_market_gap.py) - verifie l'exactitude
des calculs (Brier ligne par ligne, decomposition d'ecart, test
d'information independante) avant toute lecture des chiffres reels."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage7_diagnostic_e1_market_gap.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage7_diagnostic_e1_market_gap", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def diag_module():
    return _load_script()


def test_row_brier_matches_manual_computation(diag_module) -> None:
    probs = {"home": 0.5, "draw": 0.3, "away": 0.2}
    expected = (0.5 - 1.0) ** 2 + (0.3 - 0.0) ** 2 + (0.2 - 0.0) ** 2
    assert diag_module._row_brier(probs, "home") == pytest.approx(expected)


def test_row_brier_zero_for_perfect_prediction(diag_module) -> None:
    probs = {"home": 1.0, "draw": 0.0, "away": 0.0}
    assert diag_module._row_brier(probs, "home") == pytest.approx(0.0)


def _synthetic_df(diag_module, n: int, seed: int = 0, has_xg: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        p_market_home = float(rng.uniform(0.2, 0.7))
        p_market_draw = float(rng.uniform(0.15, 0.3))
        p_market_away = 1.0 - p_market_home - p_market_draw
        if p_market_away <= 0:
            continue
        outcome = rng.choice(["home", "draw", "away"], p=[p_market_home, p_market_draw, p_market_away])
        # poisson = marche + bruit centre, aucune info supplementaire injectee ici
        noise = rng.normal(0, 0.05, size=3)
        p_poisson = np.clip(
            np.array([p_market_home, p_market_draw, p_market_away]) + noise, 1e-6, None
        )
        p_poisson = p_poisson / p_poisson.sum()
        row = {
            "match_id": f"m{i}",
            "league": "premier_league",
            "season": "2024_25",
            "outcome_selection": outcome,
            "implied_norm_home": p_market_home,
            "implied_norm_draw": p_market_draw,
            "implied_norm_away": p_market_away,
            "model_prob_home": p_poisson[0],
            "model_prob_draw": p_poisson[1],
            "model_prob_away": p_poisson[2],
            "edge_norm_home": p_poisson[0] - p_market_home,
            "edge_norm_draw": p_poisson[1] - p_market_draw,
            "edge_norm_away": p_poisson[2] - p_market_away,
            "has_xg": has_xg,
        }
        row["erreur_poisson"] = diag_module._row_brier(
            {"home": p_poisson[0], "draw": p_poisson[1], "away": p_poisson[2]}, outcome
        )
        row["erreur_marche"] = diag_module._row_brier(
            {"home": p_market_home, "draw": p_market_draw, "away": p_market_away}, outcome
        )
        rows.append(row)
    return pd.DataFrame(rows)


def test_gap_decomposition_bias_is_near_zero_for_unbiased_noise(diag_module) -> None:
    df = _synthetic_df(diag_module, 3000, seed=1)
    d = diag_module.gap_decomposition(df, "home")
    assert abs(d["biais_moyen"]) < 0.02  # bruit centre par construction


def test_decile_table_covers_all_matches_exactly_once(diag_module) -> None:
    df = _synthetic_df(diag_module, 2000, seed=2)
    table = diag_module.decile_table(df, "home")
    assert int(table["n"].sum()) == len(df)


def test_favorite_quintile_table_covers_all_matches_exactly_once(diag_module) -> None:
    df = _synthetic_df(diag_module, 2000, seed=3)
    table = diag_module.favorite_quintile_table(df)
    assert int(table["n"].sum()) == len(df)


def test_independent_information_test_finds_no_signal_when_poisson_is_pure_noise(diag_module) -> None:
    df = _synthetic_df(diag_module, 4000, seed=4)
    res = diag_module.independent_information_test(df, "home")
    assert res is not None
    # Le bruit ajoute a poisson n'a par construction aucune information sur
    # le resultat au-dela de la probabilite de marche - l'IC95% doit
    # couvrir 0 (pas de faux positif systematique).
    assert res["ci_low"] <= 0.0 <= res["ci_high"]


def test_independent_information_test_detects_injected_signal(diag_module) -> None:
    # Construit un poisson dont le desaccord avec le marche est
    # DELIBEREMENT informatif : quand poisson prevoit plus que le marche,
    # le resultat "home" est artificiellement rendu plus frequent.
    rng = np.random.default_rng(5)
    rows = []
    for i in range(4000):
        p_market_home = float(rng.uniform(0.3, 0.5))
        edge = rng.choice([0.15, -0.15])
        p_poisson_home = float(np.clip(p_market_home + edge, 0.01, 0.99))
        true_p_home = float(np.clip(p_market_home + 0.5 * edge, 0.01, 0.99))  # le signe de l'edge est informatif
        outcome = "home" if rng.uniform() < true_p_home else "away"
        rows.append(
            {
                "match_id": f"m{i}",
                "league": "premier_league",
                "season": "2024_25",
                "outcome_selection": outcome,
                "implied_norm_home": p_market_home,
                "model_prob_home": p_poisson_home,
                "edge_norm_home": p_poisson_home - p_market_home,
                "has_xg": True,
            }
        )
    df = pd.DataFrame(rows)
    res = diag_module.independent_information_test(df, "home")
    assert res is not None
    assert res["ci_low"] > 0.0  # le signal injecte doit etre detecte (edge+ -> frequence observee plus haute)


def test_xg_vs_market_summary_empty_subset_returns_n_zero(diag_module) -> None:
    df = _synthetic_df(diag_module, 50, seed=6, has_xg=False)
    df["xg_prob_home"] = np.nan
    df["xg_prob_draw"] = np.nan
    df["xg_prob_away"] = np.nan
    df["erreur_xg"] = np.nan
    res = diag_module.xg_vs_market_summary(df)
    assert res == {"n": 0}
