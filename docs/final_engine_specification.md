# Spécification technique du moteur final — Phase A

**Nature de ce document.** Spécification technique pure. Aucun code de
moteur de production n'est écrit ici. Aucune nouvelle expérience, aucun
nouveau modèle, aucun nouveau backtest. Toute affirmation est tracée soit
à un résultat `docs/research_synthesis_e1_e16.md` / `docs/research_framework.md`,
soit à une primitive déjà implémentée et testée dans `src/sys_foot_quant/`
ou `scripts/`. Chaque décision architecturale est étiquetée
`VALIDÉ SCIENTIFIQUEMENT`, `CHOIX ARCHITECTURAL` ou `HYPOTHÈSE FUTURE` —
jamais laissée implicite. Un développeur qui lit ce document ne doit avoir
à réinterpréter ni E1→E16 ni le code existant.

---

## 1. Inspection de l'architecture actuelle — ce qui existe déjà et doit être réutilisé

Inventaire des primitives déjà implémentées et testées, à réutiliser
**telles quelles** (jamais réécrites) par le moteur final :

| Primitive | Emplacement actuel | Statut | Action requise |
|---|---|---|---|
| `PoissonModel`, `predict_lambda_mu` | `football_model/poisson.py` | Implémenté, testé, inchangé depuis l'origine | Réutiliser tel quel |
| `DixonColesModel` | `football_model/dixon_coles.py` | Implémenté, testé | Réutiliser tel quel |
| `XGModel` | `football_model/xg_model.py` | Implémenté, testé | Réutiliser tel quel |
| `score_matrix(lam, mu, max_goals)` | `football_model/scoring.py` | Implémenté, testé | Réutiliser tel quel |
| `over_under_probs(matrix, thresholds)` | dupliquée dans `scripts/run_stage8_...py` et `scripts/run_stage15_e7_...py` (fonction pure, identique dans les deux) | Validée par E7 (§1, §6 : reproduction exacte vérifiée) mais **jamais promue en `src/`** | **Porter verbatim** (aucune réécriture de logique) vers `src/sys_foot_quant/football_model/goal_distribution.py` — voir section 6 |
| `total_goals_distribution(matrix, max_bucket)` | idem | idem | idem, même module |
| `check_over_under_monotonic`, `check_distribution_validity`, `check_over_under_matches_distribution` | `scripts/run_stage15_e7_total_goals_distribution.py` | Testés (E7 §6, `hypothesis` 200 tirages) | Porter verbatim vers le même module |
| `fit_scale_correction_as_of(calibration_df, model, as_of_time, min_matches=30)` | `scripts/run_stage16_e8_walk_forward_validation.py` | **VALIDÉ SCIENTIFIQUEMENT** (Verdict A, E8) | **Porter verbatim** vers `src/sys_foot_quant/calibration_engine/scalar_correction.py` — voir section 7 |
| `attach_walk_forward_scale(calibration_df, test_df, model)` | idem | idem | idem |
| `reliability_bins(probs, outcomes, n_bins)` | `calibration_engine/reliability.py` | Implémenté, testé, réutilisé sans modification depuis E1 | Réutiliser tel quel (gates de calibration, section 12) |
| `brier_decomposition` | `calibration_engine/decomposition.py` | Implémenté, testé (E2 →E16) | Réutiliser tel quel (monitoring de discrimination hors-ligne, jamais dans le chemin de décision temps réel) |
| `remove_overround_proportional`, `hold_percentage`, `validate_odds` | `market_engine/overround.py` | Implémenté, testé depuis E1 | Réutiliser tel quel |
| `compare_model_to_market(model_probs, market_odds)` | `market_engine/model_vs_market.py` | Implémenté, testé, générique par construction (fonctionne pour tout marché à sélections multiples) | **Réutiliser tel quel** comme brique centrale du bloc D (Market comparison) |
| `edge(model_prob, market_fair_prob)` | `value_engine/edge.py` | Implémenté, testé ; docstring rappelle déjà explicitement qu'un edge positif « ne dit rien, à lui seul, sur la fiabilité de ce désaccord » | Réutiliser tel quel pour `raw_edge` (section 11) |
| `expected_value(model_prob, odds)` | `value_engine/edge.py` | Implémenté, testé | Réutiliser tel quel pour `price_edge` (section 11) — jamais renommé « value » |
| `match_league_season`, `build_understat_keys`, `MatchedRecord` | `data_engine/market_odds/matching.py` | Implémenté, testé, zéro violation détectée sur tout le corpus réel E1-E16 | Réutiliser tel quel, **jamais réimplémenté** (règle déjà appliquée par toutes les expériences E1-E16) |
| `conservative_knowledge_time_utc`, `football_data_kickoff_to_utc` | `data_engine/market_odds/time_resolution.py` | Implémenté, testé | Réutiliser tel quel |
| `FootballDataMatchRecord` (+ propriétés `has_complete_*`, `odds_1x2_by_bookmaker`, `over_under_2_5_by_bookmaker`, `closing_odds_1x2_by_bookmaker`, `closing_over_under_2_5_by_bookmaker`) | `data_engine/market_odds/football_data_loader.py` | Implémenté, testé, étendu à travers E1/E5/E9/E13/E16 | Réutiliser tel quel — **les méthodes `closing_*` ne doivent jamais être appelées par le chemin de décision** (section 4, 9, 16) |
| `classify_calibration_discrimination` | `scripts/run_stage24_e15_premier_league_discrimination_diagnostic.py` | Résultat figé (grille A/B/C/D), utilisé une fois pour produire le constat E15 | **Non réutilisé en production comme fonction vivante** — le moteur final consomme le **résultat déjà figé** de cette classification (Premier League = classe B), pas la fonction elle-même (voir section 9 — recalculer seul un score en direct pour un nouveau championnat serait une nouvelle expérience, hors périmètre) |
| `EconomicMatchRecord`, `DECISION_OFFSET_HOURS=2.0`, `MIN_TRAIN_MATCHES=10` | `data_engine/market_odds/economic_dataset.py` | Constantes utilisées sans exception depuis E1 | Réutiliser telles quelles |
| `_MIN_CALIBRATION_MATCHES_FOR_SCALE = 30` | `scripts/run_stage16_e8_walk_forward_validation.py` | Règle d'exclusion pré-enregistrée, jamais activée sur le corpus réel mais validée par construction | Réutiliser telle quelle |

**Constat structurel important (à documenter, pas à corriger silencieusement)** :
les schémas pydantic point-in-time originaux (`data_engine/schemas/entities.py`
— `PointInTimeFact`, `Match`, `MatchResult`, `OddsSnapshot`) et le
`Repository.get_as_of` (`data_engine/storage/repository.py`) datent de
l'étape 1 (données synthétiques) et **n'ont jamais été utilisés par le
pipeline de données réelles** (E1→E16 utilisent des dataclasses ad hoc —
`FootballDataMatchRecord`, `EconomicMatchRecord`, `RealMatchRecord` — avec
un filtrage explicite de `decision_time` dans chaque script). Le moteur
final doit être bâti sur le **pipeline réellement testé sur données
réelles** (dataclasses + filtrage explicite délégué à
`matching.py`/`time_resolution.py`), **pas** sur le `Repository` synthétique
jamais exercé sur ce corpus. C'est un **CHOIX ARCHITECTURAL** : réutiliser
l'infrastructure ayant fait ses preuves sur 16 expériences réelles plutôt
que ressusciter un composant non exercé sur données réelles.

