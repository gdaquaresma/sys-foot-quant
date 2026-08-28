"""CLI : E8 - validation walk-forward HORS ECHANTILLON de la distribution
finale du total de buts corrigee par facteur d'echelle (E7).

`poisson_simple`, `dixon_coles` et `xg_model` restent INCHANGES. Aucun
nouveau modele. Aucune nouvelle methode de calibration. Aucune conclusion
de rentabilite. Question unique : la correction scalaire d'E7 reste-t-elle
fiable lorsqu'elle est produite EXCLUSIVEMENT avec les informations
disponibles avant chaque match de test ?

====================================================================
ETAPE 1 - INSPECTION DU PIPELINE E7 ET DES FRONTIERES TEMPORELLES
====================================================================
E7 (`run_stage15_e7_total_goals_distribution.py`) ajuste le facteur `c`
UNE SEULE FOIS sur l'ensemble POOLE (toutes ligues x saisons confondues)
du split "calibration" defini par `run_stage10...split_burn_in_calibration_test`
(40% rodage / 30% calibration / 30% test, tri chronologique **PAR
championnat-saison**), puis applique ce meme `c` a l'ensemble du test.

Inspection des frontieres reelles (calcul direct sur le corpus) :

    ligue1         2024_25  calib=[2024-12-08 .. 2025-03-02]  test=[2025-03-02 .. 2025-05-17]
    premier_league 2024_25  calib=[2024-12-14 .. 2025-02-26]  test=[2025-02-26 .. 2025-05-25]
    liga           2024_25  calib=[2024-12-07 .. 2025-03-09]  test=[2025-03-09 .. 2025-05-25]
    ligue1         2025_26  calib=[2025-11-30 .. 2026-03-01]  test=[2026-03-01 .. 2026-05-17]
    premier_league 2025_26  calib=[2025-12-13 .. 2026-02-21]  test=[2026-02-22 .. 2026-05-24]
    liga           2025_26  calib=[2025-12-12 .. 2026-03-08]  test=[2026-03-08 .. 2026-05-24]

Le decoupage EST chronologique a l'interieur de chaque championnat-saison,
mais PAS globalement : par exemple la calibration de `liga` 2024/25 s'etend
jusqu'au 2025-03-09, soit APRES le debut du test de `premier_league`
2024/25 (2025-02-26). Le facteur `c` poole d'E7, ajuste sur la calibration
poolee des 3 championnats, incorpore donc, pour certains matchs de test,
des informations issues de matchs POSTERIEURS d'un autre championnat. Ce
n'est pas une fuite du RESULTAT du match test lui-meme, mais cela viole la
regle stricte demandee ici ("aucune donnee d'un match ulterieur, aucun
parametre calibre sur le futur") si on l'applique globalement plutot que
championnat par championnat. E8 corrige precisement ce point.

CORRECTION APPLIQUEE PAR E8 (walk-forward strict, PAR MATCH) : pour
chaque match de test m (trie par `decision_time` = kickoff - 2h, la meme
regle que partout ailleurs dans le projet, reutilisee sans modification
via `DECISION_OFFSET_HOURS`), le facteur `c(m)` est reestime a partir du
sous-ensemble du jeu de CALIBRATION (jamais le test, jamais un jeu
different) dont `decision_time < decision_time(m)` - EXCLUSIVEMENT. Aucune
donnee du test n'entre jamais dans le calcul de `c(m)`, quel que soit m.
Ceci garantit, par construction et independamment de tout chevauchement
calendaire entre championnats, qu'aucune information posterieure au match
evalue n'influence son propre facteur de correction.

REGLE D'EXCLUSION (definie AVANT observation des resultats reels) : un
match de test est exclu de l'evaluation si moins de
`_MIN_CALIBRATION_MATCHES_FOR_SCALE = 30` matchs de calibration anterieurs
sont disponibles pour estimer `c(m)` (seuil usuel minimal pour une
estimation raisonnablement stable d'un ratio de moyennes, regle CLT). Ce
seuil n'est ni ajuste ni choisi apres avoir vu les resultats.

GRILLE DE VERDICT (definie AVANT observation des resultats reels, section
10 du protocole) :
    A - VALIDATION REUSSIE : IC95% du diff (Brier corrige walk-forward -
        Brier brut) <= 0 au niveau GLOBAL pour un modele, ET aucune
        decoupe championnat/saison n'affiche un IC95% entierement > 0
        (aucune inversion), ET le facteur c(m) ne montre pas de derive
        extreme (ecart-type/moyenne < 0.10).
    B - VALIDATION PARTIELLE : amelioration demontree globalement mais
        au moins une decoupe championnat/saison affiche une inversion
        (IC95% entierement > 0) ou une incertitude large, ou le facteur
        c(m) varie notablement selon la periode (ecart-type/moyenne >= 0.10).
    C - VALIDATION ECHOUEE : IC95% global entierement > 0 (inversion), ou
        absence de preuve d'amelioration globale ET dans toutes les
        decoupes (l'amelioration d'E7 disparait completement).
Cette grille est appliquee mecaniquement, PAR MODELE, sans ajustement
apres observation.

Usage:
    python scripts/run_stage16_e8_walk_forward_validation.py
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition  # noqa: E402
from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.economic_dataset import DECISION_OFFSET_HOURS  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "dixon_coles", "xg_model")
_MAX_BUCKET = 6  # 0..5 + "6+"
_OU_THRESHOLDS = (1.5, 2.5, 3.5)
_N_RESAMPLES = 10_000
_SEED = 0
_MIN_CALIBRATION_MATCHES_FOR_SCALE = 30  # regle d'exclusion PRE-ENREGISTREE

_STAGE15_PATH = Path(__file__).resolve().parent / "run_stage15_e7_total_goals_distribution.py"


def _load_e7():
    spec = importlib.util.spec_from_file_location("run_stage15_e7_total_goals_distribution", _STAGE15_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ETAPE 1 - decision_time par match (reutilise la MEME regle que
# partout ailleurs dans le projet - jamais reimplementee differemment).
# --------------------------------------------------------------------------


def build_decision_time_lookup(stage8_module) -> pd.Series:
    """match_id -> decision_time (kickoff_utc - DECISION_OFFSET_HOURS) -
    expose simplement, pour chaque match, la valeur DEJA utilisee de facon
    implicite par `build_lambda_mu_dataframe` (E7) - aucune nouvelle regle
    point-in-time, aucun recalcul different."""
    rows: dict[str, object] = {}
    for season, leagues in stage8_module._SEASONS.items():
        for name in leagues:
            for r in stage8_module._load_records(name, season):
                rows[r.match_id] = r.kickoff_utc - timedelta(hours=DECISION_OFFSET_HOURS)
    return pd.Series(rows, name="decision_time")


# --------------------------------------------------------------------------
# ETAPE 7 - correction scalaire walk-forward, PAR MATCH, jamais poolee
# globalement sans filtre temporel.
# --------------------------------------------------------------------------


def fit_scale_correction_as_of(
    calibration_df: pd.DataFrame,
    model: str,
    as_of_time,
    min_matches: int = _MIN_CALIBRATION_MATCHES_FOR_SCALE,
) -> tuple[float | None, int]:
    """c = E[total reel]/E[lambda+mu predit], estime EXCLUSIVEMENT sur les
    matchs de `calibration_df` dont `decision_time < as_of_time` - jamais
    un match de test, jamais un match dont `decision_time >= as_of_time`.
    Retourne (None, n) si n < min_matches (regle d'exclusion pre-enregistree)."""
    lam_col, mu_col = f"{model}_lambda", f"{model}_mu"
    sub = calibration_df[calibration_df["decision_time"] < as_of_time].dropna(subset=[lam_col, mu_col])
    n = len(sub)
    if n < min_matches:
        return None, n
    predicted_mean = float((sub[lam_col] + sub[mu_col]).mean())
    actual_mean = float(sub["total_goals"].mean())
    return actual_mean / predicted_mean, n


def attach_walk_forward_scale(calibration_df: pd.DataFrame, test_df: pd.DataFrame, model: str) -> pd.DataFrame:
    """Pour chaque match de `test_df` (trie par `decision_time`), calcule
    `scale_c` walk-forward (None si insuffisant - regle d'exclusion) et
    `n_calibration_used`. `test_df` n'est JAMAIS utilise dans le calcul de
    `scale_c` - seul `calibration_df`, filtre temporellement, l'est."""
    lam_col, mu_col = f"{model}_lambda", f"{model}_mu"
    sub = test_df.dropna(subset=[lam_col, mu_col]).sort_values("decision_time").copy()

    scales: list[float | None] = []
    n_used: list[int] = []
    for as_of in sub["decision_time"]:
        c, n = fit_scale_correction_as_of(calibration_df, model, as_of)
        scales.append(c)
        n_used.append(n)
    sub["scale_c"] = scales
    sub["n_calibration_used"] = n_used
    return sub


# --------------------------------------------------------------------------
# Metriques Over/Under derivees (Brier, log loss, biais, calibration,
# resolution) - toutes deja des briques existantes reutilisees SANS
# MODIFICATION (`_calibration_weighted_error`, `brier_decomposition`).
# --------------------------------------------------------------------------


def _ou_metrics(p: np.ndarray, y: np.ndarray, calibration_weighted_error) -> dict:
    eps = 1e-12
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    brier = float(np.mean((p - y) ** 2))
    ll = float(np.mean(-(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))))
    biais = float(np.mean(p - y))
    cal = calibration_weighted_error(p, y)
    resolution = brier_decomposition(p, y)["resolution"]
    return {"brier": brier, "log_loss": ll, "biais": biais, "calibration": cal, "resolution": resolution}


