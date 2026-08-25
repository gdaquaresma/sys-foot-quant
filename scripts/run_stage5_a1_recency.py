"""CLI : re-test de l'hypothese A1 avec une definition football-realiste
de la forme recente (docs/research_framework.md, echange de validation du
protocole - remplace la question deja tranchee "la demi-vie exponentielle
calendaire A1 (45j) ameliore-t-elle sur poisson_simple ?", qui reste
DOMINEE et n'est PAS retouchee ici).

Question de recherche reformulee (validee explicitement avant execution) :
les DERNIERS matchs d'une equipe (fenetre courte, poids plat, poids nul
au-dela) apportent-ils une information predictive supplementaire au
Poisson simple, eventuellement en s'appuyant sur une faible trace de
"saison precedente" (traduite, pour ce generateur sans notion de saison,
comme un shrinkage vers l'historique complet de l'equipe) uniquement
lorsque l'echantillon recent est insuffisant ? Le dernier face-a-face
direct (H2H) est teste separement, comme hypothese INDEPENDANTE, jamais
combine par defaut a la forme recente.

Configurations comparees separement (aucune n'est jamais ajustee apres
avoir vu un resultat) :
- poisson_simple    : reference officielle, inchangee.
- forme_3/5/7       : RecentFormModel(window={3,5,7}, prior_k=0.0) - 5 est
                       la configuration de reference a priori.
- forme_5_memoire   : RecentFormModel(window=5, prior_k=2.0) - prior_k
                       fixe AVANT tout test, par analogie avec le
                       shrinkage HFA (A2, k=10.0) et B2 (prior_strength=10.0)
                       ; PAS une valeur optimisee.
- h2h_seul          : HeadToHeadModel(weight=0.10) - poids fixe AVANT tout
                       test, teste seul, jamais combine a la forme recente
                       tant qu'il n'a pas demontre une utilite propre.

Protocole de selection/confirmation (pre-enregistre, valide avant toute
execution) :
1. Scission chronologique a TROIS voies par scenario : rodage (40%),
   validation (30%), test (30%). Le rodage n'est jamais evalue (sert
   uniquement d'historique d'entrainement minimal, comme dans tous les
   scripts precedents).
2. La fenetre 3/5/7 est choisie EXCLUSIVEMENT sur la VALIDATION (la
   meilleure diff moyenne de Brier vs poisson_simple ; en cas d'ecart
   negligeable - moins de _WINDOW_TIE_EPSILON - avec la fenetre 5, la
   fenetre 5 est retenue par defaut). Le TEST ne sert JAMAIS a ce choix.
3. Les hypotheses forme_5_memoire (vs forme_5) et h2h_seul (vs
   poisson_simple) ne comportent aucun hyperparametre a choisir (valeurs
   fixees a priori) : la VALIDATION sert de premier regard (go/no-go
   informatif), le TEST sert de confirmation finale et determine seul le
   verdict.
4. Regle de verdict a 3 categories (meme famille que B1/B2, calculee sur
   le TEST, jamais la validation) :
   - VALIDE       : IC95% bootstrap aparie de (Brier_candidat -
     Brier_reference) entierement negatif sur LES DEUX scenarios.
   - REJETE       : IC95% entierement positif sur LES DEUX scenarios.
   - INDETERMINE  : tout le reste (incoherent entre scenarios, ou IC
     incluant 0 sur au moins un scenario).
5. Le rapport final separe explicitement QUATRE questions (voir sortie du
   script) : (Q1) la forme recente fonctionne-t-elle globalement, (Q2)
   quelle fenetre fonctionne le mieux (informationnel, VALIDATION
   uniquement), (Q3) la memoire longue ajoute-t-elle quelque chose, (Q4)
   le H2H ajoute-t-il quelque chose. Aucune amelioration n'est promue
   automatiquement en configuration officielle : poisson_simple reste la
   baseline tant qu'aucun arbitrage explicite n'est fait au-dela de ce
   script.
6. Si une ou plusieurs briques sont VALIDEES individuellement, leur
   combinaison N'EST PAS testee dans ce meme script : le jeu de test a
   deja ete consulte pour la confirmation, le reutiliser pour une
   combinaison serait un nouveau data snooping. Un protocole de
   combinaison dedie (nouveau split ou nouveau jeu de donnees) devra etre
   concu et valide separement.

Usage:
    python scripts/run_stage5_a1_recency.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
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
from sys_foot_quant.football_model.head_to_head import HeadToHeadModel  # noqa: E402
from sys_foot_quant.football_model.naive import NaiveModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.recent_form import RecentFormModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_VALIDATION_FRACTION_OF_REMAINDER = 0.5  # -> ~40/30/30 rodage/validation/test
_WINDOWS = (3, 5, 7)
_REFERENCE_WINDOW = 5
_WINDOW_TIE_EPSILON = 1e-4  # tolerance de Brier moyen pour un "quasi-ex-aequo" -> defaut fenetre 5
_MEMOIRE_PRIOR_K = 2.0  # fixe a priori (analogie A2/B2), non optimise
_H2H_WEIGHT = 0.10  # fixe a priori, non optimise

_SCENARIOS = {
    "constant": Path("configs/stage5_a1_recency_constant.yaml"),
    "drift": Path("configs/stage5_a1_recency_drift.yaml"),
}

_REPORT_MODEL_NAMES = [
    "naive",
    "poisson_simple",
    "forme_3",
    "forme_5",
    "forme_7",
    "forme_5_memoire",
    "h2h_seul",
]


def _all_model_configs() -> list[ModelConfig]:
    def _recent_form_fit(window: int, prior_k: float):
        return lambda df, t: RecentFormModel(window=window, prior_k=prior_k).fit(df, t)

    return [
        ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df)),
        ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df)),
        ModelConfig(name="forme_3", fit=_recent_form_fit(window=3, prior_k=0.0)),
        ModelConfig(name="forme_5", fit=_recent_form_fit(window=5, prior_k=0.0)),
        ModelConfig(name="forme_7", fit=_recent_form_fit(window=7, prior_k=0.0)),
        ModelConfig(
            name="forme_5_memoire", fit=_recent_form_fit(window=5, prior_k=_MEMOIRE_PRIOR_K)
        ),
        ModelConfig(name="h2h_seul", fit=lambda df, t: HeadToHeadModel(weight=_H2H_WEIGHT).fit(df, t)),
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


def _compare(evaluations, candidate: str, reference: str, n_resamples: int, seed: int) -> dict[str, float]:
    diffs = _paired_metric_diffs(evaluations, candidate, reference, brier_score)
    return paired_bootstrap_test(diffs, n_resamples=n_resamples, seed=seed)


def _split_match_ids(all_matches: pd.DataFrame) -> tuple[list[int], list[int], list[int]]:
    n_total = len(all_matches)
    n_burn_in = int(n_total * _BURN_IN_FRACTION)
    n_remaining = n_total - n_burn_in
    n_validation = int(n_remaining * _VALIDATION_FRACTION_OF_REMAINDER)

    burn_in_ids = all_matches["match_id"].iloc[:n_burn_in].tolist()
    validation_ids = all_matches["match_id"].iloc[n_burn_in : n_burn_in + n_validation].tolist()
    test_ids = all_matches["match_id"].iloc[n_burn_in + n_validation :].tolist()
    return burn_in_ids, validation_ids, test_ids


def _select_window(
    validation_evaluations, n_resamples: int, seed: int
) -> tuple[int, dict[int, dict[str, float]]]:
    boots: dict[int, dict[str, float]] = {}
    for w in _WINDOWS:
        boots[w] = _compare(validation_evaluations, f"forme_{w}", "poisson_simple", n_resamples, seed)

    best_window = min(_WINDOWS, key=lambda w: boots[w]["mean_diff"])
    if abs(boots[best_window]["mean_diff"] - boots[_REFERENCE_WINDOW]["mean_diff"]) < _WINDOW_TIE_EPSILON:
        best_window = _REFERENCE_WINDOW
    return best_window, boots


def _bucket_verdict(ci_low: float, ci_high: float) -> str:
    if ci_high < 0.0:
        return "candidat_meilleur"
    if ci_low > 0.0:
        return "reference_meilleure"
    return "indetermine"


def _aggregate_verdict(buckets: list[str]) -> str:
    if all(b == "candidat_meilleur" for b in buckets):
        return "VALIDE"
    if all(b == "reference_meilleure" for b in buckets):
        return "REJETE"
    return "INDETERMINE"


def _format_boot(label: str, boot: dict[str, float]) -> str:
    return (
        f"{label:<45} diff_moy={boot['mean_diff']:+.4f} "
        f"IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}] p={boot['p_value']:.4f}"
    )


def _process_scenario(
    scenario_name: str, config_path: Path, data_dir: Path, n_resamples: int, seed: int
) -> dict:
    cfg = load_config(config_path)
    dataset = generate_synthetic_dataset(cfg.synthetic_data)
    write_dataset(dataset, data_dir)

    with DuckDBRepository(data_dir) as repo:
        all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
        burn_in_ids, validation_ids, test_ids = _split_match_ids(all_matches)

        typer.echo(
            f"\n=== Scenario '{scenario_name}' : {len(all_matches)} matchs "
            f"(rodage={len(burn_in_ids)}, validation={len(validation_ids)}, test={len(test_ids)}) ==="
        )

        validation_evals = run_walk_forward(
            repository=repo,
            eval_match_ids=validation_ids,
            decision_offset_hours=cfg.decision_offset_hours_before_kickoff,
            model_configs=_all_model_configs(),
            include_market_benchmark=False,
        )
        test_evals = run_walk_forward(
            repository=repo,
            eval_match_ids=test_ids,
            decision_offset_hours=cfg.decision_offset_hours_before_kickoff,
            model_configs=_all_model_configs(),
            include_market_benchmark=False,
        )

    typer.echo("  --- Metriques brutes (TEST) ---")
    for name in _REPORT_MODEL_NAMES:
        probs, outcomes = to_probs_and_outcomes(test_evals, name)
        if len(outcomes) == 0:
            continue
        b = brier_score(probs, outcomes)
        ll = log_loss(probs, outcomes)
        typer.echo(f"    {name:<18} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")

    typer.echo("  --- Selection de fenetre (VALIDATION uniquement, jamais le TEST) ---")
    winning_window, window_val_boots = _select_window(validation_evals, n_resamples, seed)
    for w, boot in window_val_boots.items():
        marker = "  <= retenue pour ce scenario" if w == winning_window else ""
        typer.echo("    " + _format_boot(f"forme_{w} vs poisson_simple [validation]", boot) + marker)

    memoire_val_boot = _compare(validation_evals, "forme_5_memoire", "forme_5", n_resamples, seed)
    h2h_val_boot = _compare(validation_evals, "h2h_seul", "poisson_simple", n_resamples, seed)
    typer.echo("    " + _format_boot("forme_5_memoire vs forme_5 [validation]", memoire_val_boot))
    typer.echo("    " + _format_boot("h2h_seul vs poisson_simple [validation]", h2h_val_boot))

    typer.echo("  --- Confirmation (TEST, jamais utilise pour la selection ci-dessus) ---")
    winning_window_name = f"forme_{winning_window}"
    window_test_boot = _compare(test_evals, winning_window_name, "poisson_simple", n_resamples, seed)
    memoire_test_boot = _compare(test_evals, "forme_5_memoire", "forme_5", n_resamples, seed)
    h2h_test_boot = _compare(test_evals, "h2h_seul", "poisson_simple", n_resamples, seed)

    typer.echo(
        "    " + _format_boot(f"{winning_window_name} (retenue) vs poisson_simple [test]", window_test_boot)
    )
    typer.echo("    " + _format_boot("forme_5_memoire vs forme_5 [test]", memoire_test_boot))
    typer.echo("    " + _format_boot("h2h_seul vs poisson_simple [test]", h2h_test_boot))

    # Comparaison supplementaire, INFORMATIVE UNIQUEMENT (ne change aucune
    # regle de decision pre-enregistree ci-dessus) : forme_5_memoire peut
    # battre significativement forme_5 (Q3) tout en restant, en absolu,
    # moins bon que poisson_simple - les deux constats ne sont pas
    # equivalents et le rapport final doit les distinguer explicitement.
    memoire_vs_simple_test_boot = _compare(
        test_evals, "forme_5_memoire", "poisson_simple", n_resamples, seed
    )
    typer.echo(
        "    "
        + _format_boot(
            "[info] forme_5_memoire vs poisson_simple [test]", memoire_vs_simple_test_boot
        )
    )

    return {
        "n_validation": len(validation_ids),
        "n_test": len(test_ids),
        "winning_window": winning_window,
        "window_test_boot": window_test_boot,
        "memoire_test_boot": memoire_test_boot,
        "h2h_test_boot": h2h_test_boot,
        "memoire_vs_simple_test_boot": memoire_vs_simple_test_boot,
    }


@app.command()
def main(
    data_dir: Path = typer.Option(Path("data/raw_stage5_a1_recency")),
    n_resamples: int = typer.Option(2000, help="Nombre de reechantillonnages bootstrap."),
    seed: int = typer.Option(0, help="Graine du bootstrap (reproductibilite)."),
) -> None:
    results = {}
    for scenario_name, config_path in _SCENARIOS.items():
        results[scenario_name] = _process_scenario(
            scenario_name, config_path, data_dir / scenario_name, n_resamples, seed
        )

    typer.echo("\n\n=== RAPPORT FINAL : quatre questions separees (protocole pre-enregistre) ===")

    typer.echo(
        "\n[Q2] Quelle fenetre fonctionne le mieux ? (selection VALIDATION uniquement, informationnel)"
    )
    for scenario_name, r in results.items():
        typer.echo(f"    {scenario_name:<10} -> fenetre retenue : {r['winning_window']} matchs")

    typer.echo(
        "\n[Q1] La forme recente (fenetre retenue par scenario) ameliore-t-elle sur poisson_simple "
        "(confirmation TEST) ?"
    )
    q1_buckets = []
    for scenario_name, r in results.items():
        boot = r["window_test_boot"]
        bucket = _bucket_verdict(boot["ci_low"], boot["ci_high"])
        q1_buckets.append(bucket)
        typer.echo(
            f"    {scenario_name:<10} forme_{r['winning_window']} vs poisson_simple : {bucket} "
            f"(diff_moy={boot['mean_diff']:+.4f}, IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}])"
        )
    q1_verdict = _aggregate_verdict(q1_buckets)
    typer.echo(f"    => Verdict Q1 (forme recente en general) : {q1_verdict}")

    typer.echo(
        "\n[Q3] La memoire longue (forme_5_memoire, prior_k=2.0 fixe a priori) ameliore-t-elle "
        "sur forme_5 seul (confirmation TEST) ?"
    )
    q3_buckets = []
    for scenario_name, r in results.items():
        boot = r["memoire_test_boot"]
        bucket = _bucket_verdict(boot["ci_low"], boot["ci_high"])
        q3_buckets.append(bucket)
        typer.echo(
            f"    {scenario_name:<10} forme_5_memoire vs forme_5 : {bucket} "
            f"(diff_moy={boot['mean_diff']:+.4f}, IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}])"
        )
    q3_verdict = _aggregate_verdict(q3_buckets)
    typer.echo(f"    => Verdict Q3 (memoire longue) : {q3_verdict}")
    typer.echo(
        "    [info, hors regle de decision Q3] forme_5_memoire vs poisson_simple directement "
        "(la memoire peut ameliorer sur forme_5 seul tout en restant, en absolu, moins bonne "
        "que la baseline officielle - les deux constats sont distincts) :"
    )
    for scenario_name, r in results.items():
        boot = r["memoire_vs_simple_test_boot"]
        typer.echo(
            f"      {scenario_name:<10} forme_5_memoire vs poisson_simple : "
            f"diff_moy={boot['mean_diff']:+.4f} IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}]"
        )

    typer.echo(
        "\n[Q4] La derniere confrontation directe (h2h_seul, poids=0.10 fixe a priori) ameliore-t-elle "
        "sur poisson_simple (confirmation TEST) ?"
    )
    q4_buckets = []
    for scenario_name, r in results.items():
        boot = r["h2h_test_boot"]
        bucket = _bucket_verdict(boot["ci_low"], boot["ci_high"])
        q4_buckets.append(bucket)
        typer.echo(
            f"    {scenario_name:<10} h2h_seul vs poisson_simple : {bucket} "
            f"(diff_moy={boot['mean_diff']:+.4f}, IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}])"
        )
    q4_verdict = _aggregate_verdict(q4_buckets)
    typer.echo(f"    => Verdict Q4 (H2H) : {q4_verdict}")

    typer.echo("\n=== Statut de la baseline officielle ===")
    typer.echo(
        "poisson_simple reste la baseline officielle : aucune amelioration ci-dessus n'est promue "
        "automatiquement en configuration officielle - regle validee explicitement avant execution."
    )

    if "VALIDE" in (q1_verdict, q3_verdict, q4_verdict):
        typer.echo("\n=== Etape combinatoire conditionnelle (NON executee ici) ===")
        typer.echo(
            "Au moins une brique est VALIDEE individuellement. Le protocole prevoit de tester leur "
            "combinaison, mais PAS dans ce meme script : le jeu de test ci-dessus a deja ete consulte "
            "pour la confirmation - le reutiliser pour evaluer une combinaison serait un nouveau data "
            "snooping. Un protocole de combinaison dedie (nouveau split chronologique ou nouveau jeu de "
            "donnees) doit etre concu et valide explicitement avant toute execution."
        )
    else:
        typer.echo("\nAucune brique n'est VALIDEE individuellement : pas d'etape combinatoire a executer.")


if __name__ == "__main__":
    app()
