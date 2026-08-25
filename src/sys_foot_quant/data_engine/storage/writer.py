"""Ecriture des tables de faits en Parquet (append-only par construction).

Le format canonique de stockage "au repos" du projet est Parquet ;
DuckDB est utilise comme moteur de requetage par-dessus, pas comme
systeme de stockage proprietaire. Ce choix est documente dans
docs/decisions/0002-stockage-duckdb-parquet.md.
"""

from __future__ import annotations

from pathlib import Path

from sys_foot_quant.data_engine.synthetic.generator import SyntheticDataset

_FILENAMES = {
    "teams": "teams.parquet",
    "matches": "matches.parquet",
    "match_results": "match_results.parquet",
    "odds_snapshots": "odds_snapshots.parquet",
}


def write_dataset(dataset: SyntheticDataset, out_dir: str | Path) -> dict[str, Path]:
    """Ecrit chaque table du dataset en Parquet dans ``out_dir``.

    Retourne le mapping nom logique -> chemin de fichier ecrit.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for name, filename in _FILENAMES.items():
        df = getattr(dataset, name)
        path = out_dir / filename
        df.to_parquet(path, engine="pyarrow", index=False)
        written[name] = path
    return written
