"""Tests cibles pour la conversion CET/CEST isolee Ligue 1 (PHASE SHADOW -
EXTENSION CONTROLEE). Couvre : CET, CEST, jour de changement d'heure
(printemps/automne), annee non couverte, heure deja timezone-aware,
incoherence date/fixture_date, verification croisee (concordance et
divergence), et le cas reel Lille-Brest utilise comme test initial."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from sys_foot_quant.data_engine.market_odds.ligue1_kickoff_cet_conversion import (
    AmbiguousOrInvalidKickoffError,
    build_cross_checked_kickoff,
    convert_ligue1_local_kickoff_to_utc,
    timezone_label_for,
)


# --- Conversion CET (hiver) --------------------------------------------------


def test_cet_conversion_january() -> None:
    fixture_date = date(2026, 1, 15)
    local = datetime(2026, 1, 15, 21, 0)
    utc = convert_ligue1_local_kickoff_to_utc(fixture_date, local)
    assert utc == datetime(2026, 1, 15, 20, 0, tzinfo=timezone.utc)
    assert timezone_label_for(fixture_date) == "CET"


# --- Conversion CEST (ete) ---------------------------------------------------


def test_cest_conversion_july() -> None:
    fixture_date = date(2026, 7, 15)
    local = datetime(2026, 7, 15, 21, 0)
    utc = convert_ligue1_local_kickoff_to_utc(fixture_date, local)
    assert utc == datetime(2026, 7, 15, 19, 0, tzinfo=timezone.utc)
    assert timezone_label_for(fixture_date) == "CEST"


# --- Cas reel Lille-Brest (test initial de la phase) -------------------------


def test_real_case_lille_brest_17_october_2026() -> None:
    fixture_date = date(2026, 10, 17)
    local = datetime(2026, 10, 17, 20, 45)  # avant le 25/10/2026 -> encore CEST
    utc = convert_ligue1_local_kickoff_to_utc(fixture_date, local)
    assert utc == datetime(2026, 10, 17, 18, 45, tzinfo=timezone.utc)
    assert timezone_label_for(fixture_date) == "CEST"


# --- Jour du changement d'heure : refus explicite ----------------------------


def test_spring_dst_transition_day_rejected() -> None:
    fixture_date = date(2026, 3, 29)
    local = datetime(2026, 3, 29, 20, 45)
    with pytest.raises(AmbiguousOrInvalidKickoffError, match="changement d'heure"):
        convert_ligue1_local_kickoff_to_utc(fixture_date, local)


def test_autumn_dst_transition_day_rejected() -> None:
    fixture_date = date(2026, 10, 25)
    local = datetime(2026, 10, 25, 20, 45)
    with pytest.raises(AmbiguousOrInvalidKickoffError, match="changement d'heure"):
        convert_ligue1_local_kickoff_to_utc(fixture_date, local)


def test_day_immediately_after_autumn_transition_is_cet() -> None:
    fixture_date = date(2026, 10, 26)
    local = datetime(2026, 10, 26, 20, 45)
    utc = convert_ligue1_local_kickoff_to_utc(fixture_date, local)
    assert utc == datetime(2026, 10, 26, 19, 45, tzinfo=timezone.utc)
    assert timezone_label_for(fixture_date) == "CET"


def test_day_immediately_before_spring_transition_is_cet() -> None:
    fixture_date = date(2026, 3, 28)
    local = datetime(2026, 3, 28, 20, 45)
    utc = convert_ligue1_local_kickoff_to_utc(fixture_date, local)
    assert utc == datetime(2026, 3, 28, 19, 45, tzinfo=timezone.utc)
    assert timezone_label_for(fixture_date) == "CET"


# --- Annee non couverte -------------------------------------------------------


def test_year_outside_explicit_table_rejected() -> None:
    fixture_date = date(2030, 10, 17)
    local = datetime(2030, 10, 17, 20, 45)
    with pytest.raises(AmbiguousOrInvalidKickoffError, match="non couverte"):
        convert_ligue1_local_kickoff_to_utc(fixture_date, local)


# --- Heure deja timezone-aware : refus ---------------------------------------


def test_already_timezone_aware_input_rejected() -> None:
    fixture_date = date(2026, 10, 17)
    local = datetime(2026, 10, 17, 20, 45, tzinfo=timezone.utc)
    with pytest.raises(AmbiguousOrInvalidKickoffError, match="naif"):
        convert_ligue1_local_kickoff_to_utc(fixture_date, local)


# --- Incoherence fixture_date / date de kickoff_local_naive ------------------


def test_mismatched_fixture_date_rejected() -> None:
    fixture_date = date(2026, 10, 17)
    local = datetime(2026, 10, 18, 20, 45)  # jour different
    with pytest.raises(AmbiguousOrInvalidKickoffError, match="divergent"):
        convert_ligue1_local_kickoff_to_utc(fixture_date, local)


# --- Verification croisee : concordance --------------------------------------


def test_cross_check_matching_sources_is_verified_but_not_officially_confirmed() -> None:
    fixture_date = date(2026, 10, 17)
    local = datetime(2026, 10, 17, 20, 45)
    result = build_cross_checked_kickoff(
        fixture_date=fixture_date,
        kickoff_local_naive=local,
        source_local_time="OpenFootball (GitHub, deja integre)",
        cross_check_source="WebSearch - Stat Sniper",
        cross_check_local_time=local,
    )
    assert result.verified is True
    assert result.kickoff_utc == datetime(2026, 10, 17, 18, 45, tzinfo=timezone.utc)
    assert result.officially_confirmed is False  # jamais deduit par defaut


# --- Verification croisee : divergence ---------------------------------------


def test_cross_check_diverging_sources_is_not_verified() -> None:
    fixture_date = date(2026, 10, 17)
    local = datetime(2026, 10, 17, 20, 45)
    diverging = datetime(2026, 10, 17, 21, 0)  # source secondaire differente
    result = build_cross_checked_kickoff(
        fixture_date=fixture_date,
        kickoff_local_naive=local,
        source_local_time="OpenFootball (GitHub, deja integre)",
        cross_check_source="Source divergente",
        cross_check_local_time=diverging,
    )
    assert result.verified is False
    # L'heure UTC est tout de meme calculee pour tracabilite, mais ne doit
    # jamais etre utilisee par l'appelant quand verified=False.
    assert result.cross_check_kickoff_matches is False
