"""CLI : test hors echantillon de l'hypothese C7 (parlays corrleles),
PHASE 1 UNIQUEMENT (docs/research_framework.md section C7).

Question testee, unique et isolee : existe-t-il une correlation empirique
entre "l'equipe a domicile est favorite selon poisson_simple" (evenement
A) et "Over 2.5 buts" (evenement B), au-dela de l'independance implicite
que suppose la tarification d'un combine ? C'est une condition NECESSAIRE
(pas suffisante) au mecanisme de parlay correle decrit dans le corpus - ce
script ne calcule AUCUN prix reel de combine (aucune cote de marche
combine dans notre schema actuel, contrairement au 1X2). Une eventuelle
phase 2 (EV reel sur cotes de combines) n'est ni codee ni commencee ici.

N'utilise QUE poisson_simple (reference officielle, inchangee) pour
definir le favori pre-match - jamais XGModel ni HybridXGModel. N'utilise
aucune valeur de xG. Reutilise SANS MODIFICATION le meme mecanisme
point-in-time que B3/B3.2 (backtesting_engine/real_data_walk_forward.py).

TRANSPARENCE METHODOLOGIQUE (a lire avant les resultats) : les saisons
2024/25 et 2025/26 des trois championnats ont deja servi a B3 et B3.2,
mais pour une question differente (performance comparee de modeles de
buts/xG, pas correlation d'issues de match). C7 ne reutilise AUCUN
resultat ni metrique de B3/B3.2 pour definir ou ajuster son protocole -
mais ce n'est donc pas, au sens strict, un jeu de donnees vierge.

Protocole (pre-enregistre, valide avant execution) :
1. Evenements A et B, et definition du favori, fixes AVANT tout calcul
   (voir market_engine/correlated_events.py) - jamais revus apres lecture
   d'un resultat intermediaire.
2. Rodage de poisson_simple : 40% de chaque saison (meme convention que
   B3/B3.2), jamais evalue.
3. ESTIMATION = saison 2024/25 (60% post-rodage), CONFIRMATION = saison
   2025/26 (60% post-rodage) - consultees chacune UNE SEULE FOIS, la
   confirmation n'ajuste jamais la methodologie a posteriori.
4. Test de difference de proportions (Chi-deux ou Fisher exact si effectif
   de cellule < 5) par ligue et par saison, alpha=0.05 bilateral.
5. Verdict a 3 categories, par ligue puis agrege sur les trois (meme regle
   que B1/B2/A1-recence/B3/B3.2) :
   - VALIDE : ecart P(B|A)-P(B|non A) positif et significatif en
     estimation ET en confirmation, sur LES TROIS championnats.
   - REJETE : absence d'association ou effet oppose, coherent sur LES
     TROIS championnats et LES DEUX saisons.
   - INDETERMINE : tout le reste.
6. Aucune autre paire d'evenement, aucun autre seuil Over/Under, aucun
   seuil de probabilite pour le favori, aucune variante de poisson_simple
   ne sont testes - aucune experimentation complementaire automatique.

Usage:
    python scripts/run_stage5_c7_correlated_events.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (  # noqa: E402
    RealModelConfig,
    build_real_match_records,
    run_real_data_walk_forward,
)
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.market_engine.correlated_events import (  # noqa: E402
    aggregate_verdict,
    association_result_from_predictions,
    eligible_match_ids_after_burn_in,
    per_league_bucket,
)

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_BURN_IN_FRACTION = 0.4
_DECISION_OFFSET_HOURS = 2.0
_MIN_TRAIN_MATCHES = 10

_EXPECTED_MATCHES = {"ligue1": 306, "premier_league": 380, "liga": 380}
_EXPECTED_TEAMS = {"ligue1": 18, "premier_league": 20, "liga": 20}

# Memes fichiers, deja telecharges et verifies pour B3 (2025/26) et B3.2
# (2024/25) - aucun nouveau telechargement, aucun nouveau connecteur.
_DATASETS_ESTIMATION = {
    "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2024_datesData.json")),
    "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2024_datesData.json")),
    "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2024_datesData.json")),
}
_DATASETS_CONFIRMATION = {
    "ligue1": ("Ligue_1", Path("research/xg_feasibility/runs/ligue1_2025_datesData.json")),
    "premier_league": ("EPL", Path("research/xg_feasibility/runs/epl_2025_datesData.json")),
    "liga": ("La_liga", Path("research/xg_feasibility/runs/liga_2025_datesData.json")),
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
    # xg_df recu par l'interface commune (voir RealModelConfig) mais
    # jamais utilise - poisson_simple seul, aucun xG, aucun XGModel/HybridXGModel.
    return PoissonModel(use_team_hfa=False).fit(goals_df)


def _load_records(datasets: dict, name: str):
    league_id, path = datasets[name]
    with open(path) as f:
        raw = json.load(f)
    _verify_integrity(name, raw)
    return build_real_match_records(raw, league=league_id)


def _process_league_season(datasets: dict, name: str) -> dict:
    records = _load_records(datasets, name)
    eligible_ids = eligible_match_ids_after_burn_in(
        [(r.match_id, r.kickoff_utc) for r in records], _BURN_IN_FRACTION
    )
    configs = [RealModelConfig(name="poisson_simple", fit=_fit_poisson_simple, min_train_matches=_MIN_TRAIN_MATCHES)]
    evaluations = run_real_data_walk_forward(
        records,
        eval_match_ids=eligible_ids,
        decision_offset_hours=_DECISION_OFFSET_HOURS,
        model_configs=configs,
    )

    rows = []
    for ev in evaluations:
        pred = ev.predictions.get("poisson_simple")
        if pred is None:
            continue
        p_home, _p_draw, p_away = pred
        rows.append((p_home, p_away, ev.home_goals, ev.away_goals))

    result = association_result_from_predictions(rows)
    result["n_eligible"] = len(eligible_ids)
    result["n_used"] = len(rows)
    result["n_burn_in"] = len(records) - len(eligible_ids)
    return result


def _format_result(label: str, r: dict) -> str:
    return (
        f"{label:<14} n={r['n_used']:<5} P(B)={r['p_b']:.3f} P(B|A)={r['p_b_given_a']:.3f} "
        f"P(B|non A)={r['p_b_given_not_a']:.3f} diff={r['diff']:+.3f} "
        f"IC95%=[{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] p={r['p_value']:.4f} ({r['test_used']})"
    )


@app.command()
def main() -> None:
    typer.echo("=== C7 phase 1 : correlation 'favori domicile (poisson_simple)' x 'Over 2.5 buts' ===")
    typer.echo("Evenement A = P(victoire domicile) > P(victoire exterieur), point-in-time, poisson_simple SEUL.")
    typer.echo("Evenement B = home_goals + away_goals >= 3.")
    typer.echo("Estimation = 2024/25 (deja utilisee par B3.2, question differente). Confirmation = 2025/26 (deja")
    typer.echo("utilisee par B3, question differente) - pas un jeu vierge au sens strict, voir avertissement du module.\n")

    per_league = {}
    buckets = []
    for name in _DATASETS_ESTIMATION:
        typer.echo(f"--- {name} ---")
        estimation = _process_league_season(_DATASETS_ESTIMATION, name)
        confirmation = _process_league_season(_DATASETS_CONFIRMATION, name)
        typer.echo("  " + _format_result("estimation", estimation))
        typer.echo("  " + _format_result("confirmation", confirmation))

        bucket = per_league_bucket(estimation, confirmation)
        buckets.append(bucket)
        typer.echo(f"  -> {bucket}\n")
        per_league[name] = {"estimation": estimation, "confirmation": confirmation, "bucket": bucket}

    verdict = aggregate_verdict(buckets)
    typer.echo(f"=== VERDICT C7 (phase 1, agrege sur les trois championnats) : {verdict} ===")
    if verdict == "VALIDE":
        typer.echo(
            "L'ecart P(B|A) - P(B|non A) est positif et statistiquement significatif, confirme "
            "sur la saison suivante, de facon coherente sur les trois championnats."
        )
    elif verdict == "REJETE":
        typer.echo(
            "Aucune association exploitable (ou effet oppose) entre favori a domicile et Over "
            "2.5 buts, de facon coherente sur les trois championnats et les deux saisons."
        )
    else:
        typer.echo("Resultats incoherents entre championnats, ou non confirmes d'une saison a l'autre.")

    typer.echo(
        "\nCE QUE C7 (phase 1) PERMET DE CONCLURE : si (et seulement si) VALIDE, qu'une association "
        "statistique existe entre ces deux evenements dans nos donnees, au-dela de l'independance - "
        "condition necessaire au mecanisme de parlay correle decrit dans le corpus."
    )
    typer.echo(
        "CE QUE C7 (phase 1) NE PERMET PAS DE CONCLURE : aucune conclusion sur la rentabilite reelle "
        "d'un combine - cela exigerait des cotes reelles de marches combines (absentes de notre "
        "schema actuel), la verification que le bookmaker ne price pas deja cette correlation, la "
        "marge du combine, et un test EV/ROI hors echantillon dedie (Risk Engine). Rien de tout cela "
        "n'est dans le perimetre de cette phase 1."
    )
    typer.echo(
        "\nRESERVE (transparence, pas une fuite de donnees) : 2024/25 et 2025/26 ont deja servi a "
        "B3/B3.2 pour une question differente (performance de modele) - ce n'est donc pas, au sens "
        "strict, un jeu de donnees vierge pour ce nouveau test, meme si aucun resultat B3/B3.2 n'a "
        "ete utilise pour definir ou ajuster ce protocole."
    )


if __name__ == "__main__":
    app()
