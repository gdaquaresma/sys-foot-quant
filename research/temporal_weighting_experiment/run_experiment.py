"""Script d'orchestration de l'experience de ponderation temporelle -
recherche isolee, JAMAIS importee par final_engine/scripts/predict_match.py.

Repond a UNE question : la ponderation temporelle (A1-A5, decroissance
exponentielle demi-vie 30/60/90/180/365 jours) ameliore-t-elle la
prediction Over/Under 2.5 hors echantillon walk-forward, par rapport au
modele de production actuel a poids egal (A0) ?

Reutilise SANS MODIFICATION : multi_season_dataset (deja cree, deja
teste), weighted_walkforward (ce paquet), calibration_engine.significance
(paired_bootstrap_test), calibration_engine.decomposition/reliability
(brier_decomposition/reliability_bins), final_engine.market
(compare_over_under_to_market, pour l'analyse Brest-PSG uniquement -
AUCUNE modification de final_engine/, uniquement un appel a une fonction
deja exportee)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from sys_foot_quant.calibration_engine.decomposition import brier_decomposition
from sys_foot_quant.calibration_engine.reliability import reliability_bins
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test
from sys_foot_quant.data_engine.market_odds.future_match_dataset import build_match_train_dataframes
from sys_foot_quant.data_engine.market_odds.multi_season_dataset import (
    build_real_match_records_multi_season,
)
from sys_foot_quant.final_engine.market import compare_over_under_to_market
from sys_foot_quant.football_model.goal_distribution import over_under_probs
from sys_foot_quant.football_model.poisson import PoissonModel
from sys_foot_quant.football_model.scoring import score_matrix

from research.temporal_weighting_experiment.weighted_walkforward import (
    ALL_SCHEMES,
    DECAY_SCHEMES,
    FLAT_SCHEME,
    binary_brier_score,
    binary_log_loss,
    compute_weights_for_scheme,
    run_walkforward,
)

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "research/xg_feasibility/runs"

CORPORA = {
    "ligue1": ("Ligue_1", [RUNS / "ligue1_2024_datesData.json", RUNS / "ligue1_2025_datesData.json", RUNS / "ligue1_2026_datesData.json"]),
    "liga": ("La_liga", [RUNS / "liga_2024_datesData.json", RUNS / "liga_2025_datesData.json"]),
    "premier_league": ("EPL", [RUNS / "epl_2024_datesData.json", RUNS / "epl_2025_datesData.json"]),
}


def _load(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def build_all_walkforward_results() -> pd.DataFrame:
    frames = []
    for competition, (league_id, paths) in CORPORA.items():
        sources = [(_load(p), league_id) for p in paths]
        records = build_real_match_records_multi_season(sources)
        df = run_walkforward(records)
        df["competition"] = competition
        frames.append(df)
        print(f"{competition}: {len(records)} matchs charges, {len(df)} lignes walk-forward")
    return pd.concat(frames, ignore_index=True)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y = df["y_over_2_5"].to_numpy()
    for scheme in ALL_SCHEMES:
        col = f"p_over_2_5_{scheme.name}"
        mask = df[col].notna()
        p = df.loc[mask, col].to_numpy()
        y_m = y[mask.to_numpy()]
        n = len(p)
        brier_vec = binary_brier_score(p, y_m)
        logloss_vec = binary_log_loss(p, y_m)
        decomp = brier_decomposition(p, y_m, n_bins=10)
        rows.append(
            {
                "scheme": scheme.name,
                "half_life_days": scheme.half_life_days,
                "n": n,
                "brier_mean": float(brier_vec.mean()),
                "log_loss_mean": float(logloss_vec.mean()),
                "reliability": decomp["reliability"],
                "resolution": decomp["resolution"],
                "uncertainty": decomp["uncertainty"],
                "coverage": n / len(df),
                "mean_predicted_p": float(p.mean()),
                "observed_frequency": float(y_m.mean()),
            }
        )
    return pd.DataFrame(rows)


def paired_tests_vs_flat(df: pd.DataFrame) -> pd.DataFrame:
    y = df["y_over_2_5"].to_numpy()
    flat_col = f"p_over_2_5_{FLAT_SCHEME.name}"
    mask_flat = df[flat_col].notna()
    rows = []
    for scheme in DECAY_SCHEMES:
        col = f"p_over_2_5_{scheme.name}"
        mask = mask_flat & df[col].notna()
        p_flat = df.loc[mask, flat_col].to_numpy()
        p_scheme = df.loc[mask, col].to_numpy()
        y_m = y[mask.to_numpy()]
        brier_diff = binary_brier_score(p_scheme, y_m) - binary_brier_score(p_flat, y_m)
        logloss_diff = binary_log_loss(p_scheme, y_m) - binary_log_loss(p_flat, y_m)
        brier_test = paired_bootstrap_test(brier_diff, seed=42)
        logloss_test = paired_bootstrap_test(logloss_diff, seed=42)
        rows.append(
            {
                "scheme": scheme.name,
                "n_paired": mask.sum(),
                "brier_mean_diff_vs_A0": brier_test["mean_diff"],
                "brier_ci_low": brier_test["ci_low"],
                "brier_ci_high": brier_test["ci_high"],
                "brier_p_value": brier_test["p_value"],
                "logloss_mean_diff_vs_A0": logloss_test["mean_diff"],
                "logloss_ci_low": logloss_test["ci_low"],
                "logloss_ci_high": logloss_test["ci_high"],
                "logloss_p_value": logloss_test["p_value"],
            }
        )
    return pd.DataFrame(rows)


def regime_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Decoupe descriptive par tiers chronologiques (debut/milieu/fin),
    PAR competition (jamais mele entre competitions - meme discipline que
    le reste du projet). Analyse secondaire, ne remplace pas le resultat
    global."""
    rows = []
    for competition in df["competition"].unique():
        sub = df[(df["competition"] == competition) & df[f"p_over_2_5_{FLAT_SCHEME.name}"].notna()].copy()
        if len(sub) < 30:
            continue
        sub = sub.sort_values("kickoff_utc")
        thirds = np.array_split(sub.index, 3)
        labels = ["debut", "milieu", "fin"]
        y = sub["y_over_2_5"].to_numpy()
        for label, idx in zip(labels, thirds):
            part = sub.loc[idx]
            y_part = part["y_over_2_5"].to_numpy()
            for scheme in ALL_SCHEMES:
                p = part[f"p_over_2_5_{scheme.name}"].to_numpy()
                rows.append(
                    {
                        "competition": competition,
                        "regime": label,
                        "scheme": scheme.name,
                        "n": len(p),
                        "brier_mean": float(binary_brier_score(p, y_part).mean()),
                    }
                )
    return pd.DataFrame(rows)


