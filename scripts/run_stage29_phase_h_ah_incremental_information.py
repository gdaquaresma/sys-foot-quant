"""Phase H - le marche Handicap Asiatique (AH) contient-il une
information exploitable ou une inefficience que le moteur actuel ne
detecte pas ?

Protocole pre-enregistre complet : docs/ah_experiment_specification.md
(definition mathematique du marche, transformations, split, modeles,
controles, metriques, criteres de validation/rejet - tout fige AVANT
cette execution). Experience DIAGNOSTIQUE UNIQUE. Ne modifie AUCUN
modele (`poisson_simple`/`dixon_coles`/`xg_model`), AUCUNE correction
E7/E8/E14/E15/E16, AUCUN gate, AUCUN code de `final_engine`. N'ACTIVE
PAS `BET`, NE FIXE PAS `min_edge_threshold`.

====================================================================
TROIS QUESTIONS (jamais confondues, docs/ah_experiment_specification.md
section 7 / docs/operational_validation_specification.md section 2)
====================================================================
A. Le modele est-il correctement calibre sur les resultats AH ? ->
   Brier a 3 classes (Home/Push/Away), population complete.
B. Le modele apporte-t-il une information incrementale AU-DESSUS du
   marche AH ? -> test principal, walk-forward, population "propre"
   (reglement +-1, push/demi-gain/demi-perte exclus - section 5 du
   protocole), CONTROLE OBLIGATOIRE "Modele_AH-recalibre" (lecon
   Phases F/G).
C. Existe-t-il une strategie AH rentable ? -> HORS PERIMETRE de cette
   experience (necessiterait le protocole complet de
   docs/operational_validation_specification.md).

Usage:
    python scripts/run_stage29_phase_h_ah_incremental_information.py
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

from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.calibration_engine.scalar_correction import fit_scale_correction_as_of  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.data_engine.market_odds.asian_handicap_odds import build_asian_handicap_dataset  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.football_model.goal_distribution import asian_handicap_probabilities  # noqa: E402
from sys_foot_quant.football_model.scoring import score_matrix  # noqa: E402
from sys_foot_quant.market_engine.overround import remove_overround_proportional  # noqa: E402
from sys_foot_quant.value_engine.edge import edge as compute_edge  # noqa: E402
from sys_foot_quant.value_engine.edge import expected_value  # noqa: E402

app = typer.Typer(add_completion=False)

_MIN_TRAIN_LOGISTIC = 30  # E16, REUTILISE
_MAX_GOALS = 20
_PRIMARY_MODEL = "poisson_simple"

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
# ETAPE 1 - construction des enregistrements AH par championnat x saison.
# --------------------------------------------------------------------------


def load_all_ah_records() -> dict[str, object]:
    """match_id -> AsianHandicapMatchRecord, sur les six championnats x
    saisons - reutilise `build_asian_handicap_dataset` sans modification."""
    out: dict[str, object] = {}
    for (league, season), (fd_name, us_name) in _DATASETS.items():
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        with open(_US_DIR / us_name) as f:
            us_raw = json.load(f)
        report = build_asian_handicap_dataset(league, season, us_raw, fd_records)
        for r in report.records:
            out[r.match_id] = r
    return out


def settle_fraction(d: int, h: float) -> float:
    """Reutilise `asian_handicap_probabilities` (INCHANGEE) - concentre
    toute la masse sur un score unique de difference `d`, lit
    P(Home)-P(Away) - EXACTEMENT ce que vaut le reglement reel (voir
    tests dedies de goal_distribution.py, qui prouvent cette identite
    pour tous les cas de `d`)."""
    home_goals = max(d, 0) + 5
    away_goals = home_goals - d
    matrix = np.zeros((_MAX_GOALS + 1, _MAX_GOALS + 1))
    matrix[home_goals, away_goals] = 1.0
    probs = asian_handicap_probabilities(matrix, h)
    return probs["home"] - probs["away"]


def ah_outcome_class(d: int, h: float) -> int:
    """0=Home, 1=Push, 2=Away - classe reellement observee pour le Brier
    a 3 classes (section 9.2 du protocole : un push n'est possible que
    sur une ligne entiere, jamais sur un resultat de ligne quart)."""
    s = settle_fraction(d, h)
    if s > 1e-9:
        return 0
    if s < -1e-9:
        return 2
    return 1


# --------------------------------------------------------------------------
# ETAPE 2 - assemblage du corpus complet (Modele_AH + Marche_AH), UNE
# SEULE PASSE walk-forward sur le corpus complet trie par decision_time.
# --------------------------------------------------------------------------


def build_full_dataset(e8_module, e7_module, stage8_module, ah_by_match_id: dict) -> pd.DataFrame:
    df = e7_module.build_lambda_mu_dataframe(stage8_module)
    decision_time_lookup = e8_module.build_decision_time_lookup(stage8_module)
    df["decision_time"] = df["match_id"].map(decision_time_lookup)
    df["decision_time"] = pd.to_datetime(df["decision_time"], utc=True)  # meme fix tz que Phase F/G

    df = df.dropna(subset=["poisson_simple_lambda", "poisson_simple_mu", "decision_time"]).copy()
    df = df.sort_values("decision_time").reset_index(drop=True)

    calibration_pool = df  # fit_scale_correction_as_of filtre en interne par decision_time < as_of_time

    ah_line, p_home_3class, p_push_3class, p_away_3class = [], [], [], []
    p_market_home, p_model_home_condl = [], []
    outcome_class, settle = [], []
    raw_edge_home, price_edge_home = [], []

    for _, row in df.iterrows():
        ah = ah_by_match_id.get(row["match_id"])
        if ah is None:
            ah_line.append(np.nan)
            p_home_3class.append(np.nan)
            p_push_3class.append(np.nan)
            p_away_3class.append(np.nan)
            p_market_home.append(np.nan)
            p_model_home_condl.append(np.nan)
            outcome_class.append(np.nan)
            settle.append(np.nan)
            raw_edge_home.append(np.nan)
            price_edge_home.append(np.nan)
            continue

        decision_time = row["decision_time"]
        scale_c, _n = fit_scale_correction_as_of(
            calibration_pool, _PRIMARY_MODEL, as_of_time=decision_time
        )
        if scale_c is None:
            ah_line.append(ah.ah_line)
            p_home_3class.append(np.nan)
            p_push_3class.append(np.nan)
            p_away_3class.append(np.nan)
            p_market_home.append(np.nan)
            p_model_home_condl.append(np.nan)
            outcome_class.append(np.nan)
            settle.append(np.nan)
            raw_edge_home.append(np.nan)
            price_edge_home.append(np.nan)
            continue

        corrected_lam = scale_c * float(row["poisson_simple_lambda"])
        corrected_mu = scale_c * float(row["poisson_simple_mu"])
        matrix = score_matrix(corrected_lam, corrected_mu, max_goals=_MAX_GOALS)
        matrix = matrix / matrix.sum()
        probs = asian_handicap_probabilities(matrix, ah.ah_line)

        denom = probs["home"] + probs["away"]
        p_home_condl = probs["home"] / denom if denom > 0 else np.nan

        market_norm = remove_overround_proportional({"Home": ah.b365_ah_home, "Away": ah.b365_ah_away})

        d = ah.home_goals - ah.away_goals
        s = settle_fraction(d, ah.ah_line)

        # raw_edge/price_edge (docs/final_engine_specification.md section 11,
        # docs/ah_experiment_specification.md section 2.6) - REUTILISES SANS
        # MODIFICATION, jamais appeles "value", jamais utilises pour le
        # verdict (descriptif uniquement, calcules quand P(Home|not push)>0).
        if not np.isnan(p_home_condl):
            r_edge = compute_edge(p_home_condl, market_norm["Home"])
            p_edge = expected_value(p_home_condl, ah.b365_ah_home)
        else:
            r_edge, p_edge = np.nan, np.nan

        ah_line.append(ah.ah_line)
        p_home_3class.append(probs["home"])
        p_push_3class.append(probs["push"])
        p_away_3class.append(probs["away"])
        p_market_home.append(market_norm["Home"])
        p_model_home_condl.append(p_home_condl)
        outcome_class.append(ah_outcome_class(d, ah.ah_line))
        settle.append(s)
        raw_edge_home.append(r_edge)
        price_edge_home.append(p_edge)

    df["ah_line"] = ah_line
    df["p_home_3class"] = p_home_3class
    df["p_push_3class"] = p_push_3class
    df["p_away_3class"] = p_away_3class
    df["p_market_home"] = p_market_home
    df["p_model_home_condl"] = p_model_home_condl
    df["raw_edge_home"] = raw_edge_home
    df["price_edge_home"] = price_edge_home
    df["ah_outcome_class"] = outcome_class
    df["settle"] = settle
    return df


# --------------------------------------------------------------------------
# ETAPE 3 - QUESTION A : calibration du modele sur l'AH (Brier a 3
# classes, population complete).
# --------------------------------------------------------------------------


def evaluate_calibration_3class(df: pd.DataFrame) -> dict:
    sub = df.dropna(subset=["p_home_3class", "p_push_3class", "p_away_3class", "ah_outcome_class"])
    probs = sub[["p_home_3class", "p_push_3class", "p_away_3class"]].to_numpy()
    outcomes = sub["ah_outcome_class"].to_numpy(dtype=int)
    return {
        "n": len(sub),
        "brier": brier_score(probs, outcomes),
        "log_loss": log_loss(probs, outcomes),
        "push_rate_observed": float((outcomes == 1).mean()),
        "push_rate_predicted_mean": float(sub["p_push_3class"].mean()),
    }


# --------------------------------------------------------------------------
# ETAPE 4 - QUESTION B : information incrementale (population "propre",
# reglement +-1 uniquement), modeles O/O-recalibre/O+Marche (E16, INCHANGE).
# --------------------------------------------------------------------------


def clean_population(df: pd.DataFrame) -> pd.DataFrame:
    sub = df.dropna(subset=["p_model_home_condl", "p_market_home", "settle"]).copy()
    sub = sub[np.abs(np.abs(sub["settle"]) - 1.0) < 1e-9].copy()
    sub["outcome"] = (sub["settle"] > 0).astype(float)
    return sub.sort_values("decision_time").reset_index(drop=True)


def build_model_vs_market(clean: pd.DataFrame, e16_module) -> pd.DataFrame:
    def _cov_model_recal(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        logit_m = e16_module._safe_logit(d["p_model_home_condl"].to_numpy())
        X = np.column_stack([np.ones(len(d)), logit_m])
        return X, d["outcome"].to_numpy()

    def _cov_model_market(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        logit_m = e16_module._safe_logit(d["p_model_home_condl"].to_numpy())
        logit_mkt = e16_module._safe_logit(d["p_market_home"].to_numpy())
        X = np.column_stack([np.ones(len(d)), logit_m, logit_mkt])
        return X, d["outcome"].to_numpy()

    p_recal = e16_module.walk_forward_logistic(clean, _cov_model_recal, min_train=_MIN_TRAIN_LOGISTIC)
    p_combo = e16_module.walk_forward_logistic(clean, _cov_model_market, min_train=_MIN_TRAIN_LOGISTIC)
    out = clean.copy()
    out["p_model_recal"] = p_recal
    out["p_model_market"] = p_combo
    return out.dropna(subset=["p_model_recal", "p_model_market"]).reset_index(drop=True)


def _brier_logloss(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    eps = 1e-12
    brier = (p - y) ** 2
    logloss = -(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))
    return brier, logloss


def _calibration_weighted_error(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    bins = reliability_bins(p, y, n_bins=n_bins)
    non_empty = bins[bins["count"] > 0]
    if non_empty.empty:
        return float("nan")
    abs_err = (non_empty["mean_predicted"] - non_empty["observed_frequency"]).abs()
    return float((abs_err * non_empty["count"]).sum() / non_empty["count"].sum())


def evaluate_model_vs_market(compared: pd.DataFrame) -> dict:
    p_model = compared["p_model_home_condl"].to_numpy()
    p_recal = compared["p_model_recal"].to_numpy()
    p_combo = compared["p_model_market"].to_numpy()
    y = compared["outcome"].to_numpy()
    n = len(compared)

    brier_model, logloss_model = _brier_logloss(p_model, y)
    brier_recal, logloss_recal = _brier_logloss(p_recal, y)
    brier_combo, logloss_combo = _brier_logloss(p_combo, y)

    boot_vs_model = paired_bootstrap_test(brier_combo - brier_model, seed=0)
    boot_vs_recal = paired_bootstrap_test(brier_combo - brier_recal, seed=0)

    return {
        "n": n,
        "brier_model": float(brier_model.mean()),
        "brier_recal": float(brier_recal.mean()),
        "brier_combo": float(brier_combo.mean()),
        "boot_combo_minus_model": boot_vs_model,
        "boot_combo_minus_recal": boot_vs_recal,
        "calibration_recal": _calibration_weighted_error(p_recal, y),
        "calibration_combo": _calibration_weighted_error(p_combo, y),
    }


def classify_verdict(global_res: dict, scope_boots: list[dict], n_global_pool: int) -> str:
    """Grille FIGEE (docs/ah_experiment_specification.md section 8) -
    appliquee mecaniquement, jamais ajustee apres observation."""
    if n_global_pool < 30:
        return "DONNEES INSUFFISANTES"

    ci_low = global_res["boot_combo_minus_recal"]["ci_low"]
    ci_high = global_res["boot_combo_minus_recal"]["ci_high"]
    calibration_degraded = global_res["calibration_combo"] > global_res["calibration_recal"] * 1.5

    if ci_high < 0.0:
        any_scope_inversion = any(s["ci_low"] > 0.0 for s in scope_boots)
        if any_scope_inversion or calibration_degraded:
            return "NON VALIDE"
        return "VALIDE"

    # IC95% ne demontre pas d'amelioration globale.
    width = ci_high - ci_low
    if width > 0.05:  # IC tres large, aucune direction nette exploitable
        return "ABSENCE DE PREUVE"
    return "NON VALIDE"


def _print_metrics(label: str, res: dict) -> None:
    typer.echo(f"  -- {label} (n={res['n']}) --")
    typer.echo(f"    Brier Modele={res['brier_model']:.4f}  Modele-recalibre={res['brier_recal']:.4f}  Modele+Marche={res['brier_combo']:.4f}")
    typer.echo(f"      Modele+Marche vs Modele brut       diff(IC95%)=[{res['boot_combo_minus_model']['ci_low']:+.4f}, {res['boot_combo_minus_model']['ci_high']:+.4f}] "
               f"p={res['boot_combo_minus_model']['p_value']:.4f}")
    typer.echo(f"      Modele+Marche vs Modele-recalibre  diff(IC95%)=[{res['boot_combo_minus_recal']['ci_low']:+.4f}, {res['boot_combo_minus_recal']['ci_high']:+.4f}] "
               f"p={res['boot_combo_minus_recal']['p_value']:.4f}  <- TEST PRINCIPAL (question B)")
    typer.echo(f"    Calibration Modele-recalibre={res['calibration_recal']:.4f}  Modele+Marche={res['calibration_combo']:.4f}")


@app.command()
def main() -> None:
    typer.echo("=== Phase H : information incrementale du handicap asiatique (AH) ===")
    typer.echo("Modele = poisson_simple calibre (E7/E8, INCHANGE), transforme via asian_handicap_probabilities (nouvelle primitive pure).")
    typer.echo("Marche = B365 AH (Pinnacle en secondaire, non teste ici - une seule variable nouvelle par experience).\n")

    e8 = _load_e8()
    e7 = e8._load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()
    e16 = _load_e16()

    ah_by_match_id = load_all_ah_records()
    typer.echo(f"n_ah_records (tous championnats x saisons, PIT valide) = {len(ah_by_match_id)}")

    df = build_full_dataset(e8, e7, stage8, ah_by_match_id)
    typer.echo(f"n_corpus (poisson_simple disponible) = {len(df)}")

    edge_sub = df.dropna(subset=["raw_edge_home", "price_edge_home"])
    if len(edge_sub) > 0:
        typer.echo(
            f"raw_edge_home (descriptif, jamais un critere de validation) : "
            f"moyenne={edge_sub['raw_edge_home'].mean():+.4f}  "
            f"price_edge_home moyen={edge_sub['price_edge_home'].mean():+.4f}"
        )

    typer.echo("\n=== QUESTION A : le modele est-il correctement calibre sur l'AH ? (Brier a 3 classes) ===")
    calib_res = evaluate_calibration_3class(df)
    typer.echo(f"  n={calib_res['n']}  Brier(3 classes)={calib_res['brier']:.4f}  LogLoss={calib_res['log_loss']:.4f}")
    typer.echo(f"  Taux de push observe={calib_res['push_rate_observed']:.4f}  predit(moyenne)={calib_res['push_rate_predicted_mean']:.4f}")

    typer.echo("\n=== QUESTION B : information incrementale (population 'propre', reglement +-1) ===")
    clean = clean_population(df)
    typer.echo(f"n_clean (reglement plein, push/demi-gain/demi-perte exclus) = {len(clean)}")

    compared = build_model_vs_market(clean, e16)
    typer.echo(f"n_compare (apres warm-up walk-forward, min_train={_MIN_TRAIN_LOGISTIC}) = {len(compared)}\n")

    global_res = evaluate_model_vs_market(compared)
    _print_metrics("GLOBAL", global_res)

    scope_boots = []
    typer.echo("\n  -- Robustesse par championnat (descriptif) --")
    for league in sorted(compared["league"].unique()):
        sub = compared[compared["league"] == league]
        if len(sub) < 30:
            typer.echo(f"    {league} : n={len(sub)} (effectif < 30, non exploite pour la robustesse)")
            continue
        res = evaluate_model_vs_market(sub)
        _print_metrics(f"    {league}", res)
        scope_boots.append(res["boot_combo_minus_recal"])

    typer.echo("  -- Robustesse par saison (descriptif) --")
    for season in sorted(compared["season"].unique()):
        sub = compared[compared["season"] == season]
        if len(sub) < 30:
            typer.echo(f"    {season} : n={len(sub)} (effectif < 30, non exploite pour la robustesse)")
            continue
        res = evaluate_model_vs_market(sub)
        _print_metrics(f"    {season}", res)
        scope_boots.append(res["boot_combo_minus_recal"])

    typer.echo("  -- Robustesse par type de ligne (descriptif) --")
    def _line_type(h: float) -> str:
        frac = abs(h) % 1.0
        if abs(frac) < 1e-9:
            return "entier"
        if abs(frac - 0.5) < 1e-9:
            return "demi"
        return "quart"
    compared["line_type"] = compared["ah_line"].apply(_line_type)
    for lt in ("entier", "demi", "quart"):
        sub = compared[compared["line_type"] == lt]
        if len(sub) < 30:
            typer.echo(f"    {lt} : n={len(sub)} (effectif < 30, non exploite pour la robustesse)")
            continue
        res = evaluate_model_vs_market(sub)
        _print_metrics(f"    {lt}", res)
        scope_boots.append(res["boot_combo_minus_recal"])

    verdict = classify_verdict(global_res, scope_boots, len(compared))
    typer.echo(f"\n=== VERDICT QUESTION B (grille figee avant observation) : {verdict} ===")

    typer.echo("\n=== QUESTION C : rentabilite operationnelle ===")
    typer.echo("  HORS PERIMETRE de cette experience (docs/ah_experiment_specification.md section 7) - "
               "necessiterait le protocole complet de docs/operational_validation_specification.md. Non execute ici, quel que soit le verdict de la question B.")

    typer.echo(
        "\nRESERVE : aucune conclusion de rentabilite, aucune strategie de pari, aucun seuil "
        "d'edge/ROI. Aucun modele/gate/final_engine modifie. `BET` non active, `min_edge_threshold` non fixe."
    )
    typer.echo("\nARRET : Phase H terminee, conformement au protocole. Aucune experience suivante lancee automatiquement.")


if __name__ == "__main__":
    app()
