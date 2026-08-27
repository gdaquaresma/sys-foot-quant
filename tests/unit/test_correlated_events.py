from __future__ import annotations

from datetime import datetime

from sys_foot_quant.market_engine.correlated_events import (
    aggregate_verdict,
    association_result_from_predictions,
    eligible_match_ids_after_burn_in,
    label_home_favorite,
    label_over_2_5,
    per_league_bucket,
)


def test_label_home_favorite_strict_comparison() -> None:
    assert label_home_favorite(0.5, 0.3) is True
    assert label_home_favorite(0.3, 0.5) is False
    # Egalite (favori ambigu) traitee comme "non A", jamais comme favori domicile.
    assert label_home_favorite(0.4, 0.4) is False


def test_label_over_2_5_boundary() -> None:
    assert label_over_2_5(1, 1) is False  # 2 buts -> Under
    assert label_over_2_5(2, 1) is True  # 3 buts -> Over
    assert label_over_2_5(0, 0) is False
    assert label_over_2_5(3, 2) is True


def test_eligible_match_ids_after_burn_in_excludes_first_fraction() -> None:
    pairs = [(f"m{i}", datetime(2024, 1, 1 + i)) for i in range(10)]
    eligible = eligible_match_ids_after_burn_in(pairs, burn_in_fraction=0.4)
    assert eligible == [f"m{i}" for i in range(4, 10)]


def test_eligible_match_ids_after_burn_in_orders_by_kickoff_not_input_order() -> None:
    pairs = [
        ("late", datetime(2024, 1, 10)),
        ("early", datetime(2024, 1, 1)),
        ("mid", datetime(2024, 1, 5)),
    ]
    eligible = eligible_match_ids_after_burn_in(pairs, burn_in_fraction=0.34)
    # 34% de 3 = 1 (int troncature) -> le plus ancien ("early") est exclu.
    assert eligible == ["mid", "late"]


def test_association_result_detects_positive_correlation() -> None:
    # A vrai -> B presque toujours vrai ; A faux -> B presque toujours faux.
    rows = [(0.6, 0.2, 2, 1) for _ in range(60)]  # A=True, over 2.5=True
    rows += [(0.1, 0.6, 0, 1) for _ in range(60)]  # A=False, over 2.5=False
    result = association_result_from_predictions(rows)
    assert result["diff"] > 0
    assert result["ci_low"] > 0.0
    assert result["n"] == 120


def test_association_result_no_correlation_when_independent() -> None:
    # A (favori) determine par la moitie de l'indice, B (over) par sa parite -
    # les deux sont statistiquement independants par construction (50/50 croises).
    rows = []
    for i in range(200):
        is_favorite = i < 100
        is_over = i % 2 == 0
        home_goals = 2 if is_over else 1
        away_goals = 1 if is_over else 1
        rows.append((0.6 if is_favorite else 0.2, 0.2 if is_favorite else 0.6, home_goals, away_goals))
    result = association_result_from_predictions(rows)
    assert result["ci_low"] <= 0.0 <= result["ci_high"]


def test_per_league_bucket_positif_confirme_requires_both_seasons_significant() -> None:
    positive = {"ci_low": 0.05, "ci_high": 0.20}
    assert per_league_bucket(positive, positive) == "positif_confirme"


def test_per_league_bucket_non_positif_when_only_estimation_significant() -> None:
    positive = {"ci_low": 0.05, "ci_high": 0.20}
    null = {"ci_low": -0.05, "ci_high": 0.05}
    assert per_league_bucket(positive, null) == "non_positif"
    assert per_league_bucket(null, positive) == "non_positif"


def test_per_league_bucket_non_positif_when_both_null() -> None:
    null = {"ci_low": -0.05, "ci_high": 0.05}
    assert per_league_bucket(null, null) == "non_positif"


def test_per_league_bucket_non_positif_when_negative_effect() -> None:
    negative = {"ci_low": -0.20, "ci_high": -0.05}
    assert per_league_bucket(negative, negative) == "non_positif"


def test_aggregate_verdict_valide_requires_all_leagues_positive() -> None:
    assert aggregate_verdict(["positif_confirme", "positif_confirme", "positif_confirme"]) == "VALIDE"


def test_aggregate_verdict_rejete_requires_all_leagues_non_positif() -> None:
    assert aggregate_verdict(["non_positif", "non_positif", "non_positif"]) == "REJETE"


def test_aggregate_verdict_indetermine_on_mixed_leagues() -> None:
    assert aggregate_verdict(["positif_confirme", "non_positif", "positif_confirme"]) == "INDETERMINE"
