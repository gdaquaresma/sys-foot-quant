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
| `data_engine` (schemas, synthetique, stockage PIT, `market_odds/` phase economique) | Implemente (etendu etape 2 : force d'equipe + derive simulees ; etape 3 : plancher realiste du marche synthetique ; **phase economique : `market_odds/` ajoute cotes REELLES Football-Data.co.uk** - 3 championnats x 2 saisons 2024/25+2025/26, marche 1X2, bookmaker Bet365 uniquement, 2123/2132 matchs apparies (99.58%) au corpus Understat via mapping d'equipes deterministe, AUCUN timestamp individuel a la source - regle point-in-time conservatrice documentee (jamais verifiee), matchs lundi/mardi/vendredi explicitement exclus - voir docs/decisions/0006-football-data-point-in-time.md ; **`economic_dataset.py` (Experience 1)** assemble ces cotes avec les probabilites point-in-time de `poisson_simple` (`real_data_walk_forward.py`, inchange) - 1762 matchs economiquement exploitables sur 2132, exclusions comptabilisees explicitement (jour ambigu, historique insuffisant, cotes incompletes, non apparies) - voir docs/research_framework.md section I pour le verdict complet : **SIGNAL NEGATIF** (IC95% du profit moyen entierement negatif sur la strategie EV>0 pre-enregistree, n=1888 paris) ; **diagnostic post-E1** (`run_stage7_diagnostic_e1_market_gap.py`, purement descriptif, `poisson_simple` et `xg_model` INCHANGES) : calibration de `poisson_simple` 3 a 9x pire que le marche sur les trois issues sans exception, biais diffus (pas de sous-groupe localise), AUCUNE information independante detectee dans le desaccord poisson/marche (test demeanne par decile, IC95% couvrant 0 sur les trois issues), et erreurs xG PLUS correlees au marche (+0.845) que celles de poisson_simple (+0.789) - reponse negative a "xG contient-il une information non deja capturee par B365 ?", voir docs/research_framework.md section J pour le detail complet. Aucune modification de `poisson_simple`.) | 1 (base) / phase economique (`market_odds/`) |
| `backtesting_engine` (boucle chronologique minimale + walk-forward synthetique + walk-forward donnees reelles) | Implemente (`real_data_walk_forward.py` ajoute etape 5 pour B3 - walk-forward isole sur DataFrames en memoire avec deux flux de connaissance point-in-time independants (buts/xG), n'est PAS un connecteur de donnees reelles general pour le reste du projet, specifique au test B3) | 1 (boucle) / 2 (walk-forward synthetique) / 5 (walk-forward donnees reelles) |
| `football_model` (Poisson simple, attaque/defense, A1 (decroissance calendaire + re-test fenetre glissante), A2, benchmarks naif/Elo, B2 bayesien sequentiel, B1 Dixon-Coles, forme recente/H2H (re-test A1), B3 xG + B3.2 hybride + B3.3 gate de desaccord, controles negatifs E1/E7) | Implemente (A1 REJETE (infériorité significative confirmée) - decroissance calendaire (etape 2) ET fenetre glissante football-realiste avec/sans memoire longue (etape 5, `recent_form.py`/`head_to_head.py`) toutes deux significativement dominees par poisson_simple sur synthetique ; H2H seul INDETERMINE (aucun signal) ; B2 VALIDE contre A1 sur synthetique ; B1 (Dixon-Coles) VALIDE contre poisson_simple sur le sous-ensemble bas-score sur donnees SYNTHETIQUES uniquement, mais **REJETE lors du re-test sur donnees REELLES - avec nuance** : infériorité significative confirmée en Ligue 1 uniquement (IC95% entierement positif), absence de preuve d'amelioration (pas d'infériorité démontrée) en Premier League/Liga (memes donnees Understat que B3/B3.2/C7, 3 championnats x 2 saisons 2024/25+2025/26, buts reels uniquement, `DixonColesModel` inchange) - sous-ensemble bas-score sans signal coherent non plus - voir docs/research_framework.md section B1 pour le detail complet ; **A2 (HFA dynamique par equipe) REJETE - absence de preuve d'amelioration, pas refutation** lors du re-test sur donnees REELLES (`PoissonModel(use_team_hfa=True)`, `hfa_shrinkage_k=10.0` fige a l'etape 2, memes donnees que B1/B3/B3.2/C7, 640 matchs de test evalues) - aucun des trois championnats n'atteint une amelioration significative de poisson_simple, mais aucun n'atteint non plus une inferiorite significative (IC95% incluant 0 partout), signe instable entre saisons pour Ligue 1 et Liga - puissance statistique limitee, voir docs/research_framework.md section A2 et section G2 (limites de puissance) pour le detail complet ; **B2 (bayesien sequentiel) REJETE - absence de preuve d'amelioration, avec tendance favorable mais non significative** lors de la comparaison DIRECTE a poisson_simple sur donnees REELLES (`BayesianSequentialModel` inchange, `prior_strength=10.0` fige a l'etape 5, memes donnees que B1/A2/B3/B3.2/C7, 640 matchs de test evalues ; B2 n'avait ete compare qu'a A1 - desormais rejete - jamais directement a poisson_simple) - aucun des trois championnats n'atteint une amelioration significative (IC95% incluant 0 partout, Ligue 1 proche du seuil a -0.0114 [-0.0232, +0.0005], candidat le plus susceptible de changer de statut avec plus de donnees) - voir docs/research_framework.md section B2 et section G2 (limites de puissance) pour le detail complet ; **B3 (xG, `xg_model.py`) INDETERMINE**, **B3.2 (hybride Poisson/xG, `hybrid_xg_model.py`) INDETERMINE** et **B3.3 (gate de desaccord Poisson/xG, `gate_disagreement_model.py`, w=TVD zero parametre libre) REJETE - absence de preuve d'amelioration** sur donnees REELLES Understat (B3 : 3 championnats 2025/26 ; B3.2 : jeu vierge 2024/25, protocole validation/test isole ; B3.3 : 3 championnats x 2 saisons, 640 matchs test, signe favorable au gate cohérent sur les trois championnats sans jamais atteindre la significativite, PL/Liga proches du seuil p=0.089/0.080 ; les trois tests sont sous-puissants pour des effets de l'ordre de 0.01-0.02, voir section G2 de research_framework.md) - conclusion figee : l'analyse de complementarite est une observation statistique etablie sur son echantillon conditionnel (xG bat poisson_simple precisement quand ce dernier se trompe), mais sans strategie d'exploitation ex-ante identifiee - ni un modele xG seul, ni un hybride inconditionnel, ni un gate de desaccord a zero parametre n'ameliorent significativement poisson_simple hors echantillon avec les donnees actuelles (B3.3 montre neanmoins un signe favorable coherent sur les trois championnats, jamais significatif) ; ces resultats sont des hypotheses non demontrees, pas refutees ; **poisson_simple reste le modele de reference officiel** (inchange), **XGModel conserve comme modele complementaire independant** (jamais fusionne automatiquement), **HybridXGModel et GateDisagreementModel conserves pour tracabilite/reproductibilite, statut strictement experimental, non promus** ; reserve documentee sur la stabilite temporelle du xG Understat (delai de connaissance suppose, non verifie, distinct d'une fuite de donnees) - voir docs/research_framework.md section B3 pour la conclusion officielle complete. **BILAN GLOBAL (post-audit)** : aucune extension testee (A2, B1, B2, B3, B3.2, B3.3) n'a fourni a ce jour une amelioration statistiquement demontree et reproductible suffisante pour justifier le remplacement de poisson_simple ; A1 seul est refute par une preuve directe. Plusieurs hypotheses restent non demontrees plutot que refutees, notamment A2, B2 et B3/B3.2, en raison notamment de la puissance limitee des echantillons - voir docs/research_framework.md section G2 pour l'audit complet de la force des verdicts ; **diagnostic total de buts/Over-Under (purement descriptif, AUCUN modele modifie)** : poisson_simple/dixon_coles/xg_model surestiment tous les trois systematiquement le total de buts (biais +0.30/+0.30/+0.61 sur 2.79 buts observes en moyenne), concentre dans la queue haute (6+ buts surestime d'un facteur 2-3) ; Dixon-Coles mathematiquement identique a poisson_simple sur Over 2.5/3.5 (correction confinee aux cellules de total<=2) ; xg_model n'ameliore pas la calibration ponderee malgre un Brier/log loss legerement meilleur - voir docs/research_framework.md section K pour le detail complet ; **diagnostic calibration Over/Under par tranche (purement analytique, AUCUN modele modifie ni recalibre)** : decomposition de Murphy du Brier (nouvel outil de mesure pur, `calibration_engine/decomposition.py`, reutilise `reliability_bins` sans modification) montre un skill NEGATIF par rapport a la climatologie sur les 6 combinaisons testees (poisson_simple/xg_model x Over 1.5/2.5/3.5) - biais de fiabilite (0.007-0.027) superieur a la resolution (0.0017-0.0043), schema de biais en "S" (sous-confiance basse, sur-confiance haute) plausiblement corrigible par une recalibration monotone future (resolution mathematiquement preservee par construction) sans que cela soit demontre ici - voir docs/research_framework.md section L ; **experience E2 (recalibration isotonique Over/Under, poisson_simple/xg_model INCHANGES)** : `calibration_engine/isotonic_calibration.py` (PAVA via scipy, deja une dependance, aucune nouvelle), walk-forward 40/30/30 identique a B1/A2/B2/B3.3, courbe ajustee sur calibration uniquement (n=640), evaluee sur test uniquement (n=640) - AMELIORATION STATISTIQUEMENT DEMONTREE du Brier sur les 3 seuils pour xg_model et sur Over 3.5 pour poisson_simple (IC95% bootstrap entierement negatif), absence de preuve (jamais degradation) pour poisson_simple Over 1.5/2.5 - voir docs/research_framework.md section M pour le detail complet, y compris la nuance log loss/resolution) | 2 (base) / 5 (A1 re-test, B1, B2, B3, B3.2, B3.3, E1, E7) |
| `calibration_engine` (Brier, log loss, reliability, tests de significativite, Chi-Deux, `decomposition.py` fiabilite/resolution/incertitude, `isotonic_calibration.py` recalibration post-hoc PAVA) | Implemente | 2 |
| `market_engine` (snapshot, retrait de marge proportionnel + Shin, comparaison, `correlated_events.py` ajoute etape 5 pour C7, `model_vs_market.py` phase economique) | Implemente (**`model_vs_market.py` (phase economique)** : interface generique modele<->marche (probabilite implicite, overround, normalisation, diff) reutilisant `overround.py` sans modification, desormais utilisee par `economic_dataset.py` pour l'Experience 1 (verdict SIGNAL NEGATIF - voir `data_engine` ci-dessus et docs/research_framework.md section I) ; **C7 phase 1 (parlays correles, `correlated_events.py`) REJETE - absence d'association demontree pour cette paire precise, sans generalisation aux autres marches/parlays** - aucune correlation exploitable detectee entre favori a domicile selon poisson_simple et Over 2.5 buts, coherent sur 3 championnats et 2 saisons (estimation 2024/25, confirmation 2025/26) - teste uniquement l'EXISTENCE d'une correlation, aucune cote de marche combine dans le schema actuel donc aucune conclusion possible sur la rentabilite reelle d'un combine - voir docs/research_framework.md section C7 pour le detail complet) | 2 (benchmark) / 3 (complet) / 5 (C7) |
| `value_engine` (edge, EV, CLV, selection - AUCUNE selection sur EV seule) | Implemente (`edge.py::expected_value`/`edge` reutilises sans modification par l'Experience 1 economique, voir `data_engine` ci-dessus - `selection.py` non utilise, la strategie EV>0 de l'Experience 1 est deliberement plus simple, definie localement dans `scripts/run_stage6_economic_b365_ev.py`) | 3 |
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
