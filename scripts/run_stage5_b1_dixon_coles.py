"""CLI : walk-forward hors echantillon de l'etape 5, hypothese B1
(Dixon-Coles, docs/research_framework.md section B1).

Compare, sur un scenario synthetique DEDIE (configs/stage5_dixon_coles.yaml,
rho=-0.13 - voir docs/decisions/0005-protocole-generateur-dixon-coles.md
pour le protocole complet de generation), la correction de correlation
basse-score de Dixon-Coles (``football_model.dixon_coles.DixonColesModel``)
a notre baseline officielle ``poisson_simple``
(``PoissonModel(use_team_hfa=False)``, meme definition que dans
run_stage5_b2_walk_forward.py). Le HFA par equipe (A2) est desactive des
deux cotes pour isoler strictement la question testee (correction de la
loi jointe des scores), exactement comme A1/A2 sont isoles dans les
scripts precedents.

Regle d'acceptation/rejet PRE-ENREGISTREE (protocole valide avant toute
execution) :
- Metrique de decision : Brier restreint au sous-ensemble des matchs dont
  le score reel est l'une des quatre cellules bas-score (0-0, 1-0, 0-1,
  1-1) - c'est precisement le sous-ensemble que tau(x,y;rho) cible. Log
  loss sur ce meme sous-ensemble est rapporte en complement (jamais seul
  decisif, meme convention que le reste du projet : Brier est la metrique
  de decision, log loss un controle croise).
- VALIDE : IC95% bas de (Brier_poisson_simple - Brier_dixon_coles) sur le
  SOUS-ENSEMBLE BAS-SCORE > 0 (Dixon-Coles ameliore significativement,
  precisement la ou l'hypothese le predit).
- INDETERMINE : le sous-ensemble bas-score ne montre PAS d'amelioration
  significative, MAIS la metrique globale (Brier 1X2 sur tous les matchs
  evalues, meme calcul qu'aux etapes 2-5) montre elle une amelioration
  significative - une amelioration seulement globale, sans confirmation
  sur le sous-ensemble cible, ne valide pas le mecanisme specifiquement
  invoque par B1.
- REJETE : aucune des deux conditions precedentes n'est remplie (ni
  amelioration significative bas-score, ni amelioration significative
  globale) - couvre a la fois "aucune difference" et "Dixon-Coles
  significativement pire".

Controle negatif (rho=0.0, configs/stage5_dixon_coles_rho0.yaml, meme
principe que E1/E7) : rapporte separement, PAS utilise pour le verdict
ci-dessus - sert uniquement a verifier que le pipeline de test lui-meme
(protocole, metriques, generateur) ne produit pas un signal fantome
lorsqu'aucune correlation n'est reellement injectee.

Test de gliding (Miller & Davidow, methodologie - voir
docs/research_framework_audit.md section E et l'ajout correspondant dans
docs/research_framework.md section E) : verifie, a titre de controle
METHODOLOGIQUE SECONDAIRE (n'entre PAS dans le verdict ci-dessus), si
l'amelioration Dixon-Coles sur le sous-ensemble bas-score varie de facon
CONTINUE avec |rho| plutot que de n'apparaitre qu'a la valeur -0.13
retenue - utilise un scenario plus petit (n_matches reduit) pour rester
rapide, execute sur une grille de rho fixee a l'avance.

Usage:
    python scripts/run_stage5_b1_dixon_coles.py
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
    to_low_score_probs_and_goals,
    to_probs_and_outcomes,
)
from sys_foot_quant.calibration_engine.low_score_metrics import (  # noqa: E402
    LOW_SCORE_LABELS,
    cell_contribution_table,
    low_score_category_row,
    low_score_outcome_index,
)
from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.config import SyntheticDataConfig, load_config  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository  # noqa: E402
from sys_foot_quant.data_engine.storage.writer import write_dataset  # noqa: E402
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset  # noqa: E402
from sys_foot_quant.football_model.dixon_coles import DixonColesModel  # noqa: E402
from sys_foot_quant.football_model.naive import NaiveModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_MAIN_CONFIG = Path("configs/stage5_dixon_coles.yaml")
_CONTROL_CONFIG = Path("configs/stage5_dixon_coles_rho0.yaml")

# Grille de gliding PRE-ENREGISTREE (jamais ajustee apres observation des
# resultats) : n'inclut pas -0.13 pour rester clairement distincte du
# scenario de decision principal.
_GLIDING_RHOS = (0.0, -0.05, -0.10, -0.20)
_GLIDING_N_MATCHES = 1200
_GLIDING_N_RESAMPLES = 500


def _poisson_simple_config() -> ModelConfig:
    return ModelConfig(
        name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df)
    )


def _dixon_coles_config() -> ModelConfig:
    return ModelConfig(
        name="dixon_coles", fit=lambda df, t: DixonColesModel(use_team_hfa=False).fit(df)
    )


def _naive_config() -> ModelConfig:
    return ModelConfig(name="naive", fit=lambda df, t: NaiveModel().fit(df))


def _global_metric_diffs(evaluations, model_a: str, model_b: str, metric_fn) -> np.ndarray:
    """diff = metric(model_a) - metric(model_b), par match (meme pattern
    que run_stage5_b2_walk_forward.py)."""
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


def _low_score_records(evaluations, model_a: str, model_b: str) -> pd.DataFrame:
    """Une ligne par match dont le score reel EST l'une des quatre
    cellules bas-score, avec le Brier/log loss (categorisation 5 classes,
    voir calibration_engine.low_score_metrics) de chaque modele pour CE
    match precis."""
    probs_a, home_a, away_a = to_low_score_probs_and_goals(evaluations, model_a)
    probs_b, home_b, away_b = to_low_score_probs_and_goals(evaluations, model_b)
    # Les deux modeles sont toujours fits/predits sur les memes matchs
    # dans ce script (aucun des deux ne peut etre absent independamment de
    # l'autre) - verifie explicitement plutot que suppose silencieusement.
    if not (np.array_equal(home_a, home_b) and np.array_equal(away_a, away_b)):
        raise RuntimeError(
            "Les deux modeles compares n'ont pas ete evalues sur exactement les "
            "memes matchs - le walk-forward doit produire des predictions "
            "appariees pour ce protocole."
        )

    rows = []
    for i in range(len(home_a)):
        cell = low_score_outcome_index(int(home_a[i]), int(away_a[i]))
        if cell is None:
            continue
        row_a = low_score_category_row(probs_a[i])
        row_b = low_score_category_row(probs_b[i])
        outcome_arr = np.array([cell])
        rows.append(
            {
                "cell": cell,
                "brier_a": brier_score(np.array([row_a]), outcome_arr),
                "brier_b": brier_score(np.array([row_b]), outcome_arr),
                "log_loss_a": log_loss(np.array([row_a]), outcome_arr),
                "log_loss_b": log_loss(np.array([row_b]), outcome_arr),
            }
        )
    return pd.DataFrame(rows)


def _run_walk_forward_for_config(config_path: Path, data_dir: Path):
    cfg = load_config(config_path)
    dataset = generate_synthetic_dataset(cfg.synthetic_data)
    write_dataset(dataset, data_dir)

    with DuckDBRepository(data_dir) as repo:
        all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
        n_total = len(all_matches)
        n_burn_in = int(n_total * _BURN_IN_FRACTION)
        eval_ids = all_matches["match_id"].iloc[n_burn_in:].tolist()

        model_configs = [_naive_config(), _poisson_simple_config(), _dixon_coles_config()]
        evaluations = run_walk_forward(
            repository=repo,
            eval_match_ids=eval_ids,
            decision_offset_hours=cfg.decision_offset_hours_before_kickoff,
            model_configs=model_configs,
            include_market_benchmark=False,
        )
    return n_total, evaluations


def _report_scenario(
    scenario_name: str, evaluations, n_total: int, n_resamples: int, seed: int, verbose: bool = True
) -> dict:
    if verbose:
        typer.echo(f"\n--- Scenario '{scenario_name}' ({n_total} matchs, {len(evaluations)} evalues) ---")
        for name in ["naive", "poisson_simple", "dixon_coles"]:
            probs, outcomes = to_probs_and_outcomes(evaluations, name)
            b = brier_score(probs, outcomes)
            ll = log_loss(probs, outcomes)
            typer.echo(f"{name:<16} n={len(outcomes):<5} brier(1X2)={b:>8.4f} log_loss(1X2)={ll:>8.4f}")

    # --- Metrique globale (Brier/log loss 1X2, deja utilisee aux etapes 2-5) ---
    global_diffs_brier = _global_metric_diffs(evaluations, "poisson_simple", "dixon_coles", brier_score)
    global_diffs_ll = _global_metric_diffs(evaluations, "poisson_simple", "dixon_coles", log_loss)
    global_boot_brier = paired_bootstrap_test(global_diffs_brier, n_resamples=n_resamples, seed=seed)
    global_boot_ll = paired_bootstrap_test(global_diffs_ll, n_resamples=n_resamples, seed=seed)

    if verbose:
        typer.echo(
            f"  [GLOBAL] diff(poisson-dc) brier n={global_diffs_brier.size:<4} "
            f"diff_moy={global_boot_brier['mean_diff']:+.5f} "
            f"IC95%=[{global_boot_brier['ci_low']:+.5f}, {global_boot_brier['ci_high']:+.5f}] "
            f"p={global_boot_brier['p_value']:.4f}"
        )
        typer.echo(
            f"  [GLOBAL] diff(poisson-dc) log_loss n={global_diffs_ll.size:<4} "
            f"diff_moy={global_boot_ll['mean_diff']:+.5f} "
            f"IC95%=[{global_boot_ll['ci_low']:+.5f}, {global_boot_ll['ci_high']:+.5f}] "
            f"p={global_boot_ll['p_value']:.4f}"
        )

    # --- Metrique bas-score (protocole B1) ---
    records = _low_score_records(evaluations, "poisson_simple", "dixon_coles")
    n_low_score = len(records)
    low_diffs_brier = (records["brier_a"] - records["brier_b"]).to_numpy()
    low_diffs_ll = (records["log_loss_a"] - records["log_loss_b"]).to_numpy()
    low_boot_brier = paired_bootstrap_test(low_diffs_brier, n_resamples=n_resamples, seed=seed)
    low_boot_ll = paired_bootstrap_test(low_diffs_ll, n_resamples=n_resamples, seed=seed)

    if verbose:
        typer.echo(f"  [BAS-SCORE] n_low_score={n_low_score} (sur {len(evaluations)} matchs evalues)")
        typer.echo(
            f"  [BAS-SCORE] brier_poisson_simple_moy={records['brier_a'].mean():.5f} "
            f"brier_dixon_coles_moy={records['brier_b'].mean():.5f}"
        )
        typer.echo(
            f"  [BAS-SCORE] diff(poisson-dc) brier "
            f"diff_moy={low_boot_brier['mean_diff']:+.5f} "
            f"IC95%=[{low_boot_brier['ci_low']:+.5f}, {low_boot_brier['ci_high']:+.5f}] "
            f"p={low_boot_brier['p_value']:.4f}"
        )
        typer.echo(
            f"  [BAS-SCORE] log_loss_poisson_simple_moy={records['log_loss_a'].mean():.5f} "
            f"log_loss_dixon_coles_moy={records['log_loss_b'].mean():.5f}"
        )
        typer.echo(
            f"  [BAS-SCORE] diff(poisson-dc) log_loss "
            f"diff_moy={low_boot_ll['mean_diff']:+.5f} "
            f"IC95%=[{low_boot_ll['ci_low']:+.5f}, {low_boot_ll['ci_high']:+.5f}] "
            f"p={low_boot_ll['p_value']:.4f}"
        )

        contrib = cell_contribution_table(records)
        typer.echo("  [CONTRIBUTION PAR CELLULE] (diff_b_minus_a < 0 => dixon_coles fait moins d'erreur)")
        for _, row in contrib.iterrows():
            typer.echo(
                f"    {row['cell']:<5} n={int(row['n']):<4} "
                f"brier_poisson={row['brier_a_mean']:.5f} brier_dc={row['brier_b_mean']:.5f} "
                f"diff={row['brier_diff_b_minus_a']:+.5f}  "
                f"log_loss_poisson={row['log_loss_a_mean']:.5f} log_loss_dc={row['log_loss_b_mean']:.5f} "
                f"diff={row['log_loss_diff_b_minus_a']:+.5f}"
            )

    return {
        "n_total": n_total,
        "n_evaluated": len(evaluations),
        "n_low_score": n_low_score,
        "global_brier": global_boot_brier,
        "global_log_loss": global_boot_ll,
        "low_score_brier": low_boot_brier,
        "low_score_log_loss": low_boot_ll,
        "cell_contribution": cell_contribution_table(records),
    }


def _verdict(global_brier: dict, low_score_brier: dict) -> str:
    if low_score_brier["ci_low"] > 0.0:
        return "VALIDE"
    if global_brier["ci_low"] > 0.0:
        return "INDETERMINE"
    return "REJETE"


def _run_gliding_check(data_dir: Path, seed: int) -> None:
    typer.echo("\n=== Controle methodologique secondaire : test de gliding (Miller & Davidow) ===")
    typer.echo(
        "N'entre PAS dans le verdict VALIDE/INDETERMINE/REJETE ci-dessus. "
        "Verifie si l'amelioration bas-score varie continument avec |rho| "
        f"(grille pre-enregistree {_GLIDING_RHOS}, n_matches={_GLIDING_N_MATCHES})."
    )
    base_config = load_config(_MAIN_CONFIG)
    results = []
    for rho in _GLIDING_RHOS:
        synthetic_cfg: SyntheticDataConfig = base_config.synthetic_data.model_copy(
            update={"n_matches": _GLIDING_N_MATCHES, "dixon_coles_rho": rho}
        )
        dataset = generate_synthetic_dataset(synthetic_cfg)
        scenario_dir = data_dir / f"gliding_rho_{abs(rho):.2f}".replace(".", "_")
        write_dataset(dataset, scenario_dir)
        with DuckDBRepository(scenario_dir) as repo:
            all_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
            n_total = len(all_matches)
            n_burn_in = int(n_total * _BURN_IN_FRACTION)
            eval_ids = all_matches["match_id"].iloc[n_burn_in:].tolist()
            evaluations = run_walk_forward(
                repository=repo,
                eval_match_ids=eval_ids,
                decision_offset_hours=base_config.decision_offset_hours_before_kickoff,
                model_configs=[_poisson_simple_config(), _dixon_coles_config()],
                include_market_benchmark=False,
            )
        report = _report_scenario(
            f"gliding rho={rho}", evaluations, n_total, _GLIDING_N_RESAMPLES, seed, verbose=False
        )
        results.append((rho, report["low_score_brier"]["mean_diff"], report["n_low_score"]))
        typer.echo(
            f"  rho={rho:+.2f}  n_low_score={report['n_low_score']:<4}  "
            f"diff_moy(poisson-dc)={report['low_score_brier']['mean_diff']:+.5f}  "
            f"IC95%=[{report['low_score_brier']['ci_low']:+.5f}, {report['low_score_brier']['ci_high']:+.5f}]"
        )

    diffs_by_abs_rho = sorted(((abs(r), d) for r, d, _ in results), key=lambda t: t[0])
    is_monotonic = all(
        diffs_by_abs_rho[i][1] <= diffs_by_abs_rho[i + 1][1] + 1e-9
        for i in range(len(diffs_by_abs_rho) - 1)
    )
    typer.echo(
        f"  Amelioration bas-score monotone croissante avec |rho| : {is_monotonic} "
        "(indicatif seulement - pas de seuil de significativite impose a ce controle secondaire)."
    )


@app.command()
def main(
    data_dir: Path = typer.Option(Path("data/raw_stage5_b1")),
    n_resamples: int = typer.Option(2000, help="Nombre de reechantillonnages bootstrap."),
    seed: int = typer.Option(0, help="Graine du bootstrap (reproductibilite)."),
    run_gliding: bool = typer.Option(True, help="Executer le controle de gliding (Miller & Davidow)."),
) -> None:
    n_total, evaluations = _run_walk_forward_for_config(_MAIN_CONFIG, data_dir / "main")
    main_report = _report_scenario("dixon_coles_rho_-0.13", evaluations, n_total, n_resamples, seed)

    n_total_ctrl, evaluations_ctrl = _run_walk_forward_for_config(_CONTROL_CONFIG, data_dir / "control_rho0")
    typer.echo("\n=== Controle negatif (rho=0.0) - hors verdict, sanite du pipeline ===")
    control_report = _report_scenario(
        "dixon_coles_rho_0.0_controle", evaluations_ctrl, n_total_ctrl, n_resamples, seed
    )
    control_flag = (
        "OK (aucun signal significatif, comme attendu)"
        if control_report["low_score_brier"]["ci_low"] <= 0.0
        else "ALERTE : signal significatif detecte a rho=0.0, le pipeline de test doit etre investigue"
    )
    typer.echo(f"  Statut controle negatif : {control_flag}")

    if run_gliding:
        _run_gliding_check(data_dir / "gliding", seed)

    verdict = _verdict(main_report["global_brier"], main_report["low_score_brier"])
    typer.echo("\n=== Verdict B1 (Dixon-Coles vs poisson_simple, regle pre-enregistree) ===")
    typer.echo(
        f"n_total={main_report['n_total']} n_evalues={main_report['n_evaluated']} "
        f"n_bas_score={main_report['n_low_score']}"
    )
    typer.echo(
        f"Brier bas-score : diff(poisson-dc)={main_report['low_score_brier']['mean_diff']:+.5f} "
        f"IC95%=[{main_report['low_score_brier']['ci_low']:+.5f}, "
        f"{main_report['low_score_brier']['ci_high']:+.5f}] p={main_report['low_score_brier']['p_value']:.4f}"
    )
    typer.echo(
        f"Brier global   : diff(poisson-dc)={main_report['global_brier']['mean_diff']:+.5f} "
        f"IC95%=[{main_report['global_brier']['ci_low']:+.5f}, "
        f"{main_report['global_brier']['ci_high']:+.5f}] p={main_report['global_brier']['p_value']:.4f}"
    )
    typer.echo(f"VERDICT : {verdict}")
    if verdict == "VALIDE":
        typer.echo(
            "Dixon-Coles ameliore significativement Brier sur le sous-ensemble bas-score "
            "(0-0, 1-0, 0-1, 1-1), conformement a l'hypothese testee."
        )
    elif verdict == "INDETERMINE":
        typer.echo(
            "Amelioration globale significative mais NON confirmee sur le sous-ensemble "
            "bas-score cible - le mecanisme specifique invoque par B1 n'est pas valide, "
            "meme si le modele semble globalement un peu meilleur pour une autre raison."
        )
    else:
        typer.echo(
            "Aucune amelioration significative detectee (ni bas-score, ni globale). "
            "Aucun ajustement de rho ou de protocole ne doit etre tente pour obtenir "
            "un resultat different."
        )


if __name__ == "__main__":
    app()
