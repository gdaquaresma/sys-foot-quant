"""Verification de reproductibilite deterministe (et non bit-a-bit).

Deux fichiers Parquet produits par deux processus (versions de pyarrow,
plateformes) differentes peuvent legitimement differer octet pour octet
(compression, ordre des row groups, metadonnees) tout en representant
exactement les memes donnees. Ce module fournit donc une empreinte de
*contenu logique* : deux DataFrames identiques en valeur produisent la
meme empreinte, independamment de leur encodage physique. C'est cette
empreinte, pas un diff de fichiers, qui sert de preuve de
reproductibilite (voir docs/decisions/0004-reproductibilite-deterministe.md).
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def content_fingerprint(df: pd.DataFrame, key_columns: Sequence[str]) -> str:
    """Empreinte stable du contenu logique de ``df``, triee par ``key_columns``.

    Le tri prealable rend l'empreinte independante de l'ordre physique des
    lignes (qui n'est pas une garantie de Parquet/DuckDB).
    """
    ordered = df.sort_values(list(key_columns)).reset_index(drop=True)
    row_hashes = pd.util.hash_pandas_object(ordered, index=False)
    combined = int(row_hashes.sum()) & 0xFFFFFFFFFFFFFFFF
    return f"{combined:016x}"