def brest_psg_analysis() -> pd.DataFrame:
    """Analyse SCIENTIFIQUE retrospective uniquement - PAS une decision de
    pari (voir rapport). Meme decision_time deja utilise precedemment
    (kickoff - 2h = 16:45 UTC)."""
    league_id, paths = CORPORA["ligue1"]
    sources = [(_load(p), league_id) for p in paths]
    current_records = build_real_match_records_multi_season(sources)

    BREST_ID, PSG_ID = 241, 161
    KICKOFF_UTC = datetime(2026, 9, 13, 18, 45, 0)
    DECISION_OFFSET_HOURS = 2.0
    decision_time = KICKOFF_UTC - timedelta(hours=DECISION_OFFSET_HOURS)

    goals_train_df, _ = build_match_train_dataframes(
        current_records, home_team_id=BREST_ID, away_team_id=PSG_ID, decision_time=decision_time,
        exclude_match_id="brest-psg-2026-09-13",
    )

    rows = []
    for scheme in ALL_SCHEMES:
        weights = compute_weights_for_scheme(goals_train_df["kickoff_time"], decision_time, scheme)
        model = PoissonModel(use_team_hfa=False).fit(goals_train_df, weights=weights)
        lam, mu = model.predict_lambda_mu(BREST_ID, PSG_ID)
        matrix = score_matrix(lam, mu, max_goals=20)
        p_over = over_under_probs(matrix, thresholds=(2.5,))[2.5]
        fair_odds = 1.0 / p_over if p_over > 0 else float("inf")
        market = compare_over_under_to_market(p_over, 1.32, 2.92)
        rows.append(
            {
                "scheme": scheme.name,
                "lambda_brest": lam,
                "lambda_psg": mu,
                "total_lambda": lam + mu,
                "p_over_2_5": p_over,
                "fair_odds_over_2_5": fair_odds,
                "market_overround": market.market_overround,
                "raw_edge_over": market.raw_edge["Over"],
                "price_edge_over": market.price_edge["Over"],
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("=== Chargement + walk-forward (3 competitions) ===")
    df_all = build_all_walkforward_results()
    df_all.to_csv(Path(__file__).parent / "walkforward_raw_results.csv", index=False)

    print("\n=== Resume par schema ===")
    summary = summarize(df_all)
    print(summary.to_string(index=False))
    summary.to_csv(Path(__file__).parent / "summary_by_scheme.csv", index=False)

    print("\n=== Tests apparies vs A0 (flat) ===")
    tests_df = paired_tests_vs_flat(df_all)
    print(tests_df.to_string(index=False))
    tests_df.to_csv(Path(__file__).parent / "paired_tests_vs_flat.csv", index=False)

    print("\n=== Analyse par regime (debut/milieu/fin de saison) ===")
    regime_df = regime_analysis(df_all)
    print(regime_df.to_string(index=False))
    regime_df.to_csv(Path(__file__).parent / "regime_analysis.csv", index=False)

    print("\n=== Analyse Brest-PSG (retrospective, PAS une decision de pari) ===")
    bp_df = brest_psg_analysis()
    print(bp_df.to_string(index=False))
    bp_df.to_csv(Path(__file__).parent / "brest_psg_analysis.csv", index=False)