# --------------------------------------------------------------------------
# ETAPE 7 - evaluation walk-forward complete (brut vs corrige) sur un
# sous-ensemble de test deja muni de `scale_c` (matchs insuffisants exclus).
# --------------------------------------------------------------------------


def evaluate_walk_forward(df_with_scale: pd.DataFrame, model: str, e7_module) -> dict:
    """Evalue RAW (scale=1.0, toujours) vs CORRIGE walk-forward (scale=
    `scale_c` PROPRE A CHAQUE MATCH) sur les matchs non exclus
    (`scale_c` non nul). Reutilise `matrix_for_row`/`total_goals_distribution`/
    `over_under_probs` d'E7 SANS MODIFICATION."""
    included = df_with_scale[df_with_scale["scale_c"].notna()].copy()
    n_excluded = int(len(df_with_scale) - len(included))

    raw_dists, corr_dists = [], []
    raw_ou = {t: [] for t in _OU_THRESHOLDS}
    corr_ou = {t: [] for t in _OU_THRESHOLDS}
    for _, row in included.iterrows():
        m_raw = e7_module.matrix_for_row(row, model, scale=1.0)
        m_corr = e7_module.matrix_for_row(row, model, scale=float(row["scale_c"]))
        raw_dists.append(e7_module.total_goals_distribution(m_raw))
        corr_dists.append(e7_module.total_goals_distribution(m_corr))
        ou_raw = e7_module.over_under_probs(m_raw)
        ou_corr = e7_module.over_under_probs(m_corr)
        for t in _OU_THRESHOLDS:
            raw_ou[t].append(ou_raw[t])
            corr_ou[t].append(ou_corr[t])

    raw_dists = np.array(raw_dists)
    corr_dists = np.array(corr_dists)
    outcomes = np.clip(included["total_goals"].to_numpy(), 0, _MAX_BUCKET)

    brier_raw = brier_score(raw_dists, outcomes)
    brier_corr = brier_score(corr_dists, outcomes)
    logloss_raw = log_loss(raw_dists, outcomes)
    logloss_corr = log_loss(corr_dists, outcomes)

    expected_total_raw = raw_dists @ np.arange(raw_dists.shape[1])
    expected_total_corr = corr_dists @ np.arange(corr_dists.shape[1])
    actual_total = included["total_goals"].to_numpy()

    bias_raw = float((expected_total_raw - actual_total).mean())
    bias_corr = float((expected_total_corr - actual_total).mean())
    mae_raw = float(np.abs(expected_total_raw - actual_total).mean())
    mae_corr = float(np.abs(expected_total_corr - actual_total).mean())

    tail_predicted_raw = float(raw_dists[:, _MAX_BUCKET].mean())
    tail_predicted_corr = float(corr_dists[:, _MAX_BUCKET].mean())
    tail_observed = float((actual_total >= _MAX_BUCKET).mean())

    one_hot = np.eye(_MAX_BUCKET + 1)[outcomes.astype(int)]
    diffs_brier = np.sum((corr_dists - one_hot) ** 2, axis=1) - np.sum((raw_dists - one_hot) ** 2, axis=1)
    boot_brier = paired_bootstrap_test(diffs_brier, n_resamples=_N_RESAMPLES, seed=_SEED)

    eps = 1e-12
    logloss_raw_row = -np.log(np.clip(raw_dists[np.arange(len(outcomes)), outcomes.astype(int)], eps, 1.0))
    logloss_corr_row = -np.log(np.clip(corr_dists[np.arange(len(outcomes)), outcomes.astype(int)], eps, 1.0))
    diffs_logloss = logloss_corr_row - logloss_raw_row
    boot_logloss = paired_bootstrap_test(diffs_logloss, n_resamples=_N_RESAMPLES, seed=_SEED)

    ou_results = {}
    for t in _OU_THRESHOLDS:
        y_bin = (actual_total > t).astype(float)
        p_raw = np.array(raw_ou[t])
        p_corr = np.array(corr_ou[t])
        raw_m = _ou_metrics(p_raw, y_bin, e7_module._calibration_weighted_error)
        corr_m = _ou_metrics(p_corr, y_bin, e7_module._calibration_weighted_error)
        diffs_ou_brier = (p_corr - y_bin) ** 2 - (p_raw - y_bin) ** 2
        boot_ou = paired_bootstrap_test(diffs_ou_brier, n_resamples=_N_RESAMPLES, seed=_SEED)
        ou_results[t] = {"raw": raw_m, "corr": corr_m, "boot_brier": boot_ou}

    return {
        "n": len(included),
        "n_excluded": n_excluded,
        "brier_raw": brier_raw,
        "brier_corr": brier_corr,
        "logloss_raw": logloss_raw,
        "logloss_corr": logloss_corr,
        "bias_raw": bias_raw,
        "bias_corr": bias_corr,
        "mae_raw": mae_raw,
        "mae_corr": mae_corr,
        "tail_predicted_raw": tail_predicted_raw,
        "tail_predicted_corr": tail_predicted_corr,
        "tail_observed": tail_observed,
        "boot_brier_corr_minus_raw": boot_brier,
        "boot_logloss_corr_minus_raw": boot_logloss,
        "ou_results": ou_results,
    }


