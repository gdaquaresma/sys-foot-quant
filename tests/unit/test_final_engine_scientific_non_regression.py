"""Tests de non-regression SCIENTIFIQUE pour le moteur final (Etape 17,
PHASE B) - garantissent que E1-E16 restent des faits historiques figes et
que le moteur ne transforme jamais silencieusement une hypothese rejetee
ou non validee en source d'edge :

- E7/E8 reste inchange (portage verbatim verifie par identite numerique) ;
- E14 n'est jamais appliquee (aucune isotonic/logistic recalibration) ;
- aucun coefficient Premier League n'est applique (probabilites
  identiques a Liga/Ligue 1 pour les memes lambda/mu) ;
- aucune donnee de cloture n'entre dans la decision d'ouverture ;
- aucun mouvement de marche n'entre comme feature ;
- aucun ensemble de modeles n'est utilise (poisson_simple/dixon_coles/
  xg_model restent trois calculs strictement independants) ;
- aucune ponderation apprise entre modeles ;
- aucune decision ne contourne les scientific gates.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from sys_foot_quant.final_engine import prediction
from sys_foot_quant.final_engine.decision import decide
from sys_foot_quant.final_engine.orchestrator import run_match_decision
from sys_foot_quant.final_engine.types import GateResult
from sys_foot_quant.calibration_engine import scalar_correction

_FINAL_ENGINE_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "sys_foot_quant" / "final_engine"
_E8_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "run_stage16_e8_walk_forward_validation.py"
)


def _load_e8_script():
    spec = importlib.util.spec_from_file_location("run_stage16_e8_walk_forward_validation", _E8_SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


e8 = _load_e8_script()

_KICKOFF = datetime(2025, 1, 8, 20, 0, tzinfo=timezone.utc)  # mercredi


def _goals_df(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        [{"home_team_id": i % 4, "away_team_id": (i + 1) % 4, "home_goals": 1, "away_goals": 1} for i in range(n)]
    )


def _code_only_source(path: Path) -> str:
    """Retourne le code source d'un module SANS ses docstrings (module,
    classe, fonction) - evite les faux positifs quand un docstring
    explique en prose ce que le module NE fait PAS (ex. "aucune isotonic
    calibration ici")."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body[0].value.value = ""
    return ast.unparse(tree)


def _calibration_df(n: int, kickoff: datetime, lam: float = 1.4, mu: float = 1.1, total: float = 2.7) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "decision_time": [kickoff - timedelta(days=n - i, hours=-2) for i in range(n)],
            "poisson_simple_lambda": [lam] * n,
            "poisson_simple_mu": [mu] * n,
            "total_goals": [total] * n,
        }
    )


# --- E7/E8 reste inchange -----------------------------------------------------


def test_scalar_correction_produces_numerically_identical_results_to_e8_script() -> None:
    """Le portage vers src/ (docs/final_engine_specification.md section 1)
    ne doit produire AUCUN ecart numerique avec le script E8 original."""
    n = 40
    df = pd.DataFrame(
        {
            "decision_time": [_KICKOFF - timedelta(days=n - i) for i in range(n)],
            "poisson_simple_lambda": [1.3 + 0.01 * i for i in range(n)],
            "poisson_simple_mu": [1.1] * n,
            "total_goals": [2.6] * n,
        }
    )
    as_of = _KICKOFF
    c_ported, n_ported = scalar_correction.fit_scale_correction_as_of(df, "poisson_simple", as_of)
    c_original, n_original = e8.fit_scale_correction_as_of(df, "poisson_simple", as_of)
    assert c_ported == c_original
    assert n_ported == n_original


def test_min_calibration_matches_constant_matches_e8_original() -> None:
    assert scalar_correction.MIN_CALIBRATION_MATCHES_FOR_SCALE == e8._MIN_CALIBRATION_MATCHES_FOR_SCALE == 30


# --- E14 n'est jamais appliquee ------------------------------------------------


