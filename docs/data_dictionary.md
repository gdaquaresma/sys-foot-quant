# Dictionnaire de donnees - Etape 1

Toutes les tables ci-dessous, sauf `teams`, sont soumises au filtre
point-in-time du Repository (`knowledge_time <= as_of`). `teams` est une
table de dimension non filtree a ce stade (simplification assumee, voir
`data_engine/storage/repository.py`).

## `teams`

| Colonne | Type | Description |
|---|---|---|
| team_id | int | Identifiant de l'equipe |
| name | str | Nom (synthetique a ce stade) |

## `matches`

| Colonne | Type | Description |
|---|---|---|
| match_id | int | Identifiant du match |
| competition_id | str | Competition (valeur fixe en synthetique) |
| season | str | Saison (valeur fixe en synthetique) |
| home_team_id | int | Equipe recevante |
| away_team_id | int | Equipe visiteuse |
| kickoff_time | datetime (UTC) | Coup d'envoi (event_time) |
| knowledge_time | datetime (UTC) | Instant de publication du calendrier ; doit toujours etre <= kickoff_time |

## `match_results`

| Colonne | Type | Description |
|---|---|---|
| match_id | int | Reference au match |
| home_goals | int (>=0) | Buts de l'equipe recevante |
| away_goals | int (>=0) | Buts de l'equipe visiteuse |
| knowledge_time | datetime (UTC) | Instant de confirmation du resultat (strictement apres kickoff_time dans le generateur) |

## `odds_snapshots`

Table append-only : plusieurs lignes par match (une par bookmaker x
selection x instant d'observation).

| Colonne | Type | Description |
|---|---|---|
| match_id | int | Reference au match |
| bookmaker | str | Bookmaker source (synthetique) |
| market_type | str | Type de marche (`"1x2"` a ce stade) |
| selection | str | `"home"` / `"draw"` / `"away"` |
| odds_value | float (>1.0) | Cote decimale |
| knowledge_time | datetime (UTC) | Instant d'observation de la cote (= snapshot_time) |

## Notes

- Aucune source reelle n'est configuree a l'etape 1 : ces tables sont
  peuplees exclusivement par `data_engine/synthetic/generator.py`, avec
  un seed deterministe.
- Le schema evoluera aux etapes suivantes (features de modele, ratings
  Elo/Poisson versionnes en SCD type 2, table `bets`, `bankroll_history`)
  sans remettre en cause le principe `knowledge_time` sur toute nouvelle
  table de faits.
