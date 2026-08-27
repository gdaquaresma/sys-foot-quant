from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage5_b1_dixon_coles_real.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_stage5_b1_dixon_coles_real", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bucket_dixon_coles_meilleur_requires_significant_ci_and_coherent_low_score() -> None:
    script = _load_script()
    assert script._bucket_verdict(global_ci_low=-0.02, global_ci_high=-0.005, low_score_mean_diff=-0.01) == (
        "dixon_coles_meilleur"
    )


def test_bucket_indetermine_when_global_significant_but_low_score_incoherent() -> None:
    script = _load_script()
    # Global significativement meilleur (IC95% < 0) mais le sous-ensemble
    # bas-score va dans le sens OPPOSE (diff > 0) - mecanisme non confirme.
    assert script._bucket_verdict(global_ci_low=-0.02, global_ci_high=-0.005, low_score_mean_diff=+0.01) == (
        "indetermine"
    )


def test_bucket_poisson_simple_meilleur_when_ci_entirely_positive() -> None:
    script = _load_script()
    assert script._bucket_verdict(global_ci_low=0.005, global_ci_high=0.02, low_score_mean_diff=0.01) == (
        "poisson_simple_meilleur"
    )


def test_bucket_indetermine_when_ci_crosses_zero() -> None:
    script = _load_script()
    assert script._bucket_verdict(global_ci_low=-0.01, global_ci_high=0.01, low_score_mean_diff=0.0) == (
        "indetermine"
    )


def test_aggregate_valide_requires_all_three_leagues_dixon_coles_meilleur() -> None:
    script = _load_script()
    buckets = ["dixon_coles_meilleur", "dixon_coles_meilleur", "dixon_coles_meilleur"]
    assert script._aggregate_verdict(buckets) == "VALIDE"


def test_aggregate_rejete_when_no_league_shows_dixon_coles_meilleur() -> None:
    script = _load_script()
    assert script._aggregate_verdict(["poisson_simple_meilleur", "indetermine", "poisson_simple_meilleur"]) == (
        "REJETE"
    )
    assert script._aggregate_verdict(["indetermine", "indetermine", "indetermine"]) == "REJETE"
    assert script._aggregate_verdict(["poisson_simple_meilleur"] * 3) == "REJETE"


def test_aggregate_indetermine_on_genuine_disagreement() -> None:
    script = _load_script()
    buckets = ["dixon_coles_meilleur", "poisson_simple_meilleur", "indetermine"]
    assert script._aggregate_verdict(buckets) == "INDETERMINE"
    buckets2 = ["dixon_coles_meilleur", "dixon_coles_meilleur", "indetermine"]
    assert script._aggregate_verdict(buckets2) == "INDETERMINE"