# --------------------------------------------------------------------------
# ETAPE 6 - stabilite chronologique du facteur c(m)
# --------------------------------------------------------------------------


def summarize_scale_stability(df_with_scale: pd.DataFrame) -> dict:
    """Statistiques descriptives PURES sur la serie `scale_c(m)` deja
    calculee - aucune optimisation, aucun recalcul different."""
    included = df_with_scale[df_with_scale["scale_c"].notna()]
    values = included["scale_c"].to_numpy(dtype=float)
    if values.size == 0:
        return {"n": 0}
    overall = {
        "n": int(values.size),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "std": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "min": float(values.min()),
        "max": float(values.max()),
    }
    overall["coefficient_of_variation"] = overall["std"] / overall["mean"] if overall["mean"] != 0 else float("nan")

    by_season = {}
    if "season" in included.columns:
        for season in sorted(included["season"].unique()):
            v = included.loc[included["season"] == season, "scale_c"].to_numpy(dtype=float)
            if v.size == 0:
                continue
            by_season[season] = {
                "n": int(v.size),
                "mean": float(v.mean()),
                "median": float(np.median(v)),
                "std": float(v.std(ddof=1)) if v.size > 1 else 0.0,
                "min": float(v.min()),
                "max": float(v.max()),
            }
    overall["by_season"] = by_season
    return overall


