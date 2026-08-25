# sys-foot-quant

Laboratoire quantitatif falsifiable pour l'analyse et la selection de paris football.

Le but n'est pas de predire des scores : c'est d'estimer des probabilites
calibrees et de detecter, lorsqu'ils existent reellement, des ecarts avec
le prix du marche - avec une gestion rigoureuse du risque et une
discipline stricte contre le look-ahead bias, le data snooping et
l'overfitting.

## Etat actuel : Etape 1 (infrastructure uniquement)

Seule l'infrastructure de donnees point-in-time et le backtester
chronologique minimal sont implementes. **Aucun modele de prediction,
aucune calibration, aucun moteur de marche/valeur/risque n'existe
encore** - voir `docs/architecture.md` pour le plan complet et
`src/sys_foot_quant/*/​__init__.py` pour l'etat de chaque module.

## Quickstart

```bash
make install        # uv sync --extra dev
make test            # pytest (unit + integration + leakage)
make generate-data    # genere le dataset synthetique (data/raw/*.parquet)
make backtest         # execute le backtester chronologique minimal
```

Sans `make`, equivalent avec `uv` directement :

```bash
uv sync --extra dev
uv run pytest -v
uv run python scripts/generate_synthetic_data.py --config configs/backtest_stage1.yaml
uv run python scripts/run_backtest.py --config configs/backtest_stage1.yaml
```

## Documentation

- `docs/architecture.md` : architecture technique complete et plan de developpement.
- `docs/decisions/` : decisions techniques argumentees (ADR).
- `docs/data_dictionary.md` : schema des tables de faits.