def test_no_final_engine_module_imports_isotonic_or_logistic_recalibration() -> None:
    """E14 est NON VALIDEE - aucune isotonic/logistic recalibration locale
    ne doit jamais entrer dans le moteur final."""
    forbidden_substrings = ("isotonic", "logistic_recalibration", "fit_logistic_recalibration", "apply_isotonic_recalibration")
    for module_path in _FINAL_ENGINE_DIR.glob("*.py"):
        source = _code_only_source(module_path).lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in source, f"{module_path} reference '{forbidden}' - E14 ne doit jamais etre integree"


def test_probability_in_biased_zone_is_never_numerically_altered() -> None:
    """Reproduit le calcul brut (sans passer par le gate) et verifie que
    la probabilite dans la sortie du moteur est EXACTEMENT celle derivee
    de la matrice corrigee E7/E8 - aucune transformation supplementaire."""
    from sys_foot_quant.final_engine.calibration import calibrate_prediction
    from sys_foot_quant.final_engine.types import ModelPrediction

    pred = ModelPrediction(model="poisson_simple", lam=1.0, mu=1.0, rho=None, n_train_matches=40)
    df = _calibration_df(40, _KICKOFF, lam=1.0, mu=1.0, total=3.3)  # scale_c=1.65 -> zone biaisee
    result = calibrate_prediction(pred, df, as_of_time=_KICKOFF)
    assert 0.6 <= result.probabilities[2.5] < 0.7

    output = run_match_decision(
        match_id="m1",
        competition="Liga",
        season="2025/26",
        kickoff_utc=_KICKOFF,
        home_team_id=0,
        away_team_id=1,
        goals_train_df=_goals_df(40),
        xg_train_df=None,
        calibration_df_by_model={"poisson_simple": df},
        market_odds_over_2_5=1.9,
        market_odds_under_2_5=2.0,
    )
    assert output.calibration["poisson_simple"].probabilities[2.5] == result.probabilities[2.5]


# --- aucun coefficient Premier League ------------------------------------------


def test_premier_league_probabilities_are_computed_identically_to_other_leagues() -> None:
    """E15 : aucun coefficient PL - les memes (lambda, mu, scale_c)
    doivent produire EXACTEMENT la meme probabilite, quel que soit le
    championnat. Seule la QUALIFICATION (discrimination_status) differe."""
    kwargs = dict(
        match_id="m1",
        season="2025/26",
        kickoff_utc=_KICKOFF,
        home_team_id=0,
        away_team_id=1,
        goals_train_df=_goals_df(40),
        xg_train_df=None,
        calibration_df_by_model={"poisson_simple": _calibration_df(40, _KICKOFF)},
        market_odds_over_2_5=1.9,
        market_odds_under_2_5=2.0,
    )
    output_pl = run_match_decision(competition="Premier League", **kwargs)
    output_liga = run_match_decision(competition="Liga", **kwargs)

    assert output_pl.calibration["poisson_simple"].probabilities == output_liga.calibration["poisson_simple"].probabilities
    assert output_pl.pricing["poisson_simple"].fair_price == output_liga.pricing["poisson_simple"].fair_price
    assert output_pl.qualification.discrimination_status != output_liga.qualification.discrimination_status


def test_reference_tables_module_never_reads_competition_into_lambda_mu_computation() -> None:
    """Verification structurelle : ``prediction.py``/``calibration.py`` ne
    prennent jamais ``competition`` en parametre - seul ``gates.py``/
    ``orchestrator.py`` (Niveau E) en ont connaissance."""
    assert "competition" not in inspect.signature(prediction.predict_match).parameters
    from sys_foot_quant.final_engine import calibration as calibration_module

    assert "competition" not in inspect.signature(calibration_module.calibrate_prediction).parameters


# --- aucune donnee de cloture / mouvement --------------------------------------


