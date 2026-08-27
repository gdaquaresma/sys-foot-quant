"""CLI : re-test hors echantillon de l'hypothese B1 (Dixon-Coles) sur
DONNEES REELLES Understat (docs/research_framework.md section B1).

Contexte : B1 a deja ete VALIDE sur donnees SYNTHETIQUES dediees
(`scripts/run_stage5_b1_dixon_coles.py`, rho=-0.13 injecte
artificiellement) - `docs/architecture.md` documente explicitement que
cette validation "ne constitue PAS une preuve d'amelioration sur donnees
reelles, a re-tester des la connexion d'une source reelle". Ce script est
exactement ce re-test, maintenant que B3/B3.2/C7 ont etabli une source de
donnees reelles (Understat, 3 championnats x 2 saisons).

Question testee, unique et isolee : `DixonColesModel` (correction de
correlation basse-score 0-0/1-0/0-1/1-1) ameliore-t-il `poisson_simple` sur
des RESULTATS REELS de football, par rapport a `poisson_simple` seul ?
`DixonColesModel` est reutilise SANS AUCUNE MODIFICATION
(`football_model/dixon_coles.py`) : son unique parametre libre, `rho`, est
re-estime par maximum de vraisemblance a CHAQUE fit walk-forward (sur les
donnees d'entrainement disponibles a `decision_time` uniquement) - c'est le
meme mecanisme deja valide sur synthetique, PAS une optimisation nouvelle
sur les donnees reelles. Aucun xG n'est utilise (buts reels uniquement,
comme B1 originellement specifie).

Donnees : 3 championnats (Ligue 1, Premier League, Liga) x 2 saisons
(2024/25, 2025/26) - memes fichiers deja telecharges et verifies pour
B3/B3.2/C7, aucun nouveau connecteur.

Protocole (pre-enregistre, valide avant execution - voir echange de
validation) :
1. Point-in-time : reutilise SANS MODIFICATION
   `backtesting_engine/real_data_walk_forward.py` (buts connus a
   kickoff+2h, meme convention que B3/B3.2/C7 ; xG jamais utilise ici).
2. Scission chronologique a trois voies PAR CHAMPIONNAT ET PAR SAISON
   (rodage 40%, validation 30%, test 30% - meme code de split que B3),
   les deux saisons de chaque championnat etant traitees independamment
   puis leurs jeux de TEST regroupes pour le rapport "par championnat".
3. `DixonColesModel(use_team_hfa=False)` vs `poisson_simple`
   (`PoissonModel(use_team_hfa=False)`) - HFA par equipe desactive des
   deux cotes, exactement comme le script synthetique B1, pour isoler
   strictement la question testee (correction de la loi jointe des
   scores).
4. Metrique de decision : Brier score, diff = dixon_coles - poisson_simple
   (negatif = Dixon-Coles meilleur), bootstrap apparie, IC95%. Analyse
   bas-score (0-0, 1-0, 0-1, 1-1) rapportee separement, cible precise du
   mecanisme tau(x,y;rho).
5. Verdict a 3 categories, PAR CHAMPIONNAT (saisons regroupees) puis
   agrege sur les trois :
   - VALIDE : IC95% de la difference de Brier GLOBALE entierement < 0 ET
     diff bas-score de meme sens (<=0, mecanisme coherent avec
     l'amelioration globale), sur LES TROIS championnats.
   - REJETE : AUCUN des trois championnats n'atteint "dixon_coles
     significativement meilleur" (couvre a la fois "significativement
     pire" et "aucun signal", conformement a "absence d'amelioration
     coherente sur les trois championnats").
   - INDETERMINE : desaccord reel entre championnats (au moins un
     "dixon_coles meilleur" mais pas les trois), ou amelioration globale
     significative non confirmee par le sous-ensemble bas-score.
6. Aucune autre correction, aucune autre valeur de parametre, aucune
   variante de Dixon-Coles, aucun sous-ensemble favorable choisi apres
   coup - critères de decision fixes AVANT tout calcul, jamais ajustes.

Usage:
    python scripts/run_stage5_b1_dixon_coles_real.py
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
    to_probs_and_outcomes,
)
from sys_foot_quant.calibration_engine.low_score_metrics import (  # noqa: E402
    cell_contribution_table,
    low_score_category_row,
    low_score_outcome_index,
)
from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.football_model.dixon_coles import DixonColesModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_VALIDATION_FRACTION_OF_REMAINDER = 0.5  # -> ~40/30/30 rodage/validation/test, meme convention que B3
_DECISION_OFFSET_HOURS = 2.0
_MIN_TRAIN_MATCHES = 10

_EXPECTED_MATCHES = {"ligue1": 306, "premier_league": 380, "liga": 380}
_EXPECTED_TEAMS = {"ligue1": 18, "premier_league": 20, "liga": 20}

_SEASONS = {
    "2024_25": {
        "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2024_datesData.json")),
        "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2024_datesData.json")),
        "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2024_datesData.json")),
    },
    "2025_26": {
        "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2025_datesData.json")),
        "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2025_datesData.json")),
        "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2025_datesData.json")),
    },
}


def _verify_integrity(name: str, raw: list[dict]) -> None:
    n = len(raw)
    if n != _EXPECTED_MATCHES[name]:
        raise ValueError(f"{name}: {n} matchs trouves, {_EXPECTED_MATCHES[name]} attendus.")
    ids = [m["id"] for m in raw]
    if len(set(ids)) != n:
        raise ValueError(f"{name}: doublons de match_id detectes.")
    if sum(1 for m in raw if m.get("isResult")) != n:
        raise ValueError(f"{name}: des matchs n'ont pas isResult=true.")
    missing_score = sum(1 for m in raw if m["goals"]["h"] is None or m["goals"]["a"] is None)
    if missing_score:
        raise ValueError(f"{name}: {missing_score} scores manquants.")
    teams = {m["h"]["title"] for m in raw} | {m["a"]["title"] for m in raw}
    if len(teams) != _EXPECTED_TEAMS[name]:
        raise ValueError(f"{name}: {len(teams)} equipes trouvees, {_EXPECTED_TEAMS[name]} attendues.")


def _fit_poisson_simple(goals_df, xg_df, decision_time):
    # xg_df recu par l'interface commune mais jamais utilise - aucun xG dans ce protocole.
    return PoissonModel(use_team_hfa=False).fit(goals_df)


def _fit_dixon_coles(goals_df, xg_df, decision_time):
    return DixonColesModel(use_team_hfa=False).fit(goals_df)


class _LowScoreWrapper:
    """Expose ``predict_low_score_probs`` sous l'interface ``predict``
    attendue par ``run_real_data_walk_forward`` - permet de reutiliser ce
    mecanisme SANS MODIFICATION pour un second passage dedie au
    sous-ensemble bas-score, plutot que d'y ajouter un canal de capture."""

    def __init__(self, model) -> None:
        self._model = model

    def predict(self, home_team_id: int, away_team_id: int) -> tuple[float, float, float, float]:
        return self._model.predict_low_score_probs(home_team_id, away_team_id)


