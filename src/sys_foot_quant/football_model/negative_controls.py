"""Controles negatifs de specificite (hypotheses E1 et E7 du Research
Framework, docs/research_framework.md section E).

Ces deux features ne sont PAS destinees a ameliorer un modele : elles
servent a verifier que le pipeline de test statistique ne detecte pas de
signal la ou le generateur synthetique n'en injecte aucun (aucun
mecanisme de fatigue, aucun mecanisme "must-win" n'existe dans
``data_engine/synthetic/generator.py``). Un H0 NON rejete est le resultat
ATTENDU et souhaite. Un signal significatif inattendu doit etre traite
comme une alerte methodologique (fuite d'information, biais de
construction du sous-groupe) a investiguer - jamais comme une decouverte
a exploiter (voir docs/research_framework.md, section G, et l'echange de
validation de l'etape 5).

Les fonctions de calcul de flag (``is_calendar_congested``,
``rolling_win_rate``, ``is_must_win_proxy``) sont pures (aucun acces au
Repository), comme le reste du Football Model. Les fonctions
``prior_kickoffs_for_team``/``prior_results_for_team`` en bas de module
sont l'exception assumee : elles interrogent le Repository via
``get_as_of`` pour construire l'historique point-in-time necessaire aux
flags - c'est ce qui garantit, de facon testable, qu'aucun match/resultat
avec ``knowledge_time > decision_time`` ne peut influencer un sous-groupe
E1/E7 (voir tests/leakage/test_negative_controls_point_in_time.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from sys_foot_quant.data_engine.storage.repository import DuckDBRepository


def is_calendar_congested(
    this_kickoff: datetime,
    prior_kickoffs: Sequence[datetime],
    window_days: float = 7.0,
    min_matches_in_window: int = 3,
) -> bool:
    """E1 : True si ``this_kickoff`` est au moins le
    ``min_matches_in_window``-eme match de l'equipe (celui-ci inclus) sur
    une fenetre glissante de ``window_days`` jours se terminant a
    ``this_kickoff``. ``prior_kickoffs`` ne doit contenir QUE des matchs
    strictement anterieurs a ``this_kickoff`` (aucun filtrage temporel
    n'est fait ici - responsabilite de l'appelant)."""
    if min_matches_in_window < 1:
        raise ValueError("min_matches_in_window doit etre >= 1.")
    cutoff = this_kickoff - timedelta(days=window_days)
    n_recent = sum(1 for k in prior_kickoffs if cutoff <= k < this_kickoff)
    return (n_recent + 1) >= min_matches_in_window


def rolling_win_rate(
    prior_results: Sequence[tuple[datetime, bool]], window: int = 10
) -> float | None:
    """E7 (proxy) : taux de victoire de l'equipe sur ses ``window``
    derniers matchs strictement anterieurs au match evalue.
    ``prior_results`` : sequence de (kickoff_time, victoire?) pour cette
    equipe uniquement, matchs deja termines et connus a ``decision_time``
    (responsabilite de l'appelant). Retourne None si moins de ``window``
    matchs disponibles (echantillon insuffisant pour ce proxy).

    Limite assumee : ceci est une forme glissante ("forme recente"), PAS
    un classement de championnat au sens strict - le generateur
    synthetique ne modelise aucune structure de saison/journees, donc
    aucun classement formel n'est calculable sans construction
    arbitraire supplementaire. Documente explicitement comme
    simplification, pas comme un classement reel.
    """
    if window < 1:
        raise ValueError("window doit etre >= 1.")
    if len(prior_results) < window:
        return None
    ordered = sorted(prior_results, key=lambda r: r[0])
    recent = ordered[-window:]
    return sum(1 for _, won in recent if won) / window


def is_must_win_proxy(win_rate: float | None, threshold: float = 0.3) -> bool | None:
    """E7 (proxy) : equipe en "fort enjeu" si sa forme recente
    (``rolling_win_rate``) est sous ``threshold``. Retourne None si
    ``win_rate`` est None (echantillon insuffisant, propage l'absence de
    signal plutot que de forcer une classification arbitraire)."""
    if win_rate is None:
        return None
    return win_rate < threshold


def prior_kickoffs_for_team(
    repository: DuckDBRepository, team_id: int, decision_time: datetime, this_kickoff: datetime
) -> list[datetime]:
    """Coups d'envoi des matchs de ``team_id`` strictement anterieurs a
    ``this_kickoff``, visibles a ``decision_time`` (``get_as_of`` - donc
    jamais un match dont le fixture n'etait pas encore connu). Entree de
    ``is_calendar_congested``."""
    matches_asof = repository.get_as_of("matches", decision_time)
    mask = ((matches_asof["home_team_id"] == team_id) | (matches_asof["away_team_id"] == team_id)) & (
        matches_asof["kickoff_time"] < this_kickoff
    )
    return matches_asof.loc[mask, "kickoff_time"].tolist()


def prior_results_for_team(
    repository: DuckDBRepository, team_id: int, decision_time: datetime, this_kickoff: datetime
) -> list[tuple[datetime, bool]]:
    """Resultats (kickoff_time, victoire?) de ``team_id`` sur ses matchs
    strictement anterieurs a ``this_kickoff``, dont le resultat etait
    CONNU a ``decision_time`` (``get_as_of`` sur ``match_results``, donc
    jamais un resultat dont le ``knowledge_time`` est posterieur - c'est
    le garde-fou anti-look-ahead pour E7). Entree de ``rolling_win_rate``.
    """
    matches_asof = repository.get_as_of("matches", decision_time)
    results_asof = repository.get_as_of("match_results", decision_time)
    merged = matches_asof.merge(results_asof, on="match_id", how="inner")
    merged = merged[merged["kickoff_time"] < this_kickoff]

    out: list[tuple[datetime, bool]] = []
    home_rows = merged[merged["home_team_id"] == team_id]
    for _, row in home_rows.iterrows():
        out.append((row["kickoff_time"], bool(row["home_goals"] > row["away_goals"])))
    away_rows = merged[merged["away_team_id"] == team_id]
    for _, row in away_rows.iterrows():
        out.append((row["kickoff_time"], bool(row["away_goals"] > row["home_goals"])))
    return out
