"""CLI : test hors echantillon de l'hypothese B3 (xG) sur donnees REELLES
Understat (docs/research_framework.md section B3).

Question testee, unique et isolee (rien d'autre) : le xG historique d'une
equipe permet-il de mieux estimer sa force offensive/defensive que ses
buts reels, pour predire ses PROCHAINS matchs, par rapport a
`poisson_simple` (reference officielle, inchangee) ?

Donnees : trois championnats 2025/26 (Ligue 1, Premier League, Liga),
extraits d'Understat via le navigateur de l'utilisateur (voir
research/xg_feasibility/runs/), verifies intacts (aucun doublon, aucun
score/xG manquant, nombre de matchs et d'equipes conforme a l'attendu -
306/380/380). PAS de source de donnees synthetique ici, contrairement a
toutes les etapes precedentes.

AVERTISSEMENT POINT-IN-TIME (a lire avant les resultats, voir aussi
backtesting_engine/real_data_walk_forward.py) : le score reel d'un match
est suppose connu 2h apres le coup d'envoi (meme convention que le
generateur synthetique). Le xG d'un match est suppose connu 48h apres le
coup d'envoi - hypothese CONSERVATRICE et DOCUMENTEE, PAS un fait verifie
(Understat ne publie aucun horodatage officiel). Cette reserve concerne la
STABILITE/LATENCE de publication d'une donnee deja passee, pas une fuite
d'information : aucun match a l'instant T ou apres n'est jamais utilise
pour predire le match a T, quel que soit ce delai (invariant structurel
garanti par construction, verifie par tests/leakage/).

Protocole (pre-enregistre, valide avant execution) :
1. Scission chronologique a trois voies PAR CHAMPIONNAT : rodage (40%),
   validation (30%), test (30%). Le rodage n'est jamais evalue.
2. `XGModel` n'a AUCUN hyperparametre libre (meme formulation que
   poisson_simple : pas de HFA par equipe, pas de shrinkage) - la
   validation sert de premier regard informatif, pas de selection de
   parametre. Le TEST seul determine le verdict.
3. Verdict a 3 categories, sur le TEST uniquement, calcule PAR
   championnat puis agrege sur les trois (meme regle que B1/B2/A1-recence) :
   - VALIDE : IC95% de (Brier_XGModel - Brier_poisson_simple) entierement
     negatif sur LES TROIS championnats.
   - REJETE : IC95% entierement positif sur LES TROIS championnats.
   - INDETERMINE : tout le reste.
4. Aucune combinaison (hybride xG/buts) n'est testee ici : research_framework.md
   ne fixe aucun poids a priori pour cette variante - elle n'est donc pas
   testee dans ce script (voir echange de validation du protocole).

Usage:
    python scripts/run_stage5_b3_xg_walkforward.py
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
from sys_foot_quant.football_model.xg_model import XGModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_VALIDATION_FRACTION_OF_REMAINDER = 0.5  # -> ~40/30/30 rodage/validation/test
_DECISION_OFFSET_HOURS = 2.0
_MIN_TRAIN_MATCHES = 10

_DATASETS = {
    "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2025_datesData.json")),
    "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2025_datesData.json")),
    "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2025_datesData.json")),
}

_EXPECTED_MATCHES = {"ligue1": 306, "premier_league": 380, "liga": 380}
_EXPECTED_TEAMS = {"ligue1": 18, "premier_league": 20, "liga": 20}


def _model_configs() -> list[RealModelConfig]:
    def _fit_poisson_simple(goals_df, xg_df, decision_time):
        return PoissonModel(use_team_hfa=False).fit(goals_df)

    def _fit_xg(goals_df, xg_df, decision_time):
        return XGModel().fit(xg_df)

    return [
        RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES),
        RealModelConfig(name="xg_model", fit=_fit_xg, min_train_matches=_MIN_TRAIN_MATCHES),
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


def _verify_integrity(name: str, raw: list[dict]) -> None:
    """Controle d'integrite explicite - jamais suppose. Leve une erreur
    bruyante plutot que de continuer silencieusement si un ecart est
    detecte (meme discipline que le reste du projet)."""
    n = len(raw)
    if n != _EXPECTED_MATCHES[name]:
        raise ValueError(f"{name}: {n} matchs trouves, {_EXPECTED_MATCHES[name]} attendus.")
    ids = [m["id"] for m in raw]
    if len(set(ids)) != n:
        raise ValueError(f"{name}: doublons de match_id detectes ({len(set(ids))} uniques sur {n}).")
    n_result = sum(1 for m in raw if m.get("isResult"))
    if n_result != n:
        raise ValueError(f"{name}: {n - n_result} matchs sans isResult=true.")
    missing_score = sum(1 for m in raw if m["goals"]["h"] is None or m["goals"]["a"] is None)
    missing_xg = sum(1 for m in raw if m["xG"]["h"] is None or m["xG"]["a"] is None)
    if missing_score or missing_xg:
        raise ValueError(f"{name}: {missing_score} scores manquants, {missing_xg} xG manquants.")
    teams = set()
    for m in raw:
        teams.add(m["h"]["title"])
        teams.add(m["a"]["title"])
    if len(teams) != _EXPECTED_TEAMS[name]:
        raise ValueError(f"{name}: {len(teams)} equipes trouvees, {_EXPECTED_TEAMS[name]} attendues.")


def _split_eval_ids(records) -> tuple[list[str], list[str]]:
    ordered = sorted(records, key=lambda r: r.kickoff_utc)
    n_total = len(ordered)
    n_burn_in = int(n_total * _BURN_IN_FRACTION)
    n_remaining = n_total - n_burn_in
    n_validation = int(n_remaining * _VALIDATION_FRACTION_OF_REMAINDER)
    validation_ids = [r.match_id for r in ordered[n_burn_in : n_burn_in + n_validation]]
    test_ids = [r.match_id for r in ordered[n_burn_in + n_validation :]]
    return validation_ids, test_ids


def _bucket_verdict(ci_low: float, ci_high: float) -> str:
    if ci_high < 0.0:
        return "xg_meilleur"
    if ci_low > 0.0:
        return "poisson_simple_meilleur"
    return "indetermine"


def _aggregate_verdict(buckets: list[str]) -> str:
    if all(b == "xg_meilleur" for b in buckets):
        return "VALIDE"
    if all(b == "poisson_simple_meilleur" for b in buckets):
        return "REJETE"
    return "INDETERMINE"


def _format_boot(label: str, boot: dict[str, float]) -> str:
    return (
        f"{label:<45} diff_moy={boot['mean_diff']:+.4f} "
        f"IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}] p={boot['p_value']:.4f}"
    )


def _process_league(name: str, n_resamples: int, seed: int) -> dict:
    league_id, path = _DATASETS[name]
    with open(path) as f:
        raw = json.load(f)

    typer.echo(f"\n=== {name} ({league_id}) : controle d'integrite ===")
    _verify_integrity(name, raw)
    typer.echo(f"  OK : {len(raw)} matchs, {_EXPECTED_TEAMS[name]} equipes, aucune anomalie.")

    records = build_real_match_records(raw, league=league_id)
    validation_ids, test_ids = _split_eval_ids(records)
    n_total = len(records)
    n_burn_in = n_total - len(validation_ids) - len(test_ids)
    typer.echo(
        f"  Scission : {n_total} matchs (rodage={n_burn_in}, "
        f"validation={len(validation_ids)}, test={len(test_ids)})"
    )

    validation_evals = run_real_data_walk_forward(
        records,
        eval_match_ids=validation_ids,
        decision_offset_hours=_DECISION_OFFSET_HOURS,
        model_configs=_model_configs(),
    )
    test_evals = run_real_data_walk_forward(
        records,
        eval_match_ids=test_ids,
        decision_offset_hours=_DECISION_OFFSET_HOURS,
        model_configs=_model_configs(),
    )

    typer.echo("  --- Metriques brutes (TEST) ---")
    for model_name in ["poisson_simple", "xg_model"]:
        probs, outcomes = to_probs_and_outcomes(test_evals, model_name)
        if len(outcomes) == 0:
            typer.echo(f"    {model_name:<16} aucune prediction (donnees insuffisantes)")
            continue
        b = brier_score(probs, outcomes)
        ll = log_loss(probs, outcomes)
        typer.echo(f"    {model_name:<16} n={len(outcomes):<5} brier={b:>8.4f} log_loss={ll:>8.4f}")

    val_boot = _compare(validation_evals, n_resamples, seed)
    typer.echo("  --- Validation (informationnel, XGModel sans hyperparametre a choisir) ---")
    typer.echo("    " + _format_boot("xg_model - poisson_simple [validation]", val_boot))

    test_boot = _compare(test_evals, n_resamples, seed)
    typer.echo("  --- Test (hors echantillon, determine le verdict) ---")
    typer.echo("    " + _format_boot("xg_model - poisson_simple [test]", test_boot))

    return {
        "n_total": n_total,
        "n_validation": len(validation_ids),
        "n_test": len(test_ids),
        "validation_boot": val_boot,
        "test_boot": test_boot,
    }


def _compare(evaluations, n_resamples: int, seed: int) -> dict[str, float]:
    diffs = _paired_metric_diffs(evaluations, "xg_model", "poisson_simple", brier_score)
    return paired_bootstrap_test(diffs, n_resamples=n_resamples, seed=seed)


@app.command()
def main(
    n_resamples: int = typer.Option(2000, help="Nombre de reechantillonnages bootstrap."),
    seed: int = typer.Option(0, help="Graine du bootstrap (reproductibilite)."),
) -> None:
    results = {}
    for name in _DATASETS:
        results[name] = _process_league(name, n_resamples, seed)

    typer.echo("\n\n=== VERDICT B3 (xG vs poisson_simple, diff = xg_model - poisson_simple) ===")
    buckets = []
    for name, r in results.items():
        boot = r["test_boot"]
        bucket = _bucket_verdict(boot["ci_low"], boot["ci_high"])
        buckets.append(bucket)
        typer.echo(
            f"  {name:<16} n_test={r['n_test']:<5} diff_moy={boot['mean_diff']:+.4f} "
            f"IC95%=[{boot['ci_low']:+.4f}, {boot['ci_high']:+.4f}] p={boot['p_value']:.4f} -> {bucket}"
        )

    verdict = _aggregate_verdict(buckets)
    typer.echo(f"\n=== Verdict agrege (trois championnats) : {verdict} ===")
    if verdict == "VALIDE":
        typer.echo(
            "xg_model ameliore significativement sur poisson_simple, de facon coherente sur "
            "les trois championnats testes."
        )
    elif verdict == "REJETE":
        typer.echo(
            "poisson_simple reste significativement superieur a xg_model sur les trois "
            "championnats testes."
        )
    else:
        typer.echo(
            "Resultats incoherents entre championnats, ou intervalle de confiance incluant 0 "
            "sur au moins un championnat. poisson_simple reste la baseline officielle."
        )

    typer.echo(
        "\nRESERVE (point-in-time, pas une fuite de donnees) : le xG utilise ici respecte "
        "strictement l'ordre chronologique (aucun match a l'instant T ou apres n'influence sa "
        "propre prediction, verifie par tests/leakage/), mais la date de publication reelle "
        "d'Understat n'est pas documentee par la source elle-meme - le delai de 48h utilise ici "
        "est une hypothese conservatrice, pas un fait verifie. Ce resultat est une validation "
        "sur les donnees historiques actuellement disponibles, pas une preuve de stabilite "
        "des valeurs xG dans le temps."
    )


if __name__ == "__main__":
    app()
