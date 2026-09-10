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

## MVP shadow mode : `predict_match.py`

Point d'entree de production (MVP, mode shadow - aucune execution reelle
de pari) pour lancer une decision pre-match sur un match reel, deja joue
ou futur. Voir `docs/final_engine_user_guide.md` pour ce que le moteur
produit et surtout ce qu'il **ne pretend pas** (aucun `BET` n'est
actuellement atteignable - `NO_BET` est la sortie normale et attendue).

```bash
uv sync --extra dev   # aucune dependance supplementaire (typer/pandas/scipy deja requis)

uv run python scripts/predict_match.py \
    --competition liga --season 2024_25 \
    --home-team "Real Madrid" --away-team Barcelona \
    --kickoff-utc 2025-05-11T19:00:00 \
    --market-odds-over-2-5 1.85 --market-odds-under-2-5 1.95
```

- `--competition` : `liga` | `ligue1` | `premier_league`.
- `--season` : `2024_25` | `2025_26` (corpus Understat deja collecte, `research/xg_feasibility/runs/`).
- `--home-team`/`--away-team` : nom Understat (ex. `Real Madrid`) ou nom Football-Data (ex. `Ath Bilbao`, traduit automatiquement).
- `--kickoff-utc` : coup d'envoi en UTC **naif** (sans fuseau), format `AAAA-MM-JJTHH:MM:SS`.
- `--market-odds-over-2-5`/`--market-odds-under-2-5` : cote d'ouverture Bet365 Over/Under 2.5 buts (cote decimale, ex. `1.85`) - les deux ensemble, ou aucune des deux (mode projection seule, sans comparaison au marche). Aucune recuperation automatique : Football-Data ne publie jamais de cote pre-match pour un match reellement futur.

Sortie : `NO_BET` (sortie normale et attendue du MVP - aucun seuil d'edge
minimal n'a ete valide par la campagne E1-E16) ou `BET`, toujours avec les
codes de raison explicites (`INSUFFICIENT_HISTORY`,
`AMBIGUOUS_COLLECTION_DAY`, `MARKET_DATA_UNAVAILABLE`,
`INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE`,
`DISCRIMINATION_NOT_DEMONSTRATED`, `EDGE_BELOW_THRESHOLD`) et le detail
des gates declenches (Niveau E). Le rapport affiche aussi, par modele, les
projections (`lambda`/`mu`), les probabilites calibrees E7/E8, le prix
juste, et - si une cote est fournie et exploitable - la comparaison au
marche (probabilite implicite, edge, EV).

## Shadow Mode V1

Protocole d'observation hors echantillon : chaque prediction pre-match est
**figee** au moment de son enregistrement, puis reglee avec le resultat
reel une fois le match joue. Aucune donnee posterieure au `decision_time`
n'est jamais reinjectee dans la prediction, et le moteur n'est jamais
reentraine/recalibre a partir des resultats observes - **ce sont des
decisions simulees, aucun pari reel n'est execute**.

```bash
# 1. Enregistrer une prediction pre-match (execute exactement predict_match.py,
#    puis journalise une copie immuable - relancer la meme commande ne cree
#    jamais de doublon).
uv run python scripts/predict_match.py \
    --competition liga --season 2025_26 \
    --home-team Barcelona --away-team "Atletico Madrid" \
    --kickoff-utc 2026-06-20T20:00:00 \
    --market-odds-over-2-5 1.80 --market-odds-under-2-5 2.00 \
    --record-shadow
# -> affiche le prediction_id a la fin du rapport.

# 2. Une fois le match joue, regler l'observation avec le score reel
#    (n'ajoute que le resultat, ne modifie jamais la prediction d'origine).
uv run python scripts/settle_shadow.py \
    --prediction-id <prediction_id> --home-goals 2 --away-goals 1

# 3. Evaluer les observations reglees (Brier/log loss par modele, et
#    uniquement si le systeme a produit des BET : win rate/ROI theoriques).
uv run python scripts/evaluate_shadow.py
```

Journal : `research/shadow_mode/predictions.jsonl` (une ligne
``prediction`` par observation, une ligne ``settlement`` ajoutee apres
coup - jamais une reecriture). `--shadow-journal-path`/`--journal-path`
permettent d'utiliser un autre fichier (utile pour des essais).

`BET`/`NO_BET` : `NO_BET` est la sortie normale et attendue (voir section
precedente) - un grand nombre de `NO_BET` observes est une observation
valide du comportement actuel du systeme, pas un echec du protocole.
Tant qu'aucune observation `BET` n'existe, `evaluate_shadow.py` l'indique
explicitement plutot que d'inventer une strategie de mise a evaluer.

## Documentation

- `docs/architecture.md` : architecture technique complete et plan de developpement.
- `docs/decisions/` : decisions techniques argumentees (ADR).
- `docs/data_dictionary.md` : schema des tables de faits.
- `docs/final_engine_specification.md` / `docs/final_engine_user_guide.md` : specification et guide du moteur final utilise par `predict_match.py`.
