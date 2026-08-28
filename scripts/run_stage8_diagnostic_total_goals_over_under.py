"""CLI : DIAGNOSTIC (aucune nouvelle experience economique, aucune
strategie, aucune optimisation, AUCUN modele modifie ni variante testee) -
notre systeme contient-il deja une information exploitable pour predire le
nombre total de buts et les marches Over/Under ?

Question posee : mesurer la CALIBRATION des probabilites de buts et
Over/Under produites par les modeles DEJA EXISTANTS et FIGES
(`PoissonModel` = poisson_simple, `DixonColesModel` = B1, `XGModel` = B3),
sur donnees hors echantillon (memes contraintes point-in-time que partout
ailleurs dans le projet), SANS chercher a battre un marche - le corpus ne
contient d'ailleurs AUCUNE cote Over/Under (l'audit prealable des donnees
de marche, docs/research_framework.md, a confirme que seul le 1X2 Bet365
est disponible ; ce diagnostic est donc un diagnostic MODELE, pas un
diagnostic MODELE-VS-MARCHE comme E1).

Aucune modification des trois modeles reutilises. Aucune nouvelle donnee.
Le mecanisme point-in-time (buts connus a kickoff+2h, xG a kickoff+48h,
`min_train_matches=10`, `decision_offset_hours=2.0`) est repris a
l'identique de `economic_dataset.py`/`real_data_walk_forward.py`
(constantes importees, pas redefinies) - la boucle de rodage
elle-meme est dupliquee localement (duplication volontaire et minimale,
meme convention que le reste du projet pour les scripts de recherche
isoles) car ce diagnostic a besoin de l'objet modele complet (matrice de
score) et non seulement du triplet de probabilites 1X2 que
``real_data_walk_forward`` expose.

Marches Over/Under testes : 1.5 / 2.5 / 3.5 buts (seuils standards,
documentes, aucune recherche de seuil optimal).

Usage:
    python scripts/run_stage8_diagnostic_total_goals_over_under.py
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sys_foot_quant.backtesting_engine.real_data_walk_forward import (  # noqa: E402
    RealMatchRecord,
    build_real_match_records,
)
from sys_foot_quant.calibration_engine.reliability import reliability_bins  # noqa: E402
from sys_foot_quant.common.logging import get_logger  # noqa: E402
from sys_foot_quant.data_engine.market_odds.economic_dataset import (  # noqa: E402
    DECISION_OFFSET_HOURS,
    MIN_TRAIN_MATCHES,
)
from sys_foot_quant.football_model.dixon_coles import DixonColesModel  # noqa: E402
from sys_foot_quant.football_model.poisson import PoissonModel  # noqa: E402
from sys_foot_quant.football_model.scoring import score_matrix  # noqa: E402
from sys_foot_quant.football_model.xg_model import XGModel  # noqa: E402

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)

_EXPECTED_MATCHES = {"ligue1": 306, "premier_league": 380, "liga": 380}
_EXPECTED_TEAMS = {"ligue1": 18, "premier_league": 20, "liga": 20}
_UNDERSTAT_DIR = Path("research/xg_feasibility/runs")

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

_MAX_GOALS = 20
_OU_THRESHOLDS = (1.5, 2.5, 3.5)
_MAX_TOTAL_BUCKET = 6  # 0,1,...,5, "6+"
_MODELS = ("poisson_simple", "dixon_coles", "xg_model")


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


def _load_records(name: str, season: str) -> list[RealMatchRecord]:
    league_id, path = _SEASONS[season][name]
    with open(path) as f:
        raw = json.load(f)
    _verify_integrity(name, raw)
    return build_real_match_records(raw, league=league_id)


# --------------------------------------------------------------------------
# Boucle point-in-time locale (dupliquee, voir docstring module) - MEME
# LOGIQUE, EXACTEMENT, que ``real_data_walk_forward._goals_train_df`` /
# ``_xg_train_df`` (non importees car privees), necessaire ici pour garder
# l'objet modele complet (matrice de score) plutot que le seul triplet
# 1X2 renvoye par l'interface publique du walk-forward existant.
# --------------------------------------------------------------------------


def _goals_train_df(records: list[RealMatchRecord], decision_time, exclude_match_id: str) -> pd.DataFrame:
    rows = [
        {
            "home_team_id": r.home_team_id,
            "away_team_id": r.away_team_id,
            "home_goals": r.home_goals,
            "away_goals": r.away_goals,
            "kickoff_time": r.kickoff_utc,
        }
        for r in records
        if r.match_id != exclude_match_id and r.goals_knowledge_time <= decision_time
    ]
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_goals", "away_goals", "kickoff_time"])


def _xg_train_df(records: list[RealMatchRecord], decision_time, exclude_match_id: str) -> pd.DataFrame:
    rows = [
        {
            "home_team_id": r.home_team_id,
            "away_team_id": r.away_team_id,
            "home_xg": r.home_xg,
            "away_xg": r.away_xg,
            "kickoff_time": r.kickoff_utc,
        }
        for r in records
        if r.match_id != exclude_match_id and r.xg_knowledge_time <= decision_time
    ]
    return pd.DataFrame(rows, columns=["home_team_id", "away_team_id", "home_xg", "away_xg", "kickoff_time"])


def over_under_probs(matrix: np.ndarray, thresholds: tuple[float, ...] = _OU_THRESHOLDS) -> dict[float, float]:
    """P(total > seuil) pour chaque seuil, a partir d'une matrice de score
    deja normalisee - fonction pure, aucun etat."""
    n = matrix.shape[0]
    totals = np.add.outer(np.arange(n), np.arange(n))
    return {t: float(matrix[totals > t].sum()) for t in thresholds}


def total_goals_distribution(matrix: np.ndarray, max_bucket: int = _MAX_TOTAL_BUCKET) -> np.ndarray:
    """P(total=0), P(total=1), ..., P(total=max_bucket-1), P(total>=max_bucket)."""
    n = matrix.shape[0]
    totals = np.add.outer(np.arange(n), np.arange(n))
    out = np.zeros(max_bucket + 1)
    for k in range(max_bucket):
        out[k] = matrix[totals == k].sum()
    out[max_bucket] = matrix[totals >= max_bucket].sum()
    return out


def build_total_goals_dataframe() -> pd.DataFrame:
    rows = []
    for season, leagues in _SEASONS.items():
        for name in leagues:
            records = _load_records(name, season)
            ordered = sorted(records, key=lambda r: r.kickoff_utc)
            for r in ordered:
                decision_time = r.kickoff_utc - timedelta(hours=DECISION_OFFSET_HOURS)
                goals_df = _goals_train_df(records, decision_time, exclude_match_id=r.match_id)
                xg_df = _xg_train_df(records, decision_time, exclude_match_id=r.match_id)

                total_goals = r.home_goals + r.away_goals
                row = {
                    "match_id": r.match_id,
                    "league": name,
                    "season": season,
                    "total_goals": total_goals,
                }

                if len(goals_df) >= MIN_TRAIN_MATCHES:
                    poisson = PoissonModel(use_team_hfa=False).fit(goals_df)
                    lam, mu = poisson.predict_lambda_mu(r.home_team_id, r.away_team_id)
                    matrix = score_matrix(lam, mu, max_goals=_MAX_GOALS)
                    matrix = matrix / matrix.sum()
                    row["poisson_simple_lambda_plus_mu"] = lam + mu
                    for t, p in over_under_probs(matrix).items():
                        row[f"poisson_simple_p_over_{t}"] = p
                    row["poisson_simple_dist"] = total_goals_distribution(matrix)

                    dixon_coles = DixonColesModel(use_team_hfa=False).fit(goals_df)
                    dc_matrix = dixon_coles.predict_score_matrix(r.home_team_id, r.away_team_id)
                    dc_lam, dc_mu = dixon_coles.predict_lambda_mu(r.home_team_id, r.away_team_id)
                    row["dixon_coles_lambda_plus_mu"] = dc_lam + dc_mu
                    for t, p in over_under_probs(dc_matrix).items():
                        row[f"dixon_coles_p_over_{t}"] = p
                    row["dixon_coles_dist"] = total_goals_distribution(dc_matrix)
                else:
                    row["poisson_simple_lambda_plus_mu"] = np.nan
                    row["dixon_coles_lambda_plus_mu"] = np.nan
                    for t in _OU_THRESHOLDS:
                        row[f"poisson_simple_p_over_{t}"] = np.nan
                        row[f"dixon_coles_p_over_{t}"] = np.nan
                    row["poisson_simple_dist"] = None
                    row["dixon_coles_dist"] = None

                if len(xg_df) >= MIN_TRAIN_MATCHES:
                    xg_model = XGModel(max_goals=_MAX_GOALS).fit(xg_df)
                    xg_lam, xg_mu = xg_model.predict_lambda_mu(r.home_team_id, r.away_team_id)
                    xg_matrix = score_matrix(xg_lam, xg_mu, max_goals=_MAX_GOALS)
                    xg_matrix = xg_matrix / xg_matrix.sum()
                    row["xg_model_lambda_plus_mu"] = xg_lam + xg_mu
                    for t, p in over_under_probs(xg_matrix).items():
                        row[f"xg_model_p_over_{t}"] = p
                    row["xg_model_dist"] = total_goals_distribution(xg_matrix)
                else:
                    row["xg_model_lambda_plus_mu"] = np.nan
                    for t in _OU_THRESHOLDS:
                        row[f"xg_model_p_over_{t}"] = np.nan
                    row["xg_model_dist"] = None

                rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Metriques de calibration
# --------------------------------------------------------------------------


def _binary_brier_and_logloss(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    eps = 1e-12
    brier = float(np.mean((p - y) ** 2))
    p_clipped = np.clip(p, eps, 1 - eps)
    logloss = float(-np.mean(y * np.log(p_clipped) + (1 - y) * np.log(1 - p_clipped)))
    return brier, logloss


def _calibration_weighted_error(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> dict:
    bins = reliability_bins(p, y, n_bins=n_bins)
    non_empty = bins[bins["count"] > 0]
    if non_empty.empty:
        return {"weighted_mean_abs_error": float("nan"), "n_bins_used": 0}
    abs_err = (non_empty["mean_predicted"] - non_empty["observed_frequency"]).abs()
    weighted = float((abs_err * non_empty["count"]).sum() / non_empty["count"].sum())
    return {"weighted_mean_abs_error": weighted, "n_bins_used": int(len(non_empty))}


def over_under_calibration(df: pd.DataFrame, model: str, threshold: float) -> dict:
    sub = df.dropna(subset=[f"{model}_p_over_{threshold}"])
    p = sub[f"{model}_p_over_{threshold}"].to_numpy()
    y = (sub["total_goals"] > threshold).astype(float).to_numpy()
    brier, logloss = _binary_brier_and_logloss(p, y)
    cal = _calibration_weighted_error(p, y)
    return {
        "n": len(sub),
        "brier": brier,
        "log_loss": logloss,
        "taux_over_observe": float(y.mean()),
        "p_over_moyenne_predite": float(p.mean()),
        **cal,
    }


def total_goals_distribution_calibration(df: pd.DataFrame, model: str) -> pd.DataFrame:
    """Compare la masse de probabilite MOYENNE predite a chaque niveau de
    buts totaux a la frequence empirique observee - "calibration en
    moyenne" de la distribution complete (pas seulement Over/Under)."""
    sub = df[df[f"{model}_dist"].notna()]
    dists = np.stack(sub[f"{model}_dist"].to_numpy())
    mean_predicted = dists.mean(axis=0)
    totals = sub["total_goals"].clip(upper=_MAX_TOTAL_BUCKET).to_numpy()
    empirical = np.array([(totals == k).mean() for k in range(_MAX_TOTAL_BUCKET + 1)])
    labels = [str(k) for k in range(_MAX_TOTAL_BUCKET)] + [f"{_MAX_TOTAL_BUCKET}+"]
    return pd.DataFrame(
        {"total_buts": labels, "proba_predite_moyenne": mean_predicted, "frequence_observee": empirical}
    )