def _fit_poisson_simple_lowscore(goals_df, xg_df, decision_time):
    return _LowScoreWrapper(PoissonModel(use_team_hfa=False).fit(goals_df))


def _fit_dixon_coles_lowscore(goals_df, xg_df, decision_time):
    return _LowScoreWrapper(DixonColesModel(use_team_hfa=False).fit(goals_df))


def _split_eval_ids(records) -> tuple[list[str], list[str]]:
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    n_total = len(ordered)
    n_burn_in = int(n_total * _BURN_IN_FRACTION)
    n_remaining = n_total - n_burn_in
    n_validation = int(n_remaining * _VALIDATION_FRACTION_OF_REMAINDER)
    validation_ids = [r.match_id for r in ordered[n_burn_in : n_burn_in + n_validation]]
    test_ids = [r.match_id for r in ordered[n_burn_in + n_validation :]]
    return validation_ids, test_ids


def _load_records(name: str, season: str):
    league_id, path = _SEASONS[season][name]
    with open(path) as f:
        raw = json.load(f)
    _verify_integrity(name, raw)
    return build_real_match_records(raw, league=league_id)


def _low_score_records(evaluations) -> pd.DataFrame:
    """Une ligne par match du sous-ensemble bas-score reellement observe,
    avec Brier/log loss (categorisation 5 classes) de chaque modele."""
    rows = []
    for ev in evaluations:
        cell = low_score_outcome_index(ev.home_goals, ev.away_goals)
        if cell is None:
            continue
        p_poisson = ev.predictions.get("poisson_simple_lowscore")
        p_dc = ev.predictions.get("dixon_coles_lowscore")
        if p_poisson is None or p_dc is None:
            continue
        row_poisson = low_score_category_row(p_poisson)
        row_dc = low_score_category_row(p_dc)
        outcome_arr = np.array([cell])
        rows.append(
            {
                "cell": cell,
                "brier_a": brier_score(np.array([row_poisson]), outcome_arr),
                "brier_b": brier_score(np.array([row_dc]), outcome_arr),
                "log_loss_a": log_loss(np.array([row_poisson]), outcome_arr),
                "log_loss_b": log_loss(np.array([row_dc]), outcome_arr),
            }
        )
    return pd.DataFrame(rows)


