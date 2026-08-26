"""Mesure du risque de revision xG entre deux extractions datees
(protocole B3, priorite 2 - docs/research_framework.md section B3).

Fonction PURE : ne fait que comparer deux ``ExtractionFile`` deja
chargees. Ne "mesure" jamais rien tant que deux extractions REELLES
(collectees a des dates differentes) n'existent pas - ce module ne
simule ni ne suppose aucune revision, il se contente de rapporter ce
qu'il trouve dans les deux fichiers fournis.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.xg_feasibility.storage import ExtractionFile

_DEFAULT_CHANGE_EPSILON = 0.005  # tolerance pour ignorer le bruit d'arrondi, PAS une vraie revision


@dataclass(frozen=True)
class FieldDiffStats:
    n_common: int
    n_changed: int
    proportion_changed: float
    mean_abs_diff: float
    median_abs_diff: float
    max_abs_diff: float
    # Quantiles (p50/p90/p99) de la valeur absolue des ecarts, sur les
    # matchs communs uniquement (pas seulement ceux "changes") - donne une
    # vue de la distribution complete, pas seulement du taux binaire.
    p50_abs_diff: float
    p90_abs_diff: float
    p99_abs_diff: float


@dataclass(frozen=True)
class ComparisonReport:
    first_collected_at: str
    second_collected_at: str
    n_only_in_first: int
    n_only_in_second: int
    home_xg: FieldDiffStats
    away_xg: FieldDiffStats


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, int(round(pct * (len(sorted_values) - 1))))
    return sorted_values[idx]


def _field_diff_stats(
    first_values: list[float], second_values: list[float], epsilon: float
) -> FieldDiffStats:
    diffs = sorted(abs(a - b) for a, b in zip(first_values, second_values))
    n_common = len(diffs)
    n_changed = sum(1 for d in diffs if d > epsilon)
    return FieldDiffStats(
        n_common=n_common,
        n_changed=n_changed,
        proportion_changed=(n_changed / n_common) if n_common else 0.0,
        mean_abs_diff=(sum(diffs) / n_common) if n_common else 0.0,
        median_abs_diff=_percentile(diffs, 0.5),
        max_abs_diff=diffs[-1] if diffs else 0.0,
        p50_abs_diff=_percentile(diffs, 0.5),
        p90_abs_diff=_percentile(diffs, 0.9),
        p99_abs_diff=_percentile(diffs, 0.99),
    )


def compare_extractions(
    first: ExtractionFile, second: ExtractionFile, epsilon: float = _DEFAULT_CHANGE_EPSILON
) -> ComparisonReport:
    """Compare deux extractions sur les matchs presents dans les DEUX
    (jointure sur ``match_id``). Les matchs absents d'un seul cote sont
    comptes mais jamais utilises dans les statistiques d'ecart (ils ne
    disent rien sur une revision, seulement sur une difference de
    couverture entre les deux extractions)."""
    first_by_id = {r.match_id: r for r in first.records}
    second_by_id = {r.match_id: r for r in second.records}
    common_ids = sorted(set(first_by_id) & set(second_by_id))

    home_first = [first_by_id[mid].home_xg for mid in common_ids]
    home_second = [second_by_id[mid].home_xg for mid in common_ids]
    away_first = [first_by_id[mid].away_xg for mid in common_ids]
    away_second = [second_by_id[mid].away_xg for mid in common_ids]

    return ComparisonReport(
        first_collected_at=first.collected_at.isoformat(),
        second_collected_at=second.collected_at.isoformat(),
        n_only_in_first=len(set(first_by_id) - set(second_by_id)),
        n_only_in_second=len(set(second_by_id) - set(first_by_id)),
        home_xg=_field_diff_stats(home_first, home_second, epsilon),
        away_xg=_field_diff_stats(away_first, away_second, epsilon),
    )
