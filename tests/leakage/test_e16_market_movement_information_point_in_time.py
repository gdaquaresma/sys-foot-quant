"""Garde-fous anti-fuite pour E16
(scripts/run_stage25_e16_market_movement_information.py) :
- le mecanisme point-in-time (appariement, decision_time) est
  INTEGRALEMENT delegue a matching.py/time_resolution.py (deja testes) -
  jamais reimplemente ;
- la cloture n'est JAMAIS utilisee comme feature d'une decision a
  l'ouverture - seuls les modeles O (ouverture seule) et O+M
  (ouverture+mouvement, jamais la cloture elle-meme) sont presentes comme
  potentiellement "decision-usable" ; C et O+C sont explicitement
  RETROSPECTIFS ;
- toute regression walk-forward est ajustee EXCLUSIVEMENT sur des matchs
  strictement anterieurs au match evalue (fenetre expansive, jamais un
  ajustement poole une seule fois sur tout le corpus) ;
- les tranches d'amplitude et le perimetre des hypotheses primaires sont
  FIGES, jamais recalcules a partir des donnees observees ;
- E1-E15 ne sont jamais modifies (aucune ecriture dans un script existant),
  et aucun modele de buts (poisson_simple/dixon_coles/xg_model) n'est
  cree, importe ou entraine ici."""

from __future__ import annotations

import ast
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage25_e16_market_movement_information.py"

_PRIOR_SCRIPTS = (
    "run_stage15_e7_total_goals_distribution.py",
    "run_stage16_e8_walk_forward_validation.py",
    "run_stage18_e9_multi_bookmaker_market_layer.py",
    "run_stage20_e11_probability_reliability_mapping.py",
    "run_stage23_e14_local_recalibration_over25.py",
    "run_stage24_e15_premier_league_discrimination_diagnostic.py",
)

_PRIOR_MODULES = (
    Path(__file__).resolve().parent.parent.parent / "src" / "sys_foot_quant" / "data_engine" / "market_odds" / "multi_bookmaker_odds.py",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e16_module():
    return _load(_SCRIPT_PATH, "run_stage25_e16_market_movement_information")


def _dt(day: int) -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)


# --- 1. point-in-time integralement delegue, jamais reimplemente -----------


def test_e16_never_reimplements_point_in_time_filtering() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "build_understat_keys" in source
    assert "match_league_season" in source
    assert "conservative_knowledge_time_utc" in source  # reutilise via import direct, jamais reimplemente
    tree = ast.parse(source)
    func_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "conservative_knowledge_time_utc" not in func_names  # jamais REDEFINI localement
    assert "match_league_season" not in func_names


def test_e16_never_modifies_prior_scripts_or_modules() -> None:
    for prior_script in _PRIOR_SCRIPTS:
        source = (Path(_SCRIPT_PATH).parent / prior_script).read_text()
        assert "MovementMatchRecord" not in source
        assert "walk_forward_logistic" not in source
        assert "compute_market_movement" not in source
    for prior_module in _PRIOR_MODULES:
        source = prior_module.read_text()
        assert "MovementMatchRecord" not in source
        assert "b365_close" not in source  # E9 n'a jamais ete etendu a la cloture


def test_e16_never_creates_or_trains_a_goals_model() -> None:
    """Protocole explicite : etudier le marche INDEPENDAMMENT du modele -
    aucun PoissonModel/DixonColesModel/XGModel importe ou instancie."""
    source = Path(_SCRIPT_PATH).read_text()
    assert "PoissonModel" not in source
    assert "XGModel" not in source
    assert "DixonColesModel" not in source
    assert "score_matrix" not in source


# --- 2. la cloture n'est jamais un feature de decision a l'ouverture --------


def test_model_o_never_reads_any_closing_field(e16_module) -> None:
    """Le modele O (ouverture seule, le seul cense representer une
    decision reellement prise a l'ouverture) ne doit JAMAIS referencer
    prob_close ou movement dans sa construction."""
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_prediction_series")
    body_source = ast.unparse(func)
    # "O" est directement `df["prob_open_norm"].to_numpy()` - jamais derive de prob_close/movement
    assert '"O": p_open' in body_source or "'O': p_open" in body_source


def test_retrospective_models_are_explicitly_labeled_in_source() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "RETROSPECTIF" in source
    assert "jamais decision-usable" in source or "RETROSPECTIF UNIQUEMENT" in source


