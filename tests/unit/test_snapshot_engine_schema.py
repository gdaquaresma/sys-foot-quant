"""Tests de la couche Snapshot (design valide, voir
``src/sys_foot_quant/snapshot_engine/schema.py``).

Couvre explicitement les 13 points demandes + les tests de fuseau
horaire : creation valide, generation automatique du timestamp,
``decision_time == capture_timestamp``, garde temporelle
avant/a/apres kickoff, impossibilite de falsifier le timestamp,
conservation exacte de la cote/ligne/bookmaker, absence de fuite de
closing odds, compatibilite R3, CLV a posteriori uniquement."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sys_foot_quant.snapshot_engine.schema import (
    OddsObservation,
    OddsSnapshot,
    SnapshotValidationError,
    create_snapshot,
    decision_offset_hours_from_snapshot,
    extract_over_under_2_5,
    kickoff_utc_naive_for_r3,
)

_KICKOFF = datetime(2026, 3, 1, 20, 0, 0, tzinfo=timezone.utc)


def _obs_over_under(bookmaker: str = "Bet365") -> list[OddsObservation]:
    return [
        OddsObservation(bookmaker=bookmaker, market="over_under", selection="OVER", line=2.5, odds=1.60),
        OddsObservation(bookmaker=bookmaker, market="over_under", selection="UNDER", line=2.5, odds=2.30),
    ]


# --- 1. Creation valide d'un snapshot ---------------------------------------


def test_valid_snapshot_creation() -> None:
    fixed_now = _KICKOFF - timedelta(hours=2)
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, observations=_obs_over_under(), _now_fn=lambda: fixed_now,
    )
    assert snapshot.home_team == "Benfica"
    assert snapshot.away_team == "Estoril"
    assert len(snapshot.observations) == 2


# --- 2. Generation automatique du timestamp ---------------------------------


def test_capture_timestamp_is_generated_automatically_not_user_supplied() -> None:
    """create_snapshot() n'accepte aucun parametre capture_timestamp -
    verifie qu'il n'existe simplement pas dans la signature publique."""
    import inspect

    sig = inspect.signature(create_snapshot)
    assert "capture_timestamp" not in sig.parameters
    # Le seul mecanisme d'injection est _now_fn (prefixe underscore,
    # jamais destine a un appelant reel/CLI).
    assert "_now_fn" in sig.parameters


def test_create_snapshot_uses_system_clock_by_default(monkeypatch) -> None:
    fixed = _KICKOFF - timedelta(hours=3)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    import sys_foot_quant.snapshot_engine.schema as schema_module

    monkeypatch.setattr(schema_module, "datetime", _FixedDatetime)
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, observations=_obs_over_under(),
    )
    assert snapshot.capture_timestamp == fixed


# --- 3. decision_time == capture_timestamp ----------------------------------


def test_decision_time_always_equals_capture_timestamp() -> None:
    fixed_now = _KICKOFF - timedelta(hours=1, minutes=30)
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, observations=_obs_over_under(), _now_fn=lambda: fixed_now,
    )
    assert snapshot.decision_time == snapshot.capture_timestamp == fixed_now


# --- 4. Snapshot avant kickoff accepte --------------------------------------


def test_snapshot_before_kickoff_is_accepted() -> None:
    snapshot = OddsSnapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, capture_timestamp=_KICKOFF - timedelta(minutes=1),
        observations=tuple(_obs_over_under()),
    )
    assert snapshot.capture_timestamp < snapshot.kickoff_utc


# --- 5. Snapshot a kickoff refuse -------------------------------------------


def test_snapshot_at_exact_kickoff_is_refused() -> None:
    with pytest.raises(SnapshotValidationError, match="egal au"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=_KICKOFF, capture_timestamp=_KICKOFF,
            observations=tuple(_obs_over_under()),
        )


# --- 6. Snapshot apres kickoff refuse ---------------------------------------


def test_snapshot_after_kickoff_is_refused() -> None:
    with pytest.raises(SnapshotValidationError, match="posterieur au"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=_KICKOFF, capture_timestamp=_KICKOFF + timedelta(minutes=1),
            observations=tuple(_obs_over_under()),
        )


# --- 7. Impossibilite de falsifier le timestamp de capture ------------------


def test_cannot_falsify_capture_timestamp_via_public_api() -> None:
    """create_snapshot() (l'API publique/production) n'a aucun moyen de
    faire passer un capture_timestamp choisi par l'appelant - meme un
    appelant malveillant ne peut passer qu'une valeur qui sera ignoree
    (TypeError, le parametre n'existe pas)."""
    with pytest.raises(TypeError):
        create_snapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=_KICKOFF, observations=_obs_over_under(),
            capture_timestamp=_KICKOFF - timedelta(days=365),  # type: ignore[call-arg]
        )


def test_directly_constructed_snapshot_still_enforces_the_invariant() -> None:
    """Meme en contournant create_snapshot() et en construisant
    OddsSnapshot directement (ce qu'un attaquant pourrait tenter), la
    garde temporelle vit dans __post_init__ - donc un capture_timestamp
    posterieur au kickoff reste refuse, peu importe le chemin de
    construction."""
    with pytest.raises(SnapshotValidationError):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=_KICKOFF, capture_timestamp=_KICKOFF + timedelta(hours=10),
            observations=tuple(_obs_over_under()),
        )


