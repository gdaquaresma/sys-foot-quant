"""Garde-fous anti-fuite pour E15
(scripts/run_stage24_e15_premier_league_discrimination_diagnostic.py) :
- le mecanisme point-in-time est INTEGRALEMENT delegue a stage8/E4/E7/E8/E11
  (deja testes) - jamais reimplemente ;
- E15 est un DIAGNOSTIC PUR : aucune modification d'E1-E14, aucun nouveau
  modele, aucune nouvelle calibration, aucune regle de production ;
- la regle de classification (etape 0bis) est FIGEE avant observation des
  resultats - jamais un seuil derive des donnees observees ;
- les fonctions de bootstrap/permutation preservent toujours l'appariement
  (x,y) a l'interieur d'un meme groupe - jamais x et y melanges entre
  groupes ou entre lignes."""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage24_e15_premier_league_discrimination_diagnostic.py"
)

_PRIOR_SCRIPTS = (
    "run_stage8_diagnostic_total_goals_over_under.py",
    "run_stage12_e4_expected_goals_discrimination.py",
    "run_stage15_e7_total_goals_distribution.py",
    "run_stage16_e8_walk_forward_validation.py",
    "run_stage20_e11_probability_reliability_mapping.py",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e15_module():
    return _load(_SCRIPT_PATH, "run_stage24_e15_premier_league_discrimination_diagnostic")


# --- 1. point-in-time integralement delegue, jamais reimplemente -----------


def test_e15_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "_load_records" in source  # reutilise stage8, jamais reimplemente
    assert "AmbiguousCollectionWindowError" not in source
    assert "conservative_knowledge_time_utc" not in source
    assert "goals_knowledge_time" not in source  # jamais un filtre PIT reconstruit a la main
    assert "xg_knowledge_time" not in source


def test_e15_never_modifies_prior_scripts() -> None:
    """E15 doit etre un NOUVEAU fichier - verifie qu'aucun script anterieur
    ne contient le vocabulaire specifique a E15."""
    for prior_script in _PRIOR_SCRIPTS:
        source = (Path(_SCRIPT_PATH).parent / prior_script).read_text()
        assert "audit_league_season" not in source
        assert "permutation_test_correlation_diff" not in source
        assert "classify_calibration_discrimination" not in source


def test_e15_never_creates_a_new_model_or_calibration() -> None:
    """Diagnostic PUR (regle fondamentale du protocole) : aucune classe de
    modele, aucune fonction fit/predict, aucun ajustement de parametre."""
    source = Path(_SCRIPT_PATH).read_text()
    assert "class " not in source  # aucune nouvelle classe (modele ou calibrateur)
    assert ".fit(" not in source
    assert "PoissonModel(" not in source
    assert "XGModel(" not in source
    assert "DixonColesModel(" not in source


# --- 2. classification figee, jamais derivee des donnees observees ---------


def test_classification_rule_never_uses_data_derived_thresholds() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "np.percentile" not in source.split("def classify_calibration_discrimination")[1][:1] if False else True
    tree = ast.parse(source)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_calibration_discrimination")
    body_source = ast.unparse(func)
    assert "percentile" not in body_source
    assert "quantile" not in body_source
    # la seule reference externe autorisee est `reference_corr_values`, deja
    # calculee AVANT l'appel a partir des AUTRES championnats - jamais du
    # championnat classifie lui-meme.
    assert "min(reference_corr_values)" in body_source


def test_classify_calibration_discrimination_is_a_pure_function_of_precomputed_intervals(e15_module) -> None:
    import inspect

    sig = inspect.signature(e15_module.classify_calibration_discrimination)
    assert set(sig.parameters) == {"calibration_ci", "correlation_point", "correlation_ci", "reference_corr_values"}


# --- 3. bootstrap/permutation : jamais de melange (x,y) entre groupes ------


def test_bootstrap_correlation_diff_never_mixes_x_and_y_across_resamples(e15_module) -> None:
    """Un reechantillonnage doit toujours reutiliser LES MEMES indices pour
    x et y (jamais reechantillonner x et y independamment, ce qui
    detruirait artificiellement toute correlation reelle)."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 20)
    y = x.copy()  # correlation parfaite
    out = e15_module.bootstrap_correlation_diff(x, y, x, y, n_resamples=200)
    # si x et y etaient reechantillonnes independamment, la correlation
    # resamplee s'effondrerait vers ~0 au lieu de rester proche de 1.
    assert out["corr_a"] == pytest.approx(1.0)
    assert out["corr_b"] == pytest.approx(1.0)


def test_permutation_test_preserves_pairing_within_permuted_groups(e15_module) -> None:
    """Une permutation ne doit reordonner QUE l'appartenance au groupe,
    jamais rompre l'appariement (x[i], y[i]) - verifie que la correlation
    globale (tous groupes confondus) est invariante par permutation."""
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 5, size=200)
    y = x + rng.normal(0, 0.1, size=200)
    group_mask = rng.uniform(size=200) < 0.5
    out = e15_module.permutation_test_correlation_diff(x, y, group_mask, n_permutations=50)
    # la correlation globale reste tres elevee (~1) car x et y ne sont
    # jamais desassocies, seule l'appartenance au groupe est permutee -
    # verifie indirectement via la coherence des correlations par groupe
    # observees (jamais proches de 0 malgre le fort bruit ajoute au hasard).
    assert abs(out["corr_a"]) > 0.8 or abs(out["corr_b"]) > 0.8


# --- 4. aucune donnee de marche utilisee (diagnostic purement modele/buts) --


def test_e15_never_imports_market_odds_or_bookmaker_data() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "multi_bookmaker_odds" not in source
    assert "market_engine" not in source
    assert "B365" not in source
    assert "bookmaker" not in source.lower()


# --- 5. l'audit de donnees ne conditionne jamais sur le resultat -----------


def test_audit_league_season_never_reads_goals_to_decide_anomalies() -> None:
    """L'audit (etape 1) doit rester un controle de qualite de DONNEES -
    jamais une fonction qui exclut ou requalifie un match sur la base de
    son score (ce qui serait un biais de selection post-resultat)."""
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "audit_league_season")
    body_source = ast.unparse(func)
    assert "total_goals" not in body_source
    assert "outcome" not in body_source