def _paired_metric_diffs(evaluations, model_a: str, model_b: str, metric_fn) -> np.ndarray:
    diffs = []
    for ev in evaluations:
        pa = ev.predictions.get(model_a)
        pb = ev.predictions.get(model_b)
        if pa is None or pb is None:
            continue
        outcome_arr = np.array([ev.outcome])
        diffs.append(metric_fn(np.array([pb]), outcome_arr) - metric_fn(np.array([pa]), outcome_arr))
    return np.array(diffs)


def _process_league_season(name: str, season: str) -> dict:
    records = _load_records(name, season)
    validation_ids, test_ids = _split_eval_ids(records)

    outcome_configs = [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="dixon_coles", fit=_fit_dixon_coles, min_train_matches=_MIN_TRAIN_MATCHES),
    ]
    lowscore_configs = [
        RealModelConfig(
            name="poisson_simple_lowscore", fit=_fit_poisson_simple_lowscore, min_train_matches=_MIN_TRAIN_MATCHES
        ),
        RealModelConfig(
            name="dixon_coles_lowscore", fit=_fit_dixon_coles_lowscore, min_train_matches=_MIN_TRAIN_MATCHES
        ),
    ]

    validation_evals = run_real_data_walk_forward(
        records, eval_match_ids=validation_ids, decision_offset_hours=_DECISION_OFFSET_HOURS,
        model_configs=outcome_configs,
    )
    test_evals = run_real_data_walk_forward(
        records, eval_match_ids=test_ids, decision_offset_hours=_DECISION_OFFSET_HOURS,
        model_configs=outcome_configs,
    )
    test_lowscore_evals = run_real_data_walk_forward(
        records, eval_match_ids=test_ids, decision_offset_hours=_DECISION_OFFSET_HOURS,
        model_configs=lowscore_configs,
    )

    return {
        "n_total": len(records),
        "n_validation": len(validation_ids),
        "n_test": len(test_ids),
        "validation_evals": validation_evals,
        "test_evals": test_evals,
        "test_lowscore_evals": test_lowscore_evals,
    }


def _bucket_verdict(global_ci_low: float, global_ci_high: float, low_score_mean_diff: float) -> str:
    if global_ci_high < 0.0:
        return "dixon_coles_meilleur" if low_score_mean_diff <= 0.0 else "indetermine"
    if global_ci_low > 0.0:
        return "poisson_simple_meilleur"
    return "indetermine"


def _aggregate_verdict(buckets: list[str]) -> str:
    if all(b == "dixon_coles_meilleur" for b in buckets):
        return "VALIDE"
    if not any(b == "dixon_coles_meilleur" for b in buckets):
        return "REJETE"
    return "INDETERMINE"


