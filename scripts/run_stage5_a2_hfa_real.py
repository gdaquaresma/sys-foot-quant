"""CLI : test hors echantillon de l'hypothese A2 (HFA dynamique par
equipe, shrinkage bayesien) sur DONNEES REELLES Understat
(docs/research_framework.md section A2).

Contexte : A2 (`PoissonModel(use_team_hfa=True)`) a ete teste sur donnees
SYNTHETIQUES a l'etape 2 (`scripts/run_stage2_walk_forward.py`, config
`poisson_A2_hfa`), mais JAMAIS confronte a `poisson_simple` sur donnees
reelles - tous les scripts reels precedents (B1/B3/B3.2/C7) desactivaient
explicitement le HFA par equipe des deux cotes pour isoler leur propre
question. Ce script est ce test manquant.

Question testee, unique et isolee : un HFA specifique par equipe (shrink
vers la moyenne de ligue, poids proportionnel au nombre de matchs a
domicile observes) ameliore-t-il `poisson_simple` (HFA global unique) sur
des RESULTATS REELS de football ?

`PoissonModel` est reutilise SANS AUCUNE MODIFICATION
(`football_model/poisson.py`) : `hfa_shrinkage_k=10.0` est repris tel
quel, deja fige a l'etape 2 (`_HFA_SHRINKAGE_K` dans
`run_stage2_walk_forward.py`) - AUCUNE autre valeur n'est testee ni
reajustee ici. Aucun xG, aucune correction Dixon-Coles, aucun modele
hybride.

Donnees : 3 championnats (Ligue 1, Premier League, Liga) x 2 saisons
(2024/25, 2025/26) - memes fichiers deja telecharges et verifies pour
B3/B3.2/C7/B1, aucun nouveau connecteur.

Protocole (pre-enregistre, valide avant execution) :
1. Point-in-time : reutilise SANS MODIFICATION
   `backtesting_engine/real_data_walk_forward.py` (buts connus a
   kickoff+2h, meme convention que B3/B3.2/C7/B1 ; xG jamais utilise).
2. Scission chronologique a trois voies PAR CHAMPIONNAT ET PAR SAISON
   (rodage 40%, validation 30%, test 30% - meme code de split que
   B1/B3), les deux saisons de chaque championnat traitees
   independamment puis leurs jeux de TEST regroupes pour le resultat
   "par championnat" - les resultats par saison restent aussi rapportes
   separement (stabilite temporelle).
3. `PoissonModel(use_team_hfa=True, hfa_shrinkage_k=10.0)` (A2) vs
   `PoissonModel(use_team_hfa=False)` (poisson_simple, baseline
   officielle, comportement inchange).
4. Metrique de decision : Brier score, diff = Brier_A2 - Brier_poisson_simple
   (negatif = A2 meilleur), bootstrap apparie, IC95%, sur le TEST
   uniquement.
5. Verdict a 3 categories, PAR CHAMPIONNAT (saisons regroupees) puis
   agrege sur les trois (meme convention que B1/B3/B3.2/C7) :
   - VALIDE : IC95% entierement < 0 sur LES TROIS championnats.
   - REJETE : aucun des trois championnats n'atteint une amelioration
     significative.
   - INDETERMINE : tout le reste (desaccord entre championnats, ou IC95%
     incluant 0).
6. Aucune autre valeur de shrinkage, aucun autre mecanisme HFA, aucun xG,
   aucune correction Dixon-Coles, aucun modele hybride - critères de
   decision fixes AVANT tout calcul, jamais ajustes.

Usage:
    python scripts/run_stage5_a2_hfa_real.py
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
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_VALIDATION_FRACTION_OF_REMAINDER = 0.5  # -> ~40/30/30 rodage/validation/test, meme convention que B1/B3
_DECISION_OFFSET_HOURS = 2.0
_MIN_TRAIN_MATCHES = 10

# Fige a l'etape 2 (run_stage2_walk_forward.py, _HFA_SHRINKAGE_K) - reutilise
# TEL QUEL, jamais reajuste. Egal au defaut de PoissonModel.__init__, verifie
# avant execution (voir echange de validation du protocole).
_HFA_SHRINKAGE_K = 10.0

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


def _fit_a2_hfa(goals_df, xg_df, decision_time):
    return PoissonModel(use_team_hfa=True, hfa_shrinkage_k=_HFA_SHRINKAGE_K).fit(goals_df)


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

    configs = [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="a2_hfa", fit=_fit_a2_hfa, min_train_matches=_MIN_TRAIN_MATCHES),
    ]
    validation_evals = run_real_data_walk_forward(
        records, eval_match_ids=validation_ids, decision_offset_hours=_DECISION_OFFSET_HOURS, model_configs=configs
    )
    test_evals = run_real_data_walk_forward(
        records, eval_match_ids=test_ids, decision_offset_hours=_DECISION_OFFSET_HOURS, model_configs=configs
    )

    return {
        "n_total": len(records),
        "n_validation": len(validation_ids),
        "n_test": len(test_ids),
        "validation_evals": validation_evals,
        "test_evals": test_evals,
    }


def _bucket_verdict(ci_low: float, ci_high: float) -> str:
    if ci_high < 0.0:
        return "a2_meilleur"
    if ci_low > 0.0:
        return "poisson_simple_meilleur"
    return "indetermine"


def _aggregate_verdict(buckets: list[str]) -> str:
    if all(b == "a2_meilleur" for b in buckets):
        return "VALIDE"
    if not any(b == "a2_meilleur" for b in buckets):
        return "REJETE"
    return "INDETERMINE"


def _report_diff(label: str, evals, n_resamples: int, seed: int) -> dict:
    diffs = _paired_metric_diffs(evals, "poisson_simple", "a2_hfa", brier_score)
    boot = paired_bootstrap_test(diffs, n_resamples=n_resamples, seed=seed) if diffs.size else None
    if boot is not None:
        typer.echo(
            f"  [{label}] diff(a2-poisson) n={diffs.size:<4} diff_moy={boot['mean_diff']:+.5f} "
            f"IC95%=[{boot['ci_low']:+.5f}, {boot['ci_high']:+.5f}] p={boot['p_value']:.4f}"
        )
    return boot


@app.command()
def main(
    n_resamples: int = typer.Option(2000),
    seed: int = typer.Option(0),
) -> None:
    typer.echo("=== A2 (HFA dynamique par equipe) re-test hors echantillon, donnees REELLES Understat ===")
    typer.echo(f"hfa_shrinkage_k={_HFA_SHRINKAGE_K} (fige a l'etape 2, non reajuste).")
    typer.echo("diff = Brier_a2 - Brier_poisson_simple ; negatif = A2 meilleur.\n")

    per_league_results = {}
    buckets = []
    n_total_test_matches = 0
    for name in _EXPECTED_MATCHES:
        typer.echo(f"--- {name} ---")
        season_results = {season: _process_league_season(name, season) for season in _SEASONS}

        for season, r in season_results.items():
            typer.echo(
                f"  [{season}] n_total={r['n_total']} n_validation={r['n_validation']} n_test={r['n_test']}"
            )
            for model_name in ["poisson_simple", "a2_hfa"]:
                probs, outcomes = to_probs_and_outcomes(r["test_evals"], model_name)
                if len(outcomes) == 0:
                    continue
                b = brier_score(probs, outcomes)
                ll = log_loss(probs, outcomes)
                typer.echo(f"    [{season} test] {model_name:<16} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")
            _report_diff(f"{season} test", r["test_evals"], n_resamples, seed)

        pooled_test_evals = [ev for r in season_results.values() for ev in r["test_evals"]]
        pooled_validation_evals = [ev for r in season_results.values() for ev in r["validation_evals"]]
        n_total_test_matches += len(pooled_test_evals)

        typer.echo(f"  --- {name} regroupe (2024/25 + 2025/26) ---")
        for label, evals in [("validation (informationnel)", pooled_validation_evals), ("test", pooled_test_evals)]:
            for model_name in ["poisson_simple", "a2_hfa"]:
                probs, outcomes = to_probs_and_outcomes(evals, model_name)
                if len(outcomes) == 0:
                    continue
                b = brier_score(probs, outcomes)
                ll = log_loss(probs, outcomes)
                typer.echo(f"  [{label}] {model_name:<16} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")

        pooled_boot = _report_diff("TEST REGROUPE", pooled_test_evals, n_resamples, seed)
        bucket = _bucket_verdict(pooled_boot["ci_low"], pooled_boot["ci_high"])
        buckets.append(bucket)
        typer.echo(f"  -> {bucket}\n")

        per_league_results[name] = {"n_test": len(pooled_test_evals), "boot": pooled_boot, "bucket": bucket}

    verdict = _aggregate_verdict(buckets)
    typer.echo("=== VERDICT A2 (HFA dynamique vs poisson_simple, donnees reelles, regle pre-enregistree) ===")
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
            "A2 (HFA dynamique par equipe) ameliore significativement le Brier score par rapport a "
            "poisson_simple, de facon coherente sur les trois championnats."
        )
    elif verdict == "REJETE":
        typer.echo(
            "Aucun championnat ne montre A2 significativement meilleur que poisson_simple sur "
            "donnees reelles - absence d'amelioration coherente."
        )
    else:
        typer.echo("Resultats incoherents entre championnats, ou IC95% incluant 0.")
    typer.echo(
        "\npoisson_simple reste la baseline officielle quel que soit ce verdict - aucune promotion "
        "automatique. Aucune autre valeur de shrinkage, aucun autre mecanisme HFA, aucun xG, aucune "
        "correction Dixon-Coles, aucun modele hybride n'ont ete testes."
    )
    typer.echo(
        "\nRESERVE (point-in-time, pas une fuite de donnees) : buts reels connus a kickoff+2h (meme "
        "convention que B1/B3/B3.2/C7), aucun xG utilise. Invariant PIT garanti par construction et "
        "verifie par tests/leakage/ (mecanisme reutilise sans modification)."
    )


if __name__ == "__main__":
    app()
