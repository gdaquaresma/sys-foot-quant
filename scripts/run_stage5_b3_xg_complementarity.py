"""CLI : analyse de COMPLEMENTARITE entre `poisson_simple` (buts reels) et
`XGModel` (xG) - PAS un nouveau test de superiorite (deja fait, verdict
INDETERMINE, voir docs/research_framework.md section B3).

Question posee ici, differente de celle de B3 : le xG apporte-t-il une
information suffisamment DIFFERENTE des buts reels pour justifier de
conserver les deux modeles, independamment du fait qu'aucun des deux ne
batte significativement l'autre pris seul ? Aucune combinaison n'est
implementee dans ce script - seulement une analyse, conformement a la
demande explicite de l'utilisateur (une decision methodologique sur la
forme d'une eventuelle combinaison doit etre validee AVANT tout code).

Ni `poisson_simple`, ni `XGModel`, ni les datasets, ni le protocole de
scission chronologique de B3 ne sont modifies : les constantes ci-dessous
(fractions de scission, delais de connaissance, offset de decision) sont
copiees A L'IDENTIQUE depuis scripts/run_stage5_b3_xg_walkforward.py (qui
n'est pas un module important - un script CLI - d'ou la duplication
plutot qu'un import) pour garantir exactement le meme split
rodage/validation/test sur exactement les memes matchs.

Usage:
    python scripts/run_stage5_b3_xg_complementarity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (  # noqa: E402
    RealModelConfig,
    build_real_match_records,
    run_real_data_walk_forward,
)
from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.xg_model import XGModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

# --- Copie a l'identique de run_stage5_b3_xg_walkforward.py (voir docstring) ---
_BURN_IN_FRACTION = 0.4
_VALIDATION_FRACTION_OF_REMAINDER = 0.5
_DECISION_OFFSET_HOURS = 2.0
_MIN_TRAIN_MATCHES = 10

_DATASETS = {
    "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2025_datesData.json")),
    "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2025_datesData.json")),
    "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2025_datesData.json")),
}


def _model_configs() -> list[RealModelConfig]:
    def _fit_poisson_simple(goals_df, xg_df, decision_time):
        return PoissonModel(use_team_hfa=False).fit(goals_df)

    def _fit_xg(goals_df, xg_df, decision_time):
        return XGModel().fit(xg_df)

    return [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="xg_model", fit=_fit_xg, min_train_matches=_MIN_TRAIN_MATCHES),
    ]


def _split_eval_ids(records) -> tuple[list[str], list[str]]:
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    n_total = len(ordered)
    n_burn_in = int(n_total * _BURN_IN_FRACTION)
    n_remaining = n_total - n_burn_in
    n_validation = int(n_remaining * _VALIDATION_FRACTION_OF_REMAINDER)
    validation_ids = [r.match_id for r in ordered[n_burn_in : n_burn_in + n_validation]]
    test_ids = [r.match_id for r in ordered[n_burn_in + n_validation :]]
    return validation_ids, test_ids
# --- Fin de la copie ---


def _per_match_metrics(evaluations, league: str) -> pd.DataFrame:
    """Une ligne par match evalue, avec les deux predictions completes et
    leurs metriques individuelles - PAS seulement des moyennes agregees,
    necessaire pour l'analyse de complementarite (correlation, sous-groupes)."""
    rows = []
    for ev in evaluations:
        p_poisson = ev.predictions.get("poisson_simple")
        p_xg = ev.predictions.get("xg_model")
        if p_poisson is None or p_xg is None:
            continue
        outcome_arr = np.array([ev.outcome])
        rows.append(
            {
                "league": league,
                "match_id": ev.match_id,
                "outcome": ev.outcome,
                "p_poisson_home": p_poisson[0],
                "p_poisson_draw": p_poisson[1],
                "p_poisson_away": p_poisson[2],
                "p_xg_home": p_xg[0],
                "p_xg_draw": p_xg[1],
                "p_xg_away": p_xg[2],
                "brier_poisson": brier_score(np.array([p_poisson]), outcome_arr),
                "brier_xg": brier_score(np.array([p_xg]), outcome_arr),
                "log_loss_poisson": log_loss(np.array([p_poisson]), outcome_arr),
                "log_loss_xg": log_loss(np.array([p_xg]), outcome_arr),
                "poisson_argmax": int(np.argmax(p_poisson)),
            }
        )
    df = pd.DataFrame(rows)
    df["poisson_wrong"] = df["poisson_argmax"] != df["outcome"]
    return df


_TIE_EPS = 1e-9