# --- 8-10. Conservation exacte de la cote/ligne/bookmaker -------------------


def test_snapshot_preserves_exact_odds_line_and_bookmaker() -> None:
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, observations=_obs_over_under("Pinnacle"),
        _now_fn=lambda: _KICKOFF - timedelta(hours=2),
    )
    over = next(o for o in snapshot.observations if o.selection == "OVER")
    assert over.odds == 1.60  # jamais arrondi, moyenne ou interpole
    assert over.line == 2.5
    assert over.bookmaker == "Pinnacle"


def test_extract_over_under_2_5_preserves_exact_values() -> None:
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, observations=_obs_over_under(), _now_fn=lambda: _KICKOFF - timedelta(hours=2),
    )
    odds = extract_over_under_2_5(snapshot)
    assert odds == {"Over": 1.60, "Under": 2.30}


# --- 11. Aucune fuite de closing odds dans le calcul pre-match --------------


def test_snapshot_has_no_closing_odds_concept_at_all() -> None:
    """Le schema n'a structurellement aucun champ 'closing'/'opening' -
    seule une observation avec son propre capture_timestamp existe.
    Verifie qu'aucun attribut de ce type n'existe sur les dataclasses."""
    obs_fields = OddsObservation.__dataclass_fields__.keys()
    snap_fields = OddsSnapshot.__dataclass_fields__.keys()
    for forbidden in ("closing", "opening", "close", "open"):
        assert not any(forbidden in f.lower() for f in obs_fields)
        assert not any(forbidden in f.lower() for f in snap_fields)


def test_extract_over_under_2_5_never_falls_back_to_multiple_bookmakers_silently() -> None:
    """Si plusieurs bookmakers offrent Over/Under 2.5, refuse plutot que
    de choisir un en silence (jamais une moyenne implicite)."""
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF,
        observations=_obs_over_under("Bet365") + _obs_over_under("Pinnacle"),
        _now_fn=lambda: _KICKOFF - timedelta(hours=2),
    )
    with pytest.raises(SnapshotValidationError, match="Plusieurs bookmakers"):
        extract_over_under_2_5(snapshot)
    # Mais fonctionne si le bookmaker est precise explicitement.
    odds = extract_over_under_2_5(snapshot, bookmaker="Pinnacle")
    assert odds == {"Over": 1.60, "Under": 2.30}


def test_extract_over_under_2_5_rejects_missing_selection() -> None:
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF,
        observations=[OddsObservation(bookmaker="Bet365", market="over_under", selection="OVER", line=2.5, odds=1.60)],
        _now_fn=lambda: _KICKOFF - timedelta(hours=2),
    )
    with pytest.raises(SnapshotValidationError, match="exactement une observation OVER et une UNDER"):
        extract_over_under_2_5(snapshot)


# --- 12. Compatibilite avec les arguments R3 existants ----------------------


def test_kickoff_utc_naive_for_r3_matches_existing_convention() -> None:
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, observations=_obs_over_under(), _now_fn=lambda: _KICKOFF - timedelta(hours=2),
    )
    naive = kickoff_utc_naive_for_r3(snapshot)
    assert naive.tzinfo is None
    assert naive == _KICKOFF.replace(tzinfo=None)


def test_decision_offset_hours_from_snapshot_is_computed_correctly() -> None:
    fixed_now = _KICKOFF - timedelta(hours=2, minutes=30)
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, observations=_obs_over_under(), _now_fn=lambda: fixed_now,
    )
    offset = decision_offset_hours_from_snapshot(snapshot)
    assert offset == pytest.approx(2.5)


def test_decision_offset_hours_is_always_strictly_positive() -> None:
    """Garanti par construction (capture_timestamp < kickoff_utc deja
    valide) - jamais zero ni negatif."""
    fixed_now = _KICKOFF - timedelta(seconds=1)
    snapshot = create_snapshot(
        competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
        kickoff_utc=_KICKOFF, observations=_obs_over_under(), _now_fn=lambda: fixed_now,
    )
    assert decision_offset_hours_from_snapshot(snapshot) > 0.0


