"""Tests cibles pour `dyadic_power_analysis` (analyse de ROBUSTESSE,
hors chaine de production). Couvre : determinisme, cas synthetiques
verifiables analytiquement, monotonicite, injection des valeurs reelles
deja validees, garde-fou donnees (aucune nouvelle saison), entrees
invalides.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import math
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent / "dyadic_power_analysis.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dyadic_power_analysis", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def power_module():
    return _load_module()


# --- 1. Determinisme ---------------------------------------------------------


def test_current_power_is_deterministic(power_module) -> None:
    out1 = power_module.current_power_direct_wald(0.15, 0.0712, df=22)
    out2 = power_module.current_power_direct_wald(0.15, 0.0712, df=22)
    assert out1 == out2


def test_n_needed_dyadic_is_deterministic(power_module) -> None:
    out1 = power_module.n_needed_dyadic_extrapolated(0.15, 0.80, 0.071158)
    out2 = power_module.n_needed_dyadic_extrapolated(0.15, 0.80, 0.071158)
    assert out1 == out2


# --- 2. Cas synthetiques verifiables analytiquement --------------------------


def test_power_under_null_equals_true_test_size_not_nominal_alpha(power_module) -> None:
    # Sous H0 (r_ref=0), la "puissance" degenere en taux de faux positifs.
    # NOTE IMPORTANTE (decouverte par ce test) : ce taux n'est PAS
    # exactement alpha=0.05, car le seuil critique utilise est t(df) (plus
    # conservateur que z a petit df), alors que la puissance elle-meme est
    # approximee par une loi normale - un choix deliberement coherent avec
    # la convention de `dyadic_correlation_ci` (IC construit avec t_crit),
    # mais qui ne preserve pas exactement alpha=5% sous H0. Valeur exacte
    # attendue : 2*Phi(-t_crit(df)), PAS alpha.
    from scipy.stats import norm, t as student_t

    df = 22
    alpha = 0.05
    t_crit = float(student_t.ppf(1 - alpha / 2, df))
    expected_true_size = 2 * float(norm.cdf(-t_crit))

    power = power_module.current_power_direct_wald(0.0, 0.0712, df=df, alpha=alpha)
    assert power == pytest.approx(expected_true_size, abs=1e-9)
    # Documente explicitement l'ecart avec le alpha nominal (conservateur).
    assert power < alpha


def test_power_approaches_one_for_very_large_effect(power_module) -> None:
    power = power_module.current_power_direct_wald(5.0, 0.01, df=22)
    assert power > 0.999


def test_naive_fisher_z_se_matches_closed_form(power_module) -> None:
    # Formule fermee connue : 1/sqrt(n-3).
    assert power_module.naive_fisher_z_se(228) == pytest.approx(1.0 / math.sqrt(225))


def test_inflation_factor_matches_known_poisson_and_xg_cases(power_module) -> None:
    # kappa_poisson > 1 (SE dyadique gonflee), kappa_xg < 1 (SE reduite) -
    # cohrent avec le resultat deja observe en PL-E15-DYADIC-CI.
    kappa_poisson = power_module.inflation_factor(0.071158, n=228)
    kappa_xg = power_module.inflation_factor(0.051121, n=228)
    assert kappa_poisson > 1.0
    assert kappa_xg < 1.0
    assert kappa_poisson == pytest.approx(0.071158 / (1 / math.sqrt(225)), rel=1e-6)


# --- 3. Monotonicite ----------------------------------------------------------


def test_higher_power_target_requires_at_least_as_large_n(power_module) -> None:
    n80 = power_module.n_needed_naive_fisher_z(0.15, 0.80)
    n90 = power_module.n_needed_naive_fisher_z(0.15, 0.90)
    assert n90 >= n80


def test_larger_effect_requires_at_most_as_large_n(power_module) -> None:
    n_small_effect = power_module.n_needed_naive_fisher_z(0.10, 0.80)
    n_large_effect = power_module.n_needed_naive_fisher_z(0.30, 0.80)
    assert n_large_effect <= n_small_effect


def test_higher_kappa_requires_at_least_as_large_dyadic_n(power_module) -> None:
    out_low_kappa = power_module.n_needed_dyadic_extrapolated(0.15, 0.80, se_r_dyadic=0.03)
    out_high_kappa = power_module.n_needed_dyadic_extrapolated(0.15, 0.80, se_r_dyadic=0.15)
    assert out_high_kappa["kappa"] > out_low_kappa["kappa"]
    assert out_high_kappa["n_dyadic_extrapolated"] >= out_low_kappa["n_dyadic_extrapolated"]


def test_more_seasons_target_n_requires_monotonic_season_count(power_module) -> None:
    s1 = power_module.seasons_needed(300)
    s2 = power_module.seasons_needed(500)
    assert s2 >= s1


# --- 4. Valeurs reelles deja validees -----------------------------------------


def test_reference_results_constants_match_already_validated_values(power_module) -> None:
    ref = power_module.REFERENCE_RESULTS
    assert ref["poisson_simple"]["se_b"] == pytest.approx(0.378961)
    assert ref["poisson_simple"]["se_r"] == pytest.approx(0.071158)
    assert ref["xg_model"]["se_b"] == pytest.approx(0.316312)
    assert ref["xg_model"]["se_r"] == pytest.approx(0.051121)
    assert ref["poisson_simple"]["df"] == 22
    assert ref["xg_model"]["df"] == 22


def test_current_power_uses_injected_reference_values_correctly(power_module) -> None:
    ref = power_module.REFERENCE_RESULTS
    # Puissance actuelle pour detecter un effet de reference Liga (0.1460,
    # poisson_simple, deja documente en PL-E15-POWER) avec le se_r reel.
    power = power_module.current_power_direct_wald(0.1460, ref["poisson_simple"]["se_r"], df=ref["poisson_simple"]["df"])
    assert 0.0 < power < 1.0


# --- 5. Garde-fou donnees : aucune nouvelle saison ----------------------------


def test_module_never_reads_any_match_or_season_data(power_module) -> None:
    source = inspect.getsource(power_module)
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    forbidden = {"match_id", "season", "kickoff_utc", "home_team_id", "away_team_id", "_load_records"}
    assert names.isdisjoint(forbidden)
    # Aucun import de pandas/numpy de chargement de donnees, aucun acces fichier.
    import_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "pandas" not in import_names
    assert "pathlib" not in import_names


def test_current_n_constant_is_228_and_never_overridden_by_data(power_module) -> None:
    assert power_module.CURRENT_N == 228
    assert power_module.PER_SEASON == 114


# --- 6. Entrees invalides ------------------------------------------------------


def test_negative_or_zero_se_raises(power_module) -> None:
    with pytest.raises(ValueError):
        power_module.current_power_direct_wald(0.15, 0.0, df=22)
    with pytest.raises(ValueError):
        power_module.current_power_direct_wald(0.15, -0.01, df=22)


def test_power_target_outside_open_unit_interval_raises(power_module) -> None:
    with pytest.raises(ValueError):
        power_module.n_needed_naive_fisher_z(0.15, 0.0)
    with pytest.raises(ValueError):
        power_module.n_needed_naive_fisher_z(0.15, 1.0)
    with pytest.raises(ValueError):
        power_module.n_needed_naive_fisher_z(0.15, 1.5)


def test_undefined_effect_raises(power_module) -> None:
    with pytest.raises(ValueError):
        power_module.n_needed_naive_fisher_z(0.0, 0.80)
    with pytest.raises(ValueError):
        power_module.n_needed_naive_fisher_z(float("nan"), 0.80)


def test_invalid_sample_size_raises(power_module) -> None:
    with pytest.raises(ValueError):
        power_module.seasons_needed(300, current_n=2)
    with pytest.raises(ValueError):
        power_module.naive_fisher_z_se(2)