---

## 2. Pipeline directeur — confirmé contre E1→E16

Le schéma proposé par la demande est confirmé, avec une correction de
vocabulaire pour rester rigoureusement fidèle à la synthèse (section 11 de
`research_synthesis_e1_e16.md`) :

```
DATA
  → POINT-IN-TIME FEATURES
  → GOAL MODEL(S)
  → SCORE MATRIX (source unique)
  → GOAL DISTRIBUTION (dérivée de la matrice)
  → E7/E8 SCALAR CALIBRATION (walk-forward)
  → O/U PROBABILITIES (dérivées de la MÊME distribution corrigée)
  → SCIENTIFIC GATES (calibration, discrimination, données)
  → MARKET PRICE BENCHMARK (jamais un adversaire)
  → EDGE / UNCERTAINTY
  → OPERATIONAL GATES (paramètres non validés, configurables)
  → BET / NO BET
```

**Correction actée par rapport à l'énoncé** : « SCORE MATRIX » est
intercalée explicitement entre « GOAL MODEL(S) » et « GOAL DISTRIBUTION »
— ce n'est pas une étape supplémentaire mais une clarification : la
distribution et les probabilités O/U ne sont **jamais** calculées
indépendamment, elles sont **toutes deux dérivées de la même matrice**
(propriété validée scientifiquement, E7 §1, E11 Q3). Le reste du schéma
est confirmé sans changement. Chaque flèche correspond à une étape déjà
démontrée dans E1→E16, à l'exception de la toute dernière
(EDGE/UNCERTAINTY → décision positive), qui n'a **jamais** été validée —
voir section 19.

---

## 3. Séparation explicite des niveaux A→F

Chaque niveau produit une sortie **immuable**, consommée par le niveau
suivant sans jamais s'y substituer :

| Niveau | Nom | Entrée | Sortie | Ne doit JAMAIS faire |
|---|---|---|---|---|
| **A** | Prediction | Features point-in-time | `(λ, μ, [ρ])` par modèle, matrice de score brute | Appliquer une correction, comparer au marché, décider |
| **B** | Calibration | Matrice brute + historique de calibration walk-forward | Matrice **corrigée** (facteur `c(m)`), distribution de buts, probabilités O/U | Comparer au marché, décider, appliquer une correction non validée (E14) |
| **C** | Pricing | Probabilités O/U corrigées | Cote juste (`fair_price = 1 / p_model`) | Comparer au marché (c'est le rôle du niveau D) |
| **D** | Market comparison | `fair_price` + cote de marché (ouverture) | `raw_edge`, `price_edge`, probabilité implicite de marché | Qualifier la fiabilité de l'edge (c'est le rôle du niveau E) |
| **E** | Qualification | Sorties A-D + gates scientifiques/opérationnels | `calibration_status`, `discrimination_status`, `scientific_gates[]`, `operational_gates[]` | Produire une décision positive de pari sans gate validé |
| **F** | Decision | Sorties E | `BET` / `NO BET` + `decision_reason` | Recalculer une probabilité, ignorer un gate échoué |

---

## 4. Inputs exacts

### 4.1 Données nécessaires au modèle (Niveau A)