# --------------------------------------------------------------------------
# ETAPE 10 - grille de verdict (definie AVANT observation des resultats)
# --------------------------------------------------------------------------


def classify_verdict_e8(global_boot: dict, scope_boots: list[dict], scale_stability: dict) -> str:
    """Applique mecaniquement la grille A/B/C definie dans le docstring du
    module, AVANT observation des resultats reels."""
    global_ci_low, global_ci_high = global_boot["ci_low"], global_boot["ci_high"]
    any_scope_inversion = any(s["ci_low"] > 0.0 for s in scope_boots)
    cv = scale_stability.get("coefficient_of_variation", float("nan"))
    cv_high = (not np.isnan(cv)) and cv >= 0.10

    if global_ci_low > 0.0:
        return "C - VALIDATION ECHOUEE"

    global_improved = global_ci_high <= 0.0
    if not global_improved:
        # absence de preuve globale : verifier si TOUTES les decoupes sont aussi sans preuve/inversees
        any_scope_improved = any(s["ci_high"] <= 0.0 for s in scope_boots)
        if not any_scope_improved:
            return "C - VALIDATION ECHOUEE"
        return "B - VALIDATION PARTIELLE"

    if any_scope_inversion or cv_high:
        return "B - VALIDATION PARTIELLE"

    return "A - VALIDATION REUSSIE"


