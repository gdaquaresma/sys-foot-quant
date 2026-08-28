"""CLI : E5 - fiabilite des probabilites Over 2.5 CALIBREES dans les
situations de DESACCORD avec le marche B365.

Question centrale : quand notre modele et B365 donnent des probabilites
differentes pour Over 2.5, notre probabilite est-elle encore fiable dans
les situations de desaccord ? PAS "le modele gagne-t-il de l'argent" -
"le modele reste-t-il calibre quand son opinion diverge du marche ?"

`poisson_simple` et `xg_model` restent INCHANGES. Aucun nouveau modele.
La calibration isotone est ajustee UNIQUEMENT sur la partie calibration
du decoupage deja existant (reutilise `fit_isotonic_calibration`,
INCHANGEE, E2/E3), puis appliquee au test - jamais l'inverse.

Donnees marche : B365 Over/Under 2.5 uniquement (extension documentee de
`football_data_loader.py`/ADR 0006 - AUCUNE colonne de cloture, AUCUN
autre bookmaker). Appariement et point-in-time REUTILISES SANS
MODIFICATION (`over_under_odds.py`, meme mecanisme que E1). Tout match
sans cote B365 O/U point-in-time valide est exclu et compte
explicitement (jour ambigu, cotes incompletes, non apparie).

Probabilite de marche : retrait d'overround proportionnel
(`market_engine.overround.remove_overround_proportional`, INCHANGE) -
formule deja existante du projet : implied_brut = 1/cote pour chaque
issue, puis normalisation a somme 1 (implied_brut / somme des
implied_bruts).

Desaccord : `model_market_gap = P_model_calibrated - P_market_normalized`,
en points de probabilite. Tranches FIXEES avant execution : <=-15,
-15/-10, -10/-5, -5/+5, +5/+10, +10/+15, >=+15. Jamais modifiees apres
observation des resultats.

Pour chaque tranche : n, probabilite moyenne annoncee (modele), frequence
reelle d'Over 2.5, diff = reel - annonce ; Brier modele/marche et
IC95% bootstrap (`paired_bootstrap_test`, INCHANGE) sur
Brier_modele - Brier_marche ; part du test dans chaque tranche
(concentration). Analyse symetrique (desaccords positifs ET negatifs).

Aucune cote de value, aucun ROI, aucun CLV, aucune selection de pari,
aucune optimisation de seuil, aucun nouveau modele.

Usage:
    python scripts/run_stage13_e5_model_market_agreement_over25.py
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

from sys_foot_quant.calibration_engine.isotonic_calibration import fit_isotonic_calibration  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402
from sys_foot_quant.data_engine.market_odds.over_under_odds import build_over_under_25_dataset  # noqa: E402
from sys_foot_quant.market_engine.overround import remove_overround_proportional  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_MODELS = ("poisson_simple", "xg_model")
_N_RESAMPLES = 10_000
_SEED = 0
_MIN_N_FOR_LOW_UNCERTAINTY = 30  # seuil documente, pas un fait statistique universel

# Tranches de desaccord FIXEES AVANT EXECUTION (points de probabilite / 100)
_GAP_EDGES = [-np.inf, -0.15, -0.10, -0.05, 0.05, 0.10, 0.15, np.inf]
_GAP_LABELS = ["<=-15pts", "-15/-10", "-10/-5", "-5/+5", "+5/+10", "+10/+15", ">=+15pts"]

_FD_DIR = Path("research/market_odds/football_data/runs")
_US_DIR = Path("research/xg_feasibility/runs")
_DATASETS = {
    ("premier_league", "2024_25"): ("epl_2024_datesData.json", "E0_2024_25.csv"),
    ("premier_league", "2025_26"): ("epl_2025_datesData.json", "E0_2025_26.csv"),
    ("ligue1", "2024_25"): ("ligue1_2024_datesData.json", "F1_2024_25.csv"),
    ("ligue1", "2025_26"): ("ligue1_2025_datesData.json", "F1_2025_26.csv"),
    ("liga", "2024_25"): ("liga_2024_datesData.json", "SP1_2024_25.csv"),
    ("liga", "2025_26"): ("liga_2025_datesData.json", "SP1_2025_26.csv"),
}

_STAGE10_PATH = Path(__file__).resolve().parent / "run_stage10_over_under_recalibration.py"


def _load_stage10():
    spec = importlib.util.spec_from_file_location("run_stage10_over_under_recalibration", _STAGE10_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_pooled_over_under_odds() -> tuple[dict[str, tuple[float, float]], dict[str, int]]:
    """Construit, pour les 6 championnats x saisons, les cotes B365
    Over/Under 2.5 point-in-time valides (``over_under_odds.py``,
    INCHANGE) - retourne {match_id: (b365_over, b365_under)} et un
    resume des exclusions agregees."""
    odds_by_match_id: dict[str, tuple[float, float]] = {}
    totals = {
        "n_understat": 0, "n_matched": 0, "n_excluded_ambiguous_weekday": 0,
        "n_excluded_incomplete_odds": 0, "n_excluded_pit_violation": 0,
        "n_unmatched_understat": 0, "n_exploitable": 0,
    }
    for (league, season), (us_name, fd_name) in _DATASETS.items():
        with open(_US_DIR / us_name) as f:
            raw = json.load(f)
        fd_records = load_football_data_csv(_FD_DIR / fd_name, league=league, season=season)
        report = build_over_under_25_dataset(league, season, raw, fd_records)
        for r in report.records:
            odds_by_match_id[r.match_id] = (r.b365_over_2_5, r.b365_under_2_5)
        for key in totals:
            totals[key] += getattr(report, key)
    return odds_by_match_id, totals


def compute_calibrated_probs(calibration_df: pd.DataFrame, test_df: pd.DataFrame, model: str) -> pd.Series:
    """Ajuste la courbe isotonique UNIQUEMENT sur la calibration
    (`fit_isotonic_calibration`, INCHANGEE), l'applique au test - reproduit
    exactement le calcul deja fait par
    `run_stage10_over_under_recalibration.evaluate_recalibration` pour
    Over 2.5, en conservant `match_id` (necessaire pour joindre les cotes
    marche, absent du retour agrege de stage10)."""
    col = f"{model}_p_over_2.5"
    calib = calibration_df.dropna(subset=[col])
    curve = fit_isotonic_calibration(
        calib[col].to_numpy(), (calib["total_goals"] > 2.5).astype(float).to_numpy()
    )
    test = test_df.dropna(subset=[col])
    p_after = curve.predict(test[col].to_numpy())
    return pd.Series(p_after, index=test["match_id"].to_numpy())


def build_agreement_dataframe(
    p_model_calibrated: pd.Series, test_df: pd.DataFrame, odds_by_match_id: dict[str, tuple[float, float]]
) -> tuple[pd.DataFrame, dict]:
    """Joint probabilite modele CALIBREE, probabilite marche normalisee
    (overround retire, formule INCHANGEE) et resultat reel, par match_id.
    Tout match sans cote O/U point-in-time valide est exclu et compte."""
    total_goals_by_id = test_df.set_index("match_id")["total_goals"]
    rows = []
    n_excluded_no_market_odds = 0
    for match_id, p_model in p_model_calibrated.items():
        if match_id not in odds_by_match_id:
            n_excluded_no_market_odds += 1
            continue
        b365_over, b365_under = odds_by_match_id[match_id]
        normalized = remove_overround_proportional({"over": b365_over, "under": b365_under})
        p_market = normalized["over"]
        outcome = float(total_goals_by_id.loc[match_id] > 2.5)
        rows.append(
            {
                "match_id": match_id,
                "p_model": float(p_model),
                "p_market": float(p_market),
                "gap": float(p_model) - float(p_market),
                "outcome": outcome,
            }
        )
    df = pd.DataFrame(rows)
    return df, {"n_excluded_no_market_odds": n_excluded_no_market_odds, "n_joined": len(df)}


def gap_bin_table(df: pd.DataFrame) -> pd.DataFrame:
    cats = pd.cut(df["gap"], bins=_GAP_EDGES, labels=_GAP_LABELS, right=False)
    rows = []
    for label in _GAP_LABELS:
        mask = cats == label
        n = int(mask.sum())
        if n == 0:
            rows.append(
                {"tranche": label, "n": 0, "p_model_moy": float("nan"), "frequence_over_reelle": float("nan"), "diff": float("nan")}
            )
            continue
        p_model_moy = float(df.loc[mask, "p_model"].mean())
        freq = float(df.loc[mask, "outcome"].mean())
        rows.append({"tranche": label, "n": n, "p_model_moy": p_model_moy, "frequence_over_reelle": freq, "diff": freq - p_model_moy})
    return pd.DataFrame(rows)


def brier_comparison_by_bin(df: pd.DataFrame) -> pd.DataFrame:
    cats = pd.cut(df["gap"], bins=_GAP_EDGES, labels=_GAP_LABELS, right=False)
    rows = []
    for label in _GAP_LABELS:
        mask = (cats == label).to_numpy()
        n = int(mask.sum())
        if n == 0:
            rows.append(
                {"tranche": label, "n": 0, "brier_model": float("nan"), "brier_market": float("nan"), "diff_moy": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "p_value": float("nan"), "incertitude_elevee": True}
            )
            continue
        p_model = df.loc[mask, "p_model"].to_numpy()
        p_market = df.loc[mask, "p_market"].to_numpy()
        y = df.loc[mask, "outcome"].to_numpy()
        brier_model_row = (p_model - y) ** 2
        brier_market_row = (p_market - y) ** 2
        diffs = brier_model_row - brier_market_row
        boot = paired_bootstrap_test(diffs, n_resamples=_N_RESAMPLES, seed=_SEED) if n >= 2 else {
            "mean_diff": float(diffs.mean()) if n else float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "p_value": float("nan")
        }
        rows.append(
            {
                "tranche": label,
                "n": n,
                "brier_model": float(brier_model_row.mean()),
                "brier_market": float(brier_market_row.mean()),
                "diff_moy": boot["mean_diff"],
                "ci_low": boot["ci_low"],
                "ci_high": boot["ci_high"],
                "p_value": boot["p_value"],
                "incertitude_elevee": n < _MIN_N_FOR_LOW_UNCERTAINTY,
            }
        )
    return pd.DataFrame(rows)


def concentration_table(df: pd.DataFrame) -> pd.DataFrame:
    """Partie 10 : proportion du test dans chaque tranche de desaccord."""
    cats = pd.cut(df["gap"], bins=_GAP_EDGES, labels=_GAP_LABELS, right=False)
    total = len(df)
    rows = []
    for label in _GAP_LABELS:
        n = int((cats == label).sum())
        rows.append({"tranche": label, "n": n, "part_du_test": (n / total) if total else float("nan")})
    return pd.DataFrame(rows)


@app.command()
def main() -> None:
    typer.echo("=== E5 : fiabilite des probabilites Over 2.5 calibrees dans les situations de desaccord avec B365 ===")
    typer.echo(
        "poisson_simple et xg_model INCHANGES. Question : le modele reste-t-il calibre quand son "
        "opinion diverge du marche ? (PAS un test de rentabilite).\n"
    )

    stage10 = _load_stage10()
    stage8 = stage10._load_stage8()
    calibration_df, test_df = stage10.build_calibration_and_test_sets(stage8)
    typer.echo(f"n_calibration={len(calibration_df)}  n_test={len(test_df)}")

    odds_by_match_id, market_totals = build_pooled_over_under_odds()
    typer.echo(
        f"Cotes B365 Over/Under 2.5 point-in-time exploitables (tous championnats/saisons) : "
        f"{market_totals['n_exploitable']} / {market_totals['n_understat']} "
        f"(jour ambigu exclu={market_totals['n_excluded_ambiguous_weekday']}, "
        f"cotes incompletes exclues={market_totals['n_excluded_incomplete_odds']}, "
        f"violation PIT exclue={market_totals['n_excluded_pit_violation']}, "
        f"non apparies={market_totals['n_unmatched_understat']})\n"
    )

    for model in _MODELS:
        typer.echo(f"##### {model} (calibre) #####")
        p_model_calibrated = compute_calibrated_probs(calibration_df, test_df, model)
        df, join_info = build_agreement_dataframe(p_model_calibrated, test_df, odds_by_match_id)
        typer.echo(
            f"  n matchs test avec probabilite calibree : {len(p_model_calibrated)} ; "
            f"exclus (pas de cote O/U point-in-time) : {join_info['n_excluded_no_market_odds']} ; "
            f"joints (analyse finale) : {join_info['n_joined']}\n"
        )

        typer.echo("  -- Tranches de desaccord (model_market_gap = P_model - P_marche) --")
        gt = gap_bin_table(df)
        for _, row in gt.iterrows():
            if row["n"] == 0:
                typer.echo(f"    {row['tranche']:<10} n=0")
                continue
            typer.echo(
                f"    {row['tranche']:<10} n={int(row['n']):<5} p_model_moy={row['p_model_moy']:.3f} "
                f"frequence_over_reelle={row['frequence_over_reelle']:.3f} diff(reel-annonce)={row['diff']:+.3f}"
            )

        typer.echo("  -- Comparaison Brier modele/marche par tranche (caracterisation, PAS un test 'battre le marche') --")
        bt = brier_comparison_by_bin(df)
        for _, row in bt.iterrows():
            if row["n"] == 0:
                typer.echo(f"    {row['tranche']:<10} n=0")
                continue
            flag = " [INCERTITUDE ELEVEE, n faible]" if row["incertitude_elevee"] else ""
            typer.echo(
                f"    {row['tranche']:<10} n={int(row['n']):<5} brier_model={row['brier_model']:.4f} "
                f"brier_market={row['brier_market']:.4f} diff_moy={row['diff_moy']:+.4f} "
                f"IC95%=[{row['ci_low']:+.4f}, {row['ci_high']:+.4f}] p={row['p_value']:.4f}{flag}"
            )

        typer.echo("  -- Concentration (part du test par tranche) --")
        ct = concentration_table(df)
        for _, row in ct.iterrows():
            typer.echo(f"    {row['tranche']:<10} n={int(row['n']):<5} part={row['part_du_test']*100:.1f}%")
        typer.echo("")

    typer.echo(
        "RESERVE : aucune conclusion de value/rentabilite. Formule de marche INCHANGEE "
        "(implied=1/cote, normalisation proportionnelle a somme 1, market_engine.overround). "
        "Aucun nouveau modele, aucune modification de poisson_simple/xg_model."
    )
    typer.echo("\nARRET : E5 termine, conformement au protocole.")


if __name__ == "__main__":
    app()
