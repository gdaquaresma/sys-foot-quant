"""CLI : walk-forward hors echantillon de l'etape 2 (Poisson + benchmarks).

Compare, sur un dataset synthetique avec signal d'equipe simule :
- benchmarks : naif, Elo, marche sans marge (cotes synthetiques) ;
- Poisson simple (configuration de reference, sans A1 ni A2) ;
- Poisson + ponderation temporelle seule (A1) ;
- Poisson + HFA a shrinkage seule (A2) ;
- Poisson + A1 + A2 combines.

Chaque configuration est comparee a la reference (Poisson simple) via
Brier score et log loss hors echantillon, avec test de significativite
apparie (bootstrap + test t). Voir docs/research_framework.md pour le
protocole justifiant ce choix de configurations.

Usage:
    python scripts/run_stage2_walk_forward.py --config configs/stage2_walk_forward.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.walk_forward import (  # noqa: E402
    ModelConfig,
    run_walk_forward,
    to_lambda_mu_and_goals,
    to_probs_and_outcomes,
)
from sys_foot_quant.calibration_engine.goodness_of_fit import (  # noqa: E402
    contribution_table,
    poisson_goodness_of_fit,
)
from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.significance import (  # noqa: E402
    paired_bootstrap_test,
    paired_t_test,
)
from sys_foot_quant.common.config import load_config  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository  # noqa: E402
from sys_foot_quant.data_engine.storage.writer import write_dataset  # noqa: E402
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset  # noqa: E402
from sys_foot_quant.football_model.elo import EloModel  # noqa: E402
from sys_foot_quant.football_model.naive import NaiveModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.weighting import exponential_decay_weights  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_HALF_LIFE_DAYS = 45.0
_HFA_SHRINKAGE_K = 10.0
_BURN_IN_FRACTION = 0.4


def _poisson_config(name: str, use_decay: bool, use_team_hfa: bool) -> ModelConfig:
    def _fit(train_df, decision_time):
        weights = None
        if use_decay:
            age_days = (decision_time - train_df["kickoff_time"]).dt.total_seconds() / 86400.0
            weights = exponential_decay_weights(age_days.to_numpy(), _HALF_LIFE_DAYS)
        return PoissonModel(use_team_hfa=use_team_hfa, hfa_shrinkage_k=_HFA_SHRINKAGE_K).fit(
            train_df, weights=weights
        )

    return ModelConfig(name=name, fit=_fit)


def _elo_config() -> ModelConfig:
    return ModelConfig(
        name="elo",
        fit=lambda df, t: EloModel(k=20.0, home_advantage=100.0).fit(
            df.sort_values("kickoff_time")
        ),
    )


def _naive_config() -> ModelConfig:
    return ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df))


def _paired_metric_diffs(evaluations, model_a: str, model_b: str, metric_fn) -> np.ndarray:
    diffs = []
    for ev in evaluations:
        pa = ev.predictions.get(model_a)
        pb = ev.predictions.get(model_b)
        if pa is None or pb is None:
            continue
        outcome_arr = np.array([ev.outcome])
        score_a = metric_fn(np.array([pa]), outcome_arr)
        score_b = metric_fn(np.array([pb]), outcome_arr)
        diffs.append(score_a - score_b)
    return np.array(diffs)


@app.command()
def main(
    config: Path = typer.Option(Path("configs/stage2_walk_forward.yaml")),
    data_dir: Path = typer.Option(Path("data/raw_stage2")),
    n_resamples: int = typer.Option(2000, help="Nombre de reechantillonnages bootstrap."),
    seed: int = typer.Option(0, help="Graine du bootstrap (reproductibilite)."),
) -> None:
    cfg = load_config(config)
    dataset = generate_synthetic_dataset(cfg.synthetic_data)
    write_dataset(dataset, data_dir)
    logger.info(
        f"Dataset genere : {len(dataset.matches)} matchs, {cfg.synthetic_data.n_teams} equipes."
    )

    with DuckDBRepository(data_dir) as repo:
        all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
        n_total = len(all_matches)
        n_burn_in = int(n_total * _BURN_IN_FRACTION)
        eval_ids = all_matches["match_id"].iloc[n_burn_in:].tolist()
        typer.echo(
            f"{n_total} matchs au total, {n_burn_in} en periode de rodage, "
            f"{len(eval_ids)} evalues en walk-forward."
        )

        model_configs = [
            _naive_config(),
            _elo_config(),
            _poisson_config("poisson_simple", use_decay=False, use_team_hfa=False),
            _poisson_config("poisson_A1_decay", use_decay=True, use_team_hfa=False),
            _poisson_config("poisson_A2_hfa", use_decay=False, use_team_hfa=True),
            _poisson_config("poisson_A1_A2", use_decay=True, use_team_hfa=True),
        ]

        evaluations = run_walk_forward(
            repository=repo,
            eval_match_ids=eval_ids,
            decision_offset_hours=cfg.decision_offset_hours_before_kickoff,
            model_configs=model_configs,
            include_market_benchmark=True,
        )

    model_names = [c.name for c in model_configs] + ["market_no_vig"]

    typer.echo("\n=== Brier score / log loss hors echantillon ===")
    typer.echo(f"{'modele':<16} {'n':>5} {'brier':>10} {'log_loss':>10}")
    for name in model_names:
        probs, outcomes = to_probs_and_outcomes(evaluations, name)
        if len(outcomes) == 0:
            typer.echo(f"{name:<16} {'--':>5} {'--':>10} {'--':>10}")
            continue
        b = brier_score(probs, outcomes)
        ll = log_loss(probs, outcomes)
        typer.echo(f"{name:<16} {len(outcomes):>5} {b:>10.4f} {ll:>10.4f}")

    typer.echo("\n=== Comparaisons appariees vs poisson_simple (reference) ===")
    reference = "poisson_simple"
    for name in ["poisson_A1_decay", "poisson_A2_hfa", "poisson_A1_A2", "naive", "elo", "market_no_vig"]:
        for metric_name, metric_fn in [("brier", brier_score), ("log_loss", log_loss)]:
            diffs = _paired_metric_diffs(evaluations, name, reference, metric_fn)
            if diffs.size == 0:
                continue
            boot = paired_bootstrap_test(diffs, n_resamples=n_resamples, seed=seed)
            ttest = paired_t_test(diffs) if diffs.size >= 2 else {"p_value": float("nan")}
            sign = "ameliore" if boot["mean_diff"] < 0 else "degrade"
            typer.echo(
                f"{name:<16} [{metric_name:>8}] n={diffs.size:<4} "
                f"diff_moy={boot['mean_diff']:+.4f} ({sign} vs reference) "
                f"IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}] "
                f"p_boot={boot['p_value']:.4f} p_ttest={ttest['p_value']:.4f}"
            )

    typer.echo(
        "\n=== Diagnostic complementaire de Chi-Deux (forme de la distribution "
        "des scores) ===\n"
        "AVERTISSEMENT : ce diagnostic ne doit JAMAIS servir seul a "
        "accepter ou rejeter un modele - voir "
        "calibration_engine/goodness_of_fit.py pour ses limites precises."
    )
    for name in ["poisson_simple", "poisson_A1_A2"]:
        lambdas_mus, home_goals, away_goals = to_lambda_mu_and_goals(evaluations, name)
        if not lambdas_mus:
            continue
        gof = poisson_goodness_of_fit(lambdas_mus, home_goals, away_goals, max_goals_per_side=3)
        validity = "valide (tous effectifs attendus >= 5)" if gof.is_valid else (
            f"A INTERPRETER AVEC PRUDENCE (effectif attendu minimal={gof.min_expected_count:.2f} < 5)"
        )
        typer.echo(
            f"{name:<16} chi2={gof.statistic:>8.2f} dof={gof.dof:>3} "
            f"p_value={gof.p_value:.4f} n={gof.n_matches:<4} -> {validity}"
        )
        if gof.p_value < 0.05:
            top3 = contribution_table(gof).iloc[:3]
            typer.echo(f"  -> p<0.05 : categories expliquant le plus le chi2 (sur {name}) :")
            for _, row in top3.iterrows():
                typer.echo(
                    f"     {row['category']:>6}  observe={row['observed']:>4.0f}  "
                    f"attendu={row['expected']:>7.2f}  "
                    f"part_du_chi2={row['contribution_share']:.1%}"
                )


if __name__ == "__main__":
    app()