| Nom | Type | Source | Point-in-time | Oblig./Opt. | Valeurs manquantes | Contrôle de validité | Disponibilité |
|---|---|---|---|---|---|---|---|
| `home_goals`, `away_goals` (historique) | int | Understat / résultats de matchs | `knowledge_time` = fin de match (résultat connu après coup d'envoi + durée du match) | **Obligatoire** (`poisson_simple`, `dixon_coles`) | Match exclu de l'historique d'entraînement si absent | Filtrage `decision_time` strict (réutilise `matching.py`) | Disponible immédiatement après chaque match |
| `home_xg`, `away_xg` (historique) | float | Understat | `xg_knowledge_time` (délai documenté, non vérifié indépendamment — réserve actée depuis B3) | Obligatoire **uniquement** pour `xg_model` (modèle de contrôle) | Match exclu de l'historique `xg_model` uniquement si absent — n'affecte jamais `poisson_simple`/`dixon_coles` | idem | Disponible avec un délai non vérifié après chaque match |
| `home_team_id`, `away_team_id` | identifiant | Understat / mapping d'équipes | N/A (métadonnée statique) | Obligatoire | Match exclu si mapping introuvable (`team_mapping.py`) | Mapping déterministe existant, testé | Disponible à la publication du calendrier |
| `kickoff_utc` | datetime UTC | Understat | N/A | Obligatoire | Match exclu si absent | — | Disponible à la publication du calendrier |

`MIN_TRAIN_MATCHES = 10` (constante existante, `economic_dataset.py`) :
si l'historique disponible avant `decision_time` est strictement inférieur
à 10 matchs pour l'équipe/le modèle considéré, **aucune prédiction n'est
émise** pour ce modèle sur ce match (comportement déjà en vigueur depuis
E1, jamais modifié).

### 4.2 Données nécessaires au pricing (Niveau C)

Aucune donnée supplémentaire — le pricing est une transformation
déterministe (`1 / p_model`) de la sortie du Niveau B. Aucun input externe.

### 4.3 Données nécessaires à l'analyse de marché (Niveau D)

| Nom | Type | Source | Point-in-time | Oblig./Opt. | Valeurs manquantes | Contrôle de validité | Disponibilité |
|---|---|---|---|---|---|---|---|
| `B365H/D/A` (1X2, ouverture) | cote décimale | Football-Data.co.uk | `TIMESTAMP_STATUS_HYPOTHETICAL` — règle conservatrice `conservative_knowledge_time_utc`, jamais un timestamp vérifié | **Obligatoire** pour le bloc D (référence de prix primaire, couverture 100 % constatée depuis E1) | Match marqué `market_data_unavailable`, Niveau D/E dégradé (voir gate « données de marché manquantes », section 12) — **jamais** une décision BET sans cote de marché | `validate_odds` (`overround.py`) | Disponible à l'ouverture du marché, avant `decision_time` |
| `B365>2.5`/`B365<2.5` (O/U 2.5, ouverture) | cote décimale | Football-Data.co.uk | idem | Obligatoire pour le pricing du marché Over/Under 2.5 spécifiquement | idem | idem | idem |
| `PS...`/`P>2.5`/`P<2.5` (Pinnacle, ouverture) | cote décimale | Football-Data.co.uk | idem | **Optionnel** — audit/cross-check secondaire uniquement (E13 : n'améliore pas B365 seul) | Absence silencieuse, jamais imputée | idem | Couverture partielle (~76.6 %, E9/E13) |
| `BW...` (Bet&Win, ouverture) | cote décimale | Football-Data.co.uk | idem | Optionnel — audit uniquement (E9) | idem | idem | Couverture variable (~80.5 %, s'inverse entre saisons) |
| `WH.../LB...` (William Hill / Ladbrokes, ouverture) | cote décimale | Football-Data.co.uk | idem | Optionnel — audit uniquement, jamais indispensable | idem | idem | Disponibilité exclusive par saison (jamais coexistants) |

### 4.4 Données uniquement utilisées pour validation/recherche — **jamais dans le chemin de décision**

| Nom | Type | Source | Statut |
|---|---|---|---|
| `B365CH/CD/CA`, `BWCH/CD/CA`, `PSCH/CD/CA` (clôture, 1X2) | cote décimale | Football-Data.co.uk | **Rétrospectif uniquement** (E16). Accessible via `closing_odds_1x2_by_bookmaker()` — cette méthode **ne doit jamais être appelée** par un chemin de code exécuté avant/à `decision_time` |
| `B365C>2.5/C<2.5`, `PC>2.5/PC<2.5` (clôture, O/U 2.5) | cote décimale | Football-Data.co.uk | idem, via `closing_over_under_2_5_by_bookmaker()` |
| `WHCH/CD/CA`, `LBCH/CD/CA` (clôture, secondaires) | cote décimale | Football-Data.co.uk | idem |
| Résultat réel du match (`FTHG`/`FTAG`) au moment de la décision | int | Football-Data.co.uk / Understat | Utilisé uniquement pour évaluer/monitorer a posteriori (Brier, calibration) — **jamais disponible à `decision_time` par construction**, aucun contrôle supplémentaire requis au-delà du filtrage `decision_time` déjà en place |

**Règle non négociable, réaffirmée** : la cote de clôture reste
strictement dans cette dernière catégorie. Aucune fonction du chemin de
décision (Niveaux A à F) ne doit importer, lire ou référencer
`closing_odds_1x2_by_bookmaker` / `closing_over_under_2_5_by_bookmaker` —
contrôle testable statiquement (inspection AST, méthode déjà utilisée dans
`tests/leakage/test_e16_market_movement_information_point_in_time.py`, à
reproduire pour le moteur final, voir section 18).

---

## 5. Définition des modèles

Conformément à la synthèse (section 8) : **aucun classement n'est
inventé, aucun ensemble n'est supposé supérieur, aucune pondération
arbitraire n'est créée.**

- **Modèle principal** : `poisson_simple` (`PoissonModel(use_team_hfa=False)`,
  inchangé). Choix motivé par : antériorité (référence du projet depuis
  E1), dépendance de données minimale (buts uniquement, pas de xG),
  absence de preuve de supériorité d'un autre modèle (E11).
  **`CHOIX ARCHITECTURAL — NON VALIDÉ COMME SOURCE D'EDGE`** — ce choix ne
  prétend pas que `poisson_simple` est scientifiquement supérieur, mais
  qu'aucune raison démontrée ne justifie de lui préférer un autre modèle.
- **Modèles de contrôle** : `dixon_coles` et `xg_model`, calculés en
  parallèle, exposés dans la sortie structurée (section 15) à des fins de
  comparaison/traçabilité continue, **jamais fusionnés automatiquement**
  avec `poisson_simple`. `dixon_coles` est redondant avec `poisson_simple`
  sur Over 2.5/3.5 (fait mathématique démontré, K/E7/E8/E11) — son calcul
  reste peu coûteux et est conservé pour traçabilité, pas pour un
  bénéfice attendu sur ces marchés précis.
  **`CHOIX ARCHITECTURAL — NON VALIDÉ COMME SOURCE D'EDGE`**.
- **Ensemble des trois modèles (moyenne, vote, pondération dynamique)** :
  **`HYPOTHÈSE FUTURE — ENSEMBLE NON VALIDÉ EXPÉRIMENTALEMENT`**. Aucune
  implémentation d'ensemble n'entre dans le moteur tant qu'une expérience
  dédiée n'aura pas été menée.

---

## 6. Distribution de buts — contrat précis

**Module cible (nouveau, mais portage verbatim, aucune nouvelle
logique)** : `src/sys_foot_quant/football_model/goal_distribution.py`.

- **Représentation** : matrice de score `M[i][j] = P(buts_domicile=i,
  buts_extérieur=j)`, produite par `score_matrix(lam, mu, max_goals)`
  (`football_model/scoring.py`, réutilisée sans modification), corrigée
  par Dixon-Coles (`apply_dixon_coles_correction`) pour le modèle
  `dixon_coles` uniquement.
- **Support** : entiers `0..max_goals` par équipe (`max_goals=20`,
  constante déjà utilisée en E7/E8/E11, aucune queue tronquée sous ce
  seuil sur le corpus observé).
- **Calcul des probabilités O/U** : `over_under_probs(matrix, thresholds)`
  — `P(total > seuil) = Σ M[i][j]` pour tout `i+j > seuil` — **portée
  verbatim** depuis `scripts/run_stage15_e7_total_goals_distribution.py`
  (fonction pure, déjà testée par `hypothesis` sur 200 tirages aléatoires
  de `(λ, μ, ρ, c)`).
- **Relation entre seuils, garantie par construction** :
  `P(O0.5) ≥ P(O1.5) ≥ P(O2.5) ≥ P(O3.5) ≥ P(O4.5)` — garantie **parce
  que** toutes les probabilités proviennent de la même matrice
  (`totals > t`, monotone en `t` par construction ensembliste), jamais
  vérifiée a posteriori comme condition suffisante : c'est une propriété
  **structurelle** du calcul, pas un contrôle ajouté après coup.
  Néanmoins, un contrôle de non-régression (`check_over_under_monotonic`,
  porté verbatim) doit tourner en continu en production (assertion, pas
  branche corrective) — si jamais violée, c'est un bug de la matrice en
  amont (ex. corruption de `(λ, μ)`), jamais un cas à corriger
  silencieusement.
- **Gestion des valeurs extrêmes (queue haute)** : `total_goals_distribution(matrix,
  max_bucket)` agrège tout total `≥ max_bucket` (buckets `0..max_bucket-1`
  puis `≥max_bucket`, comme en E7/E8/E11) — portée verbatim.
- **Contrôles de cohérence obligatoires en production**, tous portés
  verbatim depuis `scripts/run_stage15_e7_total_goals_distribution.py` et
  exécutés à chaque calcul (pas seulement en test) :
  - `check_distribution_validity(dist)` — somme = 1, aucune masse
    négative ;
  - `check_over_under_monotonic(ou)` — monotonicité décroissante des
    seuils ;
  - `check_over_under_matches_distribution(dist, ou)` — chaque `P(Over t)`
    doit égaler exactement `Σ dist[k_min:]` — vérifie que le pricing O/U
    n'a jamais divergé de la distribution source.
- **Aucune probabilité O/U n'est jamais calculée indépendamment** : toute
  fonction qui aurait besoin d'une probabilité de seuil doit appeler
  `over_under_probs` sur la matrice déjà corrigée (section 7), jamais
  recalculer un seuil isolément (interdiction structurelle, testable par
  inspection statique — un seul point d'entrée `over_under_probs`).

---

## 7. Contrat technique exact de la correction E7/E8

**Statut : VALIDÉ SCIENTIFIQUEMENT (Verdict A, E8, les trois modèles).
Le principe n'est pas modifié.**

**Module cible** : `src/sys_foot_quant/calibration_engine/scalar_correction.py`
(portage verbatim de `fit_scale_correction_as_of` et
`attach_walk_forward_scale`, `scripts/run_stage16_e8_walk_forward_validation.py`).

- **Données utilisées** : historique de calibration (`calibration_df`) —
  pour chaque match antérieur, `(λ+μ)_prédit` du modèle et `total_goals`
  réel. **Aucune donnée du match évalué**, jamais.
- **Fenêtre historique** : **expansive stricte**, jamais glissante à
  taille fixe — tous les matchs de calibration disponibles dont
  `decision_time < as_of_time` (le `decision_time` du match évalué),
  aucune limite supérieure de fenêtre.
- **Calcul** : `c = E[total_réel] / E[λ+μ_prédit]`, moyenne simple sur
  l'ensemble filtré — un seul degré de liberté, aucune régression,
  aucun hyperparamètre.
- **Moment d'application** : `c` est appliqué **avant** la reconstruction
  de la matrice de score — `(λ, μ) → (c·λ, c·μ) → score_matrix(c·λ, c·μ)`
  — jamais après (jamais un facteur multiplicatif appliqué directement
  aux probabilités de seuil déjà calculées, ce qui romprait la garantie
  de cohérence de la section 6).
- **Gestion du premier historique insuffisant** : `min_matches = 30`
  (`_MIN_CALIBRATION_MATCHES_FOR_SCALE`, règle d'exclusion
  pré-enregistrée). Si le nombre de matchs de calibration antérieurs à
  `as_of_time` est `< 30`, `fit_scale_correction_as_of` retourne `(None, n)`.
  **Comportement de production dans ce cas** : aucune probabilité O/U
  corrigée n'est émise pour ce match — sortie `NO BET / INSUFFICIENT_HISTORY`
  (voir section 14). La matrice brute (non corrigée) ne doit **jamais**
  être présentée comme équivalente à la matrice corrigée dans la sortie
  structurée.
- **Comportement en production (régime établi)** : pour chaque décision,
  `c(m)` est recalculé à `as_of_time = decision_time` du match — jamais
  mis en cache d'un match à l'autre au-delà de la fenêtre de calibration
  déjà filtrée (le calcul est peu coûteux : une moyenne sur au plus
  quelques centaines de lignes).
- **Sorties** : `scale_c` (float ou `None`), `n_calibration_used` (int) —
  les deux doivent apparaître dans la sortie structurée (section 15) pour
  auditabilité.
- **Contrôles** : `n_calibration_used ≥ 30` est une **précondition** avant
  d'émettre toute probabilité corrigée — testable directement.

---

## 8. E14 — traitement de la zone [0.6,0.7) d'Over 2.5

**E14 est explicitement NON VALIDÉE (gate de cohérence inter-seuils violé
substantiellement pour `poisson_simple`, amélioration non démontrée pour
`xg_model`, instabilité par championnat).** Conséquences, non négociables :

- **Aucune recalibration locale n'entre dans le moteur** : ni isotonique,
  ni logistique, ni aucune autre forme de correction ciblée sur cette
  zone ou toute autre zone de probabilité.
- La probabilité `P(Over 2.5)` produite par le Niveau B (section 6-7)
  **n'est jamais modifiée** en fonction de sa propre valeur.
- **Ce que le moteur fait exactement lorsqu'une prédiction tombe dans
  [0.6,0.7)** : un `SCIENTIFIC GATE` dédié (`calibration_zone_gate`,
  voir section 12) est déclenché en lecture seule — il **observe** la
  probabilité produite par le Niveau B et positionne
  `calibration_status = "ZONE_BIAISEE_NON_CORRIGEE"` dans la sortie
  structurée. La probabilité elle-même n'est **pas** touchée (elle reste
  affichable aux Niveaux A-C, avec ce flag). Au Niveau F (Decision), ce
  gate impose une abstention **opérationnelle** par défaut (voir section
  13) — configurable, mais son état par défaut est `NO BET`, jamais un
  ajustement de la probabilité.
- **Si aucune décision scientifiquement validée n'est possible** (c'est
  le cas ici : aucune correction validée n'existe pour cette zone), la
  sortie du Niveau F est :

  ```
  decision = NO_BET
  decision_reason = "INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE"
  ```

  **jamais** une correction arbitraire de la probabilité affichée.
- **Bornes du gate** : le seuil `[0.6, 0.7)` est repris **exactement** de
  la définition d'E11 (tranche de calibration à 10 points, `[0.6-0.7)`),
  jamais redéfini ni élargi/rétréci sans nouvelle expérience.
- **Portée du gate** : uniquement Over 2.5 (seul seuil pour lequel cette
  sur-confiance a été démontrée, E11). Les autres seuils (0.5/1.5/3.5/4.5)
  n'héritent **pas** automatiquement de ce flag — voir la table générale
  de calibration par seuil, section 12.

---

## 9. E15 — gate Premier League

**E15 établit : absence de signal discriminant confirmée mais
inexpliquée, calibration correcte (classe B).** Conséquences non
négociables :

- Aucun coefficient correctif Premier League n'est créé.
- Les probabilités Premier League produites par les Niveaux A-C ne sont
  **jamais modifiées** par rapport aux autres championnats — même
  pipeline, mêmes formules.
- La Premier League n'est **jamais retirée** automatiquement de
  l'historique d'entraînement des modèles.
- Le moteur n'affirme jamais que les probabilités Premier League sont
  « fausses » — seulement qu'aucune discrimination n'y est démontrée.

**Distinction structurelle imposée dans la sortie** : deux champs
**indépendants**, jamais fusionnés :

| Champ | Définition | Source |
|---|---|---|
| `calibration_status` | La probabilité annoncée correspond-elle, en moyenne, à la fréquence réelle dans sa tranche ? (propriété testée par `reliability_bins`/E11) | Table de calibration par seuil × tranche (section 12) |
| `discrimination_status` | Le modèle sépare-t-il réellement les matchs à faible/fort total de buts, dans ce championnat ? (propriété testée par corrélation E4/E11, classification A/B/C/D E15) | **Résultat figé** de la classification E15 par championnat (table statique, pas une fonction recalculée en direct) |

**Gate `premier_league_discrimination_gate`** (conséquence directe d'E15,
identifiée comme telle dans le code et la documentation) : pour tout match
où `competition == "Premier League"`, `discrimination_status` est
positionné à `"NON_DEMONTREE"` de façon **statique** (table de référence
issue d'E4/E11/E15, pas un recalcul en ligne). Ce gate **ne bloque pas**
l'émission d'une probabilité (Niveaux A-C) mais impose, au Niveau F, une
abstention opérationnelle par défaut si `discrimination_status !=
"DEMONTREE"` — voir section 13.

**Règle d'extension explicite** : ce gate est une table de référence figée
à trois championnats (Liga, Ligue 1, Premier League), issue d'E4/E11/E15.
**L'ajout d'un nouveau championnat au moteur nécessite, avant mise en
production, la réplication du diagnostic E15 sur ce championnat** — le
moteur ne doit jamais supposer par défaut qu'un championnat non testé a
une discrimination démontrée (position par défaut prudente :
`discrimination_status = "NON_EVALUEE"` pour tout championnat hors de la
table de référence, traité comme le cas Premier League au Niveau F tant
qu'il n'a pas été audité).

---

## 10. Rôle du marché

Conformément à la synthèse (section 4) : **le marché est un `PRICE
BENCHMARK`, jamais un oracle ni un adversaire.** Contrat technique,
entièrement porté par des primitives déjà testées :

1. **Conversion cote → probabilité implicite** : `1 / cote` par sélection
   (déjà fait à l'intérieur de `compare_model_to_market`).
2. **Retrait de marge** : `remove_overround_proportional(market_odds)`
   (`market_engine/overround.py`, réutilisé sans modification depuis E1).
3. **Prix juste** : `fair_price = 1 / p_model` (Niveau C, section 6-7),
   **jamais** dérivé du marché — c'est le prix qu'impliquerait la
   probabilité du modèle, pas une correction du prix de marché.
4. **Différence modèle/marché** : `compare_model_to_market(model_probs,
   market_odds)` retourne déjà `model_minus_market` — champ réutilisé tel
   quel comme `raw_edge` par sélection (section 11).
5. **Edge théorique** : voir section 11 — jamais appelé `value`.

**Interface d'appel** (Niveau D), directement l'interface existante :

```python
compare_model_to_market(
    model_probs={"Over": p_over, "Under": 1 - p_over},   # ou {"H": ..., "D": ..., "A": ...}
    market_odds={"Over": b365_over, "Under": b365_under},
)
```

Aucune modification de `model_vs_market.py` n'est nécessaire — l'interface
est déjà générique (le docstring du module l'indique explicitement :
« fonctionne pour le 1X2 aujourd'hui, pour tout autre marché... sans
modification »).

---

## 11. Définition précise de l'EDGE

| Terme | Formule | Fonction existante | Statut |
|---|---|---|---|
| `fair_probability` | `p_model` (Niveau B, corrigé E7/E8) | — | VALIDÉ SCIENTIFIQUEMENT (calibration démontrée dans les zones non flaggées) |
| `market_price` | Cote de marché brute (ouverture, B365 en priorité) | — | Donnée d'entrée (section 4.3) |
| `market_implied_probability` | `remove_overround_proportional(market_odds)` | `overround.py` | VALIDÉ SCIENTIFIQUEMENT (méthode éprouvée depuis E1) |
| `raw_edge` | `edge(model_prob, market_fair_prob) = model_prob − market_fair_prob` | `value_engine/edge.py::edge` | Calcul **CHOIX ARCHITECTURAL** (raisonnable) ; interprétation comme signal **REJETÉE** (E5/E10/E12) |
| `price_edge` | `expected_value(model_prob, odds) = model_prob × odds − 1` | `value_engine/edge.py::expected_value` | Calcul **CHOIX ARCHITECTURAL** ; interprétation comme signal de rentabilité **REJETÉE** (E1 : IC95 % entièrement négatif sur la règle EV>0 brute) |
| `expected_value` | Alias de `price_edge` — conservé pour compatibilité avec le vocabulaire déjà utilisé dans `value_engine` | idem | idem |

**Interdiction explicite et non négociable** : aucun de ces champs n'est
jamais renommé ou présenté comme `value` dans la sortie structurée, la
documentation, ou le code. Le contrat de sortie (section 15) doit inclure,
à côté de chaque edge, les champs d'incertitude et de gate qui en
qualifient (ou non) l'usage :

```
raw_edge          : float
price_edge        : float
uncertainty       : { n_calibration_used, calibration_status, discrimination_status }
scientific_gates  : [ ... ]   # voir section 12
```

Une différence de probabilité **n'est jamais, à elle seule**, une edge
exploitable — c'est la conjonction `edge + gates tous passés + incertitude
acceptable` qui pourrait, en théorie, alimenter une décision positive —
et cette conjonction **n'a jamais été validée** par E1-E16 (voir section
19). Le moteur ne doit donc produire aucune règle qui transformerait
`raw_edge` ou `price_edge` seul en signal d'achat.

---

## 12. Scientific Gates — liste exhaustive

Chaque gate est un contrôle en **lecture seule** : il qualifie une
prédiction déjà produite, il ne la modifie jamais. Aucun seuil numérique
de pari n'est fixé ici — seule la **condition scientifique** l'est.

| Gate | Raison | Expérience(s) | Input | Condition | Sortie | Comportement en cas d'échec |
|---|---|---|---|---|---|---|
| `insufficient_data_gate` | Historique de modèle insuffisant | `MIN_TRAIN_MATCHES=10`, en vigueur depuis E1 | Nombre de matchs antérieurs disponibles pour l'équipe/le modèle | `n < 10` | `data_quality = "INSUFFICIENT_HISTORY"` | Aucune prédiction émise pour ce modèle ; `NO_BET` si c'est le modèle principal |
| `insufficient_calibration_history_gate` | Historique de calibration E7/E8 insuffisant | E8 (`_MIN_CALIBRATION_MATCHES_FOR_SCALE=30`) | `n_calibration_used` | `n < 30` | `calibration_status = "SCALE_NOT_ESTIMABLE"` | Aucune probabilité corrigée émise ; `NO_BET / INSUFFICIENT_HISTORY` |
| `ambiguous_day_gate` | Jour de collecte de cote non fiable (lundi/mardi/vendredi) | E1 (règle appliquée sans exception depuis) | Jour de la semaine du coup d'envoi | Jour ∈ {lundi, mardi, vendredi} | `data_quality = "AMBIGUOUS_COLLECTION_DAY"` | Bloc D (comparaison marché) désactivé ; `NO_BET` si le marché est requis pour la décision |
| `incomplete_market_odds_gate` | Cote de marché incomplète/absente à `decision_time` | E1/E5 (0 exclusion pour cote incomplète historiquement, mais le contrôle existe) | Complétude de `B365H/D/A` ou `B365>2.5/<2.5` | Cote manquante ou `validate_odds` échoue | `data_quality = "INCOMPLETE_MARKET_ODDS"` | Niveau D/E dégradés ; `NO_BET / MARKET_DATA_UNAVAILABLE` |
| `distribution_consistency_gate` | Cohérence structurelle de la distribution de buts | E7 §6 | `check_distribution_validity`, `check_over_under_monotonic`, `check_over_under_matches_distribution` | Une des trois vérifications échoue | `data_quality = "DISTRIBUTION_INCONSISTENT"` (ne devrait jamais se produire — signale un bug amont) | `NO_BET` inconditionnel, alerte technique |
| `calibration_zone_gate` | Sur-confiance démontrée dans [0.6,0.7) d'Over 2.5 | E11, E14 (rejet de correction) | `p_over_2_5` corrigé | `0.6 ≤ p < 0.7` | `calibration_status = "ZONE_BIAISEE_NON_CORRIGEE"` | Pas de blocage du Niveau A-C ; abstention opérationnelle par défaut au Niveau F (section 13) |
| `general_calibration_gate` | Calibration non testée sur les seuils 0.5/4.5 | E11 (pentes de Cox peu fiables, masse concentrée) | Seuil O/U concerné | Seuil ∈ {0.5, 4.5} | `calibration_status = "INSUFFICIENT_VALIDATION"` | Affichable (Niveau A-C) ; jamais interprété comme signal qualifié au Niveau E |
| `discrimination_gate` | Discrimination non démontrée pour ce championnat | E4, E11, E15 | `competition` | `competition` absent de la table de discrimination démontrée (Liga/Ligue 1 uniquement à ce jour) | `discrimination_status = "NON_DEMONTREE"` (Premier League) ou `"NON_EVALUEE"` (championnat non audité) | Pas de blocage des Niveaux A-C ; abstention opérationnelle par défaut au Niveau F |
| `market_disagreement_not_a_signal_gate` | Le désaccord modèle/marché n'est jamais un signal positif | Diagnostic post-E1, E5, E10, E12 | `raw_edge` | Toujours actif (garde structurelle, pas conditionnelle) | — | Interdit toute règle du moteur qui déclencherait `BET` **parce que** `raw_edge` est grand — vérifié par revue de code / test de non-régression |
| `movement_not_a_feature_gate` | Le mouvement de marché n'est jamais une feature de décision | E16 | Chemin de code du Niveau A-F | Toute référence à `closing_odds_1x2_by_bookmaker`/`closing_over_under_2_5_by_bookmaker` dans un module de décision | — | Interdiction structurelle testée par inspection statique (section 18) |
| `multi_bookmaker_not_edge_gate` | La dispersion multi-bookmaker n'est jamais une source d'edge | E9, E13 | Sorties de `market_engine/consensus.py`/`anomaly.py`/`arbitrage.py` | Toute utilisation de ces modules dans le calcul de `raw_edge`/`price_edge`/`decision` | — | Ces modules restent des outils d'audit hors chemin de décision — interdiction structurelle testée |

**Aucun seuil numérique de pari n'est inventé ici** — chaque gate produit
un **statut qualitatif** (`calibration_status`, `discrimination_status`,
`data_quality`), jamais un seuil de décision chiffré.

---

## 13. Operational Gates — séparés explicitement des gates scientifiques

| Paramètre opérationnel | Rôle | Valeur par défaut proposée | Statut |
|---|---|---|---|
| `min_edge_threshold` | Edge minimal (`raw_edge` ou `price_edge`) exigé pour envisager `BET` | **Non fixé** | `PARAMÈTRE OPÉRATIONNEL À VALIDER` — aucune expérience n'a validé un seuil d'edge exploitable (E5/E10/E12 : le désaccord n'est jamais fiable, quelle que soit son amplitude) |
| `min_calibration_confidence` | Niveau de confiance minimal exigé sur `calibration_status` pour autoriser `BET` | **`calibration_status == "OK"` obligatoire** (pas de zone flaggée) | `PARAMÈTRE OPÉRATIONNEL À VALIDER` dans son principe d'exigence exacte, mais la liste des statuts disqualifiants est directement dérivée des gates scientifiques (section 12) |
| `min_discrimination_confidence` | Championnats autorisés à produire `BET` | **`discrimination_status == "DEMONTREE"` obligatoire** (Liga, Ligue 1 uniquement à ce jour) | `PARAMÈTRE OPÉRATIONNEL À VALIDER` (la liste peut s'étendre après audit E15-like d'un nouveau championnat) |
| `abstain_on_calibration_zone_gate` | Abstenir automatiquement si `calibration_zone_gate` déclenché | **`True`** (abstention par défaut) | `PARAMÈTRE OPÉRATIONNEL À VALIDER` — le principe (aucune correction sans validation) est scientifique, mais le choix d'abstenir plutôt que de simplement flaguer reste une décision opérationnelle |
| `min_sample_size_cell` | Effectif minimal de la cellule de conditionnement (championnat × tranche de probabilité) pour considérer une décision | Convention `n ≥ 30` déjà utilisée dans E5-E16 | `PARAMÈTRE OPÉRATIONNEL À VALIDER` pour son usage en production — la convention `n≥30` est méthodologique (tests statistiques), pas une garantie de rentabilité |

**Distinction impérative, reformulée** :

> `SCIENTIFIC GATE` = « le signal n'est pas démontré » (fait établi par
> E1-E16, non négociable).
> `OPERATIONAL THRESHOLD` = « nous exigeons au moins X pour agir » (choix
> de gestion du risque, jamais présenté comme scientifiquement optimal,
> toujours paramétrable/configurable).

Tous les `OPERATIONAL THRESHOLD` doivent être exposés dans un fichier de
configuration explicite (ex. `config/operational_thresholds.yaml`, à
créer en Phase B), jamais codés en dur dans la logique de décision, et
chaque valeur par défaut proposée ci-dessus doit être accompagnée en
commentaire de la mention `PARAMÈTRE OPÉRATIONNEL À VALIDER`.

**Mise à jour (Phase C, cadrage)** : `min_edge_threshold` (et plus
généralement toute règle convertissant un edge qualifié en `BET`) reste
**non validé et non fixé** à ce stade — implémenté dans le moteur
(`gates.py::OperationalThresholds`, `min_edge_threshold: float | None =
None`) mais jamais activé, conformément au moteur minimal viable (section
19). Le protocole méthodologique qui devra être suivi pour, un jour,
proposer et tester une valeur de ce paramètre sans data snooping est
défini dans `docs/operational_validation_specification.md` — ce document
ne fixe aucune valeur, ne lance aucune expérience, et ne modifie pas le
moteur ; il cadre uniquement la démarche future.

**Mise à jour (Phase D, exécutée)** : ce protocole a été suivi une seule
fois sur données réelles — voir `docs/operational_validation_report.md`.
Verdict : `NO BET — EDGE NON VALIDÉ`. Aucun des seuils candidats
pré-enregistrés n'a satisfait les critères de sélection. `min_edge_threshold`
reste `None` ; `BET` n'est pas activé.

---

## 14. NO BET comme sortie de premier ordre

`NO_BET` n'est **jamais** une erreur — c'est la sortie par défaut et la
plus fréquente attendue du moteur, conformément au moteur minimal viable
(section 19). Chaque `NO_BET` porte un code de raison explicite, unique
par cause racine (plusieurs codes peuvent être présents simultanément —
`decision_reason` est une liste, pas un scalaire) :

| Code | Déclencheur |
|---|---|
| `INSUFFICIENT_HISTORY` | `insufficient_data_gate` ou `insufficient_calibration_history_gate` |
| `AMBIGUOUS_COLLECTION_DAY` | `ambiguous_day_gate` |
| `MARKET_DATA_UNAVAILABLE` | `incomplete_market_odds_gate` |
| `DISTRIBUTION_INCONSISTENT` | `distribution_consistency_gate` (anomalie technique) |
| `INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE` | `calibration_zone_gate` déclenché et `abstain_on_calibration_zone_gate=True` |
| `DISCRIMINATION_NOT_DEMONSTRATED` | `discrimination_gate` (Premier League ou championnat non audité) |
| `EDGE_BELOW_THRESHOLD` | `raw_edge`/`price_edge` sous `min_edge_threshold` |
| `UNCERTAINTY_TOO_HIGH` | Effectif de cellule sous `min_sample_size_cell` |
| `MARKET_NOT_USABLE` | Cote de marché rejetée par `validate_odds` |
| `OTHER_BLOCKING_CONDITION` | Toute condition bloquante non couverte ci-dessus — jamais une sortie silencieuse sans code |

---

## 15. Objet de sortie structuré

```
MatchDecisionOutput:
  match_id: str
  timestamp_decision: datetime (UTC)          # = decision_time
  competition: str
  season: str

  # Niveau A — Prediction
  models:
    poisson_simple: { lambda, mu, n_train_matches }
    dixon_coles:    { lambda, mu, rho, n_train_matches }
    xg_model:       { lambda, mu, n_train_matches }        # null si historique xG insuffisant
  primary_model: "poisson_simple"                          # CHOIX ARCHITECTURAL, section 5

  # Niveau B — Calibration
  scale_correction: { c, n_calibration_used }
  goal_distribution: [ P(total=0), P(total=1), ..., P(total>=max_bucket) ]
  probabilities:
    over_0_5, over_1_5, over_2_5, over_3_5, over_4_5: float

  # Niveau C — Pricing
  fair_price:
    over_2_5: float   # = 1 / probabilities.over_2_5, etc. pour chaque seuil affiché

  # Niveau D — Market comparison
  market_odds: { over_2_5, under_2_5, ... }                # cote brute d'ouverture
  market_implied_probability: { over_2_5, under_2_5, ... } # marge retirée
  market_overround: float

  # Niveau D/E — Edge et incertitude
  raw_edge: { over_2_5: float, ... }
  price_edge: { over_2_5: float, ... }

  # Niveau E — Qualification
  calibration_status: "OK" | "ZONE_BIAISEE_NON_CORRIGEE" | "INSUFFICIENT_VALIDATION" | "SCALE_NOT_ESTIMABLE"
  discrimination_status: "DEMONTREE" | "NON_DEMONTREE" | "NON_EVALUEE"
  data_quality: [ "INSUFFICIENT_HISTORY" | "AMBIGUOUS_COLLECTION_DAY" | "INCOMPLETE_MARKET_ODDS" | "DISTRIBUTION_INCONSISTENT" | "OK" ]
  scientific_gates: [ { name, triggered: bool, detail } ]
  operational_gates: [ { name, triggered: bool, threshold_used, detail } ]

  # Niveau F — Decision
  decision: "BET" | "NO_BET"
  decision_reason: [ str ]                                  # codes section 14, liste vide si BET

  # Auditabilité (section 17)
  engine_version: str
  parameters_snapshot: { operational thresholds utilisés }
```

Ce schéma est indicatif dans sa syntaxe (à adapter au langage/format de
sérialisation choisi en Phase B — dataclass Python, pydantic, JSON) mais
**complet dans son contenu** : aucun champ listé ci-dessus ne doit
manquer à l'implémentation finale, et aucun champ supplémentaire ne doit
introduire une information calculée hors des Niveaux A-F définis en
section 3.

---

## 16. Contrat point-in-time strict

Pour une décision à l'instant `T` (= `decision_time`, calculé par
`kickoff_utc − DECISION_OFFSET_HOURS`, `DECISION_OFFSET_HOURS = 2.0`) :

- **Features (Niveau A)** : aucun match d'entraînement avec
  `kickoff_utc ≥ T` (ou plus précisément, dont le résultat n'était pas
  encore connu à `T`) n'est inclus dans `matches_df` passé à
  `PoissonModel.fit`/`DixonColesModel.fit`/`XGModel.fit`. Délégué
  entièrement au filtrage déjà en place dans le pipeline de construction
  du dataset (`_goals_train_df`/`_xg_train_df`, à porter verbatim depuis
  `scripts/run_stage8_diagnostic_total_goals_over_under.py` vers un module
  `src/` de production — même logique, même filtre `<= decision_time`,
  aucune réécriture).
- **Calibration (Niveau B)** : `fit_scale_correction_as_of` ne considère
  que les matchs de calibration avec `decision_time < T` (section 7) —
  aucune donnée du match évalué, jamais.
- **Pricing (Niveau C)** : calcul déterministe à partir des sorties du
  Niveau B — aucune donnée externe supplémentaire, rien à contrôler ici
  au-delà de la correction structurelle de la section 6.
- **Gates (Niveau E)** : les gates scientifiques (section 12) n'utilisent
  que des données déjà disponibles à `T` (nombre de matchs, championnat,
  complétude de la cote d'ouverture) — jamais le résultat du match ni la
  cote de clôture.
- **Décision (Niveau F)** : dérivée exclusivement des sorties A-E.
- **Cotes de clôture** : **strictement exclues** de toute étape ci-dessus
  — contrôle structurel : aucune fonction des Niveaux A-F n'importe
  `closing_odds_1x2_by_bookmaker`/`closing_over_under_2_5_by_bookmaker`
  (section 4.4, 9, 18).
- **Contrôles obligatoires à ajouter en Phase B** :
  1. Une assertion explicite `decision_time = kickoff_utc − DECISION_OFFSET_HOURS`
     calculée une seule fois par décision, jamais recalculée différemment
     à deux endroits du pipeline (risque d'incohérence subtile).
  2. Un test qui vérifie, pour chaque input consommé, que sa
     `knowledge_time` documentée est `<= decision_time` (généralisation du
     principe déjà appliqué dans tous les tests `tests/leakage/*` d'E1-E16).
  3. Aucun appel à `debug_get_full_table` (ou tout mécanisme équivalent
     donnant un accès complet aux données) depuis un module de décision —
     règle déjà actée dans `architecture.md`.

---

## 17. Logging / auditabilité

Pour reconstituer après coup « pourquoi ce match a produit BET ou NO
BET », chaque décision doit journaliser :

| Champ | Contenu |
|---|---|
| `engine_version` | Identifiant de version du code du moteur (commit ou tag) |
| `parameters_snapshot` | Valeurs exactes de tous les `OPERATIONAL THRESHOLD` utilisés pour cette décision (section 13) |
| `models_snapshot` | `(λ, μ, [ρ])` et `n_train_matches` par modèle (Niveau A, déjà dans la sortie structurée) |
| `calibration_snapshot` | `scale_c`, `n_calibration_used` (Niveau B) |
| `gates_snapshot` | État complet de `scientific_gates`/`operational_gates` (Niveau E) |
| `market_snapshot` | Cote de marché exacte utilisée, horodatage de collecte, bookmaker |
| `fair_price_calculation` | `fair_price` et la probabilité source dont il dérive |
| `final_decision` | `decision` + `decision_reason` |

L'objet de sortie structuré (section 15) contient déjà l'essentiel de ces
champs — le logging consiste à **persister** cet objet complet à chaque
décision (jamais un résumé partiel), avec un horodatage de génération
distinct de `timestamp_decision` (moment de calcul vs moment de la
décision sportive).

---

## 18. Tests à prévoir (avant toute implémentation)

| Catégorie | Contenu | Précédent direct dans le projet |
|---|---|---|
| **Unit tests** | Chaque fonction portée (`over_under_probs`, `total_goals_distribution`, `fit_scale_correction_as_of`, `attach_walk_forward_scale`, gates individuels) testée isolément avec des cas synthétiques | `tests/unit/test_e7_*`, `test_e8_*` |
| **Integration tests** | Pipeline complet Niveau A→F sur un petit jeu de matchs synthétiques, vérifiant que chaque niveau consomme exactement la sortie du précédent sans court-circuit | Nouveau — inspiré du style `tests/unit/test_economic_dataset.py` |
| **Point-in-time / leakage tests** | (a) Aucune fonction de décision n'importe `closing_odds_1x2_by_bookmaker`/`closing_over_under_2_5_by_bookmaker` (inspection AST, comme `test_e16_never_reimplements_point_in_time_filtering`) ; (b) déplacer un match dans le futur ne change jamais une décision antérieure (comme `test_walk_forward_logistic_moving_a_row_to_the_future_never_changes_earlier_predictions`, E16) ; (c) `fit_scale_correction_as_of`/`attach_walk_forward_scale` n'utilisent jamais `test_df` dans le calcul de `c` | `tests/leakage/test_e*_point_in_time.py` (16 précédents directs) |
| **Distribution consistency tests** | `check_distribution_validity`, `check_over_under_monotonic`, `check_over_under_matches_distribution` testés par `hypothesis` sur tirages aléatoires de `(λ, μ, ρ, c)`, comme E7 §6 | `tests/unit/test_e7_total_goals_distribution.py` (200 tirages) |
| **Calibration tests** | Vérifier que `calibration_zone_gate`/`general_calibration_gate` se déclenchent exactement sur les tranches identifiées par E11, ni plus ni moins | Nouveau, mais logique directement dérivée d'E11 |
| **Market conversion tests** | `remove_overround_proportional`, `compare_model_to_market`, `validate_odds` — déjà couverts, à ne pas retester différemment | `tests/unit/test_overround.py`, `test_model_vs_market.py` (à vérifier/compléter si absents) |
| **Decision/gating tests** | Pour chaque gate scientifique et opérationnel, un cas qui le déclenche et un cas qui ne le déclenche pas ; vérifier qu'un gate scientifique échoué produit toujours `NO_BET` avec le bon `decision_reason`, jamais un `BET` | Nouveau |
| **Regression tests** | Rejouer les résultats numériques déjà connus d'E7/E8 (facteurs `c` publiés en section 2.4/2.5 de `research_framework.md`) sur le corpus réel figé, vérifier l'identité stricte après portage `scripts/` → `src/` | Nouveau, condition de non-régression du portage (section 1) |
| **Determinism tests** | Deux exécutions du pipeline complet sur les mêmes données produisent une sortie structurée strictement identique (aucun aléa non seedé) | Cohérent avec `docs/decisions/0004-reproductibilite-deterministe.md` |

**Condition non négociable, reformulée du protocole général du projet** :
le futur moteur ne doit jamais pouvoir produire une décision valide à
partir de données futures — chaque catégorie de test ci-dessus doit
inclure au moins un cas qui **injecte délibérément** une donnée future et
vérifie que le moteur soit l'ignore, soit échoue explicitement (jamais un
échec silencieux qui produirait quand même une décision).

---

## 19. Minimum Viable Final Engine

Reprise et détail technique de la section 13 de `research_synthesis_e1_e16.md`.
Contient **uniquement** les briques `VALIDÉ SCIENTIFIQUEMENT` et les
`CHOIX ARCHITECTURAL` indispensables ; exclut explicitement tout ce qui
est `HYPOTHÈSE FUTURE` :

**Inclus** :
- Niveau A : `poisson_simple` seul comme modèle **décisionnel**
  (`dixon_coles`/`xg_model` calculés pour traçabilité, jamais utilisés
  dans le calcul de la décision elle-même dans le MVP).
- Niveau B : correction scalaire walk-forward E7/E8 (section 7), seuils
  Over 1.5/2.5/3.5 uniquement (les seuls réellement validés, section 7 de
  la synthèse) — Over 0.5/4.5 calculables mais marqués
  `INSUFFICIENT_VALIDATION`, affichables non qualifiés.
- Niveau C : pricing déterministe (`fair_price`).
- Niveau D : comparaison à B365 ouverture uniquement (couverture 100 %,
  seule cote systématiquement disponible) — Pinnacle/BW/WH/LB **exclus du
  MVP**, réservés à un usage d'audit hors ligne.
- Niveau E : tous les gates scientifiques de la section 12 sauf ceux
  portant sur des données non incluses dans le MVP (ex. gates
  multi-bookmaker, sans objet si un seul bookmaker est utilisé).
- Niveau F : `NO_BET` par défaut ; **aucune règle positive de conversion
  edge→pari n'est implémentée dans le MVP** — le MVP ne produit jamais
  `BET` par une règle validée, faute d'une telle règle validée par
  E1-E16 (E1 a démontré qu'une règle simple, EV>0, est perdante). Le MVP
  s'arrête donc, en pratique, au Niveau E (Qualification) pour toute
  finalité de mise réelle, et ne complète le Niveau F que par
  l'abstention.

**Exclu du MVP (`HYPOTHÈSE FUTURE`, à ne pas coder maintenant)** :
- Tout ensemble de modèles.
- Toute règle numérique convertissant un edge qualifié en `BET`.
- Toute utilisation de Pinnacle/BW/WH/LB au-delà de l'audit hors ligne.
- Tout traitement spécial du mouvement de marché (E16, rejeté).
- Toute recalibration locale (E14, rejetée).
- Tout coefficient ou traitement différencié pour un championnat au-delà
  du gate de discrimination (E15).

---

## 20. Mise à jour de `docs/architecture.md`

Une section pointant vers ce document est ajoutée à `docs/architecture.md`
(voir modification appliquée en parallèle de ce document) — sans
duplication du contenu détaillé, qui reste la propriété de ce fichier.

---

## 21. Critère de réussite

Un développeur qui lit ce document doit savoir, sans avoir à
réinterpréter `docs/research_synthesis_e1_e16.md` ni `docs/research_framework.md` :

- **Quels modules coder** : `football_model/goal_distribution.py`,
  `calibration_engine/scalar_correction.py`, et un nouveau module
  d'orchestration (Niveaux A-F, nom laissé à la Phase B) — le reste
  (modèles, overround, edge, comparaison marché, matching, résolution
  temporelle) existe déjà et se réutilise tel quel (section 1).
- **Quelles données utiliser/exclure** : section 4.
- **Quelles formules utiliser** : sections 6, 7, 10, 11 (toutes tracées à
  une fonction existante ou une formule déjà validée).
- **Quelles sorties produire** : section 15.
- **Quels gates appliquer** : sections 12-13.
- **Quand retourner `NO BET`** : section 14.
- **Quels tests écrire** : section 18.

---

## 22. Validation documentaire

- Chaque décision architecturale de ce document a été vérifiée contre
  `docs/research_synthesis_e1_e16.md` (sections 2, 4-14) et
  `docs/research_framework.md` (sections R, S, V, Y, Z, AA pour E7, E8,
  E11, E14, E15, E16 respectivement) — aucune affirmation non tracée n'a
  été introduite.
- Aucun seuil numérique de décision de pari n'a été fixé (section 13) —
  toute valeur par défaut proposée est explicitement marquée
  `PARAMÈTRE OPÉRATIONNEL À VALIDER`.
- E14 (section 8), E15 (section 9) et E16 (sections 4.4, 12) sont
  chacune vérifiées comme **non transformées en source d'edge** : E14
  n'introduit aucune correction, E15 n'introduit aucun coefficient, E16
  n'introduit aucune lecture de cote de clôture dans le chemin de
  décision.
- Aucun résultat historique d'E1-E16 n'a été modifié — ce document ne
  fait que consommer les conclusions déjà écrites.
- Suite de tests complète exécutée après rédaction (aucun code de
  production modifié à ce stade — voir résultat ci-dessous) ; aucun test
  n'a été modifié pour faire passer la suite.