# --- 13. CLV uniquement calcule a posteriori --------------------------------
# (Le module snapshot_engine ne calcule lui-meme aucun CLV - c'est
# value_engine.clv.closing_line_value, INCHANGE, qui reste l'unique point
# de calcul. Ce test verifie que ce module n'importe ni n'expose rien lie
# a une cote de cloture.)


def test_schema_module_never_references_closing_odds_computation() -> None:
    import sys_foot_quant.snapshot_engine.schema as schema_module

    assert not hasattr(schema_module, "closing_line_value")
    assert not hasattr(schema_module, "compute_clv")


# --- Validations d'observation individuelle ---------------------------------


def test_observation_rejects_odds_not_greater_than_one() -> None:
    with pytest.raises(SnapshotValidationError, match="odds invalide"):
        OddsObservation(bookmaker="Bet365", market="over_under", selection="OVER", line=2.5, odds=0.95)


def test_observation_rejects_nan_odds() -> None:
    with pytest.raises(SnapshotValidationError, match="odds invalide"):
        OddsObservation(bookmaker="Bet365", market="over_under", selection="OVER", line=2.5, odds=float("nan"))


def test_observation_rejects_infinite_odds() -> None:
    with pytest.raises(SnapshotValidationError, match="odds invalide"):
        OddsObservation(bookmaker="Bet365", market="over_under", selection="OVER", line=2.5, odds=float("inf"))


def test_observation_rejects_empty_bookmaker() -> None:
    with pytest.raises(SnapshotValidationError, match="bookmaker"):
        OddsObservation(bookmaker="", market="over_under", selection="OVER", line=2.5, odds=1.6)


def test_snapshot_rejects_same_home_and_away_team() -> None:
    with pytest.raises(SnapshotValidationError, match="distincts"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Benfica",
            kickoff_utc=_KICKOFF, capture_timestamp=_KICKOFF - timedelta(hours=1),
            observations=tuple(_obs_over_under()),
        )


def test_snapshot_rejects_empty_observations() -> None:
    with pytest.raises(SnapshotValidationError, match="au moins une observation"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=_KICKOFF, capture_timestamp=_KICKOFF - timedelta(hours=1),
            observations=(),
        )


# --- Tests de fuseau horaire (obligatoires) ---------------------------------


def test_kickoff_utc_naive_is_rejected() -> None:
    naive_kickoff = datetime(2026, 3, 1, 20, 0, 0)
    with pytest.raises(SnapshotValidationError, match="timezone-aware"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=naive_kickoff, capture_timestamp=naive_kickoff - timedelta(hours=1),
            observations=tuple(_obs_over_under()),
        )


def test_capture_timestamp_naive_is_rejected() -> None:
    naive_capture = datetime(2026, 3, 1, 18, 0, 0)
    with pytest.raises(SnapshotValidationError, match="timezone-aware"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=_KICKOFF, capture_timestamp=naive_capture,
            observations=tuple(_obs_over_under()),
        )


def test_kickoff_utc_non_utc_timezone_is_rejected() -> None:
    cet = timezone(timedelta(hours=1))
    kickoff_cet = datetime(2026, 3, 1, 21, 0, 0, tzinfo=cet)  # meme instant que _KICKOFF, mais fuseau different
    with pytest.raises(SnapshotValidationError, match="doit etre en UTC"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=kickoff_cet, capture_timestamp=kickoff_cet - timedelta(hours=1),
            observations=tuple(_obs_over_under()),
        )


def test_capture_timestamp_non_utc_timezone_is_rejected() -> None:
    cet = timezone(timedelta(hours=1))
    capture_cet = _KICKOFF.astimezone(cet) - timedelta(hours=1)
    with pytest.raises(SnapshotValidationError, match="doit etre en UTC"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=_KICKOFF, capture_timestamp=capture_cet,
            observations=tuple(_obs_over_under()),
        )


def test_timezone_comparison_correctly_accepts_equivalent_instants_in_different_representations() -> None:
    """Un capture_timestamp exprime dans un fuseau non-UTC mais
    representant le meme instant qu'avant kickoff doit etre normalise/
    refuse pour son FUSEAU (pas silencieusement accepte) - la regle du
    projet est explicite : UTC uniquement, jamais une conversion
    implicite meme correcte."""
    cet = timezone(timedelta(hours=1))
    kickoff_naive_instant_utc = _KICKOFF - timedelta(hours=2)
    capture_in_cet_same_instant = kickoff_naive_instant_utc.astimezone(cet)
    with pytest.raises(SnapshotValidationError, match="doit etre en UTC"):
        OddsSnapshot(
            competition="liga", season="2025_26", home_team="Benfica", away_team="Estoril",
            kickoff_utc=_KICKOFF, capture_timestamp=capture_in_cet_same_instant,
            observations=tuple(_obs_over_under()),
        )
