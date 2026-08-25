"""CLI : controles negatifs de specificite de l'etape 5 (E1 et E7).

Verifie que le pipeline de test statistique ne detecte PAS de signal la
ou le generateur synthetique n'en injecte aucun (aucun mecanisme de
fatigue de calendrier, aucun mecanisme "must-win" dans
``data_engine/synthetic/generator.py``) - voir
``football_model/negative_controls.py`` pour l'avertissement complet sur
la portee de ce test.

Pour chaque match evalue en walk-forward (Poisson simple, sans A1/A2,
comme reference neutre), et pour chaque APPARITION d'equipe (domicile ou
exterieur) :

- E1 : l'equipe a-t-elle deja joue >= 2 matchs dans les 7 jours precedant
  celui-ci (calendrier charge) ? Calcule depuis les seules dates de
  coup d'envoi (information publique bien avant le match, aucun risque
  de fuite).
- E7 (proxy) : l'equipe est-elle en méforme recente (taux de victoire
  glissant sur 10 matchs < 30%) ? Calcule depuis les seuls resultats
  CONNUS a l'instant de decision (``repository.get_as_of``, point-in-time
  strict).

Le residu compare est (buts reellement marques - buts attendus par le
modele) pour cette apparition d'equipe. Un test bootstrap non apparie
(deux groupes independants) compare la distribution du residu du
sous-groupe au reste de l'echantillon.

Regle d'acceptation/rejet PRE-ENREGISTREE : l'issue ATTENDUE est un IC95%
incluant 0 (aucun signal). Un IC95% excluant 0 est signale comme
ANOMALIE METHODOLOGIQUE A INVESTIGUER, jamais promu en feature - conforme
a l'instruction explicite de ne pas transformer un resultat inattendu en
feature exploitable sans validation humaine prealable.

Usage:
    python scripts/run_stage5_negative_controls.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.walk_forward import ModelConfig, run_walk_forward  # noqa: E402
from sys_foot_quant.calibration_engine.significance import two_sample_bootstrap_test  # noqa: E402
from sys_foot_quant.common.config import load_config  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository  # noqa: E402
from sys_foot_quant.data_engine.storage.writer import write_dataset  # noqa: E402
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset  # noqa: E402
from sys_foot_quant.football_model.negative_controls import (  # noqa: E402
    is_calendar_congested,
    is_must_win_proxy,
    prior_kickoffs_for_team,
    prior_results_for_team,
    rolling_win_rate,
)
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_WIN_RATE_WINDOW = 10
_MUST_WIN_THRESHOLD = 0.3
_CONGESTION_WINDOW_DAYS = 7.0


def _poisson_reference_config() -> ModelConfig:
    return ModelConfig(name="poisson_simple", fit=lambda df, t: PoissonModel(use_team_hfa=False).fit(df))


@app.command()
def main(
    config: Path = typer.Option(Path("configs/stage2_walk_forward.yaml")),
    data_dir: Path = typer.Option(Path("data/raw_stage5_negctrl")),
    n_resamples: int = typer.Option(2000),
    seed: int = typer.Option(0),
) -> None:
    cfg = load_config(config)
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
            model_configs=[_poisson_reference_config()],
            include_market_benchmark=False,
        )

        residual_e1_congested: list[float] = []
        residual_e1_rest: list[float] = []
        residual_e7_must_win: list[float] = []
        residual_e7_rest: list[float] = []

        for ev in evaluations:
            lm = ev.lambda_mu.get("poisson_simple")
            if lm is None:
                continue
            lam, mu = lm
            this_kickoff = all_matches.set_index("match_id").loc[ev.match_id, "kickoff_time"]

            for team_id, expected_goals, actual_goals in (
                (ev.home_team_id, lam, ev.home_goals),
                (ev.away_team_id, mu, ev.away_goals),
            ):
                residual = actual_goals - expected_goals

                prior_kickoffs = prior_kickoffs_for_team(repo, team_id, ev.decision_time, this_kickoff)
                congested = is_calendar_congested(
                    this_kickoff, prior_kickoffs, window_days=_CONGESTION_WINDOW_DAYS
                )
                if congested:
                    residual_e1_congested.append(residual)
                else:
                    residual_e1_rest.append(residual)

                prior_results = prior_results_for_team(repo, team_id, ev.decision_time, this_kickoff)
                win_rate = rolling_win_rate(prior_results, window=_WIN_RATE_WINDOW)
                must_win = is_must_win_proxy(win_rate, threshold=_MUST_WIN_THRESHOLD)
                if must_win is None:
                    continue
                if must_win:
                    residual_e7_must_win.append(residual)
                else:
                    residual_e7_rest.append(residual)

    typer.echo(f"{n_total} matchs, {len(eval_ids)} evalues (Poisson simple, reference neutre).\n")

    typer.echo("=== E1 - calendrier charge (>=3e match en 7 jours) : controle negatif ===")
    typer.echo(
        f"n_congestionne={len(residual_e1_congested)}  n_reste={len(residual_e1_rest)}"
    )
    if residual_e1_congested and residual_e1_rest:
        result_e1 = two_sample_bootstrap_test(
            residual_e1_congested, residual_e1_rest, n_resamples=n_resamples, seed=seed
        )
        typer.echo(
            f"diff_moy(residu)={result_e1['mean_diff']:+.4f} "
            f"IC95%=[{result_e1['ci_low']:+.4f}, {result_e1['ci_high']:+.4f}] "
            f"p={result_e1['p_value']:.4f}"
        )
        if result_e1["ci_low"] <= 0.0 <= result_e1["ci_high"]:
            typer.echo("-> Aucun signal detecte (attendu). H0 non rejete.")
        else:
            typer.echo(
                "-> ALERTE METHODOLOGIQUE : signal detecte alors qu'aucun mecanisme de fatigue "
                "n'est injecte dans le generateur. A investiguer (fuite d'information ou biais "
                "de construction du sous-groupe) - NE PAS promouvoir en feature."
            )
    else:
        typer.echo("-> Echantillon insuffisant pour ce controle.")

    typer.echo("\n=== E7 - forme recente < 30% (proxy must-win) : controle negatif ===")
    typer.echo(f"n_must_win={len(residual_e7_must_win)}  n_reste={len(residual_e7_rest)}")
    if residual_e7_must_win and residual_e7_rest:
        result_e7 = two_sample_bootstrap_test(
            residual_e7_must_win, residual_e7_rest, n_resamples=n_resamples, seed=seed
        )
        typer.echo(
            f"diff_moy(residu)={result_e7['mean_diff']:+.4f} "
            f"IC95%=[{result_e7['ci_low']:+.4f}, {result_e7['ci_high']:+.4f}] "
            f"p={result_e7['p_value']:.4f}"
        )
        if result_e7["ci_low"] <= 0.0 <= result_e7["ci_high"]:
            typer.echo("-> Aucun signal detecte (attendu). H0 non rejete.")
        else:
            typer.echo(
                "-> ALERTE METHODOLOGIQUE : signal detecte alors qu'aucun mecanisme must-win "
                "n'est injecte dans le generateur. A investiguer - NE PAS promouvoir en feature."
            )
    else:
        typer.echo("-> Echantillon insuffisant pour ce controle.")


if __name__ == "__main__":
    app()
