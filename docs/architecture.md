# Architecture technique - sys-foot-quant

Ce document reprend l'architecture validee avant le debut de l'implementation,
avec les deux corrections suivantes actees :

1. La reproductibilite exigee est **deterministe et verifiable**, pas
   bit-a-bit (voir `docs/decisions/0004-reproductibilite-deterministe.md`).
2. Le benchmark "marche" doit etre manie avec prudence : la cote de
   cloture ne peut servir de benchmark d'un modele pre-match que si elle
   etait reellement disponible au moment de la decision evaluee. Pour un
   modele pre-match, elle sert avant tout a mesurer le CLV, pas a simuler
   une decision qui aurait utilise une information non disponible a
   l'epoque (voir `docs/decisions/0003-prudence-benchmark-marche.md`).

## 1. Principe directeur

Chaque donnee porte deux temps :

- `event_time` : quand la chose s'est produite (coup d'envoi, but marque).
- `knowledge_time` : quand cette information est devenue disponible pour
  le systeme.

Le backtester ne doit jamais pouvoir joindre une donnee dont
`knowledge_time > decision_time`. C'est la garantie structurelle centrale
du projet, implementee dans un unique composant : le Repository
(`data_engine/storage/repository.py`).

## 2. Etat d'implementation par module

| Module | Etat | Etape prevue |
|---|---|---|
| `common` | Implemente | 1 |
| `data_engine` (schemas, synthetique, stockage PIT) | Implemente (etendu etape 2 : force d'equipe + derive simulees ; etape 3 : plancher realiste du marche synthetique) | 1 |
| `backtesting_engine` (boucle chronologique minimale + walk-forward synthetique + walk-forward donnees reelles) | Implemente (`real_data_walk_forward.py` ajoute etape 5 pour B3 - walk-forward isole sur DataFrames en memoire avec deux flux de connaissance point-in-time independants (buts/xG), n'est PAS un connecteur de donnees reelles general pour le reste du projet, specifique au test B3) | 1 (boucle) / 2 (walk-forward synthetique) / 5 (walk-forward donnees reelles) |
| `football_model` (Poisson simple, attaque/defense, A1 (decroissance calendaire + re-test fenetre glissante), A2, benchmarks naif/Elo, B2 bayesien sequentiel, B1 Dixon-Coles, forme recente/H2H (re-test A1), B3 xG, controles negatifs E1/E7) | Implemente (A1 REJETE - decroissance calendaire (etape 2) ET fenetre glissante football-realiste avec/sans memoire longue (etape 5, `recent_form.py`/`head_to_head.py`) toutes deux significativement dominees par poisson_simple sur synthetique ; H2H seul INDETERMINE (aucun signal) ; B2 VALIDE contre A1 sur synthetique ; B1 (Dixon-Coles) VALIDE contre poisson_simple sur le sous-ensemble bas-score - validation du MECANISME sur donnees SYNTHETIQUES uniquement, ne constitue PAS une preuve d'amelioration sur donnees reelles, a re-tester des la connexion d'une source reelle - voir rapport etape 5 ; B3 (xG, `xg_model.py`) INDETERMINE sur donnees REELLES Understat (3 championnats 2025/26, 1066 matchs) - signe coherent mais non significatif hors echantillon sur les trois, reserve documentee sur la stabilite temporelle du xG Understat (non verifiee, distincte d'une fuite de donnees) - voir docs/research_framework.md section B3) | 2 (base) / 5 (A1 re-test, B1, B2, B3, E1, E7) |
| `calibration_engine` (Brier, log loss, reliability, tests de significativite, Chi-Deux) | Implemente | 2 |
| `market_engine` (snapshot, retrait de marge proportionnel + Shin, comparaison) | Implemente | 2 (benchmark) / 3 (complet) |
| `value_engine` (edge, EV, CLV, selection - AUCUNE selection sur EV seule) | Implemente | 3 |
| `risk_engine` (bankroll, Flat Betting, Kelly informatif + quality gates, limites, metriques de risque, Monte Carlo) | Implemente (Flat Betting seul active en production - Kelly verrouille, voir `risk_engine/kelly.py`) | 4 |
| `live_betting_engine` | Non implemente | 6 (conditionnel) |

Detail des etapes : voir `docs/research_framework.md` (section H) pour le
protocole ayant guide l'etape 2, et les scripts `scripts/run_stage2_walk_forward.py`
/ `scripts/run_stage3_value_engine.py` pour les resultats empiriques (tous
sur donnees synthetiques - voir avertissements dans chaque script). Le
Risk Engine (etape 4) n'a pas de script de resultats empiriques dedie :
ses simulations Monte Carlo sont theoriques (comparaison de strategies de
mise sur un flux de paris hypothetique), pas une evaluation sur le
dataset synthetique des etapes 1-3 - voir rapport d'etape 4 (message de
livraison) pour le detail.

## 3. Ce qui est implemente a l'etape 1

- **Schemas de donnees** (`data_engine/schemas/entities.py`) : `Team`,
  `Match`, `MatchResult`, `OddsSnapshot`, valides par pydantic. Toute
  table de faits herite de `PointInTimeFact` et porte un
  `knowledge_time` obligatoire, timezone-aware (UTC). `Match` refuse une
  configuration ou `knowledge_time > kickoff_time`.
- **Generateur synthetique deterministe**
  (`data_engine/synthetic/generator.py`) : aucune source reelle
  configuree pour l'instant. Pour un `seed` donne, produit un dataset
  reproductible avec une structure temporelle realiste (fixtures connues
  bien avant le coup d'envoi, resultats connus apres, cotes publiees a
  plusieurs echeances avant le coup d'envoi).
- **Stockage** (`data_engine/storage/writer.py`) : ecriture Parquet,
  format canonique "au repos".
- **Repository point-in-time** (`data_engine/storage/repository.py`) :
  seul point d'acces autorise aux donnees pour tout module en aval.
  `get_as_of(entity, timestamp)` filtre strictement sur
  `knowledge_time <= timestamp`. Le nom de table est valide contre une
  liste blanche avant toute interpolation SQL ; le timestamp est toujours
  passe en parametre lie. Une methode `debug_get_full_table` existe
  explicitement pour les tests/diagnostics et ne doit jamais etre
  utilisee par un module de decision.
- **Backtester chronologique minimal**
  (`backtesting_engine/engine.py`) : itere une liste de
  `decision_times` strictement (non-decroissante), interroge le
  Repository a chaque instant, et delegue a un callback fourni par
  l'appelant. Aucune strategie n'est integree - le callback utilise dans
  les scripts est un stub de diagnostic explicitement documente comme
  tel.

## 4. Ce qui N'est PAS implemente (volontairement)

Aucun modele de prediction (Poisson, Elo, xG, Dixon-Coles), aucune
calibration, aucun retrait de marge/calcul d'EV, aucun Kelly/flat
betting, aucun live betting. Ces modules existent comme paquets Python
vides avec un docstring renvoyant a leur etape prevue, pour que
l'arborescence documentee soit visible sans que leur contenu preempte les
etapes suivantes.

## 5. Technologies utilisees a l'etape 1

- Python 3.11+, gestion de dependances via `uv`.
- DuckDB (moteur de requetage) + Parquet (stockage au repos).
- pydantic v2 (contrats de donnees).
- pandas / numpy (manipulation, generation synthetique).
- Typer (CLI des scripts).
- pytest + Hypothesis (tests, notamment property-based pour l'anti-look-ahead).

## 6. Prochaine etape (non commencee)

Etape 2 : modele Poisson simple + CalibrationEngine (Brier, log loss,
reliability diagrams) + benchmarks (naif, Elo, marche sans marge - avec
la prudence actee au point 1 ci-dessus).
