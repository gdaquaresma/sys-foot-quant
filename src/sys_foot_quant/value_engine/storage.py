"""Persistance des candidats de value bet (edge/EV/CLV).

Ce ne sont PAS des donnees de marche du Data Engine : ce sont nos propres
calculs, chacun horodate une fois pour toutes au moment ou il est produit
(pas de revision ulterieure) - il n'y a donc pas de semantique
``knowledge_time``/point-in-time a gerer ici, a la difference des tables
de faits de ``data_engine``. Le format Parquet est reutilise par
coherence avec le reste du projet, pas parce qu'il s'agit d'une table
point-in-time.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_value_log(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False)
    return path


def read_value_log(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(Path(path), engine="pyarrow")
