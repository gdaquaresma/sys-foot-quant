from __future__ import annotations

import pytest

from sys_foot_quant.market_engine.consensus import bookmaker_rank, compute_consensus


def test_compute_consensus_basic_stats() -> None:
    out = compute_consensus({"B365": 0.50, "BW": 0.52, "PS": 0.48})
    assert out["n_bookmakers"] == 3
    assert out["mean"] == pytest.approx(0.50)
    assert out["median"] == pytest.approx(0.50)
    assert out["min"] == pytest.approx(0.48)
    assert out["max"] == pytest.approx(0.52)
    assert out["std"] > 0
    assert out["by_bookmaker"] == {"B365": 0.50, "BW": 0.52, "PS": 0.48}


def test_compute_consensus_single_bookmaker_nan_std() -> None:
    out = compute_consensus({"B365": 0.5})
    assert out["n_bookmakers"] == 1
    assert out["mean"] == pytest.approx(0.5)
    assert out["std"] != out["std"]  # NaN


def test_compute_consensus_empty_raises() -> None:
    with pytest.raises(ValueError):
        compute_consensus({})


def test_compute_consensus_never_reweights_bookmakers() -> None:
    # deux bookmakers identiques, un different - la moyenne simple doit
    # rester influencee egalement par chaque entree (pas de poids cache)
    out = compute_consensus({"A": 0.4, "B": 0.4, "C": 0.6})
    assert out["mean"] == pytest.approx((0.4 + 0.4 + 0.6) / 3)


def test_bookmaker_rank_best_price_is_rank_one() -> None:
    odds = {"B365": 1.90, "BW": 2.00, "PS": 1.85}
    out = bookmaker_rank("BW", odds)
    assert out["rank"] == 1
    assert out["n_bookmakers"] == 3


def test_bookmaker_rank_worst_price_is_last_rank() -> None:
    odds = {"B365": 1.90, "BW": 2.00, "PS": 1.85}
    out = bookmaker_rank("PS", odds)
    assert out["rank"] == 3


def test_bookmaker_rank_missing_bookmaker_raises() -> None:
    with pytest.raises(ValueError):
        bookmaker_rank("XYZ", {"B365": 1.9})
