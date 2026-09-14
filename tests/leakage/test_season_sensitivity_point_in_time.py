"""Garanties anti-fuite pour data_engine.market_odds.season_sensitivity -
donnees SYNTHETIQUES uniquement. Ce module ne reimplemente aucun filtrage
point-in-time (delegue integralement a future_match_dataset/
calibration_dataset, deja testes dans
tests/leakage/test_future_match_dataset_point_in_time.py et
tests/leakage/test_calibration_dataset_point_in_time.py) - les tests
ci-dessous verifient que season_sensitivity ne CONTOURNE pas ces
garanties (ex. en oubliant de propager exclude_match_id), pas que le
filtrage lui-meme est correct (deja prouve ailleurs)."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta

from sys_foot_quant.backtesting_engine.real_data_walk_forward import RealMatchRecord
from sys_foot_quant.data_engine.market_odds.season_sensitivity import compute_season_sensitivity

_T0 = datetime(2020, 1, 1)
_HOME = 0
_AWAY = 1
_DECISION_OFFSET_HOURS = 2.0
_TARGET_KICKOFF = _T0 + timedelta(days=250)
_TARGET_MATCH_ID = "target-brest-psg"


def _record(match_id: str, kickoff: datetime, home_id: int, away_id: int, home_goals: int, away_goals: int) -> RealMatchRecord:
    return RealMatchRecord(
        match_id=match_id,
        league="ligue1",
        kickoff_utc=kickoff,
        home_team_id=home_id,
        away_team_id=away_id,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=float(home_goals) + 0.2,
        away_xg=float(away_goals) + 0.2,
        goals_knowledge_time=kickoff + timedelta(hours=2.0),
        xg_knowledge_time=kickoff + timedelta(hours=48.0),
    )


def _baseline_history() -> list[RealMatchRecord]:
    pairs = [(0, 1), (2, 3), (1, 2), (3, 0), (0, 2), (1, 3)]
    return [
        _record(f"b{i}", _T0 + timedelta(days=4 * i), *pairs[i % len(pairs)], home_goals=1 + (i % 3), away_goals=1 + ((i + 1) % 2))
        for i in range(50)
    ]


def _compare(baseline, current):
    return compute_season_sensitivity(
        baseline_records=baseline,
        current_records=current,
        match_id=_TARGET_MATCH_ID,
        competition="ligue1",
        season="2026_27",
        home_team_id=_HOME,
        away_team_id=_AWAY,
        kickoff_utc=_TARGET_KICKOFF,
        decision_offset_hours=_DECISION_OFFSET_HOURS,
        market_odds_over_2_5=1.32,
        market_odds_under_2_5=2.92,
    )


def test_a_match_played_after_the_target_kickoff_never_enters_training() -> None:
    baseline = _baseline_history()
    future_leak = _record(
        "future-leak", _TARGET_KICKOFF + timedelta(days=5), _HOME, _AWAY, home_goals=9, away_goals=0
    )
    current_with_leak = sorted(baseline + [future_leak], key=lambda r: r.kickoff_utc)

    comparison_clean = _compare(baseline, baseline)
    comparison_with_leak = _compare(baseline, current_with_leak)

    assert comparison_with_leak.current.n_train_matches == comparison_clean.current.n_train_matches
    assert comparison_with_leak.current.attack_home == comparison_clean.current.attack_home
    assert comparison_with_leak.current.defense_home == comparison_clean.current.defense_home
    assert comparison_with_leak.current.lambda_home == comparison_clean.current.lambda_home
    assert comparison_with_leak.current.p_over_2_5 == comparison_clean.current.p_over_2_5


def test_a_match_played_between_decision_time_and_kickoff_never_enters_training() -> None:
    """Un match dont le coup d'envoi tombe APRES decision_time mais AVANT
    le coup d'envoi de la cible (fenetre des ~2h de decision_offset_hours)
    ne doit pas non plus etre utilise - c'est exactement la fenetre que
    decision_offset_hours protege."""
    baseline = _baseline_history()
    near_leak = _record(
        "near-leak",
        _TARGET_KICKOFF - timedelta(minutes=30),  # apres decision_time (kickoff - 2h), avant kickoff
        _HOME,
        _AWAY,
        home_goals=9,
        away_goals=0,
    )
    current_with_leak = sorted(baseline + [near_leak], key=lambda r: r.kickoff_utc)

    comparison_clean = _compare(baseline, baseline)
    comparison_with_leak = _compare(baseline, current_with_leak)

    assert comparison_with_leak.current.n_train_matches == comparison_clean.current.n_train_matches
    assert comparison_with_leak.current.attack_home == comparison_clean.current.attack_home


def test_target_match_itself_is_excluded_even_if_a_record_shares_its_match_id() -> None:
    """Contamination simulee : un enregistrement partageant le match_id de
    la cible (ex. le fichier saison courante re-emet par erreur le match
    lui-meme) doit rester exclu, meme si son horodatage passerait le
    filtre temporel seul (garde-fou exclude_match_id explicite, pas
    seulement une consequence indirecte du filtre PIT)."""
    baseline = _baseline_history()
    contaminating_record = _record(
        _TARGET_MATCH_ID,  # meme match_id que la cible
        _TARGET_KICKOFF - timedelta(days=1),  # anterieur a decision_time, passerait le filtre temporel seul
        _HOME,
        _AWAY,
        home_goals=9,
        away_goals=0,
    )
    current_clean = baseline
    current_contaminated = sorted(baseline + [contaminating_record], key=lambda r: r.kickoff_utc)

    comparison_clean = _compare(baseline, current_clean)
    comparison_contaminated = _compare(baseline, current_contaminated)

    assert comparison_contaminated.current.n_train_matches == comparison_clean.current.n_train_matches
    assert comparison_contaminated.current.attack_home == comparison_clean.current.attack_home
    assert comparison_contaminated.current.defense_home == comparison_clean.current.defense_home


def test_baseline_records_are_never_mutated_by_the_comparison() -> None:
    baseline = _baseline_history()
    baseline_before = copy.deepcopy(baseline)
    extension = [_record("c0", _T0 + timedelta(days=210), _HOME, 2, home_goals=3, away_goals=0)]
    current = sorted(baseline + extension, key=lambda r: r.kickoff_utc)

    _compare(baseline, current)

    assert baseline == baseline_before


def test_current_season_matches_beyond_decision_time_are_dropped_but_earlier_ones_kept() -> None:
    """Verifie le comportement mixte : sur un lot de matchs "saison
    courante", seuls ceux strictement anterieurs a decision_time
    contribuent - jamais tout ou rien par accident d'implementation."""
    baseline = _baseline_history()
    early_extension = _record("c-early", _T0 + timedelta(days=210), _HOME, 2, home_goals=3, away_goals=0)
    late_leak = _record("c-late", _TARGET_KICKOFF + timedelta(days=1), _HOME, 2, home_goals=9, away_goals=0)

    current_early_only = sorted(baseline + [early_extension], key=lambda r: r.kickoff_utc)
    current_mixed = sorted(baseline + [early_extension, late_leak], key=lambda r: r.kickoff_utc)

    comparison_early_only = _compare(baseline, current_early_only)
    comparison_mixed = _compare(baseline, current_mixed)

    assert comparison_mixed.current.n_train_matches == comparison_early_only.current.n_train_matches
    assert comparison_mixed.current.attack_home == comparison_early_only.current.attack_home
