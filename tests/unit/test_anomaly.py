from __future__ import annotations

import pytest

from sys_foot_quant.market_engine.anomaly import (
    CLOSE_TO_CONSENSUS,
    MARKED_GAP,
    NOT_INTERPRETABLE,
    NOTABLE_GAP,
    book_vs_consensus,
    classify_gap,
    model_vs_consensus,
)
from sys_foot_quant.market_engine.consensus import compute_consensus


def test_classify_gap_close() -> None:
    assert classify_gap(0.01) == CLOSE_TO_CONSENSUS
    assert classify_gap(-0.049) == CLOSE_TO_CONSENSUS


def test_classify_gap_notable() -> None:
    assert classify_gap(0.05) == NOTABLE_GAP
    assert classify_gap(-0.09) == NOTABLE_GAP


def test_classify_gap_marked() -> None:
    assert classify_gap(0.10) == MARKED_GAP
    assert classify_gap(-0.30) == MARKED_GAP


def test_book_vs_consensus_isolated_bookmaker_flagged_marked() -> None:
    consensus = compute_consensus({"B365": 0.50, "BW": 0.50, "PS": 0.65})
    out = book_vs_consensus("PS", 0.65, consensus)
    assert out["classification"] == MARKED_GAP
    assert out["direction"] == "au-dessus du consensus"


def test_book_vs_consensus_close_bookmaker_not_flagged() -> None:
    consensus = compute_consensus({"B365": 0.50, "BW": 0.51, "PS": 0.49})
    out = book_vs_consensus("B365", 0.50, consensus)
    assert out["classification"] == CLOSE_TO_CONSENSUS


def test_book_vs_consensus_single_bookmaker_not_interpretable() -> None:
    consensus = compute_consensus({"B365": 0.5})
    out = book_vs_consensus("B365", 0.5, consensus)
    assert out["classification"] == NOT_INTERPRETABLE
    assert out["gap"] == 0.0


def test_model_vs_consensus_never_labeled_value() -> None:
    consensus = compute_consensus({"B365": 0.50, "BW": 0.52})
    out = model_vs_consensus(0.60, consensus)
    assert out["classification"] in (CLOSE_TO_CONSENSUS, NOTABLE_GAP, MARKED_GAP)
    assert "value" not in str(out).lower()


def test_model_vs_consensus_gap_matches_manual() -> None:
    consensus = compute_consensus({"B365": 0.40, "BW": 0.40})
    out = model_vs_consensus(0.50, consensus)
    assert out["gap"] == pytest.approx(0.10)
