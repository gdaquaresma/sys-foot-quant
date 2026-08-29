"""Phase F - les tirs cadres (HST/AST, Football-Data) apportent-ils une
information PREDICTIVE INCREMENTALE sur Over/Under 2.5, au-dela de ce que
le moteur actuel (`poisson_simple` + correction E7/E8) possede deja ?

Experience DIAGNOSTIQUE UNIQUE (docs/next_signal_strategy.md,
docs/sot_incremental_information_experiment.md) - PAS une construction de
modele de production. Ne modifie AUCUN modele existant (`poisson_simple`,
`dixon_coles`, `xg_model`), AUCUNE correction E7/E8/E14/E15/E16, AUCUN
gate du moteur final, N'ACTIVE PAS `BET`, NE FIXE PAS `min_edge_threshold`.
Une seule source d'information nouvelle a la fois (jamais BFE/AH/multi-
bookmaker/multi-lignes en meme temps) - voir la liste d'interdictions
explicites en fin de docstring.

====================================================================
ETAPE 1 - DONNEES (deja presentes, aucun telechargement)
====================================================================
Six fichiers Football-Data deja commit
(``research/market_odds/football_data/runs``) etendus (Phase F,
``football_data_loader.py``) pour lire ``HST``/``AST`` - COUVERTURE
VERIFIEE (jamais supposee) : 0 valeur manquante sur les 2132 lignes,
``HST<=HS``/``AST<=AS`` toujours vrai. Aucune autre statistique de match
(``HS``/``AS``/``HC``/``AC``/``HF``/``AF``/``HY``/``AY``/``HR``/``AR``)
n'est lue - hypothese prioritaire uniquement (tirs cadres).

====================================================================
ETAPE 2 - FEATURES (figees AVANT execution, ``shots_on_target.py``)
====================================================================
Exactement DEUX scalaires, JAMAIS multiplies :
    sot_produced_total = moyenne_historique(tirs_cadres_marques, domicile)
                        + moyenne_historique(tirs_cadres_marques, exterieur)
    sot_conceded_total = son miroir (tirs cadres ENCAISSES)
Moyenne calculee sur un pool POOLE (championnat x saison), walk-forward,
matchs strictement anterieurs a `decision_time` (`sot_knowledge_time =
kickoff+2h`, REUTILISE de `real_data_walk_forward.py`, aucun nouveau
delai invente). Seuil minimal du pool : REUTILISE EXACTEMENT
`MIN_TRAIN_MATCHES` (=10, `economic_dataset.py`) - meme convention que
`poisson_simple`/`xg_model`. Une equipe SANS historique dans un pool
suffisant recoit la moyenne DU POOL (repli neutre translittere de
`XGModel.fit`, jamais une exclusion ni une valeur inventee).

====================================================================
ETAPE 3 - MODELES COMPARES (figes avant execution)
====================================================================
    O     (moteur actuel seul)   : p = calibrate_prediction(poisson_simple)
                                    - ZERO parametre supplementaire, pur
                                    passe-plat de la sortie deja existante
                                    du moteur (E7/E8, INCHANGEE).
    O+SOT (moteur + tirs cadres) : p = sigmoid(a + b*logit(p_O) +
                                    c*sot_produced_total +
                                    d*sot_conceded_total) - 4 parametres,
                                    ajustes EN FENETRE GLISSANTE EXPANSIVE
                                    (walk-forward), REUTILISE SANS
                                    MODIFICATION `fit_logistic`/
                                    `predict_logistic`/`_safe_logit`/
                                    `walk_forward_logistic` d'E16
                                    (`run_stage25...py`), MEME
                                    `_MIN_TRAIN=30`.
Aucun marche n'intervient dans cette comparaison (le moteur actuel, tel
que defini par le protocole, EST `poisson_simple` calibre - la
comparaison au marche est un niveau separe du pipeline, hors perimetre
de cette question).

====================================================================
ETAPE 3bis - UNE SEULE PASSE WALK-FORWARD SUR LE CORPUS COMPLET
====================================================================
Contrairement a la Phase D (qui separait rodage/VALIDATION/TEST pour
proteger un SEUIL contre le surapprentissage), cette experience ne
selectionne AUCUN seuil - c'est un test d'information walk-forward pur,
exactement comme E16 (qui n'introduit pas non plus de split
rodage/calibration/test). Chaque prediction, a chaque etape, n'utilise
QUE les matchs dont `decision_time` est strictement anterieur (Modele O :
`calibrate_prediction`/`fit_scale_correction_as_of`, INCHANGES, filtrent
deja ainsi en interne ; Modele O+SOT : `walk_forward_logistic`,
INCHANGE). Ceci maximise l'effectif exploitable (n proche de 2132 moins
les periodes de rodage) - preference explicite du protocole ("effectif
suffisant").

====================================================================
ETAPE 7 - TEST STATISTIQUE PRINCIPAL (jamais une simple comparaison de
score moyen)
====================================================================
`paired_bootstrap_test` (REUTILISE SANS MODIFICATION,
`calibration_engine.significance`) sur les differences appariees de
Brier (O+SOT - O) et de log loss, sur l'ensemble eligible (les DEUX
modeles disponibles pour le meme match). IC95% et p-value rapportes -
une amelioration numerique NON significative est classee comme ABSENCE
DE PREUVE d'information incrementale, jamais un signal.

====================================================================
ETAPE 10 - GRILLE DE VERDICT (definie AVANT observation des resultats)
====================================================================
    VALIDE : IC95% du diff de Brier (O+SOT - O) ENTIEREMENT < 0 (walk-
        forward, effectif global) ET aucune degradation majeure de la
        calibration/coherence ET le resultat n'est pas limite a une
        seule anomalie (verifie par les decoupes championnat/saison,
        section robustesse) ET aucune fuite detectee.
    NON VALIDE : IC95% chevauchant 0, OU amelioration instable (inversee
        dans une decoupe majeure), OU information deja redondante
        (coefficient SOT non distinguable de 0 dans la regression
        walk-forward).
    REJETE : fuite detectee, protocole invalide, ou feature impossible a
        calculer point-in-time.
Applique mecaniquement, jamais ajuste apres observation.

====================================================================
INTERDICTIONS EXPLICITES (protocole Phase F, etape 11)
====================================================================
Pas de recherche de meilleur ROI/seuil d'edge, pas d'optimisation de
feature, pas de test de dizaines de fenetres puis selection de la
meilleure, pas d'introduction simultanee de BFE/AH/multi-bookmaker, pas
d'utilisation de statistique du match courant ni de cloture, pas de
modification de `poisson_simple`/E7/E8/gates, pas d'activation de `BET`,
pas de fixation de `min_edge_threshold`.

Usage:
    python scripts/run_stage27_phase_f_sot_incremental_information.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.data_engine.market_odds.shots_on_target import (  # noqa: E402
    build_shots_on_target_dataset,
    sot_features_for_match,
    sot_training_pool,
)
from sys_foot_quant.final_engine.calibration import calibrate_prediction  # noqa: E402
from sys_foot_quant.final_engine.types import ModelPrediction  # noqa: E402

app = typer.Typer(add_completion=False)

_PRIMARY_MODEL = "poisson_simple"
_MIN_TRAIN_LOGISTIC = 30  # E16, REUTILISE - meme convention

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FD_DIR = _REPO_ROOT / "research" / "market_odds" / "football_data" / "runs"
_US_DIR = _REPO_ROOT / "research" / "xg_feasibility" / "runs"

_DATASETS = {
    ("premier_league", "2024_25"): ("E0_2024_25.csv", "epl_2024_datesData.json"),
    ("premier_league", "2025_26"): ("E0_2025_26.csv", "epl_2025_datesData.json"),
    ("ligue1", "2024_25"): ("F1_2024_25.csv", "ligue1_2024_datesData.json"),
    ("ligue1", "2025_26"): ("F1_2025_26.csv", "ligue1_2025_datesData.json"),
    ("liga", "2024_25"): ("SP1_2024_25.csv", "liga_2024_datesData.json"),
    ("liga", "2025_26"): ("SP1_2025_26.csv", "liga_2025_datesData.json"),
}

_STAGE16_PATH = Path(__file__).resolve().parent / "run_stage16_e8_walk_forward_validation.py"
_STAGE25_PATH = Path(__file__).resolve().parent / "run_stage25_e16_market_movement_information.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_e8():
    return _load_module("run_stage16_e8_walk_forward_validation", _STAGE16_PATH)


def _load_e16():
    return _load_module("run_stage25_e16_market_movement_information", _STAGE25_PATH)


# --------------------------------------------------------------------------
# ETAPE 1/4 - construction des enregistrements SOT par championnat x saison
# et lookup match_id -> (home_team_id, away_team_id) (REUTILISE le meme
# schema de cle que `build_decision_time_lookup`, jamais un nouvel
# identifiant invente).
# --------------------------------------------------------------------------


def build_sot_records_by_league_season() -> dict[tuple[str, str], list]:
    out: dict[tuple[str, str], list] = {}
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        report = build_shots_on_target_dataset(league, season, us_raw, fd_records)
        out[(league, season)] = list(report.records)
    return out


def build_team_id_lookup(stage8_module) -> dict[str, tuple[int, int]]:
    """match_id -> (home_team_id, away_team_id), Understat - meme espace
    d'identifiants que `poisson_simple`/`xg_model`."""
    out: dict[str, tuple[int, int]] = {}
    for season, leagues in stage8_module._SEASONS.items():
        for name in leagues:
            for r in stage8_module._load_records(name, season):
                out[r.match_id] = (r.home_team_id, r.away_team_id)
    return out