def _print_evaluation(label: str, res: dict) -> None:
    typer.echo(f"  -- {label} (n={res['n']}, exclus={res['n_excluded']}) --")
    typer.echo(
        f"    Brier(7cat)   raw={res['brier_raw']:.4f}  corrige={res['brier_corr']:.4f}  "
        f"diff(IC95%)=[{res['boot_brier_corr_minus_raw']['ci_low']:+.4f}, "
        f"{res['boot_brier_corr_minus_raw']['ci_high']:+.4f}] p={res['boot_brier_corr_minus_raw']['p_value']:.4f}"
    )
    typer.echo(
        f"    log loss(7cat) raw={res['logloss_raw']:.4f}  corrige={res['logloss_corr']:.4f}  "
        f"diff(IC95%)=[{res['boot_logloss_corr_minus_raw']['ci_low']:+.4f}, "
        f"{res['boot_logloss_corr_minus_raw']['ci_high']:+.4f}]"
    )
    typer.echo(f"    biais E[Total] raw={res['bias_raw']:+.4f}  corrige={res['bias_corr']:+.4f}")
    typer.echo(f"    MAE E[Total]   raw={res['mae_raw']:.4f}  corrige={res['mae_corr']:.4f}")
    typer.echo(
        f"    queue P(>=6) predite raw={res['tail_predicted_raw']:.4f}  corrigee={res['tail_predicted_corr']:.4f}  "
        f"observee={res['tail_observed']:.4f}"
    )
    for t, ou in res["ou_results"].items():
        r, c, b = ou["raw"], ou["corr"], ou["boot_brier"]
        typer.echo(
            f"    Over {t} : Brier raw={r['brier']:.4f} corr={c['brier']:.4f} diff(IC95%)=[{b['ci_low']:+.4f},{b['ci_high']:+.4f}] "
            f"| logloss raw={r['log_loss']:.4f} corr={c['log_loss']:.4f} "
            f"| biais raw={r['biais']:+.4f} corr={c['biais']:+.4f} "
            f"| calib raw={r['calibration']:.4f} corr={c['calibration']:.4f} "
            f"| resolution raw={r['resolution']:.4f} corr={c['resolution']:.4f}"
        )


