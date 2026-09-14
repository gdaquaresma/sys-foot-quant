from __future__ import annotations

import json
from pathlib import Path

import pytest

from sys_foot_quant.data_engine.market_odds.current_season_contract import (
    CurrentSeasonContractError,
)
from sys_foot_quant.data_engine.market_odds.current_season_merge import (
    CurrentSeasonSourceInconsistencyError,
    compute_diff,
    merge_current_season,
    update_current_season_file,
    write_current_season_atomic,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_2026_FILE = REPO_ROOT / "research/xg_feasibility/runs/ligue1_2026_datesData.json"


def _match(
    match_id: str,
    dt: str,
    home_id: str = "279",
    home_title: str = "Brest",
    away_id: str = "296",
    away_title: str = "Marseille",
    home_goals: str = "1",
    away_goals: str = "2",
    home_xg: str = "1.32",
    away_xg: str = "1.87",
) -> dict:
    return {
        "id": match_id,
        "isResult": True,
        "datetime": dt,
        "h": {"id": home_id, "title": home_title},
        "a": {"id": away_id, "title": away_title},
        "goals": {"h": home_goals, "a": away_goals},
        "xG": {"h": home_xg, "a": away_xg},
    }


# --- A/B/C : nouveau match, source identique, idempotence ------------------


def test_a_new_match_is_merged_in() -> None:
    local = [_match("1", "2026-08-15 19:45:00")]
    source = [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")]
    merged, diff = merge_current_season(local, source)
    assert [m["id"] for m in merged] == ["1", "2"]
    assert len(diff.new_matches) == 1
    assert diff.new_matches[0]["id"] == "2"
    assert len(diff.unchanged_matches) == 1
    assert not diff.modified_matches
    assert not diff.missing_from_source


def test_b_identical_source_produces_no_change() -> None:
    local = [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")]
    source = [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")]
    merged, diff = merge_current_season(local, source)
    assert merged == local
    assert len(diff.unchanged_matches) == 2
    assert not diff.new_matches
    assert not diff.has_inconsistency


def test_c_idempotence_applying_same_source_twice_gives_identical_file(tmp_path: Path) -> None:
    path = tmp_path / "ligue1_2026_datesData.json"
    source = [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")]
    update_current_season_file(path, source)
    content_after_first = path.read_bytes()
    update_current_season_file(path, source)
    content_after_second = path.read_bytes()
    assert content_after_first == content_after_second


# --- D/E/F : modification detectee -> rejet ---------------------------------


def test_d_score_modification_is_rejected() -> None:
    local = [_match("1", "2026-08-15 19:45:00", home_goals="1", away_goals="2")]
    source = [_match("1", "2026-08-15 19:45:00", home_goals="3", away_goals="2")]
    with pytest.raises(CurrentSeasonSourceInconsistencyError, match="1"):
        merge_current_season(local, source)


def test_e_xg_modification_is_rejected() -> None:
    local = [_match("1", "2026-08-15 19:45:00", home_xg="1.32")]
    source = [_match("1", "2026-08-15 19:45:00", home_xg="2.50")]
    with pytest.raises(CurrentSeasonSourceInconsistencyError):
        merge_current_season(local, source)


def test_f_team_or_date_modification_is_rejected() -> None:
    local = [_match("1", "2026-08-15 19:45:00", home_title="Brest")]
    source = [_match("1", "2026-08-15 19:45:00", home_title="Rennes")]
    with pytest.raises(CurrentSeasonSourceInconsistencyError):
        merge_current_season(local, source)

    local2 = [_match("1", "2026-08-15 19:45:00")]
    source2 = [_match("1", "2026-08-16 19:45:00")]
    with pytest.raises(CurrentSeasonSourceInconsistencyError):
        merge_current_season(local2, source2)


# --- G : match disparu -------------------------------------------------------


def test_g_match_missing_from_source_is_rejected() -> None:
    local = [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")]
    source = [_match("1", "2026-08-15 19:45:00")]  # "2" a disparu
    with pytest.raises(CurrentSeasonSourceInconsistencyError, match="2"):
        merge_current_season(local, source)


# --- H/I/J : source elle-meme invalide (delegue au contrat) -----------------


def test_h_source_with_internal_duplicate_is_rejected() -> None:
    source = [_match("1", "2026-08-15 19:45:00"), _match("1", "2026-08-22 19:45:00")]
    with pytest.raises(CurrentSeasonContractError):
        merge_current_season([], source)


def test_i_source_with_unplayed_match_is_rejected() -> None:
    bad = _match("1", "2026-08-15 19:45:00")
    bad["isResult"] = False
    with pytest.raises(CurrentSeasonContractError):
        merge_current_season([], [bad])


def test_j_source_with_missing_xg_is_rejected() -> None:
    bad = _match("1", "2026-08-15 19:45:00")
    del bad["xG"]
    with pytest.raises(CurrentSeasonContractError):
        merge_current_season([], [bad])


# --- K : JSON invalide au niveau fichier local -------------------------------


def test_k_corrupted_local_file_is_rejected_and_left_untouched(tmp_path: Path) -> None:
    path = tmp_path / "ligue1_2026_datesData.json"
    path.write_text("{not valid json", encoding="utf-8")
    corrupted_content = path.read_bytes()
    with pytest.raises(CurrentSeasonContractError, match="corrompu"):
        update_current_season_file(path, [_match("1", "2026-08-15 19:45:00")])
    assert path.read_bytes() == corrupted_content


# --- L : ecriture atomique ----------------------------------------------------


def test_l_atomic_write_leaves_no_temp_file_after_success(tmp_path: Path) -> None:
    path = tmp_path / "ligue1_2026_datesData.json"
    write_current_season_atomic(path, [_match("1", "2026-08-15 19:45:00")])
    assert path.exists()
    remaining_tmp = list(tmp_path.glob(".*.tmp"))
    assert remaining_tmp == []


def test_l_atomic_write_failure_leaves_original_file_and_no_partial_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ligue1_2026_datesData.json"
    original_matches = [_match("1", "2026-08-15 19:45:00")]
    write_current_season_atomic(path, original_matches)
    original_content = path.read_bytes()

    import sys_foot_quant.data_engine.market_odds.current_season_merge as merge_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated crash mid-write")

    monkeypatch.setattr(merge_module.json, "dump", _boom)
    with pytest.raises(RuntimeError, match="simulated crash"):
        write_current_season_atomic(path, [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")])

    assert path.read_bytes() == original_content
    assert list(tmp_path.glob(".*.tmp")) == []


# --- M : fichier canonique inchange apres chaque echec -----------------------


def test_m_file_unchanged_after_inconsistency_error(tmp_path: Path) -> None:
    path = tmp_path / "ligue1_2026_datesData.json"
    local = [_match("1", "2026-08-15 19:45:00"), _match("2", "2026-08-22 19:45:00")]
    write_current_season_atomic(path, local)
    original_content = path.read_bytes()

    bad_source = [_match("1", "2026-08-15 19:45:00", home_goals="9")]  # "2" disparu + "1" modifie
    with pytest.raises(CurrentSeasonSourceInconsistencyError):
        update_current_season_file(path, bad_source)

    assert path.read_bytes() == original_content


def test_dry_run_never_writes(tmp_path: Path) -> None:
    path = tmp_path / "ligue1_2026_datesData.json"
    source = [_match("1", "2026-08-15 19:45:00")]
    diff = update_current_season_file(path, source, dry_run=True)
    assert not path.exists()
    assert len(diff.new_matches) == 1


# --- N : tri chronologique ----------------------------------------------------


def test_n_merged_result_is_sorted_chronologically() -> None:
    local = [_match("2", "2026-08-22 19:45:00")]
    source = [_match("2", "2026-08-22 19:45:00"), _match("1", "2026-08-15 19:45:00"), _match("3", "2026-08-29 19:45:00")]
    merged, _diff = merge_current_season(local, source)
    dates = [m["datetime"] for m in merged]
    assert dates == sorted(dates)
    assert [m["id"] for m in merged] == ["1", "2", "3"]


# --- O : aucun match existant silencieusement modifie ------------------------


def test_o_existing_match_content_is_never_altered_by_a_successful_merge() -> None:
    local = [_match("1", "2026-08-15 19:45:00", home_goals="1", away_goals="2")]
    source = [
        _match("1", "2026-08-15 19:45:00", home_goals="1", away_goals="2"),
        _match("2", "2026-08-22 19:45:00"),
    ]
    merged, _diff = merge_current_season(local, source)
    kept = next(m for m in merged if m["id"] == "1")
    assert kept is local[0]  # meme objet, jamais reconstruit/modifie


# --- P : le fichier reel 2026/27 respecte le chemin de merge -----------------


def test_p_real_2026_file_bootstraps_cleanly_through_merge() -> None:
    with open(REAL_2026_FILE, encoding="utf-8") as f:
        real_matches = json.load(f)
    merged, diff = merge_current_season([], real_matches)
    assert len(merged) == len(real_matches) == 35
    assert len(diff.new_matches) == 35
    assert not diff.has_inconsistency


def test_p_real_2026_file_reapplied_against_itself_is_fully_unchanged() -> None:
    with open(REAL_2026_FILE, encoding="utf-8") as f:
        real_matches = json.load(f)
    merged, diff = merge_current_season(real_matches, real_matches)
    assert len(diff.unchanged_matches) == 35
    assert not diff.new_matches
    assert not diff.has_inconsistency
    assert [m["id"] for m in merged] == [m["id"] for m in sorted(real_matches, key=lambda m: m["datetime"])]


# --- compute_diff en isolation (dry-run explicite) ---------------------------


def test_compute_diff_never_writes_and_is_pure() -> None:
    local = [_match("1", "2026-08-15 19:45:00")]
    source = [_match("1", "2026-08-15 19:45:00", home_goals="9")]
    diff = compute_diff(local, source)
    assert len(diff.modified_matches) == 1
    assert diff.has_inconsistency
    # local inchange en memoire (fonction pure)
    assert local[0]["goals"]["h"] == "1"
