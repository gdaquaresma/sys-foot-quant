# Contrat de donnees "saison courante" (ex. 2026/27)

Ce document definit le contrat minimal qu'un fichier de saison courante
doit respecter pour etre charge par
`data_engine/market_odds/multi_season_dataset.build_real_match_records_multi_season`
et compare via `data_engine/market_odds/season_sensitivity.compute_season_sensitivity`.
Aucun code de ce document n'a ete execute sur une vraie donnee 2026/27 -
ce fichier n'existe pas encore dans le depot (voir section 5).

## 1. Format

Identique, champ pour champ, au format `datesData` deja utilise par
`research/xg_feasibility/runs/ligue1_2024_datesData.json`/
`ligue1_2025_datesData.json` : une liste JSON d'objets, un objet par
match, consommable directement par
`backtesting_engine.real_data_walk_forward.build_real_match_records`
(INCHANGE) :

```json
[
  {
    "id": "27381",
    "isResult": true,
    "datetime": "2026-08-15 19:45:00",
    "h": {"id": "279", "title": "Brest"},
    "a": {"id": "296", "title": "Marseille"},
    "goals": {"h": "1", "a": "2"},
    "xG": {"h": "1.32", "a": "1.87"}
  }
]
```

## 2. Regle specifique a une saison EN COURS (absente du schema Understat brut)

Un fichier de saison **complete et close** (comme les fichiers 2024/25 et
2025/26 deja presents) peut legitimement contenir des entrees
`isResult: false` (matchs pas encore joues au moment de la capture) -
`build_real_match_records` les ignore deja silencieusement, ce qui est
correct pour ce cas.

Un fichier de **saison courante** ne doit en revanche contenir QUE des
matchs deja joues : la simple presence d'une entree `isResult: false`
dedans indiquerait un export du calendrier complet de la saison plutot
que de son etat reellement joue a la date de collecte - un risque de
confusion, jamais une fuite en soi (le point-in-time reste garanti en
aval par `kickoff_utc`), mais un signal que le fichier ne respecte pas
le contrat attendu ici. C'est pourquoi
`current_season_contract.validate_current_season_understat_raw` refuse
explicitement toute entree `isResult != true` dans ce fichier precis.

## 3. Champs obligatoires, par match

| Champ | Type | Contrainte |
|---|---|---|
| `id` | string/int | unique dans le fichier, unique entre TOUTES les sources chargees ensemble (verifie par `multi_season_dataset`) |
| `isResult` | bool | doit etre `true` (section 2) |
| `datetime` | string `"YYYY-MM-DD HH:MM:SS"` | heure de coup d'envoi, meme convention que les fichiers existants (naif, interprete comme UTC par `build_real_match_records`, INCHANGE) |
| `h.id`, `h.title` | string | identifiant et nom Understat de l'equipe a domicile |
| `a.id`, `a.title` | string | identifiant et nom Understat de l'equipe a l'exterieur |
| `goals.h`, `goals.a` | string/int | buts marques, match termine |
| `xG.h`, `xG.a` | string/float | **obligatoire** - `RealMatchRecord.home_xg`/`away_xg` n'ont pas de valeur par defaut ; un match sans xG ne peut pas etre charge sans modifier le schema, ce qui reviendrait a fabriquer une donnee (interdit) |

## 4. Ce que ce contrat ne couvre PAS

- Aucune garantie que les identifiants d'equipe (`h.id`/`a.id`) sont
  coherents avec ceux des fichiers 2024/25/2025/26 au-dela de ce que
  `build_understat_team_id_by_name`/`resolve_team_id` verifient deja a
  l'usage (memes noms Understat "Brest"/"Paris SG" attendus).
- Aucune tolerance de reprise partielle : un match dont le score serait
  connu mais pas le xG (ex. source degradee) est explicitement rejete
  par `validate_current_season_understat_raw`, jamais charge avec un xG
  substitue.
- Aucune fraicheur minimale : le contrat ne dit rien sur QUAND le
  fichier a ete genere - c'est `kickoff_utc < decision_time`, applique
  en aval par `future_match_dataset`/`calibration_dataset` (INCHANGES),
  qui garantit qu'aucun match trop recent n'est utilise a tort.

## 5. Etat actuel

Aucun fichier respectant ce contrat n'existe dans ce depot pour la
Ligue 1 2026/27 (ni pour aucune autre competition/saison 2026/27). La
seule source jamais utilisee par ce projet pour produire un fichier de
ce format est Understat (`research/xg_feasibility/understat_source.py`),
inaccessible depuis cet environnement d'execution (voir l'audit
precedent). Tant que ce fichier n'existe pas, `compute_season_sensitivity`
ne doit etre execute qu'avec `current_records == baseline_records`
(CURRENT degenere en BASELINE, delta nul par construction) ou pas execute
du tout sur Brest-PSG - jamais avec une donnee substituee ou inventee.
