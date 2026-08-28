"""CLI : PREMIERE EXPERIENCE ECONOMIQUE REELLE du projet.

Question unique testee : le modele `poisson_simple` (`PoissonModel(use_team_hfa=False)`,
benchmark officiel fige, INCHANGE) produit-il, ex ante, des probabilites
suffisamment differentes du marche B365 pour identifier une value mesurable
sur le marche 1X2 - sur donnees REELLES (Understat + Football-Data.co.uk,
2024/25 + 2025/26, Ligue 1 / Premier League / Liga) ?

Ce script suit EXACTEMENT le protocole valide (etapes 1 a 11) :
1. Construction du dataset economique (`data_engine.market_odds.economic_dataset`,
   INCHANGE) - probabilites point-in-time strictes, cotes B365 uniquement,
   matchs exclus proprement et comptabilises (historique insuffisant, jour
   ambigu, cotes incompletes).
2. edge_raw = p_model - p_market_raw ET edge_norm = p_model - p_market_norm,
   les deux toujours rapportes, aucun choix a priori.
3. EV = p_model * cote - 1, purement descriptif a ce stade.
4. Comparaison modele/marche : Brier (poisson_simple, marche normalise,
   marche BRUT - NON STANDARD, somme des probabilites != 1, interpretation
   prudente uniquement), calibration, distribution des edges/EV -
   globalement, par championnat, par saison.
5. UNE SEULE strategie, fixee avant observation : PARI si EV_modele > 0
   (p_model * cote_B365 > 1). Mise flat 1 unite. Aucun Kelly, aucun
   staking, aucun filtre, aucune grille de seuils.
6. Performance realisee des paris EV>0 : n, gagnants, taux de reussite,
   profit total, ROI, par championnat/saison/issue - presentee comme une
   PREMIERE OBSERVATION, jamais comme preuve de rentabilite.
7. IC95% par bootstrap apparie (`paired_bootstrap_test`, REUTILISE SANS
   MODIFICATION) sur le profit par pari - PAS d'hypothese de normalite.
8. Verdict a 4 categories (formulation imposee, non negociable) :
   - PREUVE D'AMELIORATION ECONOMIQUE : IC95% du profit moyen entierement > 0.
   - SIGNAL NEGATIF : IC95% entierement < 0.
   - SIGNAL POSITIF : ROI observe > 0 mais IC95% couvrant 0.
   - ABSENCE DE PREUVE : ROI observe <= 0 et IC95% couvrant 0.
   (Ces quatre cas sont mutuellement exclusifs et exhaustifs une fois la
   position du point estime prise en compte - resolution explicite de la
   formulation du protocole, documentee ici, jamais inventee en cours de
   route.)
9. ARRET OBLIGATOIRE apres ce script : aucun autre seuil EV, aucun Kelly,
   aucun staking, aucun CLV, aucun autre bookmaker/marche, pas de B3.3, pas
   de nouveau modele, aucune optimisation.

Usage:
    python scripts/run_stage6_economic_b365_ev.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.calibration_engine.metrics import brier_score, log_loss  # noqa: E402
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.calibration_engine.significance import paired_bootstrap_test  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.economic_dataset import (  # noqa: E402
    SELECTIONS,
    EconomicDatasetReport,
    EconomicMatchRecord,
    build_economic_dataset,
)
from sys_foot_quant.data_engine.market_odds.football_data_loader import load_football_data_csv  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_EXPECTED_MATCHES = {"ligue1": 306, "premier_league": 380, "liga": 380}
_EXPECTED_TEAMS = {"ligue1": 18, "premier_league": 20, "liga": 20}

_UNDERSTAT_DIR = Path("research/xg_feasibility/runs")
_FOOTBALL_DATA_DIR = Path("research/market_odds/football_data/runs")

_DATASETS = {
    ("premier_league", "2024_25"): ("epl_2024_datesData.json", "E0_2024_25.csv"),
    ("premier_league", "2025_26"): ("epl_2025_datesData.json", "E0_2025_26.csv"),
    ("ligue1", "2024_25"): ("ligue1_2024_datesData.json", "F1_2024_25.csv"),
    ("ligue1", "2025_26"): ("ligue1_2025_datesData.json", "F1_2025_26.csv"),
    ("liga", "2024_25"): ("liga_2024_datesData.json", "SP1_2024_25.csv"),
    ("liga", "2025_26"): ("liga_2025_datesData.json", "SP1_2025_26.csv"),
}

# Seuil documente (pas un fait statistique universel) pour declarer le
# signal "sous-puissant" plutot que de tenter une lecture fine d'un IC95%
# construit sur trop peu d'observations - jamais utilise pour modifier la
# regle EV>0 elle-meme.
_MIN_BETS_FOR_POWERED_ANALYSIS = 30

_N_RESAMPLES = 10_000
_SEED = 0


def _verify_understat_integrity(name: str, raw: list[dict]) -> None:
    n = len(raw)
    if n != _EXPECTED_MATCHES[name]:
        raise ValueError(f"{name}: {n} matchs trouves, {_EXPECTED_MATCHES[name]} attendus.")
    ids = [m["id"] for m in raw]
    if len(set(ids)) != n:
        raise ValueError(f"{name}: doublons de match_id detectes.")
    if sum(1 for m in raw if m.get("isResult")) != n:
        raise ValueError(f"{name}: des matchs n'ont pas isResult=true.")
    teams = {m["h"]["title"] for m in raw} | {m["a"]["title"] for m in raw}
    if len(teams) != _EXPECTED_TEAMS[name]:
        raise ValueError(f"{name}: {len(teams)} equipes trouvees, {_EXPECTED_TEAMS[name]} attendues.")


def _load_all_reports() -> list[EconomicDatasetReport]:
    reports = []
    for (league, season), (us_name, fd_name) in _DATASETS.items():
        with open(_UNDERSTAT_DIR / us_name) as f:
            raw = json.load(f)
        _verify_understat_integrity(league, raw)
        fd_records = load_football_data_csv(_FOOTBALL_DATA_DIR / fd_name, league=league, season=season)
        reports.append(build_economic_dataset(league, season, raw, fd_records))
    return reports


def records_to_dataframe(records: list[EconomicMatchRecord]) -> pd.DataFrame:
    """Convertit les enregistrements economiques en DataFrame large (une
    ligne par match), une colonne par issue et par grandeur - utilisee
    UNIFORMEMENT par toutes les analyses descriptives et par la strategie
    ci-dessous (etape 9, garantie "memes matchs pour toutes les metriques")."""
    rows = []
    for r in records:
        row = {
            "match_id": r.match_id,
            "league": r.league,
            "season": r.season,
            "kickoff_utc": r.kickoff_utc,
            "outcome": r.outcome,
            "outcome_selection": r.outcome_selection,
        }
        for s in SELECTIONS:
            row[f"model_prob_{s}"] = r.model_probs[s]
            row[f"odds_{s}"] = r.market_odds[s]
            row[f"implied_raw_{s}"] = r.implied_prob_raw[s]
            row[f"implied_norm_{s}"] = r.implied_prob_normalized[s]
            row[f"edge_raw_{s}"] = r.edge_raw[s]
            row[f"edge_norm_{s}"] = r.edge_norm[s]
            row[f"ev_{s}"] = r.ev[s]
        rows.append(row)
    return pd.DataFrame(rows)


def _probs_outcomes(df: pd.DataFrame, prefix: str) -> tuple[np.ndarray, np.ndarray]:
    probs = df[[f"{prefix}_{s}" for s in SELECTIONS]].to_numpy()
    outcomes = df["outcome"].to_numpy()
    return probs, outcomes


def unnormalized_brier(df: pd.DataFrame, prefix: str) -> float:
    """Brier score calcule directement sur des probabilites qui NE somment
    PAS a 1 (cas des probabilites implicites BRUTES, marge incluse) - NON
    STANDARD (ne respecte pas la definition originale de Brier 1950, qui
    suppose une distribution de probabilite propre). Fournie uniquement en
    complement descriptif ("si pertinent", etape 4) - jamais utilisee pour
    un verdict, jamais comparee directement a un Brier standard sans cette
    reserve explicite."""
    probs, outcomes = _probs_outcomes(df, prefix)
    one_hot = np.zeros_like(probs)
    one_hot[np.arange(len(outcomes)), outcomes] = 1.0
    return float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))


def brier_and_log_loss(df: pd.DataFrame, prefix: str) -> tuple[float, float]:
    probs, outcomes = _probs_outcomes(df, prefix)
    return brier_score(probs, outcomes), log_loss(probs, outcomes)


def calibration_summary(df: pd.DataFrame, prefix: str, selection: str, n_bins: int = 10) -> dict:
    """Resume condense de calibration one-vs-rest pour UNE issue : erreur de
    calibration absolue moyenne, ponderee par effectif de tranche (sur les
    tranches non vides uniquement)."""
    probs = df[f"{prefix}_{selection}"].to_numpy()
    outcomes = (df["outcome_selection"] == selection).to_numpy().astype(float)
    bins = reliability_bins(probs, outcomes, n_bins=n_bins)
    non_empty = bins[bins["count"] > 0]
    if non_empty.empty:
        return {"weighted_mean_abs_error": float("nan"), "n_bins_used": 0}
    abs_err = (non_empty["mean_predicted"] - non_empty["observed_frequency"]).abs()
    weighted = float((abs_err * non_empty["count"]).sum() / non_empty["count"].sum())
    return {"weighted_mean_abs_error": weighted, "n_bins_used": int(len(non_empty))}


def edge_ev_distribution(df: pd.DataFrame, column_prefix: str) -> dict[str, dict]:
    out = {}
    for s in SELECTIONS:
        col = df[f"{column_prefix}_{s}"]
        out[s] = {
            "mean": float(col.mean()),
            "std": float(col.std()),
            "min": float(col.min()),
            "p25": float(col.quantile(0.25)),
            "p50": float(col.quantile(0.50)),
            "p75": float(col.quantile(0.75)),
            "max": float(col.max()),
        }
    return out


def select_ev_positive_bets(df: pd.DataFrame) -> pd.DataFrame:
    """ETAPE 5 - regle UNIQUE et fixe : PARI si EV_modele > 0, pour chaque
    (match, issue). Aucun parametre de seuil expose - '0.0' est le seul
    seuil possible avec cette fonction, par construction (etape 9, garantie
    "aucune optimisation post-hoc du seuil n'est possible"). Ne lit JAMAIS
    'outcome'/'outcome_selection' : la selection ne peut pas dependre du
    resultat reel (etape 9)."""
    rows = []
    for _, row in df.iterrows():
        for s in SELECTIONS:
            ev = row[f"ev_{s}"]
            if ev > 0.0:
                rows.append(
                    {
                        "match_id": row["match_id"],
                        "league": row["league"],
                        "season": row["season"],
                        "selection": s,
                        "odds": row[f"odds_{s}"],
                        "ev": ev,
                    }
                )
    return pd.DataFrame(rows, columns=["match_id", "league", "season", "selection", "odds", "ev"])


def realize_profit(bets: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """ETAPE 6 - calcule le profit REALISE, la SEULE fonction qui lit
    'outcome_selection', et seulement APRES que la selection (ci-dessus)
    a deja ete figee - mise flat 1 unite, aucun Kelly."""
    outcome_by_match = df.set_index("match_id")["outcome_selection"]
    bets = bets.copy()
    bets["won"] = bets.apply(lambda r: outcome_by_match.loc[r["match_id"]] == r["selection"], axis=1)
    bets["profit"] = np.where(bets["won"], bets["odds"] - 1.0, -1.0)
    return bets


def performance_summary(bets: pd.DataFrame) -> dict:
    n_bets = len(bets)
    if n_bets == 0:
        return {"n_bets": 0}
    n_wins = int(bets["won"].sum())
    total_profit = float(bets["profit"].sum())
    return {
        "n_bets": n_bets,
        "n_wins": n_wins,
        "win_rate": n_wins / n_bets,
        "total_profit": total_profit,
        "roi": total_profit / n_bets,
    }


def bootstrap_ci(bets: pd.DataFrame) -> dict:
    return paired_bootstrap_test(bets["profit"].to_numpy(), n_resamples=_N_RESAMPLES, seed=_SEED)


def classify_verdict(mean_profit: float, ci_low: float, ci_high: float) -> str:
    """Formulation imposee par le protocole (etape 8), resolue explicitement
    (les quatre cas sont mutuellement exclusifs et exhaustifs) :
    - IC95% entierement > 0            -> PREUVE D'AMELIORATION ECONOMIQUE
    - IC95% entierement < 0            -> SIGNAL NEGATIF
    - IC95% couvre 0, ROI observe > 0  -> SIGNAL POSITIF
    - IC95% couvre 0, ROI observe <= 0 -> ABSENCE DE PREUVE
    """
    if ci_low > 0.0:
        return "PREUVE D'AMELIORATION ECONOMIQUE"
    if ci_high < 0.0:
        return "SIGNAL NEGATIF"
    if mean_profit > 0.0:
        return "SIGNAL POSITIF"
    return "ABSENCE DE PREUVE"


def _print_scope_metrics(label: str, df: pd.DataFrame) -> None:
    n = len(df)
    if n == 0:
        typer.echo(f"  [{label}] n=0 - aucun match exploitable.")
        return
    b_model, ll_model = brier_and_log_loss(df, "model_prob")
    b_norm, ll_norm = brier_and_log_loss(df, "implied_norm")
    b_raw = unnormalized_brier(df, "implied_raw")
    typer.echo(
        f"  [{label}] n={n:<5} Brier poisson_simple={b_model:.4f} (log_loss={ll_model:.4f})  "
        f"Brier marche_norm={b_norm:.4f} (log_loss={ll_norm:.4f})  "
        f"Brier marche_BRUT(non standard)={b_raw:.4f}"
    )
    for s in SELECTIONS:
        cal_model = calibration_summary(df, "model_prob", s)
        cal_market = calibration_summary(df, "implied_norm", s)
        typer.echo(
            f"    calibration[{s:<5}] poisson_simple: erreur_abs_ponderee="
            f"{cal_model['weighted_mean_abs_error']:.4f} (n_tranches={cal_model['n_bins_used']})  "
            f"marche_norm: erreur_abs_ponderee={cal_market['weighted_mean_abs_error']:.4f} "
            f"(n_tranches={cal_market['n_bins_used']})"
        )
    edge_raw_dist = edge_ev_distribution(df, "edge_raw")
    edge_norm_dist = edge_ev_distribution(df, "edge_norm")
    ev_dist = edge_ev_distribution(df, "ev")
    for s in SELECTIONS:
        er, en, ev = edge_raw_dist[s], edge_norm_dist[s], ev_dist[s]
        typer.echo(
            f"    [{s:<5}] edge_raw  moy={er['mean']:+.4f} ecart-type={er['std']:.4f} "
            f"[{er['min']:+.4f}, {er['p50']:+.4f}, {er['max']:+.4f}]"
        )
        typer.echo(
            f"    [{s:<5}] edge_norm moy={en['mean']:+.4f} ecart-type={en['std']:.4f} "
            f"[{en['min']:+.4f}, {en['p50']:+.4f}, {en['max']:+.4f}]"
        )
        typer.echo(
            f"    [{s:<5}] EV        moy={ev['mean']:+.4f} ecart-type={ev['std']:.4f} "
            f"[{ev['min']:+.4f}, {ev['p50']:+.4f}, {ev['max']:+.4f}]"
        )


def _print_bet_breakdown(label: str, bets: pd.DataFrame) -> None:
    perf = performance_summary(bets)
    if perf["n_bets"] == 0:
        typer.echo(f"  [{label}] 0 pari EV>0.")
        return
    typer.echo(
        f"  [{label}] n_bets={perf['n_bets']:<5} n_wins={perf['n_wins']:<5} "
        f"win_rate={perf['win_rate']:.3f} profit_total={perf['total_profit']:+.2f} "
        f"ROI={perf['roi']:+.4f}"
    )


@app.command()
def main() -> None:
    typer.echo("=== PREMIERE EXPERIENCE ECONOMIQUE REELLE : poisson_simple vs marche B365 (1X2) ===")
    typer.echo(
        "Question : poisson_simple produit-il, ex ante, des probabilites suffisamment "
        "differentes du marche B365 pour identifier une value mesurable ?\n"
    )

    reports = _load_all_reports()

    typer.echo("--- Couverture et exclusions (par championnat/saison) ---")
    all_records: list[EconomicMatchRecord] = []
    for r in reports:
        typer.echo(
            f"  {r.league:<16} {r.season}  understat={r.n_understat:<4} matched={r.n_matched:<4} "
            f"exploitable={r.n_exploitable:<4}  exclus: jour_ambigu={r.n_excluded_ambiguous_weekday:<3} "
            f"cotes_incompletes={r.n_excluded_incomplete_odds:<3} "
            f"historique_insuffisant={r.n_excluded_insufficient_history:<3} "
            f"non_apparies_understat={r.n_unmatched_understat:<3} "
            f"non_apparies_football_data={r.n_unmatched_football_data:<3} "
            f"cles_dupliquees={r.n_duplicate_keys:<3} "
            f"violation_pit(devrait etre 0)={r.n_excluded_pit_violation}"
        )
        all_records.extend(r.records)

    df = records_to_dataframe(all_records)
    typer.echo(f"\nTotal matchs economiquement exploitables (toutes ligues/saisons) : {len(df)}\n")

    typer.echo("=== ETAPE 4 : Brier / calibration / edge / EV - descriptif ===")
    typer.echo("-- Global --")
    _print_scope_metrics("GLOBAL", df)
    typer.echo("-- Par championnat --")
    for league in sorted(df["league"].unique()):
        _print_scope_metrics(league, df[df["league"] == league])
    typer.echo("-- Par saison --")
    for season in sorted(df["season"].unique()):
        _print_scope_metrics(season, df[df["season"] == season])

    typer.echo("\n=== ETAPE 5-6 : strategie unique EV>0, mise flat 1 unite - performance realisee ===")
    bets = select_ev_positive_bets(df)
    bets = realize_profit(bets, df)

    typer.echo("-- Global --")
    _print_bet_breakdown("GLOBAL", bets)
    typer.echo("-- Par championnat --")
    for league in sorted(df["league"].unique()):
        _print_bet_breakdown(league, bets[bets["league"] == league])
    typer.echo("-- Par saison --")
    for season in sorted(df["season"].unique()):
        _print_bet_breakdown(season, bets[bets["season"] == season])
    typer.echo("-- Par issue (Home/Draw/Away) --")
    for s in SELECTIONS:
        _print_bet_breakdown(s, bets[bets["selection"] == s])

    typer.echo("\n=== ETAPE 7-8 : incertitude statistique et verdict ===")
    perf = performance_summary(bets)
    if perf["n_bets"] == 0:
        typer.echo("Aucun pari EV>0 genere - signal SOUS-PUISSANT par construction, aucun verdict possible.")
        return

    boot = bootstrap_ci(bets)
    typer.echo(
        f"n_bets={perf['n_bets']}  profit_moyen={boot['mean_diff']:+.5f}  "
        f"IC95%=[{boot['ci_low']:+.5f}, {boot['ci_high']:+.5f}]  p={boot['p_value']:.4f}  "
        f"(bootstrap i.i.d. sur les paris, PAS un bootstrap par blocs temporels - "
        f"aucune methode de ce type n'est encore disponible dans le projet, voir limites)."
    )
    if perf["n_bets"] < _MIN_BETS_FOR_POWERED_ANALYSIS:
        typer.echo(
            f"AVERTISSEMENT : n_bets={perf['n_bets']} < {_MIN_BETS_FOR_POWERED_ANALYSIS} - signal "
            "declare SOUS-PUISSANT (seuil documente, pas un fait statistique universel). La regle "
            "EV>0 n'est PAS modifiee pour augmenter ce nombre."
        )

    verdict = classify_verdict(boot["mean_diff"], boot["ci_low"], boot["ci_high"])
    typer.echo(f"\n=== VERDICT ECONOMIQUE : {verdict} ===")
    typer.echo(
        "\nRESERVE (point-in-time, pas une fuite) : timestamp Football-Data non verifie, hypothese "
        "temporelle conservatrice documentee (docs/decisions/0006-football-data-point-in-time.md). "
        "Les matchs du lundi/mardi/vendredi sont exclus, pas resolus par hypothese silencieuse."
    )
    typer.echo(
        "\nDATA SNOOPING : le corpus 2024/25+2025/26 a deja servi a A1/A2/B1/B2/B3/B3.2/B3.3/C7. La "
        "regle EV>0 est neanmoins une regle economique fixee AVANT observation du ROI de CETTE "
        "experience - aucune variante de seuil n'a ete testee ni ne sera testee apres ce resultat."
    )
    typer.echo(
        "\nARRET OBLIGATOIRE : conformement au protocole, aucun autre seuil EV, aucun Kelly, aucun "
        "staking dynamique, aucun CLV, aucun autre bookmaker/marche, pas de B3.3, pas de nouveau "
        "modele, aucune optimisation ne suivent ce script."
    )


if __name__ == "__main__":
    app()
