from __future__ import annotations

from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sys_foot_quant.value_engine.clv import closing_line_value, compute_clv_for_selection


def test_closing_line_value_known_case() -> None:
    # Prix pris a 2.20, cloture juste a 2.00 -> CLV = (2.00/2.20 - 1)*100 = -9.0909%
    assert closing_line_value(2.20, 2.00) == pytest.approx(-9.0909, abs=1e-3)


def test_closing_line_value_sign_convention() -> None:
    # Cote prise 1.80, cote de cloture juste 2.00 : la cote a MONTE entre
    # notre prise et la cloture, donc l'issue est devenue MOINS probable
    # selon le marche depuis notre decision - on avait pris un prix plus
    # bas (moins genereux) que ce que le marche offrait finalement.
    # CLV = (2.00/1.80 - 1)*100 = +11.11% : positif signifie que la cote
    # de cloture est SUPERIEURE a celle prise, conformement a la formule
    # documentee (Dolan, docs/research_framework.md section C5).
    clv_up = closing_line_value(odds_taken=1.80, closing_fair_odds=2.00)
    assert clv_up == pytest.approx(11.111, abs=1e-2)

    # Cas symetrique : cote prise 2.20, cloture juste 2.00 (cote
    # descendue = issue devenue PLUS probable) -> CLV negatif.
    clv_down = closing_line_value(odds_taken=2.20, closing_fair_odds=2.00)
    assert clv_down < 0.0


def test_closing_line_value_rejects_invalid_odds() -> None:
    with pytest.raises(ValueError):
        closing_line_value(1.0, 2.0)
    with pytest.raises(ValueError):
        closing_line_value(2.0, 1.0)


@given(
    odds_taken=st.floats(min_value=1.01, max_value=100.0, allow_nan=False),
    closing_fair_odds=st.floats(min_value=1.01, max_value=100.0, allow_nan=False),
)
@settings(max_examples=150)
def test_closing_line_value_matches_direct_formula(odds_taken, closing_fair_odds) -> None:
    expected = (closing_fair_odds / odds_taken - 1.0) * 100.0
    assert closing_line_value(odds_taken, closing_fair_odds) == pytest.approx(expected, rel=1e-9)


def test_closing_line_value_zero_when_odds_taken_equals_closing() -> None:
    assert closing_line_value(2.30, 2.30) == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# compute_clv_for_selection : garde-fou anti-look-ahead + integration Repository.
# ---------------------------------------------------------------------------


def test_compute_clv_rejects_closing_time_at_or_before_decision_time(repo) -> None:
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    match_id = int(full_matches.iloc[0]["match_id"])
    kickoff = full_matches.iloc[0]["kickoff_time"]
    decision_time = kickoff - timedelta(hours=2)

    with pytest.raises(ValueError, match="posterieur"):
        compute_clv_for_selection(
            repo, match_id, "home", 2.0, decision_time, decision_time
        )
    with pytest.raises(ValueError, match="posterieur"):
        compute_clv_for_selection(
            repo, match_id, "home", 2.0, decision_time, decision_time - timedelta(hours=1)
        )


def test_compute_clv_returns_none_when_no_snapshot_at_closing(repo) -> None:
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    match_id = int(full_matches.iloc[0]["match_id"])
    kickoff = full_matches.iloc[0]["kickoff_time"]
    fixture_known = full_matches.iloc[0]["knowledge_time"]
    decision_time = fixture_known
    closing_reference_time = fixture_known + timedelta(minutes=1)

    result = compute_clv_for_selection(
        repo, match_id, "home", 2.0, decision_time, closing_reference_time
    )
    assert result is None


def test_compute_clv_matches_manual_computation(repo) -> None:
    full_matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
    match_id = int(full_matches.iloc[0]["match_id"])
    kickoff = full_matches.iloc[0]["kickoff_time"]
    decision_time = kickoff - timedelta(hours=3)

    result = compute_clv_for_selection(
        repo, match_id, "home", odds_taken=2.0, decision_time=decision_time,
        closing_reference_time=kickoff,
    )
    assert result is not None

    full_odds = repo.debug_get_full_table("odds_snapshots")
    match_odds = full_odds[full_odds["match_id"] == match_id]
    latest_time = match_odds["knowledge_time"].max()
    latest = match_odds[match_odds["knowledge_time"] == latest_time]
    fair_home = dict(zip(latest["selection"], latest["odds_value"]))
    from sys_foot_quant.market_engine.overround import remove_overround_proportional

    fair = remove_overround_proportional(fair_home)
    expected = closing_line_value(2.0, 1.0 / fair["home"])
    assert result == pytest.approx(expected, abs=1e-9)