def test_movement_dataset_never_uses_closing_to_exclude_a_match(e16_module) -> None:
    """Seule l'ouverture B365 1X2 conditionne l'inclusion d'un match -
    verifie par inspection statique qu'AUCUN `continue` (exclusion) de
    `build_movement_dataset` ne depend d'un champ de cloture - les
    references a `has_complete_close_*` n'apparaissent QUE dans la
    construction de champs (valeur None si incomplet), jamais dans une
    condition de `if` suivie d'un `continue`. Comportement confirme
    directement par `test_build_movement_dataset_missing_closing_is_none_never_excludes_match`
    (tests/unit)."""
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_movement_dataset")
    for node in ast.walk(func):
        if isinstance(node, ast.If) and any(isinstance(s, ast.Continue) for s in node.body):
            condition_source = ast.unparse(node.test)
            assert "close" not in condition_source.lower()
    assert "has_complete_odds" in ast.unparse(func)  # seule condition d'exclusion sur les cotes (ouverture B365)


# --- 3. walk-forward strict : jamais le futur --------------------------------


def test_walk_forward_logistic_uses_strict_slicing_never_full_corpus() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "walk_forward_logistic")
    body_source = ast.unparse(func)
    assert "X_all[:i]" in body_source
    assert "y_all[:i]" in body_source


def test_walk_forward_logistic_prediction_uses_only_current_row(e16_module) -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "walk_forward_logistic")
    body_source = ast.unparse(func)
    assert "X_all[i : i + 1]" in body_source or "X_all[i:i + 1]" in body_source or "X_all[i:i+1]" in body_source


def test_walk_forward_logistic_moving_a_row_to_the_future_never_changes_earlier_predictions(e16_module) -> None:
    """Balayage : deplacer une ligne DANS LE FUTUR (au-dela d'un match deja
    evalue) ne peut jamais influencer les predictions des matchs
    anterieurs - propriete structurelle du tri chronologique strict."""
    rng = np.random.default_rng(0)
    n = 30
    mv = rng.uniform(-0.05, 0.05, n)
    y = rng.binomial(1, 0.5, n).astype(float)
    df = pd.DataFrame({"decision_time": [_dt(d) for d in range(1, n + 1)], "movement_prob_norm": mv, "outcome": y})

    def cov(d):
        X = np.column_stack([np.ones(len(d)), d["movement_prob_norm"].to_numpy()])
        return X, d["outcome"].to_numpy()

    preds_before = e16_module.walk_forward_logistic(df, cov, min_train=10)

    df_shuffled_tail = df.copy()
    # deplace la derniere ligne encore plus loin dans le futur (ne change
    # pas son RANG chronologique, seulement sa date absolue)
    df_shuffled_tail.loc[n - 1, "decision_time"] = _dt(10_000)
    preds_after = e16_module.walk_forward_logistic(df_shuffled_tail, cov, min_train=10)

    np.testing.assert_allclose(preds_before[:-1], preds_after[:-1])


# --- 4. tranches et hypotheses primaires figees, jamais recalculees ---------


def test_amplitude_edges_are_frozen_constants(e16_module) -> None:
    assert e16_module._AMPLITUDE_EDGES == [0.0, 0.01, 0.03, 0.06, np.inf]
    assert e16_module._MIN_TRAIN == 30


def test_classification_functions_never_use_data_derived_thresholds() -> None:
    source = Path(_SCRIPT_PATH).read_text()
    assert "np.percentile" not in source
    assert "np.quantile" not in source
    assert ".quantile(" not in source


def test_classify_amplitude_never_uses_outcome_in_source() -> None:
    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_amplitude")
    body_source = ast.unparse(func)
    assert "outcome" not in body_source


def test_holm_bonferroni_never_depends_on_which_hypotheses_are_primary() -> None:
    """`holm_bonferroni` est une fonction PURE et generique - le choix des
    4 hypotheses primaires est fait dans `main()` (visible et figee dans
    le docstring), jamais a l'interieur de la fonction de correction
    elle-meme."""
    import inspect

    tree = ast.parse(Path(_SCRIPT_PATH).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "holm_bonferroni")
    sig_params = [a.arg for a in func.args.args]
    assert sig_params == ["p_values", "alpha"]
