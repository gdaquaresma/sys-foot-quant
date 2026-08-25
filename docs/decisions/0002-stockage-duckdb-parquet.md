# ADR 0002 - Stockage : Parquet + DuckDB

## Statut
Accepte.

## Contexte
Le projet a besoin d'un stockage analytique simple a operer en solo/petite
equipe, capable de gerer des filtres temporels stricts sur des historiques
de plusieurs saisons sans l'operationnel d'un serveur de base de donnees.

## Decision
- **Parquet** est le format canonique de stockage "au repos" pour les
  tables de faits (`matches`, `match_results`, `odds_snapshots`, ...).
  Format colonnaire, portable, versionnable par snapshot immuable.
- **DuckDB** est le moteur de requetage utilise par le Repository pour
  interroger ces fichiers Parquet (via `read_parquet`), pas un systeme de
  stockage proprietaire distinct - les fichiers Parquet restent la source
  de verite.

## Alternatives ecartees (pour l'instant)
- PostgreSQL/TimescaleDB : justifie seulement si le volume ou les besoins
  de concurrence d'ecriture le requierent. Migration possible plus tard
  sans changer les interfaces du Repository.
- SQLite : moins adapte aux requetes analytiques (agregations sur
  historique complet) que DuckDB.

## Consequences
- Aucune garantie d'identite bit-a-bit des fichiers Parquet entre
  environnements (versions de pyarrow, plateforme) - voir ADR 0004. La
  verification de reproductibilite se fait sur le contenu logique, pas
  sur les octets du fichier.
- Toute ecriture est traitee comme un snapshot immuable : on ne
  re-ecrit jamais un fichier historique en place une fois qu'il a servi a
  un backtest publie.