def _complementarity_stats(df: pd.DataFrame, n_resamples: int, seed: int) -> dict:
    n = len(df)
    xg_better = int((df["brier_xg"] < df["brier_poisson"] - _TIE_EPS).sum())
    poisson_better = int((df["brier_poisson"] < df["brier_xg"] - _TIE_EPS).sum())
    ties = n - xg_better - poisson_better

    error_corr = float(np.corrcoef(df["brier_poisson"], df["brier_xg"])[0, 1])
    prob_home_corr = float(np.corrcoef(df["p_poisson_home"], df["p_xg_home"])[0, 1])
    total_variation = float(
        (
            0.5
            * (
                (df["p_poisson_home"] - df["p_xg_home"]).abs()
                + (df["p_poisson_draw"] - df["p_xg_draw"]).abs()
                + (df["p_poisson_away"] - df["p_xg_away"]).abs()
            )
        ).mean()
    )

    overall_diffs = (df["brier_xg"] - df["brier_poisson"]).to_numpy()
    overall_boot = paired_bootstrap_test(overall_diffs, n_resamples=n_resamples, seed=seed)

    wrong_df = df[df["poisson_wrong"]]
    if len(wrong_df) >= 2:
        wrong_diffs = (wrong_df["brier_xg"] - wrong_df["brier_poisson"]).to_numpy()
        wrong_boot = paired_bootstrap_test(wrong_diffs, n_resamples=n_resamples, seed=seed)
    else:
        wrong_boot = None

    return {
        "n": n,
        "xg_better": xg_better,
        "poisson_better": poisson_better,
        "ties": ties,
        "error_corr": error_corr,
        "prob_home_corr": prob_home_corr,
        "total_variation": total_variation,
        "brier_poisson_mean": float(df["brier_poisson"].mean()),
        "brier_xg_mean": float(df["brier_xg"].mean()),
        "log_loss_poisson_mean": float(df["log_loss_poisson"].mean()),
        "log_loss_xg_mean": float(df["log_loss_xg"].mean()),
        "overall_boot": overall_boot,
        "n_poisson_wrong": len(wrong_df),
        "wrong_boot": wrong_boot,
        "brier_poisson_mean_when_wrong": float(wrong_df["brier_poisson"].mean()) if len(wrong_df) else None,
        "brier_xg_mean_when_wrong": float(wrong_df["brier_xg"].mean()) if len(wrong_df) else None,
    }


def _print_stats(label: str, s: dict) -> None:
    typer.echo(f"\n--- {label} (n={s['n']}) ---")
    typer.echo(f"  Brier      poisson_simple={s['brier_poisson_mean']:.4f}  xg_model={s['brier_xg_mean']:.4f}")
    typer.echo(
        f"  Log loss   poisson_simple={s['log_loss_poisson_mean']:.4f}  xg_model={s['log_loss_xg_mean']:.4f}"
    )
    boot = s["overall_boot"]
    typer.echo(
        f"  xg_model - poisson_simple : diff_moy={boot['mean_diff']:+.4f} "
        f"IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}] p={boot['p_value']:.4f}"
    )
    typer.echo(
        f"  Matchs ou xG strictement meilleur : {s['xg_better']} ({s['xg_better']/s['n']:.1%}) | "
        f"poisson strictement meilleur : {s['poisson_better']} ({s['poisson_better']/s['n']:.1%}) | "
        f"ex-aequo : {s['ties']} ({s['ties']/s['n']:.1%})"
    )
    typer.echo(f"  Correlation des erreurs Brier (poisson vs xG) : {s['error_corr']:.4f}")
    typer.echo(f"  Correlation des probabilites domicile predites (poisson vs xG) : {s['prob_home_corr']:.4f}")
    typer.echo(f"  Distance de variation totale moyenne (P_poisson, P_xg) : {s['total_variation']:.4f}")
    typer.echo(f"  Matchs ou poisson_simple s'est trompe (argmax != issue) : {s['n_poisson_wrong']}")
    if s["wrong_boot"] is not None:
        wb = s["wrong_boot"]
        typer.echo(
            f"    Dans ce sous-groupe : brier_poisson={s['brier_poisson_mean_when_wrong']:.4f} "
            f"brier_xg={s['brier_xg_mean_when_wrong']:.4f} | "
            f"xg_model - poisson_simple : diff_moy={wb['mean_diff']:+.4f} "
            f"IC95%=[{wb['ci_low']:+.4f}, {wb['ci_high']:+.4f}] p={wb['p_value']:.4f}"
        )
    else:
        typer.echo("    Sous-groupe trop petit pour un bootstrap fiable.")


@app.command()
def main(
    n_resamples: int = typer.Option(2000),
    seed: int = typer.Option(0),
) -> None:
    all_dfs = []
    for name, (league_id, path) in _DATASETS.items():
        with open(path) as f:
            raw = json.load(f)
        records = build_real_match_records(raw, league=league_id)
        _validation_ids, test_ids = _split_eval_ids(records)

        test_evals = run_real_data_walk_forward(
            records,
            eval_match_ids=test_ids,
            decision_offset_hours=_DECISION_OFFSET_HOURS,
            model_configs=_model_configs(),
        )
        df = _per_match_metrics(test_evals, league=name)
        all_dfs.append(df)
        stats = _complementarity_stats(df, n_resamples, seed)
        _print_stats(name, stats)

    combined = pd.concat(all_dfs, ignore_index=True)
    combined_stats = _complementarity_stats(combined, n_resamples, seed)
    _print_stats("AGREGE (trois championnats)", combined_stats)

    typer.echo("\n=== Reponses ===")
    typer.echo(
        f"1. Le xG contient-il un signal different des buts reels ? "
        f"Correlation des erreurs = {combined_stats['error_corr']:.3f}, "
        f"correlation des probabilites domicile = {combined_stats['prob_home_corr']:.3f}, "
        f"distance de variation totale moyenne = {combined_stats['total_variation']:.3f}."
    )
    typer.echo(
        f"2. Repartition des victoires par match : xG meilleur sur "
        f"{combined_stats['xg_better']}/{combined_stats['n']} "
        f"({combined_stats['xg_better']/combined_stats['n']:.1%}), poisson meilleur sur "
        f"{combined_stats['poisson_better']}/{combined_stats['n']} "
        f"({combined_stats['poisson_better']/combined_stats['n']:.1%})."
    )
    if combined_stats["wrong_boot"] is not None:
        wb = combined_stats["wrong_boot"]
        typer.echo(
            f"3. Quand poisson_simple se trompe (n={combined_stats['n_poisson_wrong']}) : "
            f"xg_model - poisson_simple diff_moy={wb['mean_diff']:+.4f} "
            f"IC95%=[{wb['ci_low']:+.4f}, {wb['ci_high']:+.4f}]."
        )


if __name__ == "__main__":
    app()
