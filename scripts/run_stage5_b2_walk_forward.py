"""CLI : walk-forward hors echantillon de l'etape 5, hypothese B2.

Compare, sur les DEUX scenarios synthetiques deja utilises pour tester A1
a l'etape 2 (constant et derive - configs/stage2_walk_forward*.yaml,
inchanges), la mise a jour bayesienne sequentielle (B2,
football_model/bayesian_sequential.py) a la ponderation temporelle par
fenetre glissante (A1, deja implementee, reste INDETERMINEE et n'est PAS
retouchee ici) : ce sont deux solutions concurrentes au meme probleme
(capter la forme recente d'une equipe), traitees comme des hypotheses
mutuellement exclusives a departager (protocole valide dans
docs/research_framework.md, section B2), pas comme des briques
cumulatives.

Regle d'acceptation/rejet PRE-ENREGISTREE (protocole valide avant toute
execution, voir echange de validation de l'etape 5) :
- VALIDE  : IC95% bas de (Brier_A1 - Brier_B2) > 0 sur LES DEUX scenarios
  (B2 ameliore significativement sur A1, de facon coherente).
- REJETE  : IC95% bas de (Brier_B2 - Brier_A1) > 0 sur LES DEUX scenarios
  (A1 reste significativement superieur sur les deux).
- INDETERMINE : tout le reste (resultats incoherents entre scenarios, ou
  intervalle de confiance incluant 0 sur au moins un scenario).

Le HFA teste (A2) est desactive des deux cotes (use_team_hfa=False) pour
isoler strictement la question testee (methode d'estimation de la force
d'equipe), exactement comme "poisson_A1_decay" l'a ete a l'etape 2.
Aucun parametre (demi-vie A1, prior_strength B2, seuils de decision) n'est
ajuste dans ce script apres observation des resultats.

Usage:
    python scripts/run_stage5_b2_walk_forward.py
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
    to_probs_and_outcomes,
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
from sys_foot_quant.football_model.bayesian_sequential import BayesianSequentialModel  # noqa: E402
from sys_foot_quant.football_model.naive import NaiveModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.weighting import exponential_decay_weights  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_HALF_LIFE_DAYS = 45.0  # A1, gele depuis l'etape 2 - non retouche ici
_BURN_IN_FRACTION = 0.4

_SCENARIOS = {
    "constant": Path("configs/stage2_walk_forward.yaml"),
    "drift": Path("configs/stage2_walk_forward_drift.yaml"),
}


def _poisson_a1_config() -> ModelConfig:
    def _fit(train_df, decision_time):
        age_days = (decision_time - train_df["kickoff_time"]).dt.total_seconds() / 86400.0
        weights = exponential_decay_weights(age_days.to_numpy(), _HALF_LIFE_DAYS)
        return PoissonModel(use_team_hfa=False).fit(train_df, weights=weights)

    return ModelConfig(name="poisson_A1_decay", fit=_fit)


def _poisson_b2_config() -> ModelConfig:
    return ModelConfig(
        name="poisson_B2_bayesian",
        fit=lambda df, t: BayesianSequentialModel().fit(df, t),
    )


def _poisson_simple_config() -> ModelConfig:
    return ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df))


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


def _run_scenario(scenario_name: str, config_path: Path, data_dir: Path, n_resamples: int, seed: int):
    cfg = load_config(config_path)
    dataset = generate_synthetic_dataset(cfg.synthetic_data)
    write_dataset(dataset, data_dir)

    with DuckDBRepository(data_dir) as repo:
        all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
        n_total = len(all_matches)
        n_burn_in = int(n_total * _BURN_IN_FRACTION)
        eval_ids = all_matches["match_id"].iloc[n_burn_in:].tolist()

        model_configs = [
            _naive_config(),
            _poisson_simple_config(),
            _poisson_a1_config(),
            _poisson_b2_config(),
        ]
        evaluations = run_walk_forward(
            repository=repo,
            eval_match_ids=eval_ids,
            decision_offset_hours=cfg.decision_offset_hours_before_kickoff,
            model_configs=model_configs,
            include_market_benchmark=False,
        )

    typer.echo(f"\n--- Scenario '{scenario_name}' ({n_total} matchs, {len(eval_ids)} evalues) ---")
    typer.echo("[contexte, hors regle de decision B2 vs A1 pre-enregistree]")
    for name in ["naive", "poisson_simple", "poisson_A1_decay", "poisson_B2_bayesian"]:
        probs, outcomes = to_probs_and_outcomes(evaluations, name)
        b = brier_score(probs, outcomes)
        ll = log_loss(probs, outcomes)
        typer.echo(f"{name:<20} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")

    results = {}
    for metric_name, metric_fn in [("brier", brier_score), ("log_loss", log_loss)]:
        diffs = _paired_metric_diffs(evaluations, "poisson_B2_bayesian", "poisson_A1_decay", metric_fn)
        boot = paired_bootstrap_test(diffs, n_resamples=n_resamples, seed=seed)
        ttest = paired_t_test(diffs) if diffs.size >= 2 else {"p_value": float("nan")}
        sign = "B2 ameliore" if boot["mean_diff"] < 0 else "A1 ameliore"
        typer.echo(
            f"  diff(B2-A1) [{metric_name:>8}] n={diffs.size:<4} "
            f"diff_moy={boot['mean_diff']:+.4f} ({sign}) "
            f"IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}] "
            f"p_boot={boot['p_value']:.4f} p_ttest={ttest['p_value']:.4f}"
        )
        results[metric_name] = boot
    return results


def _verdict(ci_low: float, ci_high: float) -> str:
    if ci_high < 0.0:
        return "B2_meilleur"  # diff(B2-A1) significativement < 0
    if ci_low > 0.0:
        return "A1_meilleur"  # diff(B2-A1) significativement > 0
    return "indetermine"


@app.command()
def main(
    data_dir: Path = typer.Option(Path("data/raw_stage5_b2")),
    n_resamples: int = typer.Option(2000, help="Nombre de reechantillonnages bootstrap."),
    seed: int = typer.Option(0, help="Graine du bootstrap (reproductibilite)."),
) -> None:
    all_results = {}
    for scenario_name, config_path in _SCENARIOS.items():
        all_results[scenario_name] = _run_scenario(
            scenario_name, config_path, data_dir / scenario_name, n_resamples, seed
        )

    typer.echo("\n=== Verdict par scenario (metrique Brier, pre-enregistree) ===")
    verdicts = []
    for scenario_name, results in all_results.items():
        boot = results["brier"]
        v = _verdict(boot["ci_low"], boot["ci_high"])
        verdicts.append(v)
        typer.echo(f"{scenario_name:<10} -> {v}")

    typer.echo("\n=== Verdict global B2 vs A1 (regle pre-enregistree) ===")
    if all(v == "B2_meilleur" for v in verdicts):
        typer.echo("VALIDE : B2 ameliore significativement sur A1, de facon coherente sur les deux scenarios.")
    elif all(v == "A1_meilleur" for v in verdicts):
        typer.echo("REJETE : A1 reste significativement superieur a B2 sur les deux scenarios.")
    else:
        typer.echo(
            "INDETERMINE : resultats incoherents entre scenarios, ou intervalle de confiance "
            "incluant 0 sur au moins un scenario. Aucune conclusion ne doit etre tiree au-dela "
            "de ce constat - pas d'ajustement de parametre pour tenter d'obtenir un resultat "
            "different."
        )


if __name__ == "__main__":
    app()
