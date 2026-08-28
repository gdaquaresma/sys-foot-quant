"""Garde-fous anti-fuite et de coherence pour E7
(scripts/run_stage15_e7_total_goals_distribution.py) :
- le mecanisme point-in-time est INTEGRALEMENT delegue aux fonctions deja
  testees de stage8 (`_load_records`, `_goals_train_df`, `_xg_train_df`) -
  jamais reimplemente ;
- la correction scalaire n'est jamais ajustee sur le test ;
- `evaluate_distributions` n'ajuste jamais elle-meme le facteur de
  correction (toujours recu en parametre, fige avant l'appel) ;
- la coherence Over/Under (monotonicite, somme=1, non-negativite,
  reproduction exacte depuis la distribution) est verifiee sur un large
  balayage aleatoire de (lambda, mu, rho), pas seulement des cas
  ponctuels ;
- non-regression : les (lambda+mu) recalcules separement par E7
  correspondent exactement a ceux deja produits par stage8 pour les memes
  matchs (meme mecanisme, verifie independamment)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage15_e7_total_goals_distribution.py"
_STAGE8_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage8_diagnostic_total_goals_over_under.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e7_module():
    return _load(_SCRIPT_PATH, "run_stage15_e7_total_goals_distribution")


# --- 1. point-in-time integralement delegue --------------------------------


def test_e7_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "stage8_module._load_records" in source
    assert "stage8_module._goals_train_df" in source
    assert "stage8_module._xg_train_df" in source
    # aucune reimplementation d'un filtre de connaissance par date
    assert "AmbiguousCollectionWindowError" not in source
    assert "conservative_knowledge_time_utc" not in source


# --- 2. correction scalaire jamais ajustee sur le test ----------------------


def test_fit_scale_correction_independent_of_test_content(e7_module) -> None:
    calib = pd.DataFrame(
        {
            "poisson_simple_lambda": [1.2, 1.5, 1.8, 2.0],
            "poisson_simple_mu": [1.0, 1.1, 1.0, 1.2],
            "total_goals": [3, 2, 4, 3],
        }
    )
    c = e7_module.fit_scale_correction(calib, "poisson_simple")
    # rien dans la signature ni le corps de la fonction ne prend de "test_df"
    import inspect

    sig = inspect.signature(e7_module.fit_scale_correction)
    assert list(sig.parameters) == ["calibration_df", "model"]
    assert c > 0


def test_evaluate_distributions_never_refits_scale_internally() -> None:
    import ast

    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "evaluate_distributions")
    body_source = ast.unparse(func)
    assert "fit_scale_correction" not in body_source  # scale toujours recu en parametre


# --- 3. coherence sur un large balayage aleatoire (hypothesis) -------------


@given(
    lam=st.floats(0.3, 6.0),
    mu=st.floats(0.3, 6.0),
    rho=st.floats(-0.15, 0.15),
    scale=st.floats(0.7, 1.6),
)
@settings(max_examples=200)
def test_property_distribution_always_coherent(lam, mu, rho, scale) -> None:
    e7 = _load(_SCRIPT_PATH, "run_stage15_e7_total_goals_distribution_prop")
    lam_s, mu_s = scale * lam, scale * mu
    # bornes de rho valides pour ce (lam_s, mu_s) - evite un rho hors domaine
    lo = max(-1.0 / lam_s, -1.0 / mu_s)
    hi = min(1.0, 1.0 / (lam_s * mu_s))
    rho_valid = min(max(rho, lo + 1e-6), hi - 1e-6) if lo + 1e-6 < hi - 1e-6 else 0.0

    m = e7.dixon_coles_matrix(lam_s, mu_s, rho_valid)
    dist = e7.total_goals_distribution(m)
    ou = e7.over_under_probs(m)

    validity = e7.check_distribution_validity(dist)
    assert validity["all_non_negative"]
    assert validity["sums_to_one"]
    assert e7.check_over_under_monotonic(ou)
    assert e7.check_over_under_matches_distribution(dist, ou)


# --- 4. non-regression : (lambda+mu) d'E7 == lambda_plus_mu de stage8 ------


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs").exists(),
    reason="Fichiers Understat reels non presents.",
)
def test_real_corpus_lambda_plus_mu_matches_stage8_exactly(e7_module) -> None:
    stage8 = _load(_STAGE8_PATH, "run_stage8_diagnostic_total_goals_over_under")
    stage8_df = stage8.build_total_goals_dataframe()
    # limite a une seule (championnat, saison) pour rester rapide - non
    # regression suffisante, pas besoin de refaire les 6 fichiers.
    e7_df = e7_module.build_lambda_mu_dataframe(stage8)

    merged = stage8_df.merge(e7_df, on="match_id", suffixes=("_stage8", "_e7"))
    assert len(merged) > 2000  # les deux dataframes couvrent bien le meme corpus

    for model in ("poisson_simple", "xg_model"):
        stage8_sum = merged[f"{model}_lambda_plus_mu"]
        e7_sum = merged[f"{model}_lambda"] + merged[f"{model}_mu"]
        both_present = stage8_sum.notna() & e7_sum.notna()
        assert both_present.sum() > 2000
        np.testing.assert_allclose(
            stage8_sum[both_present].to_numpy(), e7_sum[both_present].to_numpy(), atol=1e-9
        )