# --------------------------------------------------------------------------
# ETAPE 3/3bis - assemblage du dataset complet (Modele O + features SOT),
# UNE SEULE PASSE walk-forward sur le corpus complet, trie par
# decision_time.
# --------------------------------------------------------------------------


def build_full_dataset(e8_module, e7_module, stage8_module, sot_by_league_season: dict) -> pd.DataFrame:
    df = e7_module.build_lambda_mu_dataframe(stage8_module)
    decision_time_lookup = e8_module.build_decision_time_lookup(stage8_module)
    df["decision_time"] = df["match_id"].map(decision_time_lookup)
    # ``decision_time`` perd son tzinfo UTC en traversant ``Series.map()``
    # (meme particularite deja rencontree et corrigee en Phase D,
    # `run_stage26...build_backtest_rows` - jamais une ambiguite de fuseau
    # reelle, `build_decision_time_lookup` produit bien des datetimes UTC
    # a la source). Reattache explicitement UTC sur TOUTE la colonne ici
    # (plutot que ligne par ligne) pour que `calibrate_prediction`
    # (comparaison interne `decision_time < as_of_time`) compare deux
    # valeurs tz-aware coherentes.
    df["decision_time"] = pd.to_datetime(df["decision_time"], utc=True)
    team_id_lookup = build_team_id_lookup(stage8_module)

    df = df.dropna(subset=["poisson_simple_lambda", "poisson_simple_mu", "decision_time"]).copy()
    df = df.sort_values("decision_time").reset_index(drop=True)

    calibration_pool = df  # filtre interne par decision_time < as_of_time (fit_scale_correction_as_of)

    p_model_over: list[float] = []
    n_calibration_used: list[int] = []
    sot_produced_total: list[float] = []
    sot_conceded_total: list[float] = []
    n_sot_used: list[float] = []

    for _, row in df.iterrows():
        decision_time = row["decision_time"]  # deja tz-aware UTC (colonne corrigee ci-dessus)

        pred = ModelPrediction(
            model=_PRIMARY_MODEL, lam=float(row["poisson_simple_lambda"]), mu=float(row["poisson_simple_mu"]),
            rho=None, n_train_matches=0,
        )
        calibrated = calibrate_prediction(pred, calibration_pool, as_of_time=decision_time)
        if calibrated.probabilities is not None:
            p_model_over.append(calibrated.probabilities[2.5])
            n_calibration_used.append(calibrated.n_calibration_used)
        else:
            p_model_over.append(np.nan)
            n_calibration_used.append(calibrated.n_calibration_used)

        home_team_id, away_team_id = team_id_lookup[row["match_id"]]
        sot_records = sot_by_league_season.get((row["league"], row["season"]), [])
        pool = sot_training_pool(sot_records, decision_time, exclude_match_id=row["match_id"])
        features = sot_features_for_match(pool, home_team_id, away_team_id)
        if features is not None:
            produced, conceded, n_used = features
            sot_produced_total.append(produced)
            sot_conceded_total.append(conceded)
            n_sot_used.append(n_used)
        else:
            sot_produced_total.append(np.nan)
            sot_conceded_total.append(np.nan)
            n_sot_used.append(np.nan)

    df["p_model_over"] = p_model_over
    df["n_calibration_used"] = n_calibration_used
    df["sot_produced_total"] = sot_produced_total
    df["sot_conceded_total"] = sot_conceded_total
    df["n_sot_used"] = n_sot_used
    df["outcome"] = (df["total_goals"] > 2.5).astype(float)
    return df


