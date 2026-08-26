from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from research.xg_feasibility.storage import load_extraction, save_extraction
from research.xg_feasibility.understat_source import MatchXGRecord

_T0 = datetime(2024, 8, 1, 15, 0, tzinfo=timezone.utc)
_COLLECTED_AT = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def _sample_records() -> list[MatchXGRecord]:
    return [
        MatchXGRecord(
            match_id="1",
            league="EPL",
            season="2024",
            kickoff_utc=_T0,
            home_team="Arsenal",
            away_team="Chelsea",
            home_goals=2,
            away_goals=1,
            home_xg=1.83,
            away_xg=0.92,
        )
    ]


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    out_path = tmp_path / "extraction.json"
    save_extraction(
        _sample_records(), out_path, league="EPL", season="2024", collected_at=_COLLECTED_AT
    )

    loaded = load_extraction(out_path)

    assert loaded.collected_at == _COLLECTED_AT
    assert loaded.league == "EPL"
    assert loaded.season == "2024"
    assert loaded.records == _sample_records()


def test_save_defaults_collected_at_to_now(tmp_path: Path) -> None:
    out_path = tmp_path / "extraction.json"
    before = datetime.now(timezone.utc)
    save_extraction(_sample_records(), out_path, league="EPL", season="2024")
    after = datetime.now(timezone.utc)

    loaded = load_extraction(out_path)
    assert before <= loaded.collected_at <= after


def test_load_rejects_unknown_schema_version(tmp_path: Path) -> None:
    out_path = tmp_path / "extraction.json"
    save_extraction(
        _sample_records(), out_path, league="EPL", season="2024", collected_at=_COLLECTED_AT
    )
    out_path.write_text(out_path.read_text().replace('"schema_version": 1', '"schema_version": 99'))

    try:
        load_extraction(out_path)
        assert False, "devrait lever ValueError"
    except ValueError:
        pass