@app.command()
def main() -> None:
    typer.echo("=== E8 : validation walk-forward hors echantillon de la distribution corrigee (E7) ===")
    typer.echo(
        "poisson_simple, dixon_coles et xg_model INCHANGES. Aucune nouvelle methode de calibration. "
        "Aucune conclusion de rentabilite.\n"
    )

    e7 = _load_e7()
    stage10 = e7._load_stage10()
    stage8 = stage10._load_stage8()

    df = e7.build_lambda_mu_dataframe(stage8)
    decision_time = build_decision_time_lookup(stage8)
    df["decision_time"] = df["match_id"].map(decision_time)

    calibration_df_stage8, test_df_stage8 = stage10.build_calibration_and_test_sets(stage8)
    calibration_ids = set(calibration_df_stage8["match_id"])
    test_ids = set(test_df_stage8["match_id"])
    calibration_df = df[df["match_id"].isin(calibration_ids)].copy()
    test_df = df[df["match_id"].isin(test_ids)].copy()

    typer.echo(f"n_calibration (pooled, protocole inchange) : {len(calibration_df)}")
    typer.echo(f"n_test (pooled, protocole inchange)        : {len(test_df)}\n")

    verdicts = {}
    for model in _MODELS:
        typer.echo(f"##### {model} #####")
        with_scale = attach_walk_forward_scale(calibration_df, test_df, model)

        stability = summarize_scale_stability(with_scale)
        typer.echo("--- ETAPE 6 : stabilite chronologique du facteur c(m) ---")
        if stability["n"] > 0:
            typer.echo(
                f"  n={stability['n']}  moyenne={stability['mean']:.4f}  mediane={stability['median']:.4f}  "
                f"ecart-type={stability['std']:.4f}  min={stability['min']:.4f}  max={stability['max']:.4f}  "
                f"CV={stability['coefficient_of_variation']:.4f}"
            )
            for season, s in stability["by_season"].items():
                typer.echo(
                    f"    saison {season} : n={s['n']} moyenne={s['mean']:.4f} mediane={s['median']:.4f} "
                    f"ecart-type={s['std']:.4f} min={s['min']:.4f} max={s['max']:.4f}"
                )
        typer.echo("")

        typer.echo("=== GLOBAL (TEST, walk-forward) ===")
        global_res = evaluate_walk_forward(with_scale, model, e7)
        _print_evaluation("GLOBAL", global_res)

        scope_boots = []
        typer.echo("=== Par championnat (TEST, walk-forward) ===")
        for league in sorted(test_df["league"].unique()):
            sub_scale = with_scale[with_scale["league"] == league]
            res = evaluate_walk_forward(sub_scale, model, e7)
            _print_evaluation(league, res)
            scope_boots.append(res["boot_brier_corr_minus_raw"])

        typer.echo("=== Par saison (TEST, walk-forward) ===")
        for season in sorted(test_df["season"].unique()):
            sub_scale = with_scale[with_scale["season"] == season]
            res = evaluate_walk_forward(sub_scale, model, e7)
            _print_evaluation(season, res)
            scope_boots.append(res["boot_brier_corr_minus_raw"])

        verdict = classify_verdict_e8(global_res["boot_brier_corr_minus_raw"], scope_boots, stability)
        verdicts[model] = verdict
        typer.echo(f"\n  -> VERDICT {model} : {verdict}\n")

    typer.echo("=== VERDICTS (grille A/B/C definie avant observation des resultats) ===")
    for model, v in verdicts.items():
        typer.echo(f"  {model:<16} -> {v}")

    typer.echo(
        "\nRESERVE : aucune conclusion de rentabilite. Aucune regle de pari, ROI, yield, Kelly, "
        "staking, seuil de cote, optimisation de value, selection de bookmaker, arbitrage. "
        "poisson_simple, dixon_coles et xg_model restent inchanges."
    )
    typer.echo("\nARRET : E8 termine, conformement au protocole. Aucune experience suivante lancee automatiquement.")


if __name__ == "__main__":
    app()