def test_no_final_engine_module_references_market_movement_primitives() -> None:
    """E16 : le mouvement de marche n'est jamais une feature du moteur
    final - aucune reference a un calcul de mouvement ouverture/cloture."""
    forbidden_substrings = ("movement", "mouvement_prob", "b365c", "psc", "wch", "lbch")
    for module_path in _FINAL_ENGINE_DIR.glob("*.py"):
        source = _code_only_source(module_path).lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in source, f"{module_path} reference '{forbidden}' - E16 ne doit jamais etre integree"


# --- aucun ensemble, aucune ponderation apprise --------------------------------


def test_no_final_engine_module_computes_a_weighted_average_across_models() -> None:
    """HYPOTHESE FUTURE non integree (docs/research_synthesis_e1_e16.md
    section 8) : aucune moyenne ponderee, aucun vote, aucun apprentissage
    de poids entre poisson_simple/dixon_coles/xg_model."""
    forbidden_substrings = ("ensemble", "weighted_average", "model_weight", "blend")
    for module_path in _FINAL_ENGINE_DIR.glob("*.py"):
        source = _code_only_source(module_path).lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in source, f"{module_path} reference '{forbidden}' - aucun ensemble non valide"


def _rhs_of_subscript_assignment(func: ast.FunctionDef, key: str) -> str:
    """Retourne le code de l'expression assignee a ``predictions[key]``
    (jamais tout le bloc englobant, qui peut legitimement contenir
    d'autres calculs a cote - seule l'expression EFFECTIVEMENT assignee
    importe pour verifier une dependance)."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "predictions"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == key
        ):
            return ast.unparse(node.value)
    raise AssertionError(f"aucune assignation predictions[{key!r}] trouvee")


def test_control_models_never_feed_into_primary_model_prediction() -> None:
    """Verification par AST : l'expression assignee a
    ``predictions["poisson_simple"]`` ne reference jamais une variable ou
    une classe liee a ``dixon_coles``/``xg_model`` (calculs strictement
    independants, jamais de combinaison)."""
    tree = ast.parse(Path(inspect.getfile(prediction)).read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "predict_match")
    poisson_rhs = _rhs_of_subscript_assignment(func, "poisson_simple")
    assert "xg_model" not in poisson_rhs.lower()
    assert "dixon_coles" not in poisson_rhs.lower()
    assert "DixonColesModel" not in poisson_rhs
    assert "XGModel" not in poisson_rhs


# --- aucune decision ne contourne les scientific gates -------------------------


def test_decide_never_returns_bet_when_any_scientific_gate_is_triggered() -> None:
    def _gate(name: str, triggered: bool) -> GateResult:
        return GateResult(name=name, triggered=triggered, reason="r", metric="m", observed_value=None, threshold=None, failure_code="CODE")

    for i in range(4):
        scientific = [_gate(f"s{j}", j == i) for j in range(4)]
        result = decide(scientific, [])
        assert result.decision == "NO_BET"


def test_decide_never_returns_bet_when_any_operational_gate_is_triggered() -> None:
    def _gate(name: str, triggered: bool) -> GateResult:
        return GateResult(name=name, triggered=triggered, reason="r", metric="m", observed_value=None, threshold=None, failure_code="CODE")

    result = decide([], [_gate("op", True)])
    assert result.decision == "NO_BET"


def test_mvp_default_thresholds_can_never_reach_bet_because_edge_threshold_is_unset() -> None:
    """Consequence directe de la section 13/19 de la specification : avec
    la configuration operationnelle PAR DEFAUT (min_edge_threshold=None),
    le moteur ne peut jamais emettre BET, quel que soit le reste."""
    output = run_match_decision(
        match_id="m1",
        competition="Liga",
        season="2025/26",
        kickoff_utc=_KICKOFF,
        home_team_id=0,
        away_team_id=1,
        goals_train_df=_goals_df(40),
        xg_train_df=None,
        calibration_df_by_model={"poisson_simple": _calibration_df(40, _KICKOFF)},
        market_odds_over_2_5=1.9,
        market_odds_under_2_5=2.0,
    )
    assert output.decision.decision == "NO_BET"