# --------------------------------------------------------------------------
# ETAPE 3/7 - eligibilite (Modele O ET features SOT tous deux disponibles)
# et construction de la comparaison O vs O+SOT (E16, INCHANGE).
# --------------------------------------------------------------------------


def eligible_dataset(df: pd.DataFrame) -> pd.DataFrame:
    elig = df.dropna(subset=["p_model_over", "sot_produced_total", "sot_conceded_total"]).copy()
    return elig.sort_values("decision_time").reset_index(drop=True)


def build_o_vs_osot(elig: pd.DataFrame, e16_module) -> pd.DataFrame:
    """Construit TROIS series walk-forward sur le meme DataFrame trie :
    - `p_model_over` (deja presente) : O BRUT, ZERO parametre.
    - `p_o_recal` : CONTROLE OBLIGATOIRE - O reajuste par la MEME
      mecanique de regression logistique walk-forward (intercept + pente
      sur `logit(p_O)`, SANS aucune covariable SOT). Necessaire pour ne
      jamais confondre "O+SOT ameliore le score" avec "n'importe quelle
      re-calibration lineaire de O l'aurait deja ameliore autant" -
      exigence directe du protocole (etape 10, critere NON VALIDE :
      "information deja redondante avec le moteur actuel"). Sans ce
      controle, le test principal (O+SOT vs O BRUT) ne repond PAS a la
      question posee (information INCREMENTALE), uniquement a "une
      regression logistique quelconque ameliore-t-elle O ?", question
      differente et non posee par le protocole.
    - `p_osot` : O + les 2 covariables SOT (voir docstring module).
    Les trois REUTILISENT `fit_logistic`/`predict_logistic`/`_safe_logit`/
    `walk_forward_logistic` d'E16 SANS MODIFICATION - seule la liste de
    covariables differe entre `p_o_recal` et `p_osot`."""

    def _cov_o_recal(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        logit_o = e16_module._safe_logit(d["p_model_over"].to_numpy())
        X = np.column_stack([np.ones(len(d)), logit_o])
        return X, d["outcome"].to_numpy()

    def _cov_osot(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        logit_o = e16_module._safe_logit(d["p_model_over"].to_numpy())
        X = np.column_stack([np.ones(len(d)), logit_o, d["sot_produced_total"].to_numpy(), d["sot_conceded_total"].to_numpy()])
        return X, d["outcome"].to_numpy()

    p_o_recal = e16_module.walk_forward_logistic(elig, _cov_o_recal, min_train=_MIN_TRAIN_LOGISTIC)
    p_osot = e16_module.walk_forward_logistic(elig, _cov_osot, min_train=_MIN_TRAIN_LOGISTIC)
    out = elig.copy()
    out["p_o_recal"] = p_o_recal
    out["p_osot"] = p_osot
    return out.dropna(subset=["p_o_recal", "p_osot"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# ETAPE 7/8 - metriques et tests statistiques.
# --------------------------------------------------------------------------


def _brier_logloss(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    eps = 1e-12
    brier = (p - y) ** 2
    logloss = -(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))
    return brier, logloss


def evaluate_o_vs_osot(compared: pd.DataFrame, stage8_module) -> dict:
    """Metriques et tests statistiques pour les TROIS series
    (`p_model_over`=O BRUT, `p_o_recal`=CONTROLE O re-calibre SANS SOT,
    `p_osot`=O+SOT). Le test PRINCIPAL (protocole etape 7 : "O+SOT
    apporte-t-il une information au-dela de O" - jamais "un meilleur
    score") compare O+SOT au CONTROLE O-recalibre, PAS au O brut : sans
    ce controle, une amelioration de O+SOT pourrait n'etre que l'effet
    d'une re-calibration lineaire generique, non specifique aux tirs
    cadres (voir docstring de `build_o_vs_osot`)."""
    p_o = compared["p_model_over"].to_numpy()
    p_o_recal = compared["p_o_recal"].to_numpy()
    p_osot = compared["p_osot"].to_numpy()
    y = compared["outcome"].to_numpy()
    n = len(compared)

    brier_o, logloss_o_arr = _brier_logloss(p_o, y)
    brier_o_recal, logloss_o_recal_arr = _brier_logloss(p_o_recal, y)
    brier_osot, logloss_osot_arr = _brier_logloss(p_osot, y)

    boot_brier_osot_minus_o = paired_bootstrap_test(brier_osot - brier_o, seed=0)
    boot_logloss_osot_minus_o = paired_bootstrap_test(logloss_osot_arr - logloss_o_arr, seed=0)
    # TEST PRINCIPAL - information INCREMENTALE au-dela d'une simple
    # re-calibration de O (jamais au-dela du seul O brut).
    boot_brier_osot_minus_o_recal = paired_bootstrap_test(brier_osot - brier_o_recal, seed=0)
    boot_logloss_osot_minus_o_recal = paired_bootstrap_test(logloss_osot_arr - logloss_o_recal_arr, seed=0)

    cal_o = stage8_module._calibration_weighted_error(p_o, y)
    cal_o_recal = stage8_module._calibration_weighted_error(p_o_recal, y)
    cal_osot = stage8_module._calibration_weighted_error(p_osot, y)
    resolution_o = brier_decomposition(p_o, y)["resolution"]
    resolution_o_recal = brier_decomposition(p_o_recal, y)["resolution"]
    resolution_osot = brier_decomposition(p_osot, y)["resolution"]

    return {
        "n": n,
        "brier_o": float(brier_o.mean()),
        "brier_o_recal": float(brier_o_recal.mean()),
        "brier_osot": float(brier_osot.mean()),
        "logloss_o": float(logloss_o_arr.mean()),
        "logloss_o_recal": float(logloss_o_recal_arr.mean()),
        "logloss_osot": float(logloss_osot_arr.mean()),
        "boot_brier_osot_minus_o": boot_brier_osot_minus_o,
        "boot_logloss_osot_minus_o": boot_logloss_osot_minus_o,
        "boot_brier_osot_minus_o_recal": boot_brier_osot_minus_o_recal,
        "boot_logloss_osot_minus_o_recal": boot_logloss_osot_minus_o_recal,
        "calibration_weighted_error_o": cal_o["weighted_mean_abs_error"],
        "calibration_weighted_error_o_recal": cal_o_recal["weighted_mean_abs_error"],
        "calibration_weighted_error_osot": cal_osot["weighted_mean_abs_error"],
        "resolution_o": resolution_o,
        "resolution_o_recal": resolution_o_recal,
        "resolution_osot": resolution_osot,
    }


def classify_verdict(global_res: dict, scope_boots: list[dict]) -> str:
    """Grille de verdict FIGEE (voir docstring module, etape 10) -
    appliquee mecaniquement, jamais ajustee apres observation. Le critere
    de significativite porte sur O+SOT vs le CONTROLE O-recalibre
    (`boot_brier_osot_minus_o_recal`), jamais sur O+SOT vs O brut - c'est
    la seule comparaison qui isole l'effet specifique des tirs cadres
    d'un simple effet de re-calibration generique."""
    ci_low = global_res["boot_brier_osot_minus_o_recal"]["ci_low"]
    ci_high = global_res["boot_brier_osot_minus_o_recal"]["ci_high"]
    globally_improved = ci_high < 0.0
    any_scope_inversion = any(s["ci_low"] > 0.0 for s in scope_boots)
    calibration_degraded = global_res["calibration_weighted_error_osot"] > global_res["calibration_weighted_error_o_recal"] * 1.5

    if not globally_improved:
        return "NON VALIDE"
    if any_scope_inversion or calibration_degraded:
        return "NON VALIDE"
    return "VALIDE"


def _print_metrics(label: str, res: dict) -> None:
    typer.echo(f"  -- {label} (n={res['n']}) --")
    typer.echo(f"    Brier   O={res['brier_o']:.4f}  O-recalibre={res['brier_o_recal']:.4f}  O+SOT={res['brier_osot']:.4f}")
    typer.echo(f"      O+SOT vs O brut       diff(IC95%)=[{res['boot_brier_osot_minus_o']['ci_low']:+.4f}, {res['boot_brier_osot_minus_o']['ci_high']:+.4f}] "
               f"p={res['boot_brier_osot_minus_o']['p_value']:.4f}")
    typer.echo(f"      O+SOT vs O-recalibre  diff(IC95%)=[{res['boot_brier_osot_minus_o_recal']['ci_low']:+.4f}, {res['boot_brier_osot_minus_o_recal']['ci_high']:+.4f}] "
               f"p={res['boot_brier_osot_minus_o_recal']['p_value']:.4f}  <- TEST PRINCIPAL (information incrementale)")
    typer.echo(f"    LogLoss O={res['logloss_o']:.4f}  O-recalibre={res['logloss_o_recal']:.4f}  O+SOT={res['logloss_osot']:.4f}")
    typer.echo(f"      O+SOT vs O-recalibre  diff(IC95%)=[{res['boot_logloss_osot_minus_o_recal']['ci_low']:+.4f}, {res['boot_logloss_osot_minus_o_recal']['ci_high']:+.4f}]")
    typer.echo(f"    Calibration (erreur ponderee) O={res['calibration_weighted_error_o']:.4f}  O-recalibre={res['calibration_weighted_error_o_recal']:.4f}  O+SOT={res['calibration_weighted_error_osot']:.4f}")
    typer.echo(f"    Resolution (discrimination)   O={res['resolution_o']:.4f}  O-recalibre={res['resolution_o_recal']:.4f}  O+SOT={res['resolution_osot']:.4f}")


@app.command()
def main() -> None:
    typer.echo("=== Phase F : information incrementale des tirs cadres (SOT) sur Over/Under 2.5 ===")
    typer.echo("Modele O = poisson_simple calibre (E7/E8, INCHANGE). Modele O+SOT = O + 2 covariables SOT, walk-forward (E16, INCHANGE).\n")

    e8 = _load_e8()
    e7 = e8._load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()
    e16 = _load_e16()

    sot_by_ls = build_sot_records_by_league_season()
    typer.echo(f"Championnats x saisons SOT charges : {sorted(sot_by_ls.keys())}")
    for k, v in sorted(sot_by_ls.items()):
        typer.echo(f"  {k} : n_matched={len(v)}")

    df = build_full_dataset(e8, e7, stage8, sot_by_ls)
    typer.echo(f"\nn_corpus (poisson_simple disponible) = {len(df)}")

    elig = eligible_dataset(df)
    typer.echo(f"n_eligible (Modele O ET SOT tous deux disponibles) = {len(elig)}")

    compared = build_o_vs_osot(elig, e16)
    typer.echo(f"n_compare (apres warm-up walk-forward logistique, min_train={_MIN_TRAIN_LOGISTIC}) = {len(compared)}\n")

    typer.echo("=== GLOBAL ===")
    global_res = evaluate_o_vs_osot(compared, stage8)
    _print_metrics("GLOBAL", global_res)

    scope_boots = []
    typer.echo("\n=== Robustesse par championnat (descriptif, jamais une re-selection) ===")
    for league in sorted(compared["league"].unique()):
        sub = compared[compared["league"] == league]
        if len(sub) < 10:
            typer.echo(f"  {league} : n={len(sub)} (trop peu pour une metrique fiable, non exploite)")
            continue
        res = evaluate_o_vs_osot(sub, stage8)
        _print_metrics(league, res)
        scope_boots.append(res["boot_brier_osot_minus_o_recal"])

    typer.echo("\n=== Robustesse par saison (descriptif, jamais une re-selection) ===")
    for season in sorted(compared["season"].unique()):
        sub = compared[compared["season"] == season]
        if len(sub) < 10:
            typer.echo(f"  {season} : n={len(sub)} (trop peu pour une metrique fiable, non exploite)")
            continue
        res = evaluate_o_vs_osot(sub, stage8)
        _print_metrics(season, res)
        scope_boots.append(res["boot_brier_osot_minus_o_recal"])

    verdict = classify_verdict(global_res, scope_boots)
    typer.echo(f"\n=== VERDICT (grille figee avant observation) : {verdict} ===")

    typer.echo(
        "\nRESERVE : aucune conclusion de rentabilite, aucune strategie de pari, aucun seuil "
        "d'edge/ROI. poisson_simple/dixon_coles/xg_model, E7/E8/E14/E15/E16 et tous les gates "
        "restent INCHANGES. `BET` non active, `min_edge_threshold` non fixe."
    )
    typer.echo("\nARRET : Phase F terminee, conformement au protocole. Aucune experience suivante lancee automatiquement.")


if __name__ == "__main__":
    app()
