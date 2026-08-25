"""Repository point-in-time : l'unique porte d'acces aux donnees.

C'est le composant le plus important de l'etape 1. Toute la garantie
anti-look-ahead du systeme repose sur une regle unique, appliquee ici et
nulle part ailleurs :

    une ligne d'une table de faits n'est visible a l'instant T que si
    ``knowledge_time <= T``.

Aucun autre module ne doit lire les fichiers Parquet directement : passer
par ce Repository est ce qui rend la garantie verifiable (on peut tester
*ce module* de facon exhaustive, plutot que d'esperer que chaque
consommateur applique le filtre correctement).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, get_args

import duckdb
import pandas as pd

from sys_foot_quant.common.time_utils import to_utc

PointInTimeEntity = Literal["matches", "match_results", "odds_snapshots"]
_PIT_ENTITIES: frozenset[str] = frozenset(get_args(PointInTimeEntity))

_ALL_TABLES = {*_PIT_ENTITIES, "teams"}


class UnknownEntityError(ValueError):
    pass


class DuckDBRepository:
    """Lit des tables Parquet via DuckDB en appliquant un filtre point-in-time.

    Le nom de table (``entity``) n'est jamais construit a partir d'une
    entree utilisateur libre : il est valide contre une liste blanche
    fixee (``PointInTimeEntity``) avant toute interpolation dans une
    requete SQL. La valeur de ``timestamp``, elle, est toujours passee en
    parametre lie (``?``), jamais interpolee.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self._conn = duckdb.connect(database=":memory:")
        self._register_views()

    def _register_views(self) -> None:
        for table in _ALL_TABLES:
            path = self.data_dir / f"{table}.parquet"
            if not path.exists():
                raise FileNotFoundError(
                    f"Table attendue introuvable : {path}. "
                    "Generez d'abord le dataset (voir scripts/generate_synthetic_data.py)."
                )
            self._conn.execute(
                f"CREATE OR REPLACE VIEW {table} AS "
                f"SELECT * FROM read_parquet('{path.as_posix()}')"
            )

    def get_teams(self) -> pd.DataFrame:
        """Table de dimension : non soumise au filtre point-in-time.

        Simplification assumee pour l'etape 1 : on suppose la liste des
        equipes stable et connue d'emblee. Un traitement PIT des
        changements d'equipe (renommage, promotion/relegation) est hors
        perimetre de cette etape et devra etre traite specifiquement si
        besoin.
        """
        return self._conn.execute("SELECT * FROM teams").fetch_df()

    def get_as_of(self, entity: PointInTimeEntity, timestamp: datetime) -> pd.DataFrame:
        """Retourne les lignes de ``entity`` connues au plus tard a ``timestamp``.

        Invariant garanti par construction : pour toute ligne du
        DataFrame retourne, ``knowledge_time <= timestamp``.
        """
        if entity not in _PIT_ENTITIES:
            raise UnknownEntityError(
                f"Entite point-in-time inconnue : {entity!r}. "
                f"Entites valides : {sorted(_PIT_ENTITIES)}."
            )
        ts = to_utc(timestamp)
        query = f"SELECT * FROM {entity} WHERE knowledge_time <= ? ORDER BY knowledge_time"
        return self._conn.execute(query, [ts]).fetch_df()

    def debug_get_full_table(self, entity: PointInTimeEntity) -> pd.DataFrame:
        """Retourne la table complete, SANS filtre point-in-time.

        Reserve aux tests et au diagnostic (ex : comparer ce qu'un
        `get_as_of` aurait du exclure). Ne jamais appeler cette methode
        depuis un module de decision (modele, backtester, etc.).
        """
        if entity not in _PIT_ENTITIES:
            raise UnknownEntityError(f"Entite point-in-time inconnue : {entity!r}.")
        return self._conn.execute(f"SELECT * FROM {entity}").fetch_df()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DuckDBRepository":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
