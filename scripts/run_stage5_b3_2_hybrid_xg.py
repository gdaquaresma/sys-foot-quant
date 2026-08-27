"""CLI : B3.2 - test de l'hypothese hybride, sur un jeu de donnees
ENTIEREMENT VIERGE (docs/research_framework.md section B3).

Question testee (differente de B3 et de l'analyse de complementarite,
toutes deux basees sur 2025/26 - voir avertissement d'isolation
ci-dessous) : l'ajout du xG, sous forme d'un melange lineaire de
probabilites avec les buts reels, ameliore-t-il `poisson_simple` ?

    p_final = (1 - w) * p_poisson + w * p_xg      (HybridXGModel)

AVERTISSEMENT D'ISOLATION DES DONNEES (le point le plus important de ce
protocole) : B3 (verdict INDETERMINE) et l'analyse de complementarite qui
a genere l'hypothese hybride ont TOUS DEUX ete calcules sur la saison
2025/26 des trois championnats. Ce script utilise exclusivement la saison
2024/25 (entierement disjointe, aucun match en commun, voir
research/xg_feasibility/runs/*_2024_datesData.json) - ni pour choisir w,
ni pour le test final, la saison 2025/26 n'est jamais chargee ici.

Protocole a deux etapes strictement separees, sans exception (pre-
enregistre, valide avant execution) :
- ETAPE A (validation, fonction `_select_weight_on_validation`) : calcule
  les metriques de `HybridXGModel` pour w dans {0.25, 0.50, 0.75}
  UNIQUEMENT sur la periode de validation (30% de la saison 2024/25, apres
  rodage). Le poids retenu est celui minimisant le Brier moyen sur cette
  periode (regle de selection deterministe, fixee avant execution -
  "meilleur des trois candidats autorises", aucune autre valeur testee).
  Cette fonction ne touche JAMAIS aux identifiants de matchs du test final.
- ETAPE B (test, fonction `_run_frozen_test`) : n'est appelee qu'APRES que
  `_select_weight_on_validation` a retourne sa decision - le poids est un
  simple flottant fige en argument, aucune donnee de validation n'y
  transite. Un seul HybridXGModel (poids fige) y est evalue, une seule
  fois, aux cotes de poisson_simple (comparaison principale) et xg_model
  (reference descriptive).

Verdict (calcule EXCLUSIVEMENT sur le test B, jamais la validation A),
meme famille a 3 categories que B1/B2/A1-recence/B3 :
- VALIDE : IC95% de (Brier_hybride - Brier_poisson_simple) entierement
  negatif sur LES TROIS championnats.
- REJETE : IC95% entierement positif sur LES TROIS championnats.
- INDETERMINE : tout le reste.

Reserve deja documentee pour B3, valable a l'identique ici : le delai de
connaissance xG (kickoff+48h) est une hypothese conservatrice non
verifiee, distincte d'une fuite de donnees (invariant PIT garanti par
construction, voir tests/leakage/).

Usage:
    python scripts/run_stage5_b3_2_hybrid_xg.py
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
from sys_foot_quant.football_model.hybrid_xg_model import HybridXGModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.xg_model import XGModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_VALIDATION_FRACTION_OF_REMAINDER = 0.5
_DECISION_OFFSET_HOURS = 2.0
_MIN_TRAIN_MATCHES = 10
_ALLOWED_WEIGHTS = (0.25, 0.50, 0.75)  # seules valeurs autorisees, fixees a priori

# Saison 2024/25 UNIQUEMENT - jamais 2025/26 (voir avertissement d'isolation en tete de module).
_DATASETS = {
    "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2024_datesData.json")),
    "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2024_datesData.json")),
    "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2024_datesData.json")),
}
_EXPECTED_MATCHES = {"ligue1": 306, "premier_league": 380, "liga": 380}
_EXPECTED_TEAMS = {"ligue1": 18, "premier_league": 20, "liga": 20}


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


def _split_ids(records) -> tuple[list[str], list[str]]:
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    n_total = len(ordered)
    n_burn_in = int(n_total * _BURN_IN_FRACTION)
    n_remaining = n_total - n_burn_in
    n_validation = int(n_remaining * _VALIDATION_FRACTION_OF_REMAINDER)
    validation_ids = [r.match_id for r in ordered[n_burn_in : n_burn_in + n_validation]]
    test_ids = [r.match_id for r in ordered[n_burn_in + n_validation :]]
    return validation_ids, test_ids


def _configs_for_weights(weights: tuple[float, ...]) -> list[RealModelConfig]:
    def _fit_poisson_simple(goals_df, xg_df, decision_time):
        return PoissonModel(use_team_hfa=False).fit(goals_df)

    def _fit_xg(goals_df, xg_df, decision_time):
        return XGModel().fit(xg_df)

    def _make_hybrid_fit(w: float):
        def _fit(goals_df, xg_df, decision_time):
            return HybridXGModel(w=w).fit(goals_df, xg_df)

        return _fit

    configs = [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="xg_model", fit=_fit_xg, min_train_matches=_MIN_TRAIN_MATCHES),
    ]
    for w in weights:
        configs.append(
            RealModelConfig(name=f"hybrid_w{w:.2f}", fit=_make_hybrid_fit(w), min_train_matches=_MIN_TRAIN_MATCHES)
        )
    return configs


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


def _load_records(name: str):
    league_id, path = _DATASETS[name]
    with open(path) as f:
        raw = json.load(f)
    _verify_integrity(name, raw)
    return build_real_match_records(raw, league=league_id)


# --------------------------------------------------------------------------
# ETAPE A - validation uniquement. Ne touche JAMAIS test_ids.
# --------------------------------------------------------------------------
def _select_weight_on_validation(n_resamples: int, seed: int) -> tuple[float, dict]:
    typer.echo("\n=== ETAPE A : selection de w sur la VALIDATION uniquement ===")
    typer.echo(f"Valeurs autorisees : {_ALLOWED_WEIGHTS} (aucune autre ne sera testee)")

    per_league_validation = {}
    mean_brier_by_weight = {w: [] for w in _ALLOWED_WEIGHTS}

    for name in _DATASETS:
        records = _load_records(name)
        validation_ids, _test_ids_not_used_here = _split_ids(records)
        evals = run_real_data_walk_forward(
            records,
            eval_match_ids=validation_ids,
            decision_offset_hours=_DECISION_OFFSET_HOURS,
            model_configs=_configs_for_weights(_ALLOWED_WEIGHTS),
        )
        typer.echo(f"\n  --- {name} : validation, n={len(validation_ids)} ---")
        league_results = {}
        for model_name in ["poisson_simple", "xg_model"] + [f"hybrid_w{w:.2f}" for w in _ALLOWED_WEIGHTS]:
            probs, outcomes = to_probs_and_outcomes(evals, model_name)
            b = brier_score(probs, outcomes) if len(outcomes) else float("nan")
            ll = log_loss(probs, outcomes) if len(outcomes) else float("nan")
            typer.echo(f"    {model_name:<16} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")
            league_results[model_name] = {"n": len(outcomes), "brier": b, "log_loss": ll}
            if model_name.startswith("hybrid_w"):
                w = float(model_name.replace("hybrid_w", ""))
                mean_brier_by_weight[w].append(b)
        per_league_validation[name] = league_results

    typer.echo("\n  --- Brier moyen (validation, moyenne non ponderee sur les 3 championnats) ---")
    for w in _ALLOWED_WEIGHTS:
        avg = float(np.mean(mean_brier_by_weight[w]))
        typer.echo(f"    w={w:.2f} -> brier moyen = {avg:.4f}")

    chosen_w = min(_ALLOWED_WEIGHTS, key=lambda w: float(np.mean(mean_brier_by_weight[w])))
    typer.echo(f"\n  => w retenu (Brier moyen le plus bas sur validation) : {chosen_w:.2f}")
    typer.echo("  (le test final n'a pas encore ete consulte a ce stade)")

    return chosen_w, per_league_validation


# --------------------------------------------------------------------------
# ETAPE B - test final, une seule fois, poids deja fige en argument.
# --------------------------------------------------------------------------
def _run_frozen_test(chosen_w: float, n_resamples: int, seed: int) -> dict:
    typer.echo(f"\n\n=== ETAPE B : TEST FINAL (w fige = {chosen_w:.2f}, jamais reconsidere) ===")

    def _fit_poisson_simple(goals_df, xg_df, decision_time):
        return PoissonModel(use_team_hfa=False).fit(goals_df)

    def _fit_xg(goals_df, xg_df, decision_time):
        return XGModel().fit(xg_df)

    def _fit_hybrid(goals_df, xg_df, decision_time):
        return HybridXGModel(w=chosen_w).fit(goals_df, xg_df)

    configs = [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="xg_model", fit=_fit_xg, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="hybrid", fit=_fit_hybrid, min_train_matches=_MIN_TRAIN_MATCHES),
    ]

    results = {}
    for name in _DATASETS:
        records = _load_records(name)
        _validation_ids_not_used_here, test_ids = _split_ids(records)
        evals = run_real_data_walk_forward(
            records,
            eval_match_ids=test_ids,
            decision_offset_hours=_DECISION_OFFSET_HOURS,
            model_configs=configs,
        )

        typer.echo(f"\n  --- {name} : test final, n={len(test_ids)} ---")
        raw_metrics = {}
        for model_name in ["poisson_simple", "xg_model", "hybrid"]:
            probs, outcomes = to_probs_and_outcomes(evals, model_name)
            b = brier_score(probs, outcomes)
            ll = log_loss(probs, outcomes)
            typer.echo(f"    {model_name:<16} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")
            raw_metrics[model_name] = {"n": len(outcomes), "brier": b, "log_loss": ll}

        diffs_vs_poisson = _paired_metric_diffs(evals, "hybrid", "poisson_simple", brier_score)
        boot_vs_poisson = paired_bootstrap_test(diffs_vs_poisson, n_resamples=n_resamples, seed=seed)
        diffs_vs_xg = _paired_metric_diffs(evals, "hybrid", "xg_model", brier_score)
        boot_vs_xg = paired_bootstrap_test(diffs_vs_xg, n_resamples=n_resamples, seed=seed)

        typer.echo(
            f"    hybrid - poisson_simple : diff_moy={boot_vs_poisson['mean_diff']:+.4f} "
            f"IC95%=[{boot_vs_poisson['ci_low']:+.4f}, {boot_vs_poisson['ci_high']:+.4f}] "
            f"p={boot_vs_poisson['p_value']:.4f}"
        )
        typer.echo(
            f"    hybrid - xg_model       : diff_moy={boot_vs_xg['mean_diff']:+.4f} "
            f"IC95%=[{boot_vs_xg['ci_low']:+.4f}, {boot_vs_xg['ci_high']:+.4f}] "
            f"p={boot_vs_xg['p_value']:.4f}"
        )

        results[name] = {
            "n_test": len(test_ids),
            "raw_metrics": raw_metrics,
            "boot_vs_poisson": boot_vs_poisson,
            "boot_vs_xg": boot_vs_xg,
        }

    return results


def _bucket_verdict(ci_low: float, ci_high: float) -> str:
    if ci_high < 0.0:
        return "hybride_meilleur"
    if ci_low > 0.0:
        return "poisson_simple_meilleur"
    return "indetermine"


def _aggregate_verdict(buckets: list[str]) -> str:
    if all(b == "hybride_meilleur" for b in buckets):
        return "VALIDE"
    if all(b == "poisson_simple_meilleur" for b in buckets):
        return "REJETE"
    return "INDETERMINE"


@app.command()
def main(
    n_resamples: int = typer.Option(2000),
    seed: int = typer.Option(0),
) -> None:
    typer.echo("Jeu de donnees : saison 2024/25 (Ligue 1, Premier League, Liga) - jamais consultee")
    typer.echo("auparavant (ni B3, ni l'analyse de complementarite, toutes deux basees sur 2025/26).")

    # --- ETAPE A : w choisi, la fonction ne retourne QUE ce flottant + les
    # metriques de validation deja affichees. Aucune structure de donnees
    # issue du test final n'existe encore a ce point du programme. ---
    chosen_w, validation_results = _select_weight_on_validation(n_resamples, seed)

    # --- ETAPE B : le test final est charge et evalue MAINTENANT, avec un
    # seul poids fige recu en argument simple (float) - aucune donnee de
    # validation ne transite dans cette fonction. ---
    test_results = _run_frozen_test(chosen_w, n_resamples, seed)

    typer.echo(f"\n\n=== VERDICT B3.2 (hybride, w={chosen_w:.2f} fige sur validation) ===")
    buckets = []
    n_total_test = 0
    for name, r in test_results.items():
        boot = r["boot_vs_poisson"]
        bucket = _bucket_verdict(boot["ci_low"], boot["ci_high"])
        buckets.append(bucket)
        n_total_test += r["n_test"]
        typer.echo(
            f"  {name:<16} n_test={r['n_test']:<5} diff_moy={boot['mean_diff']:+.4f} "
            f"IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}] p={boot['p_value']:.4f} -> {bucket}"
        )

    verdict = _aggregate_verdict(buckets)
    typer.echo(f"\n  Total matchs test final : {n_total_test}")
    typer.echo(f"=== Verdict agrege (trois championnats) : {verdict} ===")

    typer.echo(
        f"\nMethode : w choisi parmi {len(_ALLOWED_WEIGHTS)} valeurs autorisees "
        f"({_ALLOWED_WEIGHTS}) sur la validation 2024/25 uniquement, fige avant toute lecture "
        f"du test final. poisson_simple reste la baseline officielle quel que soit ce verdict "
        f"- aucune promotion automatique."
    )
    typer.echo(
        "\nRESERVE (identique a B3, pas une fuite de donnees) : le delai de connaissance xG "
        "(kickoff+48h) est une hypothese conservatrice documentee, pas un fait verifie aupres "
        "d'Understat - ce resultat est une validation sur donnees historiques actuellement "
        "disponibles, pas une preuve de stabilite temporelle du xG."
    )


if __name__ == "__main__":
    app()
