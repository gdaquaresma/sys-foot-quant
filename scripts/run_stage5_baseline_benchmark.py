"""CLI : benchmark pre-enregistre a trois variantes (etape 5) - designe la
baseline officielle du Football Model pour la suite du projet.

Compare, sur les DEUX scenarios synthetiques deja utilises (constant et
derive - configs/stage2_walk_forward*.yaml, inchanges), avec la MEME
scission walk-forward (rodage 40%) et les MEMES metriques (Brier, log
loss) que tous les runs precedents de l'etape 2/5 :

1. poisson_simple   - aucune ponderation temporelle, aucun HFA par equipe.
2. poisson_A1_decay - ponderation temporelle A1 (demi-vie 45j, gelee).
3. poisson_B2_bayesian - mise a jour bayesienne sequentielle B2 (prior_strength=10, gele).

Le HFA par equipe (A2) est desactive sur les trois (comme dans tous les
tests A1/B2 precedents) : ce benchmark repond uniquement a la question
"quelle methode d'estimation de la force d'equipe dans le temps doit
devenir la reference ?", pas a une combinaison optimale de tous les
modules.

AVERTISSEMENT DE TRANSPARENCE (a lire avant les resultats) : ce pipeline
est entierement deterministe (seed fixe, aucun tirage aleatoire cote
modele) - relancer exactement les memes scenarios avec exactement les
memes configurations reproduit donc necessairement les memes chiffres
bruts de Brier/log loss deja obtenus et rapportes lors du test B2 vs A1
(scripts/run_stage5_b2_walk_forward.py). Une "pre-inscription" au sens
strict (protocole fixe avant de voir des donnees encore inconnues) n'a
pas de sens ici pour ces chiffres precis. Ce qui EST pre-enregistre ici,
avant execution de ce script, c'est la REGLE DE DECISION ci-dessous - les
deux comparaisons par paire manquantes (poisson_simple vs A1,
poisson_simple vs B2) sont en revanche un calcul statistique neuf, non
effectue lors du run precedent.

REGLE DE DECISION PRE-ENREGISTREE (fixee avant ce run, non modifiee
apres) :
1. Metrique principale : Brier score (coherence avec tout le projet).
2. Sur CHAQUE scenario, un modele A est juge "significativement meilleur"
   qu'un modele B si l'IC95% bootstrap apparie de (Brier_A - Brier_B) est
   entierement negatif.
3. Un modele est "candidat baseline" sur un scenario s'il n'est
   significativement battu par AUCUN autre modele sur ce scenario (il peut
   etre a egalite statistique avec un autre, mais jamais domine).
4. La baseline officielle est le modele candidat sur LES DEUX scenarios.
   S'il y a plusieurs candidats a egalite statistique sur les deux
   scenarios, le plus simple (poisson_simple > A1/B2 en parcimonie -
   moins de parametres/hypotheses) est retenu par defaut.
5. Si aucun modele n'est candidat sur les deux scenarios a la fois
   (resultats incoherents entre scenarios), verdict INDETERMINE : la
   baseline actuelle (poisson_simple, deja en usage depuis l'etape 2)
   est conservee par defaut jusqu'a nouvel arbitrage.

Usage:
    python scripts/run_stage5_baseline_benchmark.py
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
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.config import load_config  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository  # noqa: E402
from sys_foot_quant.data_engine.storage.writer import write_dataset  # noqa: E402
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset  # noqa: E402
from sys_foot_quant.football_model.bayesian_sequential import BayesianSequentialModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.weighting import exponential_decay_weights  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_HALF_LIFE_DAYS = 45.0
_BURN_IN_FRACTION = 0.4
_MODEL_NAMES = ["poisson_simple", "poisson_A1_decay", "poisson_B2_bayesian"]

_SCENARIOS = {
    "constant": Path("configs/stage2_walk_forward.yaml"),
    "drift": Path("configs/stage2_walk_forward_drift.yaml"),
}


def _model_configs() -> list[ModelConfig]:
    def _fit_simple(df, t):
        return PoissonModel(use_team_hfa=False).fit(df)

    def _fit_a1(df, t):
        age_days = (t - df["kickoff_time"]).dt.total_seconds() / 86400.0
        weights = exponential_decay_weights(age_days.to_numpy(), _HALF_LIFE_DAYS)
        return PoissonModel(use_team_hfa=False).fit(df, weights=weights)

    def _fit_b2(df, t):
        return BayesianSequentialModel().fit(df, t)

    return [
        ModelConfig(name="poisson_simple", fit=_fit_simple),
        ModelConfig(name="poisson_A1_decay", fit=_fit_a1),
        ModelConfig(name="poisson_B2_bayesian", fit=_fit_b2),
    ]


def _paired_metric_diffs(evaluations, model_a: str, model_b: str, metric_fn) -> np.ndarray:
    diffs = []
    for ev in evaluations:
        pa = ev.predictions.get(model_a)
        pb = ev.predictions.get(model_b)
        if pa is None or pb is None:
            continue
        outcome_arr = np.array([ev.outcome])
        diffs.append(metric_fn(np.array([pa]), outcome_arr) - metric_fn(np.array([pb]), outcome_arr))
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

        evaluations = run_walk_forward(
            repository=repo,
            eval_match_ids=eval_ids,
            decision_offset_hours=cfg.decision_offset_hours_before_kickoff,
            model_configs=_model_configs(),
            include_market_benchmark=False,
        )

    typer.echo(f"\n--- Scenario '{scenario_name}' ({n_total} matchs, {len(eval_ids)} evalues) ---")
    brier_by_model = {}
    for name in _MODEL_NAMES:
        probs, outcomes = to_probs_and_outcomes(evaluations, name)
        b = brier_score(probs, outcomes)
        ll = log_loss(probs, outcomes)
        brier_by_model[name] = b
        typer.echo(f"{name:<20} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")

    typer.echo("  Comparaisons par paire (Brier, bootstrap apparie IC95%) :")
    pairwise_ci = {}
    for i, model_a in enumerate(_MODEL_NAMES):
        for model_b in _MODEL_NAMES[i + 1 :]:
            diffs = _paired_metric_diffs(evaluations, model_a, model_b, brier_score)
            boot = paired_bootstrap_test(diffs, n_resamples=n_resamples, seed=seed)
            pairwise_ci[(model_a, model_b)] = boot
            sign = f"{model_a} meilleur" if boot["mean_diff"] < 0 else f"{model_b} meilleur"
            sig = "significatif" if (boot["ci_high"] < 0 or boot["ci_low"] > 0) else "non significatif"
            typer.echo(
                f"    {model_a} vs {model_b}: diff_moy={boot['mean_diff']:+.4f} "
                f"IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}] ({sign}, {sig})"
            )

    # Determine, pour ce scenario, les modeles jamais significativement battus.
    beaten = {name: False for name in _MODEL_NAMES}
    for (model_a, model_b), boot in pairwise_ci.items():
        if boot["ci_high"] < 0.0:  # diff(A-B) < 0 sur toute la plage -> A significativement meilleur que B
            beaten[model_b] = True
        elif boot["ci_low"] > 0.0:  # diff(A-B) > 0 sur toute la plage -> B significativement meilleur que A
            beaten[model_a] = True
    candidates = [name for name, was_beaten in beaten.items() if not was_beaten]
    typer.echo(f"  -> Candidats non domines sur ce scenario : {candidates}")
    return candidates


@app.command()
def main(
    data_dir: Path = typer.Option(Path("data/raw_stage5_baseline")),
    n_resamples: int = typer.Option(2000),
    seed: int = typer.Option(0),
) -> None:
    candidates_by_scenario = {}
    for scenario_name, config_path in _SCENARIOS.items():
        candidates_by_scenario[scenario_name] = set(
            _run_scenario(scenario_name, config_path, data_dir / scenario_name, n_resamples, seed)
        )

    typer.echo("\n=== Verdict : baseline officielle (regle pre-enregistree) ===")
    common_candidates = set(_MODEL_NAMES)
    for scenario_name, candidates in candidates_by_scenario.items():
        typer.echo(f"{scenario_name:<10} candidats non domines : {sorted(candidates)}")
        common_candidates &= candidates

    if not common_candidates:
        typer.echo(
            "\nINDETERMINE : aucun modele n'est candidat non-domine sur les DEUX scenarios a la "
            "fois. Baseline conservee par defaut : poisson_simple (statu quo depuis l'etape 2), "
            "en attendant un arbitrage ulterieur."
        )
    elif len(common_candidates) == 1:
        (winner,) = common_candidates
        typer.echo(f"\nBASELINE OFFICIELLE : {winner} (seul candidat non-domine sur les deux scenarios).")
    else:
        # Egalite statistique entre plusieurs candidats -> parcimonie.
        order_of_parsimony = ["poisson_simple", "poisson_A1_decay", "poisson_B2_bayesian"]
        winner = next(m for m in order_of_parsimony if m in common_candidates)
        typer.echo(
            f"\nEgalite statistique entre {sorted(common_candidates)} sur les deux scenarios. "
            f"Regle de parcimonie (pre-enregistree) : BASELINE OFFICIELLE = {winner}."
        )


if __name__ == "__main__":
    app()
