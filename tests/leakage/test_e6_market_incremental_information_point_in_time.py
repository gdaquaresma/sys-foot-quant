"""Garde-fous anti-fuite pour E6
(scripts/run_stage14_e6_market_incremental_information.py), couvrant
explicitement les six garanties demandees (section 12) :

1. aucune information du resultat final n'est utilisee pour construire
   les variables predictives (esperance, p_model, p_market) ;
2. les cotes sont strictement point-in-time selon les regles deja
   validees (delegue integralement a over_under_odds.py, deja teste) ;
3. aucune calibration n'est entrainee sur le test ;
4. les tranches sont definies avant observation des resultats (constantes
   figees) ;
5. aucun seuil n'est optimise apres coup (seuils naturels fixes) ;
6. le marche et le modele sont compares sur EXACTEMENT le meme
   sous-echantillon exploitable."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage14_e6_market_incremental_information.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage14_e6_market_incremental_information", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e6_module():
    return _load_script()


def _calib_test_dfs():
    rng_c = np.random.default_rng(0)
    n_c = 200
    calib = pd.DataFrame(
        {
            "match_id": [f"c{i}" for i in range(n_c)],
            "total_goals": rng_c.poisson(2.5, size=n_c),
            "poisson_simple_p_over_2.5": rng_c.uniform(0.2, 0.8, size=n_c),
            "poisson_simple_lambda_plus_mu": rng_c.uniform(1.5, 4.0, size=n_c),
        }
    )
    rng_t = np.random.default_rng(1)
    n_t = 100
    test = pd.DataFrame(
        {
            "match_id": [f"t{i}" for i in range(n_t)],
            "league": ["premier_league"] * n_t,
            "season": ["2024_25"] * n_t,
            "total_goals": rng_t.poisson(2.5, size=n_t),
            "poisson_simple_p_over_2.5": rng_t.uniform(0.2, 0.8, size=n_t),
            "poisson_simple_lambda_plus_mu": rng_t.uniform(1.5, 4.0, size=n_t),
        }
    )
    odds = {f"t{i}": (1.8, 2.0) for i in range(n_t)}
    return calib, test, odds


# --- 1. aucune info du resultat dans les variables predictives -------------


def test_build_e6_dataframe_variables_independent_of_test_outcome(e6_module) -> None:
    stage13 = e6_module._load_stage13()
    calib, test_a, odds = _calib_test_dfs()
    test_b = test_a.copy()
    test_b["total_goals"] = rng_alt = np.random.default_rng(99).poisson(2.5, size=len(test_b))

    df_a = e6_module.build_e6_dataframe("poisson_simple", calib, test_a, odds, stage13)
    df_b = e6_module.build_e6_dataframe("poisson_simple", calib, test_b, odds, stage13)

    df_a = df_a.sort_values("match_id").reset_index(drop=True)
    df_b = df_b.sort_values("match_id").reset_index(drop=True)
    np.testing.assert_allclose(df_a["expected_goals"].to_numpy(), df_b["expected_goals"].to_numpy())
    np.testing.assert_allclose(df_a["p_model_over25"].to_numpy(), df_b["p_model_over25"].to_numpy())
    np.testing.assert_allclose(df_a["p_market_over25"].to_numpy(), df_b["p_market_over25"].to_numpy())


# --- 2. cotes point-in-time deleguees a over_under_odds.py ------------------


def test_e6_script_never_reimplements_temporal_or_matching_logic() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    for forbidden in (
        "conservative_knowledge_time_utc",
        "AmbiguousCollectionWindowError",
        "match_league_season",
        "ZoneInfo",
    ):
        assert forbidden not in source, f"E6 ne doit pas reimplementer '{forbidden}'."
    assert "build_pooled_over_under_odds" in source  # delegue a E5 (over_under_odds.py sous-jacent)


# --- 3. aucune calibration entrainee sur le test ---------------------------


def test_e6_reuses_compute_calibrated_probs_never_touches_test_outcome(e6_module) -> None:
    stage13 = e6_module._load_stage13()
    calib, test_a, odds = _calib_test_dfs()
    test_b = test_a.copy()
    test_b["total_goals"] = np.where(test_b["total_goals"] > 2.5, 0, 5)  # resultats inverses

    probs_a = stage13.compute_calibrated_probs(calib, test_a, "poisson_simple")
    probs_b = stage13.compute_calibrated_probs(calib, test_b, "poisson_simple")
    pd.testing.assert_series_equal(probs_a.sort_index(), probs_b.sort_index())


def test_e6_script_never_calls_fit_on_test_dataframe() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "fit_isotonic_calibration" not in source  # uniquement via compute_calibrated_probs (E5, deja teste)


# --- 4. tranches figees avant observation ----------------------------------


def test_fixed_bins_are_hardcoded_constants(e6_module) -> None:
    assert e6_module._EXPECTED_GOALS_EDGES == [-np.inf, 2.0, 2.5, 3.0, 3.5, np.inf]
    assert e6_module._MARKET_PROB_EDGES == [-np.inf, 0.45, 0.50, 0.55, 0.60, np.inf]


def test_bin_functions_never_reference_outcome_when_building_categories() -> None:
    """pd.cut est toujours appele sur expected_goals/p_market_over25 - pas
    sur total_goals ni outcome_over25 - verifie par inspection AST des
    fonctions de binning."""
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "cut":
            call_source = ast.unparse(node)
            assert "outcome_over25" not in call_source
            assert "total_goals" not in call_source


# --- 5. seuils naturels, non optimises --------------------------------------


def test_natural_thresholds_are_fixed_and_not_searched(e6_module) -> None:
    assert e6_module._MARKET_NATURAL_SPLIT == 0.50
    assert e6_module._MODEL_NATURAL_SPLIT == 2.5
    source = Path(_SCRIPT_PATH).read_text()
    assert "np.linspace" not in source
    assert "for threshold in" not in source
    assert "best_threshold" not in source


# --- 6. modele et marche compares sur exactement le meme sous-echantillon --


def test_model_and_market_share_identical_row_index(e6_module) -> None:
    stage13 = e6_module._load_stage13()
    calib, test, odds = _calib_test_dfs()
    df = e6_module.build_e6_dataframe("poisson_simple", calib, test, odds, stage13)
    # une seule ligne par match, p_model/p_market/expected_goals tous
    # presents simultanement (jamais NaN d'un cote sans l'autre) -
    # garantit que toute analyse (correlation, tranches, tests) porte sur
    # exactement le meme sous-echantillon pour les deux sources.
    assert df["p_model_over25"].notna().all()
    assert df["p_market_over25"].notna().all()
    assert df["expected_goals"].notna().all()
    assert df["match_id"].is_unique
