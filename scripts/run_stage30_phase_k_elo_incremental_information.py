"""Phase K - l'ecart de rating Elo pre-match (ClubElo) apporte-t-il une
information PREDICTIVE INCREMENTALE sur Over/Under 2.5, au-dela de ce que
le moteur actuel (`poisson_simple` + correction E7/E8) possede deja,
APRES recalibration du modele de base ?

Experience DIAGNOSTIQUE UNIQUE (docs/elo_experiment_specification.md) -
PAS une construction de modele de production. Ne modifie AUCUN modele
existant, AUCUNE correction E7/E8/E14/E15/E16, AUCUN gate du moteur
final, N'ACTIVE PAS `BET`, NE FIXE PAS `min_edge_threshold`.

====================================================================
BLOCAGE OPERATIONNEL CONSTATE (docs/elo_experiment_specification.md
section 0bis/16) - A LIRE AVANT TOUTE CHOSE
====================================================================
Cet environnement d'execution ne peut PAS atteindre `clubelo.com` ni
`api.clubelo.com` (bloque par la politique de sortie reseau de la
session - verifie directement, jamais contourne). Les fonctions
ci-dessous qui chargeraient des fichiers ClubElo REELS
(`load_all_elo_records`) supposent des fichiers deja presents sous
`research/market_odds/clubelo/runs/` (meme convention que Football-Data)
- CES FICHIERS N'EXISTENT PAS a ce jour. `main()` NE DOIT PAS etre
execute tant que ces fichiers ne sont pas obtenus ET que le mapping
`elo_team_mapping.py` n'a pas ete verifie a la main (
`MAPPING_VERIFIED_AGAINST_REAL_DATA=True`). Toute tentative d'execution
reelle sans cela echoue explicitement (`EloMappingUnverifiedError` ou
`FileNotFoundError`), jamais silencieusement.

====================================================================
MODELES A/B/C/D (figes, docs/elo_experiment_specification.md section 6)
====================================================================
    A : p_A = calibrate_prediction(poisson_simple)              - 0 param
    B : p_B = sigmoid(a0 + 1*logit(p_A) + c*elo_diff)           - offset, 2 param (a0, c)
    C : p_C = sigmoid(a + b*logit(p_A))                         - 2 param (a, b) - CONTROLE
    D : p_D = sigmoid(a + b*logit(p_A) + c*elo_diff)            - 3 param (a, b, c) - TEST

Test principal (docs/elo_experiment_specification.md section 9) :
`paired_bootstrap_test` sur Brier(D) - Brier(C), population VALIDATION+TEST
(split 40/30/30 REUTILISE de `run_stage10_over_under_recalibration.
split_burn_in_calibration_test`, INCHANGE), avec VALIDATION et TEST
rapportes separement comme controle de robustesse temporelle obligatoire.

Usage (une fois les fichiers ClubElo reels obtenus et le mapping verifie) :
    python scripts/run_stage30_phase_k_elo_incremental_information.py
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.data_engine.market_odds.elo_join import build_elo_dataset  # noqa: E402
from sys_foot_quant.data_engine.market_odds.elo_ratings import EloRatingRow, parse_clubelo_csv_rows  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.final_engine.calibration import calibrate_prediction  # noqa: E402
from sys_foot_quant.final_engine.types import ModelPrediction  # noqa: E402

_PRIMARY_MODEL = "poisson_simple"
_MIN_TRAIN_LOGISTIC = 30  # E16, REUTILISE - meme convention que Phases F/G/H
_TARGET_THRESHOLD = 2.5  # Over 2.5, DEFAULT_OU_THRESHOLDS - meme cible qu'E11/E14/E16/Phases F/G/H

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FD_DIR = _REPO_ROOT / "research" / "market_odds" / "football_data" / "runs"
_US_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"
_ELO_DIR = _REPO_ROOT / "research" / "market_odds" / "clubelo" / "runs"  # N'EXISTE PAS A CE JOUR - voir docstring

_DATASETS = {
    ("premier_league", "2024_25"): ("E0_2024_25.csv", "epl_2024_datesData.json"),
    ("premier_league", "2025_26"): ("E0_2025_26.csv", "epl_2025_datesData.json"),
    ("ligue1", "2024_25"): ("F1_2024_25.csv", "ligue1_2024_datesData.json"),
    ("ligue1", "2025_26"): ("F1_2025_26.csv", "ligue1_2025_datesData.json"),
    ("liga", "2024_25"): ("SP1_2024_25.csv", "liga_2024_datesData.json"),
    ("liga", "2025_26"): ("SP1_2025_26.csv", "liga_2025_datesData.json"),
}

_STAGE10_PATH = Path(__file__).resolve().parent / "run_stage10_over_under_recalibration.py"
_STAGE15_PATH = Path(__file__).resolve().parent / "run_stage15_e7_total_goals_distribution.py"
_STAGE25_PATH = Path(__file__).resolve().parent / "run_stage25_e16_market_movement_information.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_stage10():
    return _load_module("run_stage10_over_under_recalibration", _STAGE10_PATH)


def _load_e7():
    return _load_module("run_stage15_e7_total_goals_distribution", _STAGE15_PATH)


def _load_e16():
    return _load_module("run_stage25_e16_market_movement_information", _STAGE25_PATH)


# --------------------------------------------------------------------------
# Regression logistique a offset (docs/elo_experiment_specification.md
# section 6) - generalisation MINIMALE de `fit_logistic`/`predict_logistic`
# (E16, INCHANGEES) : le terme `offset` (ici `logit(p_A)`) a un coefficient
# FIXE a 1, jamais reestime - seuls les coefficients de `X` sont libres.
# Si `offset` est un vecteur de zeros, `fit_logistic_with_offset` reproduit
# EXACTEMENT `fit_logistic` (verifie par un test dedie).
# --------------------------------------------------------------------------


def fit_logistic_with_offset(offset: np.ndarray, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    offset = np.asarray(offset, dtype=float)
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)

    def neg_log_lik(beta: np.ndarray) -> float:
        z = offset + X @ beta
        return float(np.mean(np.logaddexp(0.0, -z) * y + np.logaddexp(0.0, z) * (1 - y)))

    beta0 = np.zeros(X.shape[1])
    res = minimize(neg_log_lik, beta0, method="BFGS")
    return res.x


def predict_logistic_with_offset(offset: np.ndarray, beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    offset = np.asarray(offset, dtype=float)
    X = np.asarray(X, dtype=float)
    z = offset + X @ beta
    return 1.0 / (1.0 + np.exp(-z))


def walk_forward_logistic_with_offset(
    offset_all: np.ndarray, X_all: np.ndarray, y_all: np.ndarray, min_train: int = _MIN_TRAIN_LOGISTIC
) -> np.ndarray:
    """Identique en structure a `walk_forward_logistic` (E16, INCHANGEE) :
    pour chaque ligne, ajuste EXCLUSIVEMENT sur les lignes PRECEDENTES
    (deja triees par `decision_time` en amont par l'appelant), jamais la
    ligne elle-meme ni une ligne posterieure."""
    n = len(y_all)
    preds = np.full(n, np.nan)
    for i in range(n):
        if i < min_train:
            continue
        beta = fit_logistic_with_offset(offset_all[:i], X_all[:i], y_all[:i])
        preds[i] = predict_logistic_with_offset(offset_all[i : i + 1], beta, X_all[i : i + 1])[0]
    return preds


# --------------------------------------------------------------------------
# Chargement des donnees Elo reelles - BLOQUE tant que les fichiers
# ClubElo n'existent pas sous `_ELO_DIR` et que le mapping n'est pas
# verifie (voir docstring du module).
# --------------------------------------------------------------------------


def load_all_elo_records() -> dict[str, list]:
    """match_id -> EloMatchRecord, tous championnats/saisons confondus.
    Necessite des fichiers CSV ClubElo reels sous `_ELO_DIR` (un par club,
    ou un fichier consolide - format a fixer une fois les fichiers reels
    obtenus) - N'EXISTENT PAS a ce jour (docstring du module). Leve
    explicitement si absent, jamais un dataset vide silencieux."""
    if not _ELO_DIR.exists():
        raise FileNotFoundError(
            f"{_ELO_DIR} n'existe pas - aucun fichier ClubElo reel disponible dans ce depot "
            "(docs/elo_experiment_specification.md section 0bis : environnement sans acces "
            "reseau a clubelo.com/api.clubelo.com). Execution reelle bloquee."
        )
    raise NotImplementedError(
        "Format de consolidation des fichiers ClubElo reels non encore fixe - a completer "
        "une fois les fichiers obtenus, conformement au protocole (aucune valeur inventee)."
    )


def build_elo_by_club_from_raw(raw_rows_by_club: dict[str, list[dict]]) -> dict[str, list[EloRatingRow]]:
    return {club: parse_clubelo_csv_rows(rows) for club, rows in raw_rows_by_club.items()}


# --------------------------------------------------------------------------
# Split 40/30/30 (Phase D, `split_burn_in_calibration_test`, INCHANGEE) -
# applique par championnat x saison, docs/elo_experiment_specification.md
# section 5.
# --------------------------------------------------------------------------


def tag_burn_in_validation_test(df: pd.DataFrame, stage10_module, stage8_module) -> pd.DataFrame:
    """Ajoute une colonne `split` (`burn_in`/`validation`/`test`) a `df`,
    calculee PAR CHAMPIONNAT x SAISON via `split_burn_in_calibration_test`
    (INCHANGEE). `df` doit deja porter `match_id`/`league`/`season`."""
    validation_ids: set[str] = set()
    test_ids: set[str] = set()
    for season, leagues in stage8_module._SEASONS.items():
        for league in leagues:
            records = stage8_module._load_records(league, season)
            v_ids, t_ids = stage10_module.split_burn_in_calibration_test(records)
            validation_ids |= v_ids
            test_ids |= t_ids

    def _tag(match_id: str) -> str:
        if match_id in validation_ids:
            return "validation"
        if match_id in test_ids:
            return "test"
        return "burn_in"

    out = df.copy()
    out["split"] = out["match_id"].map(_tag)
    return out


# --------------------------------------------------------------------------
# Verdict (docs/elo_experiment_specification.md section 13) - grille
# figee, mecanique, 5 valeurs autorisees uniquement.
# --------------------------------------------------------------------------


def classify_verdict(
    primary_boot: dict, validation_boot: dict, test_boot: dict, scope_boots: list[dict], n_global_pool: int
) -> str:
    if n_global_pool < 30:
        return "DONNEES INSUFFISANTES"

    validation_favorable = validation_boot["ci_high"] < 0.0
    validation_unfavorable = validation_boot["ci_low"] > 0.0
    test_favorable = test_boot["ci_high"] < 0.0
    test_unfavorable = test_boot["ci_low"] > 0.0
    contradiction = (validation_favorable and test_unfavorable) or (validation_unfavorable and test_favorable)

    primary_favorable = primary_boot["ci_high"] < 0.0
    primary_width = primary_boot["ci_high"] - primary_boot["ci_low"]

    if contradiction:
        return "ABSENCE DE PREUVE" if not any(b["ci_low"] > 0.0 for b in scope_boots) else "NON VALIDE"

    if primary_favorable:
        any_scope_inversion = any(b["ci_low"] > 0.0 for b in scope_boots)
        if any_scope_inversion:
            return "NON VALIDE"
        return "VALIDE"

    if primary_width > 0.05:
        return "ABSENCE DE PREUVE"
    return "NON VALIDE"


# --------------------------------------------------------------------------
# main() - NE PAS EXECUTER tant que le blocage operationnel (docstring)
# n'est pas leve.
# --------------------------------------------------------------------------


def main() -> None:
    raise RuntimeError(
        "Execution reelle bloquee (docs/elo_experiment_specification.md section 0bis/16) : "
        "aucun fichier ClubElo reel disponible dans cet environnement (clubelo.com/"
        "api.clubelo.com non accessibles), et le mapping elo_team_mapping.py n'a pas ete "
        "verifie a la main. Ne pas contourner - obtenir les fichiers reels et verifier le "
        "mapping avant de retirer ce garde-fou."
    )


if __name__ == "__main__":
    main()
