"""CLI : test hors echantillon de l'hypothese B3.3 (gate de desaccord
Poisson/xG) sur DONNEES REELLES Understat, EXACTEMENT selon la
specification validee (docs/research_framework.md section B3.3).

Question testee, unique : le systeme `GateDisagreementModel`
(`p_final = (1-w)*p_poisson + w*p_xg`, ou `w = distance de variation
totale(p_poisson, p_xg)` - AUCUN parametre libre) ameliore-t-il
`poisson_simple` sur des resultats reels de football ?

Ce script n'introduit AUCUNE variante par rapport a la specification :
une seule mesure de desaccord (TVD), un seul poids (`w = TVD`, identite),
aucun seuil, aucune grille de calibration. La phase "calibration" est
PUREMENT DIAGNOSTIQUE (verifie que la distribution de TVD n'est pas
degeneree) - aucun chiffre qui en sort n'ajuste le gate ni ne change son
comportement. `poisson_simple` (`PoissonModel(use_team_hfa=False)`)
n'est ni modifie ni retouche.

Protocole (identique a B1/A2/B2 pour le decoupage, integralement fige
avant execution) :
1. Point-in-time : reutilise SANS MODIFICATION
   `backtesting_engine/real_data_walk_forward.py` (buts connus a
   kickoff+2h, xG connu a kickoff+48h, memes conventions que B3/B3.2).
2. Scission chronologique a trois voies PAR CHAMPIONNAT ET PAR SAISON
   (rodage 40%, calibration 30%, test 30%), les deux saisons regroupees
   au niveau du test pour le resultat "par championnat".
3. `GateDisagreementModel` vs `poisson_simple` - Brier appari, IC95%,
   bootstrap, sur le TEST uniquement, evalue une seule fois.
4. Verdict, avec la nuance de force de preuve deja adoptee pour B1/A2/B2/C7 :
   - VALIDE : IC95% entierement < 0 sur LES TROIS championnats.
   - REJETE - inferiorite demontree : IC95% entierement > 0 sur LES TROIS.
   - REJETE - absence de preuve d'amelioration : aucun des trois
     championnats n'atteint une amelioration significative (sans que les
     trois montrent non plus une inferiorite significative).
   - INDETERMINE : desaccord reel entre championnats (au moins un
     "gate meilleur" mais pas les trois).
5. Aucune autre mesure de desaccord, aucun seuil, aucune ponderation
   alternative, aucune recherche du "meilleur poids" apres coup - ce
   script ne doit produire qu'UN SEUL resultat final, jamais reexecute
   avec une variante en cas de resultat decevant.

Usage:
    python scripts/run_stage5_b3_3_gate_disagreement.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (  # noqa: E402
    RealModelConfig,
    build_real_match_records,
    run_real_data_walk_forward,
    to_probs_and_outcomes,
)
from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.football_model.gate_disagreement_model import GateDisagreementModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.scoring import total_variation_distance  # noqa: E402
from sys_foot_quant.football_model.xg_model import XGModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_CALIBRATION_FRACTION_OF_REMAINDER = 0.5  # -> ~40/30/30 rodage/calibration/test, meme convention que B1/A2/B2
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
    missing_xg = sum(1 for m in raw if m["xG"]["h"] is None or m["xG"]["a"] is None)
    if missing_score or missing_xg:
        raise ValueError(f"{name}: {missing_score} scores manquants, {missing_xg} xG manquants.")
    teams = {m["h"]["title"] for m in raw} | {m["a"]["title"] for m in raw}
    if len(teams) != _EXPECTED_TEAMS[name]:
        raise ValueError(f"{name}: {len(teams)} equipes trouvees, {_EXPECTED_TEAMS[name]} attendues.")


def _fit_poisson_simple(goals_df, xg_df, decision_time):
    return PoissonModel(use_team_hfa=False).fit(goals_df)


def _fit_xg(goals_df, xg_df, decision_time):
    return XGModel().fit(xg_df)


def _fit_gate(goals_df, xg_df, decision_time):
    return GateDisagreementModel().fit(goals_df, xg_df)


def _split_eval_ids(records) -> tuple[list[str], list[str]]:
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    n_total = len(ordered)
    n_burn_in = int(n_total * _BURN_IN_FRACTION)
    n_remaining = n_total - n_burn_in
    n_calibration = int(n_remaining * _CALIBRATION_FRACTION_OF_REMAINDER)
    calibration_ids = [r.match_id for r in ordered[n_burn_in : n_burn_in + n_calibration]]
    test_ids = [r.match_id for r in ordered[n_burn_in + n_calibration :]]
    return calibration_ids, test_ids


def _load_records(name: str, season: str):
    league_id, path = _SEASONS[season][name]
    with open(path) as f:
        raw = json.load(f)
    _verify_integrity(name, raw)
    return build_real_match_records(raw, league=league_id)


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


def _tvd_diagnostics(evaluations) -> dict:
    """Diagnostic PUR de la distribution de TVD sur cet ensemble de
    matchs - ne sert qu'a verifier l'absence de degenerescence, ne
    modifie jamais le gate ni son comportement."""
    values = []
    for ev in evaluations:
        p_poisson = ev.predictions.get("poisson_simple")
        p_xg = ev.predictions.get("xg_model")
        if p_poisson is None or p_xg is None:
            continue
        values.append(total_variation_distance(p_poisson, p_xg))
    arr = np.array(values)
    if arr.size == 0:
        return {"n": 0}
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "min": float(arr.min()),
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "max": float(arr.max()),
    }


def _process_league_season(name: str, season: str) -> dict:
    records = _load_records(name, season)
    calibration_ids, test_ids = _split_eval_ids(records)

    diag_configs = [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="xg_model", fit=_fit_xg, min_train_matches=_MIN_TRAIN_MATCHES),
    ]
    main_configs = [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="xg_model", fit=_fit_xg, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="gate", fit=_fit_gate, min_train_matches=_MIN_TRAIN_MATCHES),
    ]

    calibration_evals = run_real_data_walk_forward(
        records, eval_match_ids=calibration_ids, decision_offset_hours=_DECISION_OFFSET_HOURS,
        model_configs=diag_configs,
    )
    test_evals = run_real_data_walk_forward(
        records, eval_match_ids=test_ids, decision_offset_hours=_DECISION_OFFSET_HOURS, model_configs=main_configs
    )

    return {
        "n_total": len(records),
        "n_calibration": len(calibration_ids),
        "n_test": len(test_ids),
        "calibration_tvd": _tvd_diagnostics(calibration_evals),
        "test_evals": test_evals,
    }


def _bucket_verdict(ci_low: float, ci_high: float) -> str:
    if ci_high < 0.0:
        return "gate_meilleur"
    if ci_low > 0.0:
        return "poisson_simple_meilleur"
    return "indetermine"


def _aggregate_verdict(buckets: list[str]) -> str:
    if all(b == "gate_meilleur" for b in buckets):
        return "VALIDE"
    if all(b == "poisson_simple_meilleur" for b in buckets):
        return "REJETE - inferiorite demontree"
    if not any(b == "gate_meilleur" for b in buckets):
        return "REJETE - absence de preuve d'amelioration"
    return "INDETERMINE"


@app.command()
def main(
    n_resamples: int = typer.Option(2000),
    seed: int = typer.Option(0),
) -> None:
    typer.echo("=== B3.3 (gate de desaccord Poisson/xG) hors echantillon, donnees REELLES Understat ===")
    typer.echo("w = TVD(p_poisson, p_xg) ; p_final = (1-w)*p_poisson + w*p_xg ; ZERO parametre libre.")
    typer.echo("diff = Brier_gate - Brier_poisson_simple ; negatif = gate meilleur.\n")

    per_league_results = {}
    buckets = []
    n_total_test_matches = 0
    for name in _EXPECTED_MATCHES:
        typer.echo(f"--- {name} ---")
        season_results = {season: _process_league_season(name, season) for season in _SEASONS}

        for season, r in season_results.items():
            typer.echo(
                f"  [{season}] n_total={r['n_total']} n_calibration={r['n_calibration']} n_test={r['n_test']}"
            )
            diag = r["calibration_tvd"]
            if diag["n"]:
                typer.echo(
                    f"    [calibration, diagnostique uniquement] TVD : n={diag['n']} "
                    f"moyenne={diag['mean']:.4f} ecart-type={diag['std']:.4f} "
                    f"min={diag['min']:.4f} p50={diag['p50']:.4f} p90={diag['p90']:.4f} max={diag['max']:.4f}"
                )

        pooled_test_evals = [ev for r in season_results.values() for ev in r["test_evals"]]
        n_total_test_matches += len(pooled_test_evals)

        typer.echo(f"  --- {name} regroupe (2024/25 + 2025/26), TEST uniquement ---")
        for model_name in ["poisson_simple", "xg_model", "gate"]:
            probs, outcomes = to_probs_and_outcomes(pooled_test_evals, model_name)
            if len(outcomes) == 0:
                continue
            b = brier_score(probs, outcomes)
            ll = log_loss(probs, outcomes)
            typer.echo(f"  {model_name:<16} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")

        diffs = _paired_metric_diffs(pooled_test_evals, "poisson_simple", "gate", brier_score)
        boot = paired_bootstrap_test(diffs, n_resamples=n_resamples, seed=seed)
        typer.echo(
            f"  diff(gate-poisson) n={diffs.size:<4} diff_moy={boot['mean_diff']:+.5f} "
            f"IC95%=[{boot['ci_low']:+.5f}, {boot['ci_high']:+.5f}] p={boot['p_value']:.4f}"
        )

        bucket = _bucket_verdict(boot["ci_low"], boot["ci_high"])
        buckets.append(bucket)
        typer.echo(f"  -> {bucket}\n")

        per_league_results[name] = {"n_test": len(pooled_test_evals), "boot": boot, "bucket": bucket}

    verdict = _aggregate_verdict(buckets)
    typer.echo("=== VERDICT B3.3 (gate de desaccord vs poisson_simple, donnees reelles, regle pre-enregistree) ===")
    for name, r in per_league_results.items():
        typer.echo(
            f"  {name:<16} n_test={r['n_test']:<5} diff_moy={r['boot']['mean_diff']:+.4f} "
            f"IC95%=[{r['boot']['ci_low']:+.4f}, {r['boot']['ci_high']:+.4f}] "
            f"p={r['boot']['p_value']:.4f} -> {r['bucket']}"
        )
    typer.echo(f"\n  Total matchs de test evalues (3 championnats x 2 saisons) : {n_total_test_matches}")
    typer.echo(f"=== Verdict agrege (trois championnats) : {verdict} ===")

    if verdict == "VALIDE":
        typer.echo(
            "Le gate de desaccord ameliore significativement le Brier score par rapport a "
            "poisson_simple, de facon coherente sur les trois championnats."
        )
    elif verdict.startswith("REJETE"):
        typer.echo(
            "Le gate de desaccord n'ameliore pas poisson_simple de facon demontree - la regle "
            "simple testee ne transforme PAS le signal xG retrospectif en amelioration reelle "
            "du Brier score sur donnees hors echantillon."
        )
    else:
        typer.echo("Resultats incoherents entre championnats - INDETERMINE, pas une preuve d'amelioration.")

    typer.echo(
        "\npoisson_simple reste la baseline officielle quel que soit ce verdict - aucune promotion "
        "automatique, aucune modification. Conformement au protocole : aucune autre mesure de "
        "desaccord, aucun seuil, aucune ponderation alternative n'ont ete testes, et aucune nouvelle "
        "variante ne sera tentee si ce resultat est decevant."
    )
    typer.echo(
        "\nRESERVE (point-in-time, pas une fuite de donnees) : meme convention que B3/B3.2 pour le "
        "delai de connaissance xG (kickoff+48h, hypothese conservatrice documentee, pas verifiee "
        "aupres d'Understat). Invariant PIT garanti par construction et verifie par tests/leakage/."
    )


if __name__ == "__main__":
    app()
