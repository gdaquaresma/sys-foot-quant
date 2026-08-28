"""Garde-fous anti-fuite pour E4 (discrimination de l'esperance totale de
buts, scripts/run_stage12_e4_expected_goals_discrimination.py) :

- le script ne reimplemente AUCUN calcul de prediction (ni PoissonModel,
  ni XGModel, ni DixonColesModel importes) - il reutilise exclusivement
  les colonnes ``{model}_lambda_plus_mu`` deja produites et deja testees
  point-in-time par run_stage8 ;
- les frontieres de tranches/quintiles ne dependent jamais du resultat
  reel (deja verifie unitairement, reconfirme ici sur un cas structurel) ;
- l'ensemble de calibration (30%, reutilise du decoupage E2/E3) n'est
  utilise pour AUCUN calcul dans E4 (seul le TEST sert a l'evaluation) ;
- non-regression des frontieres fixes du protocole."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage12_e4_expected_goals_discrimination.py"
)
_STAGE8_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage8_diagnostic_total_goals_over_under.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e4_module():
    return _load(_SCRIPT_PATH, "run_stage12_e4_expected_goals_discrimination")


def test_script_never_imports_or_refits_a_model(e4_module) -> None:
    """E4 doit se contenter des colonnes deja produites par le stage8 -
    aucune reimplementation locale de PoissonModel/XGModel/DixonColesModel
    (qui contournerait le mecanisme point-in-time deja teste)."""
    source = Path(_SCRIPT_PATH).read_text()
    for forbidden in ("PoissonModel", "XGModel", "DixonColesModel", "predict_lambda_mu", "score_matrix"):
        assert forbidden not in source, f"E4 ne doit pas reimplementer/reimporter '{forbidden}'."


def test_expected_total_goals_column_is_the_exact_stage8_column(e4_module) -> None:
    """La variable etudiee doit provenir EXACTEMENT de
    ``{model}_lambda_plus_mu`` (colonne stage8 deja testee point-in-time),
    jamais d'une combinaison inventee localement."""
    source = Path(_SCRIPT_PATH).read_text()
    assert 'f"{model}_lambda_plus_mu"' in source


def test_calibration_split_is_never_used_by_e4(e4_module) -> None:
    """``build_calibration_and_test_sets`` renvoie (calibration_df,
    test_df) - E4 doit ignorer le premier element (aucun ajustement n'est
    necessaire pour cette analyse) : verifie que le nom de variable
    correspondant est bien '_' (jete), jamais reutilise ensuite."""
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    found_assignment = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            func_name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if func_name == "build_calibration_and_test_sets":
                found_assignment = True
                targets = node.targets[0]
                assert isinstance(targets, ast.Tuple)
                first_target = targets.elts[0]
                assert isinstance(first_target, ast.Name) and first_target.id == "_", (
                    "L'ensemble de calibration doit etre explicitement jete ('_'), jamais nomme "
                    "et reutilise dans E4 (aucun ajustement necessaire pour cette analyse)."
                )
    assert found_assignment, "build_calibration_and_test_sets doit etre appele dans E4."


def test_quintile_boundaries_do_not_depend_on_actual_outcome_real_shape(e4_module) -> None:
    rng = np.random.default_rng(0)
    expected = rng.uniform(0.5, 5.0, size=800)
    actual_1 = rng.poisson(2.5, size=800).astype(float)
    actual_2 = rng.poisson(2.5, size=800).astype(float)  # tirage independant different
    t1 = e4_module.quintile_table(expected, actual_1)
    t2 = e4_module.quintile_table(expected, actual_2)
    assert list(t1["n"]) == list(t2["n"])
    assert np.allclose(t1["predit_moy"].to_numpy(), t2["predit_moy"].to_numpy())


def test_fixed_bins_match_protocol_exactly(e4_module) -> None:
    assert e4_module._FIXED_BIN_LABELS == ["<1.5", "1.5-2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", "3.5+"]
    assert e4_module._FIXED_BIN_EDGES == [-np.inf, 1.5, 2.0, 2.5, 3.0, 3.5, np.inf]


@pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "research" / "xg_feasibility" / "runs").exists(),
    reason="Fichiers Understat reels non presents.",
)
def test_real_corpus_expected_goals_are_strictly_positive_and_finite() -> None:
    """Non-regression minimale sur le corpus reel : lambda_home+lambda_away
    doit toujours etre fini et strictement positif (aucune valeur
    aberrante issue d'une mauvaise reutilisation des colonnes stage8)."""
    stage8 = _load(_STAGE8_PATH, "run_stage8_diagnostic_total_goals_over_under")
    df = stage8.build_total_goals_dataframe()
    for model in ("poisson_simple", "xg_model"):
        col = df[f"{model}_lambda_plus_mu"].dropna()
        assert (col > 0).all()
        assert np.isfinite(col).all()