@app.command()
def main() -> None:
    typer.echo("=== DIAGNOSTIC : information exploitable sur le total de buts / Over-Under ===")
    typer.echo(
        "Modeles reutilises SANS MODIFICATION : poisson_simple (PoissonModel), dixon_coles "
        "(DixonColesModel, B1), xg_model (XGModel, B3). Aucune cote Over/Under dans le corpus - "
        "diagnostic MODELE uniquement, aucune comparaison au marche, aucune strategie.\n"
    )

    df = build_total_goals_dataframe()
    typer.echo(f"Matchs totaux (corpus complet, 3 championnats x 2 saisons) : {len(df)}")
    for model in _MODELS:
        n_avail = df[f"{model}_p_over_2.5"].notna().sum()
        typer.echo(f"  ...avec prediction {model:<16} disponible (historique >= {MIN_TRAIN_MATCHES}) : {n_avail}")

    typer.echo("\n=== Buts totaux attendus vs observes ===")
    actual_mean = df["total_goals"].mean()
    typer.echo(f"  Moyenne de buts totaux REELLEMENT observee (tout le corpus) : {actual_mean:.4f}")
    for model in _MODELS:
        col = f"{model}_lambda_plus_mu"
        sub = df.dropna(subset=[col])
        typer.echo(
            f"  {model:<16} n={len(sub):<5} E[buts totaux] moyen predit={sub[col].mean():.4f} "
            f"biais={sub[col].mean() - sub['total_goals'].mean():+.4f}"
        )

    typer.echo("\n=== Calibration de la distribution complete des buts totaux (moyenne predite vs frequence observee) ===")
    for model in _MODELS:
        typer.echo(f"  -- {model} --")
        table = total_goals_distribution_calibration(df, model)
        for _, row in table.iterrows():
            typer.echo(
                f"    total={row['total_buts']:<3} predit_moy={row['proba_predite_moyenne']:.4f} "
                f"observe={row['frequence_observee']:.4f} "
                f"ecart={row['proba_predite_moyenne'] - row['frequence_observee']:+.4f}"
            )

    typer.echo("\n=== Calibration Over/Under (global) ===")
    for model in _MODELS:
        typer.echo(f"  -- {model} --")
        for t in _OU_THRESHOLDS:
            r = over_under_calibration(df, model, t)
            typer.echo(
                f"    Over {t:<4} n={r['n']:<5} brier={r['brier']:.4f} log_loss={r['log_loss']:.4f} "
                f"taux_over_observe={r['taux_over_observe']:.3f} p_over_predite_moy={r['p_over_moyenne_predite']:.3f} "
                f"calibration(erreur_abs_ponderee)={r['weighted_mean_abs_error']:.4f} (n_tranches={r['n_bins_used']})"
            )

    typer.echo("\n=== Calibration Over/Under par championnat ===")
    for league in sorted(df["league"].unique()):
        sub_league = df[df["league"] == league]
        typer.echo(f"  -- {league} --")
        for model in _MODELS:
            for t in _OU_THRESHOLDS:
                r = over_under_calibration(sub_league, model, t)
                if r["n"] == 0:
                    continue
                typer.echo(
                    f"    {model:<16} Over {t:<4} n={r['n']:<5} brier={r['brier']:.4f} "
                    f"calibration={r['weighted_mean_abs_error']:.4f}"
                )

    typer.echo("\n=== Calibration Over/Under par saison ===")
    for season in sorted(df["season"].unique()):
        sub_season = df[df["season"] == season]
        typer.echo(f"  -- {season} --")
        for model in _MODELS:
            for t in _OU_THRESHOLDS:
                r = over_under_calibration(sub_season, model, t)
                if r["n"] == 0:
                    continue
                typer.echo(
                    f"    {model:<16} Over {t:<4} n={r['n']:<5} brier={r['brier']:.4f} "
                    f"calibration={r['weighted_mean_abs_error']:.4f}"
                )

    typer.echo(
        "\nRESERVE : aucune cote Over/Under n'existe dans le corpus (seul le 1X2 Bet365 est "
        "disponible, voir l'audit des donnees de marche) - ce diagnostic mesure la calibration "
        "des modeles CONTRE LE RESULTAT REEL uniquement, jamais contre un marche. Aucune "
        "conclusion de rentabilite n'est possible ni recherchee."
    )
    typer.echo(
        "\nARRET : aucun modele modifie, aucune nouvelle variante testee, aucune strategie, "
        "aucune optimisation. Diagnostic termine."
    )


if __name__ == "__main__":
    app()
