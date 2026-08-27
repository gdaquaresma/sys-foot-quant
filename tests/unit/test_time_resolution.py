from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sys_foot_quant.data_engine.market_odds.time_resolution import (
    TIMESTAMP_STATUS_HYPOTHETICAL,
    TIMESTAMP_STATUS_VERIFIED,
    AmbiguousCollectionWindowError,
    conservative_knowledge_time_utc,
    football_data_kickoff_to_utc,
)


def test_winter_kickoff_gmt_equals_utc() -> None:
    # 15 fevrier 2025 (GMT, UTC+0) - aucun decalage attendu.
    dt = football_data_kickoff_to_utc("15/02/2025", "15:00")
    assert dt == datetime(2025, 2, 15, 15, 0, tzinfo=timezone.utc)


def test_summer_kickoff_bst_is_one_hour_ahead_of_utc() -> None:
    # 16 aout 2024 (BST, UTC+1) - la cote de 20:00 heure de Londres est 19:00 UTC.
    dt = football_data_kickoff_to_utc("16/08/2024", "20:00")
    assert dt == datetime(2024, 8, 16, 19, 0, tzinfo=timezone.utc)


def test_across_dst_transition_weekend() -> None:
    # 26 octobre 2025 (encore BST, transition le 26/10 a 2h locales) vs
    # 27 octobre 2025 (deja GMT) - la conversion doit refleter le bon
    # decalage de chaque cote de la transition sans intervention manuelle.
    before = football_data_kickoff_to_utc("25/10/2025", "15:00")  # samedi, encore BST
    after = football_data_kickoff_to_utc("28/10/2025", "15:00")  # mardi, deja GMT
    assert before == datetime(2025, 10, 25, 14, 0, tzinfo=timezone.utc)
    assert after == datetime(2025, 10, 28, 15, 0, tzinfo=timezone.utc)


def test_timestamp_status_constants_are_distinct() -> None:
    assert TIMESTAMP_STATUS_VERIFIED != TIMESTAMP_STATUS_HYPOTHETICAL


@pytest.mark.parametrize(
    "kickoff_iso,expected_reference_date",
    [
        ("2024-08-17T15:00:00+00:00", "2024-08-16"),  # samedi -> vendredi precedent
        ("2024-08-18T15:00:00+00:00", "2024-08-16"),  # dimanche -> vendredi precedent
        ("2024-08-21T19:00:00+00:00", "2024-08-20"),  # mercredi -> mardi precedent
        ("2024-08-22T19:00:00+00:00", "2024-08-20"),  # jeudi -> mardi precedent
    ],
)
def test_conservative_knowledge_time_reference_day(kickoff_iso: str, expected_reference_date: str) -> None:
    kickoff = datetime.fromisoformat(kickoff_iso)
    result = conservative_knowledge_time_utc(kickoff)
    # Reconverti en heure de Londres pour lire la date de reference choisie.
    from zoneinfo import ZoneInfo

    local = result.astimezone(ZoneInfo("Europe/London"))
    assert local.date().isoformat() == expected_reference_date
    assert local.time().isoformat() == "23:59:59"


def test_conservative_knowledge_time_strictly_before_kickoff() -> None:
    kickoff = datetime(2024, 8, 18, 15, 0, tzinfo=timezone.utc)  # dimanche
    knowledge = conservative_knowledge_time_utc(kickoff)
    assert knowledge < kickoff


@pytest.mark.parametrize(
    "kickoff_iso",
    [
        "2024-08-16T19:45:00+00:00",  # vendredi
        "2024-08-19T19:45:00+00:00",  # lundi
        "2024-08-20T19:45:00+00:00",  # mardi (le jour lui-meme, ambigu par rapport a son propre match)
    ],
)
def test_friday_monday_and_tuesday_kickoffs_raise_ambiguous_error(kickoff_iso: str) -> None:
    kickoff = datetime.fromisoformat(kickoff_iso)
    with pytest.raises(AmbiguousCollectionWindowError):
        conservative_knowledge_time_utc(kickoff)
