"""Tests de reproductibilite.

Objectif : garantir une reproductibilite deterministe et verifiable
(memes valeurs, meme comportement du backtester), PAS une identite
bit-a-bit des fichiers Parquet produits (qui depend de la version de
pyarrow/de la plateforme et n'est pas une garantie que ce projet prend).
Voir docs/decisions/0004-reproductibilite-deterministe.md.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

from sys_foot_quant.backtesting_engine.engine import (
    ChronologicalBacktestEngine,
    DecisionSnapshot,
)
from sys_foot_quant.common.config import SyntheticDataConfig
from sys_foot_quant.common.reproducibility import content_fingerprint
from sys_foot_quant.data_engine.storage.repository import DuckDBRepository
from sys_foot_quant.data_engine.storage.writer import write_dataset
from sys_foot_quant.data_engine.synthetic.generator import generate_synthetic_dataset

_KEY_COLUMNS = {
    "teams": ["team_id"],
    "matches": ["match_id"],
    "match_results": ["match_id"],
    "odds_snapshots": ["match_id", "bookmaker", "market_type", "selection", "knowledge_time"],
}


def _diagnostic_stub(snapshot: DecisionSnapshot) -> dict[str, int]:
    return {entity: len(df) for entity, df in snapshot.visible.items()}


def test_same_seed_produces_identical_logical_content(small_config: SyntheticDataConfig) -> None:
    """Deux generations independantes, meme seed -> meme contenu logique.

    On ne compare pas les octets des fichiers ecrits (non garanti
    identique selon l'environnement), mais le contenu des DataFrames,
    ligne a ligne, une fois tries par cle primaire.
    """
    dataset_a = generate_synthetic_dataset(small_config)
    dataset_b = generate_synthetic_dataset(small_config.model_copy())

    for table_name, keys in _KEY_COLUMNS.items():
        df_a = getattr(dataset_a, table_name).sort_values(keys).reset_index(drop=True)
        df_b = getattr(dataset_b, table_name).sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(df_a, df_b)
        assert content_fingerprint(df_a, keys) == content_fingerprint(df_b, keys)


def test_different_seed_produces_different_content(small_config: SyntheticDataConfig) -> None:
    """Garde-fou : un generateur constant passerait le test precedent a tort."""
    other_config = small_config.model_copy(update={"seed": small_config.seed + 1})
    dataset_a = generate_synthetic_dataset(small_config)
    dataset_b = generate_synthetic_dataset(other_config)

    fp_a = content_fingerprint(dataset_a.match_results, ["match_id"])
    fp_b = content_fingerprint(dataset_b.match_results, ["match_id"])
    assert fp_a != fp_b


def test_backtest_trace_is_deterministic_across_independent_runs(
    tmp_path: Path, small_config: SyntheticDataConfig
) -> None:
    """Le meme seed et la meme configuration doivent produire la meme trace
    de backtest (memes comptes de lignes visibles a chaque instant de
    decision), meme lorsque le dataset est regenere et re-ecrit sur
    disque independamment pour chaque run.
    """

    def run_once(out_dir: Path) -> list[dict[str, int]]:
        dataset = generate_synthetic_dataset(small_config.model_copy())
        write_dataset(dataset, out_dir)
        with DuckDBRepository(out_dir) as repo:
            matches = repo.debug_get_full_table("matches").sort_values("kickoff_time")
            decision_times = [kt - timedelta(hours=1) for kt in matches["kickoff_time"]]
            engine = ChronologicalBacktestEngine(
                repository=repo, entities=("matches", "match_results", "odds_snapshots")
            )
            return engine.run(decision_times, on_decision=_diagnostic_stub)

    trace_a = run_once(tmp_path / "run_a")
    trace_b = run_once(tmp_path / "run_b")

    assert trace_a == trace_b