@app.command()
def main(
    n_resamples: int = typer.Option(2000),
    seed: int = typer.Option(0),
) -> None:
    typer.echo("=== B1 (Dixon-Coles) re-test hors echantillon, donnees REELLES Understat ===")
    typer.echo("diff = dixon_coles - poisson_simple (Brier) ; negatif = Dixon-Coles meilleur.\n")

    per_league_results = {}
    buckets = []
    for name in _EXPECTED_MATCHES:
        typer.echo(f"--- {name} ---")
        season_results = {season: _process_league_season(name, season) for season in _SEASONS}
        for season, r in season_results.items():
            typer.echo(
                f"  [{season}] n_total={r['n_total']} n_validation={r['n_validation']} n_test={r['n_test']}"
            )

        pooled_test_evals = [ev for r in season_results.values() for ev in r["test_evals"]]
        pooled_lowscore_evals = [ev for r in season_results.values() for ev in r["test_lowscore_evals"]]
        pooled_validation_evals = [ev for r in season_results.values() for ev in r["validation_evals"]]

        for label, evals in [("validation (informationnel)", pooled_validation_evals), ("test", pooled_test_evals)]:
            for model_name in ["poisson_simple", "dixon_coles"]:
                probs, outcomes = to_probs_and_outcomes(evals, model_name)
                if len(outcomes) == 0:
                    continue
                b = brier_score(probs, outcomes)
                ll = log_loss(probs, outcomes)
                typer.echo(f"  [{label}] {model_name:<16} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")

        global_diffs = _paired_metric_diffs(pooled_test_evals, "poisson_simple", "dixon_coles", brier_score)
        global_boot = paired_bootstrap_test(global_diffs, n_resamples=n_resamples, seed=seed)
        typer.echo(
            f"  [TEST GLOBAL] diff(dc-poisson) n={global_diffs.size:<4} diff_moy={global_boot['mean_diff']:+.5f} "
            f"IC95%=[{global_boot['ci_low']:+.5f}, {global_boot['ci_high']:+.5f}] p={global_boot['p_value']:.4f}"
        )

        low_records = _low_score_records(pooled_lowscore_evals)
        n_low_score = len(low_records)
        low_diffs = (low_records["brier_b"] - low_records["brier_a"]).to_numpy() if n_low_score else np.array([])
        low_boot = (
            paired_bootstrap_test(low_diffs, n_resamples=n_resamples, seed=seed)
            if n_low_score > 0
            else {"mean_diff": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "p_value": float("nan")}
        )
        typer.echo(
            f"  [TEST BAS-SCORE] n={n_low_score} diff_moy(dc-poisson)={low_boot['mean_diff']:+.5f} "
            f"IC95%=[{low_boot['ci_low']:+.5f}, {low_boot['ci_high']:+.5f}] p={low_boot['p_value']:.4f}"
        )
        if n_low_score:
            contrib = cell_contribution_table(low_records)
            for _, row in contrib.iterrows():
                typer.echo(
                    f"    {row['cell']:<5} n={int(row['n']):<4} brier_poisson={row['brier_a_mean']:.5f} "
                    f"brier_dc={row['brier_b_mean']:.5f} diff={row['brier_diff_b_minus_a']:+.5f}"
                )

        bucket = _bucket_verdict(global_boot["ci_low"], global_boot["ci_high"], low_boot["mean_diff"])
        buckets.append(bucket)
        typer.echo(f"  -> {bucket}\n")

        per_league_results[name] = {
            "n_test": len(pooled_test_evals),
            "n_low_score": n_low_score,
            "global_boot": global_boot,
            "low_score_boot": low_boot,
            "bucket": bucket,
        }

    verdict = _aggregate_verdict(buckets)
    typer.echo("=== VERDICT B1 (Dixon-Coles vs poisson_simple, donnees reelles, regle pre-enregistree) ===")
    for name, r in per_league_results.items():
        typer.echo(
            f"  {name:<16} n_test={r['n_test']:<5} n_bas_score={r['n_low_score']:<4} "
            f"diff_global={r['global_boot']['mean_diff']:+.4f} "
            f"IC95%=[{r['global_boot']['ci_low']:+.4f}, {r['global_boot']['ci_high']:+.4f}] "
            f"diff_bas_score={r['low_score_boot']['mean_diff']:+.4f} -> {r['bucket']}"
        )
    typer.echo(f"\n=== Verdict agrege (trois championnats) : {verdict} ===")

    if verdict == "VALIDE":
        typer.echo(
            "Dixon-Coles ameliore significativement le Brier score par rapport a poisson_simple, "
            "de facon coherente sur les trois championnats, avec un mecanisme bas-score de meme sens."
        )
    elif verdict == "REJETE":
        typer.echo(
            "Aucun championnat ne montre Dixon-Coles significativement meilleur que poisson_simple "
            "sur donnees reelles - absence d'amelioration coherente."
        )
    else:
        typer.echo(
            "Resultats incoherents entre championnats, ou amelioration globale non confirmee par le "
            "sous-ensemble bas-score cible."
        )
    typer.echo(
        "\npoisson_simple reste la baseline officielle quel que soit ce verdict - aucune promotion "
        "automatique. Aucune autre correction, aucun autre parametre, aucune variante n'ont ete testes."
    )
    typer.echo(
        "\nRESERVE (point-in-time, pas une fuite de donnees) : buts reels connus a kickoff+2h (meme "
        "convention que B3/B3.2/C7), aucun xG utilise. Invariant PIT garanti par construction et "
        "verifie par tests/leakage/ (mecanisme reutilise sans modification)."
    )


if __name__ == "__main__":
    app()
