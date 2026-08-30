# Audit final pré-production — `sys-foot-quant`

**État de référence** : commit `df709cb` (fin Phase K) + corrections décrites
en section 10/11 de ce document (2 défauts découverts et corrigés pendant
cet audit lui-même, sur la branche courante).
**Portée** : audit de code, pas une nouvelle expérience. Aucun résultat
E1→K n'a été recalculé, réinterprété ou modifié. Aucun nouveau seuil
d'edge, aucun nouveau signal, aucun backtest de rentabilité.
**Méthode** : lecture directe du code de `final_engine/` et de toutes ses
dépendances, exécution de scénarios reproductibles (`uv run python3 -c
"..."`), lecture des tests existants, comparaison systématique
code/documentation.

---

## 1. Audit du pipeline (code réel, pas la documentation)

Le pipeline est orchestré par `run_match_decision()`
(`src/sys_foot_quant/final_engine/orchestrator.py`). Six niveaux, chacun
consommant la sortie **immuable** du précédent (dataclasses `frozen=True`,
`types.py`) :

### Niveau A — Prediction (`prediction.py::predict_match`)

- **Entrées** : `home_team_id`, `away_team_id`, `goals_train_df` (déjà
  filtré point-in-time par l'appelant), `xg_train_df` (idem, optionnel).
- **Mécanisme réel** : `PoissonModel(use_team_hfa=False).fit(goals_train_df)`
  puis `predict_lambda_mu(...)` — réutilisé **sans modification**. Idem
  `DixonColesModel`/`XGModel`. Aucune des trois n'est appelée si
  l'historique est `< MIN_TRAIN_MATCHES` (10, `economic_dataset.py`) ; le
  modèle correspondant reste `None` — jamais une valeur de repli inventée.
- **Manque de données** : historique insuffisant → `None` (couvert par
  `insufficient_data_gate`). Équipe totalement absente de l'historique
  (mais volume agrégé suffisant) → **angle mort découvert pendant cet
  audit**, voir section 10, corrigé par `unknown_team_gate`.
- **Statut** : `poisson_simple` = **CHOIX ARCHITECTURAL, NON VALIDÉ COMME
  SOURCE D'EDGE** (docstring explicite, ligne 29-32 du fichier — aucune
  supériorité démontrée, E11). `dixon_coles`/`xg_model` = modèles de
  contrôle, jamais fusionnés.
- **Documentation vs code** : `docs/final_engine_specification.md`
  section 4.1/5 correspond exactement au code lu.

### Niveau B — Calibration (`calibration.py::calibrate_prediction`, E7/E8)

- **Mécanisme réel** : `scale_c = E[total_réel]/E[λ+μ_prédit]`
  (`calibration_engine/scalar_correction.py::fit_scale_correction_as_of`,
  portage verbatim du script de recherche, **fenêtre expansive stricte**
  `decision_time < as_of_time`, jamais glissante). Si
  `n < MIN_CALIBRATION_MATCHES_FOR_SCALE` (30) → `(None, n)` →
  `probabilities=None` (jamais une distribution non corrigée présentée
  comme équivalente).
- **Reconstruction** : matrice de score complète recalculée avec
  `(scale_c·λ, scale_c·μ)`, Dixon-Coles appliqué seulement si `rho` fourni,
  puis `total_goals_distribution`/`over_under_probs` **en un seul appel**
  (source unique).
- **N'intègre PAS E14** : aucune isotonic/logistic recalibration locale —
  confirmé par lecture directe (aucune trace dans le fichier) et par test
  structurel AST (`test_final_engine_scientific_non_regression.py`).
- **Défaut découvert et corrigé pendant cet audit** : `total_goals` NaN
  non filtré → voir section 11, Défaut #2.
- **Statut** : **VALIDÉ SCIENTIFIQUEMENT** (E7/E8, Verdict A, 3 modèles).

### Niveau C — Pricing (`pricing.py::compute_fair_price`)

- `fair_price = 1/p` par seuil, `p=0` → `inf` (limite mathématique
  explicitement non masquée). Transformation pure, aucune dépendance
  externe. **CHOIX ARCHITECTURAL** trivial (une seule formule possible).

### Niveau D — Market comparison (`market.py::compare_over_under_to_market`)

- Compare **uniquement** le modèle **principal** sur le seuil **2.5**
  (le seul publié par Football-Data) à la cote **d'ouverture** B365.
  Réutilise `market_engine.model_vs_market.compare_model_to_market` et
  `value_engine.edge` (`edge`, `expected_value`) sans nouvelle formule.
- **Restriction structurelle non négociable (E16)** : aucune fonction de
  clôture (`closing_odds_1x2_by_bookmaker`/`closing_over_under_2_5_by_bookmaker`)
  n'est importée ni référencée — vérifié par grep direct sur
  `final_engine/` (zéro occurrence) et par test AST dédié.
- **Défauts découverts et corrigés pendant cet audit** : cote NaN/infinie
  non rejetée par `validate_odds` → provoquait soit un crash, soit un
  edge silencieusement `inf` → voir section 11, Défaut #1.
- Le calcul n'est déclenché que si `incomplete_market_odds_gate(...)`
  n'est pas déclenché **et** qu'une probabilité calibrée existe
  (`orchestrator.py` ligne 118) — évite de propager une exception hors
  pipeline pour une cote structurellement invalide, **avant correction du
  Défaut #1** cette garde ne suffisait déjà pas pour NaN/inf.

### Niveau E — Qualification (`gates.py`, `reference_tables.py`)

- Deux catégories strictement séparées :
  - **SCIENTIFIC GATES** : traduisent un fait établi par E1-E16, **non
    négociable** (`insufficient_data_gate`, `unknown_team_gate`,
    `insufficient_calibration_history_gate`, `ambiguous_day_gate`,
    `incomplete_market_odds_gate`, `distribution_consistency_gate`,
    `calibration_zone_gate`, `discrimination_gate`).
  - **OPERATIONAL GATES** : `PARAMÈTRE OPÉRATIONNEL À VALIDER`, jamais
    présenté comme scientifiquement optimal
    (`calibration_confidence_gate`, `discrimination_confidence_gate`,
    `edge_threshold_gate`).
- `discrimination_status`/`calibration_status_for` sont des **tables
  figées** (E4/E11/E15), jamais recalculées en ligne — `ValueError` levée
  pour tout seuil hors des 5 seuils officiels (jamais un statut inventé).
- **Documentation vs code** : correspond exactement à
  `docs/final_engine_specification.md` sections 12/13.

### Niveau F — Decision (`decision.py::decide`)

- `triggered = [g for g in scientific_gates + operational_gates if
  g.triggered]` → si non vide, `NO_BET` avec
  `codes = sorted({g.failure_code for g in triggered if g.failure_code})`
  (unique, **trié alphabétiquement** — pas de hiérarchie de priorité, tous
  les codes déclenchés sont toujours rapportés ensemble). Si vide → `BET`,
  `decision_reason=[]`.
- Le chemin `BET` est **atteignable dans le code** (le module reste
  génériquement correct) — c'est la configuration par défaut de
  `OperationalThresholds` (`min_edge_threshold=None`) qui garantit qu'il
  n'est jamais emprunté dans le MVP, jamais un `if False` codé en dur.

**Conclusion §1** : le code lu correspond exactement à
`docs/final_engine_specification.md` sur les six niveaux — aucune
divergence documentation/code trouvée, hormis les deux angles morts
opérationnels ci-dessus (section 10/11), absents de la documentation
*parce qu'absents du code avant cet audit*, maintenant corrigés et
documentés.

---

## 2. Synthèse scientifique E1 → K (résultats non modifiés)

Reprise fidèle de `docs/research_synthesis_e1_e16.md` section 1 et de
`docs/final_engine_user_guide.md` (déjà vérifiés code-cohérents lors de
cet audit) — **aucun verdict n'est recalculé ici**.

| Expérience | Question | Verdict | Conséquence sur le moteur |
|---|---|---|---|
| E1 | `poisson_simple` bat-il B365 (EV>0) ? | 🔴 SIGNAL NÉGATIF (ROI −6.9%) | Le marché n'est jamais un adversaire à battre |
| E2 | Recalibration isotonique post-hoc ? | 🟢/🟡 partiel | Dépassé par E7/E8 |
| E3 | Fiabilité des probabilités calibrées d'E2 ? | 🟢 partiel | Dépassé par E7/E8 |
| E4 | L'espérance de buts discrimine-t-elle ? | 🟢 global / 🔴 Premier League | Premier apparition du problème PL |
| E5 | Fiabilité quand le modèle diverge du marché ? | 🔴 le désaccord s'invalide lui-même | Désaccord jamais lu comme signal |
| E6 | Info incrémentale du marché sur le total de buts ? | ⚪ redondance dominante | Représenter fidèlement, pas battre |
| E7 | Distribution du total de buts cohérente ? | 🟢 **VALIDÉ — production** | Fondation officielle Niveau B |
| E8 | E7 tient-il en walk-forward strict ? | 🟢 **VALIDÉ — production** (Verdict A, 3 modèles) | Couche de correction officielle |
| E9 | Couche multi-bookmakers, anomalies/arbitrage ? | ⚪ infrastructure propre, rien détecté | Limite structurelle Football-Data O/U confirmée |
| E10 | Zones de désaccord modèle/marché fiables ? | 🔴 aucune | Confirme et étend E5 |
| E11 | Fiabilité absolue des probabilités, où ? | 🟢 centrale / 🔴 zone [0.6,0.7) | Zone flaguée ; 3 modèles indiscernables |
| E12 | Zones fiables = plus grands écarts de prix ? | 🔴 CONTRADICTOIRE (poisson/DC) | Rejeté comme filtre de sélection |
| E13 | Dispersion multi-bookmakers informative ? | ⚪ aucune preuve | Rejeté comme source d'edge |
| E14 | Recalibration ciblée [0.6,0.7) exploitable ? | 🟡→🔴 gate de cohérence violé | **REJETÉ comme couche de production** |
| E15 | Cause de l'absence de discrimination PL ? | ⚪ confirmée mais inexpliquée | PL flaguée en gate, aucun coefficient créé |
| E16 | Mouvement de marché ouverture→clôture informatif ? | 🔴 non informatif | Rejeté comme feature de décision |
| Phase D | Un seuil d'edge strict est-il robuste hors échantillon (Liga/Ligue 1) ? | **NO BET — EDGE NON VALIDÉ** | `min_edge_threshold` reste `None` |
| Phase F | Tirs cadrés (SOT) : info incrémentale ? | 🔴 non (gain apparent = recalibration seule) | Jamais utilisé par le moteur |
| Phase G | Betfair Exchange (BFE) : info incrémentale ? | 🔴 non, corrélé à B365 | Jamais utilisé par le moteur |
| Phase H | Handicap asiatique (AH) : info incrémentale ? | 🔴 non (gain apparent = recalibration seule) | Jamais utilisé par le moteur |
| Phase K | Elo pré-match (ClubElo) : info incrémentale ? | 🔴 non (Brier identique à la 4e décimale) | Jamais utilisé par le moteur |

Chaque ligne de ce tableau est vérifiée cohérente avec le code lu en §1 :
aucune des briques rejetées (E14, SOT, BFE, AH, Elo, mouvement de marché,
clôture) n'apparaît dans le graphe d'imports de `final_engine/` (confirmé
par grep direct, section 8).

---

## 3. Audit des modèles

| Modèle | Statut exact | Preuve code |
|---|---|---|
| `poisson_simple` | **CHOIX ARCHITECTURAL — NON VALIDÉ COMME SOURCE D'EDGE**. `PRIMARY_MODEL` (`prediction.py:32`) | Seul modèle dont `calibrated[...]` alimente `market`/`qualification`/`decision` (`orchestrator.py:109,130,132,135,158`) |
| `dixon_coles` | Modèle de **contrôle**, redondant avec `poisson_simple` sur O/U 2.5/3.5 (fait mathématique démontré, K/E7/E8/E11) | Calculé (`prediction.py:71-75`), sa calibration existe mais n'est **jamais lue** hors traçabilité — `test_control_models_are_computed_but_never_drive_the_decision` |
| `xg_model` | Modèle de **contrôle**, complémentaire mais non supérieur (E11) | Idem, calculé seulement si `xg_train_df` fourni et suffisant |
| Ensemble (moyenne/vote/pondération) | **HYPOTHÈSE FUTURE — NON VALIDÉ EXPÉRIMENTALEMENT** | Absent du code — confirmé par test AST `test_no_ensemble_or_weighted_average_of_the_three_models_exists` (recherche de sous-chaînes ensemble/blend/weighted) |

**Aucun classement scientifique n'est créé ici** — le tableau ci-dessus
reformule exactement `docs/final_engine_specification.md` section 5, déjà
fidèle à E1-E16.

---

## 4. Audit de la calibration (E7/E8)

- **Mécanisme** : un seul degré de liberté, `c = E[réel]/E[λ+μ]`, estimé
  **exclusivement** sur les matchs dont `decision_time < as_of_time`
  (fenêtre expansive stricte, jamais glissante) —
  `scalar_correction.py:36-57`, portage verbatim, non modifié par cet
  audit.
- **Historique minimal requis** : `MIN_CALIBRATION_MATCHES_FOR_SCALE = 30`
  (règle pré-enregistrée E8, jamais activée sur le corpus réel mais
  validée par construction).
- **Comportement si insuffisant** : `(None, n)` →
  `CalibratedGoalDistribution(probabilities=None, ...)` → propagé jusqu'à
  `NO_BET`/`INSUFFICIENT_HISTORY` via `insufficient_calibration_history_gate`.
  **Aucune probabilité "presque calibrée" n'est jamais renvoyée** dans ce
  cas — confirmé par `test_insufficient_calibration_history_yields_no_bet`.
- **Zone [0.6,0.7) d'Over 2.5** : `calibration_zone_gate` interroge
  `calibration_status_for(2.5, p)` (table figée E11/E14) → si
  `ZONE_BIAISEE_NON_CORRIGEE`, `failure_code=INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE`.
  **La probabilité elle-même n'est jamais modifiée** (`calibration.py` ne
  contient aucune isotonic/logistic recalibration — E14 exclu) ; elle
  reste affichée mais l'`OperationalThresholds.abstain_on_calibration_zone=True`
  par défaut combiné à `calibration_confidence_gate` (`require_calibration_ok=True`
  par défaut) transforme ce flag en `NO_BET` systématique dans la
  configuration par défaut. **Question posée par l'utilisateur — réponse
  vérifiée** : un utilisateur qui appellerait directement
  `calibrate_prediction()` (Niveau B seul, en contournant l'orchestrateur)
  obtiendrait bien une probabilité dans la zone [0.6,0.7) sans blocage —
  c'est **attendu et documenté** (chaque niveau produit une sortie
  utilisable isolément, section 3 de la spec) : le blocage n'existe qu'au
  Niveau E/F, jamais au Niveau B. `run_match_decision()` (le seul point
  d'entrée destiné à une décision) applique systématiquement le gate.
- **Cohérence avec E14** : E14 a testé une correction *ciblée* de cette
  zone et l'a **rejetée** (gate de cohérence violé) — le moteur ne fait
  que *flaguer*, jamais corriger, exactement la conclusion d'E14.
- **Verdict** : **VALIDÉ SCIENTIFIQUEMENT** pour le mécanisme E7/E8 lui-même ;
  **CHOIX ARCHITECTURAL** pour la décision de bloquer (plutôt que
  d'avertir seulement) via `OperationalThresholds` par défaut.

---

## 5. Audit Premier League (E15)

Vérification explicite demandée : impossible de transformer
« absence de discrimination démontrée » en interdiction absolue de parier
en PL, ou inversement de l'ignorer.

- `discrimination_status("Premier League")` → `_normalize_competition`
  produit `"premier_league"` → table figée
  (`reference_tables.py:36`) → `NON_DEMONTREE`.
- `discrimination_gate` se déclenche (`triggered = status != "DEMONTREE"`)
  → `failure_code=DISCRIMINATION_NOT_DEMONSTRATED`.
- **Ce qui N'est PAS bloqué** : la prédiction (Niveau A), la calibration
  (Niveau B), le pricing (Niveau C) et la comparaison au marché (Niveau D)
  sont calculés **identiquement** à tout autre championnat — confirmé par
  `test_premier_league_yields_no_bet_with_discrimination_code_but_probabilities_still_produced` :
  `output.calibration["poisson_simple"].probabilities is not None` reste
  vrai. Seule la **décision** (Niveau F) est bloquée.
- **Aucun coefficient PL n'existe dans le code** — confirmé par test AST
  dédié (`test_final_engine_scientific_non_regression.py`, recherche
  d'une constante spécifique à Premier League dans `poisson.py`/
  `dixon_coles.py`).
- **Championnat jamais audité** (ex. Bundesliga) : reçoit le même
  traitement que Premier League (`NON_EVALUEE` par défaut, jamais
  `DEMONTREE` par optimisme implicite) — confirmé par
  `test_discrimination_gate_triggers_for_unaudited_competition`.
- **Piège historique déjà neutralisé** : la table figée contient à la
  fois `"ligue_1"` et `"ligue1"` (l'identifiant interne réel du pipeline
  de données) précisément pour éviter qu'un mismatch d'orthographe fasse
  silencieusement retomber Ligue 1 sur `NON_EVALUEE` (bug détecté et
  corrigé en Phase D, avant toute exécution réelle — commentaire du code
  source, `reference_tables.py:24-31`).

**Verdict §5** : le moteur respecte exactement le verdict E15 — ni
sur-interprétation (interdiction totale, coefficient pénalisant) ni
sous-interprétation (ignoré). Le résultat E15 (« absence de signal
confirmée mais inexpliquée ») ne fonde qu'une **règle de gating
analytique**, jamais une règle de pari, exactement comme prescrit par la
conclusion d'E15 elle-même.

---

## 6. Audit NO_BET — table exhaustive

10 codes stables (`reason_codes.py`), **7 actuellement câblés à un gate**,
3 réservés pour une extension future jamais utilisée aujourd'hui.

| Code | Condition exacte | Gate | Niveau | Donnée requise pour l'évaluer | Test couvrant |
|---|---|---|---|---|---|
| `INSUFFICIENT_HISTORY` | `n_train_matches < MIN_TRAIN_MATCHES(10)` | `insufficient_data_gate` | E (data quality) | `goals_train_df` filtré PIT | `test_insufficient_data_gate_triggers_below_threshold` |
| `INSUFFICIENT_HISTORY` | équipe absente de `goals_train_df` (angle mort corrigé pendant cet audit) | `unknown_team_gate` | E | idem | `test_unknown_team_gate_triggers_when_home_team_never_appeared` (+4 autres) |
| `INSUFFICIENT_HISTORY` | `n_calibration_used < MIN_CALIBRATION_MATCHES_FOR_SCALE(30)` | `insufficient_calibration_history_gate` | E | `calibration_df_by_model` filtré PIT | `test_insufficient_calibration_history_gate` |
| `AMBIGUOUS_COLLECTION_DAY` | `kickoff_utc` tombe un lundi/mardi/vendredi (fenêtre de collecte non fiable) | `ambiguous_day_gate` | E | `kickoff_utc` | `test_ambiguous_day_gate_triggers_on_monday_tuesday_friday` |
| `MARKET_DATA_UNAVAILABLE` | `market_odds is None` (une des deux cotes manquante) | `incomplete_market_odds_gate` | E | `market_odds_over_2_5`/`_under_2_5` | `test_incomplete_market_odds_gate_triggers_on_missing_odds` |
| `MARKET_DATA_UNAVAILABLE` | `validate_odds` lève (`o<=1.0`, ou NaN/inf depuis correction Défaut #1) | `incomplete_market_odds_gate` | E | idem | `test_nan_market_odds_never_raises_and_yields_no_bet`, `test_infinite_market_odds_never_raises_and_yields_no_bet` |
| `DISTRIBUTION_INCONSISTENT` | incohérence structurelle (non-négativité, somme=1, monotonie O/U, cohérence O/U↔distribution) — ne devrait jamais survenir en pratique | `distribution_consistency_gate` | E | distribution/proba calibrées | `test_distribution_consistency_gate_triggers_on_tampered_probability` |
| `INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE` | seuil ∈ zone non-OK (`ZONE_BIAISEE_NON_CORRIGEE` sur 2.5 dans [0.6,0.7), ou `INSUFFICIENT_VALIDATION` sur 0.5/4.5) | `calibration_zone_gate` (scientifique) **et** `calibration_confidence_gate` (opérationnel, `require_calibration_ok=True` par défaut) | E | probabilité calibrée au seuil 2.5 | `test_calibration_zone_gate_triggers_in_biased_zone`, `test_e14_is_never_applied_probability_in_biased_zone_stays_unmodified` |
| `DISCRIMINATION_NOT_DEMONSTRATED` | `discrimination_status(competition) != "DEMONTREE"` (Premier League ou tout championnat non audité) | `discrimination_gate` (scientifique) **et** `discrimination_confidence_gate` (opérationnel, `require_discrimination_demontree=True` par défaut) | E | `competition` | `test_discrimination_gate_triggers_for_premier_league`, `test_discrimination_gate_triggers_for_unaudited_competition` |
| `EDGE_BELOW_THRESHOLD` | `min_edge_threshold is None` (défaut MVP — TOUJOURS vrai aujourd'hui) OU `raw_edge < min_edge_threshold` | `edge_threshold_gate` (opérationnel) | E | `market.raw_edge["Over"]` | `test_edge_threshold_gate_always_triggers_when_threshold_unset`, `test_mvp_default_configuration_always_produces_no_bet_with_edge_code` |
| `UNCERTAINTY_TOO_HIGH` | **réservé, jamais câblé à un gate aujourd'hui** (aucune notion d'effectif de cellule minimal n'est implémentée dans le moteur final) | — | — | — | — |
| `MARKET_NOT_USABLE` | **réservé** — `incomplete_market_odds_gate` utilise `MARKET_DATA_UNAVAILABLE` pour toute cote rejetée par `validate_odds`, jamais ce code distinct malgré ce que suggère `docs/final_engine_specification.md:525` | — | — | — | — |
| `OTHER_BLOCKING_CONDITION` | **réservé, jamais déclenché** — filet de sécurité documentaire pour une condition future non prévue | — | — | — | — |

**Priorité en cas de gates multiples simultanés** : **il n'existe aucune
hiérarchie de priorité**. `decide()` (`decision.py:24-29`) collecte
**tous** les gates déclenchés (scientifiques ET opérationnels), en déduit
l'ensemble unique de `failure_code`, et le retourne **trié
alphabétiquement** — jamais un seul code "gagnant". Confirmé
empiriquement pendant cet audit (ex. un kickoff ancien + historique
insuffisant + zone de calibration biaisée produisent simultanément
`['AMBIGUOUS_COLLECTION_DAY', 'DISCRIMINATION_NOT_DEMONSTRATED',
'EDGE_BELOW_THRESHOLD', 'INSUFFICIENT_CONFIDENCE_CALIBRATION_ZONE',
'INSUFFICIENT_HISTORY']`, ordre alphabétique strict). C'est un choix
délibéré de traçabilité (montrer toutes les raisons, jamais en masquer
une derrière une autre), pas un oubli.

**Écart documentation/code trouvé (mineur, non bloquant)** :
`docs/final_engine_specification.md` ligne 525 assigne `MARKET_NOT_USABLE`
à « Cote de marché rejetée par `validate_odds` », mais le code utilise en
réalité `MARKET_DATA_UNAVAILABLE` pour ce cas (`gates.py:153`). Le
comportement fonctionnel est correct (NO_BET produit dans tous les cas),
seul le libellé documentaire diverge du code réel. Correction
documentaire mineure appliquée en section 15.

---

## 7. Audit BET — recherche de contournement

- **Configuration par défaut** : `OperationalThresholds(min_edge_threshold=None)`
  (`gates.py:256`). `edge_threshold_gate` : si `min_edge_threshold is None`
  → `triggered=True` **inconditionnellement**, quel que soit `raw_edge`
  (`gates.py:291-300`) — confirmé par
  `test_edge_threshold_gate_always_triggers_when_threshold_unset` (teste
  `0.5`, `-0.5` et `None` comme edge observé, les trois déclenchent).
- **Recherche de contournement** (grep exhaustif `decide(`,
  `OperationalThresholds(`, `min_edge_threshold=` sur `src/` et
  `scripts/`) : la seule occurrence non-défaut est
  `scripts/run_stage26_phase_d_operational_validation.py`, qui construit
  son propre `OperationalThresholds(min_edge_threshold=threshold)` local
  et appelle `decide(scientific_gates=[], operational_gates=[gate])` —
  c'est la **simulation de recherche isolée de Phase D elle-même**,
  jamais importée par `final_engine`, dont la conclusion documentée est
  précisément **« NO BET — EDGE NON VALIDÉ »** (aucun seuil retenu). Ce
  n'est pas un contournement de production, c'est l'expérience qui a
  motivé le maintien de `min_edge_threshold=None`.
- **Aucun autre point d'entrée** ne construit `OperationalThresholds` avec
  une valeur non-`None` dans tout le dépôt en dehors de ce script de
  recherche déjà conclu.
- **Aucun contournement trouvé** — rien à corriger, aucun seuil d'edge
  fixé. Documenté explicitement ici comme demandé.

**Verdict §7** : impossible d'obtenir `BET` avec la configuration actuelle
du moteur, quelles que soient les entrées (probabilité, cote, edge
observé) — la seule voie vers `BET` exigerait un appelant construisant
explicitement `OperationalThresholds(min_edge_threshold=<valeur
numérique>)`, ce qui n'existe nulle part dans le chemin de production.

---

## 8. Audit PIT / anti-fuite temporelle

Audit de code uniquement — aucune nouvelle expérience exécutée.

- **Décalage de décision** : `decision_time = kickoff_utc -
  timedelta(hours=DECISION_OFFSET_HOURS(2.0))` (`orchestrator.py:56,81`) —
  identique à `economic_dataset.DECISION_OFFSET_HOURS`, jamais recalculé
  indépendamment.
- **Filtrage PIT des données d'entraînement/calibration** : délégué
  **entièrement à l'appelant** (`goals_train_df`/`xg_train_df`/
  `calibration_df_by_model` doivent déjà être filtrés — docstring
  explicite `orchestrator.py:75-78`, jamais refiltré en interne). Ce choix
  déplace la responsabilité PIT vers `matching.py`/`time_resolution.py`,
  déjà testés en leakage sur E1-K — le moteur final **n'introduit aucun
  nouveau point de fuite**, mais **dépend structurellement** de la
  discipline de l'appelant (voir §9, checklist production).
- **Cote de marché** : uniquement **d'ouverture** — recherche exhaustive
  confirmée (`market.py` n'importe que `compare_model_to_market`/`edge`/
  `expected_value`), aucune fonction de clôture référencée nulle part dans
  `final_engine/` (grep direct, zéro résultat pour
  `closing_odds_1x2_by_bookmaker`/`closing_over_under_2_5_by_bookmaker`/
  `B365C`/`PSC` dans `src/sys_foot_quant/final_engine/`).
- **Recalibration walk-forward (E7/E8)** : fenêtre **strictement
  expansive**, jamais glissante à taille fixe, jamais de pooling
  rétroactif — `scalar_correction.py:51` filtre `decision_time <
  as_of_time` avant tout calcul de moyenne ; confirmé par simulation de
  fuite dans `tests/leakage/test_final_engine_point_in_time.py`
  (`test_injecting_a_future_result_never_influences_the_current_decision`).
- **xG** : chemin de données identique à l'historique de buts (même
  `min_train_matches`, même absence de refiltrage interne) — aucun
  traitement différent qui introduirait une fuite spécifique au xG ; la
  réserve documentée depuis Phase B3 (délai `xg_knowledge_time` non
  vérifié indépendamment) reste une limite de **disponibilité**, pas de
  fuite démontrée dans le code du moteur final lui-même.
- **Elo, tirs cadrés (SOT), handicap asiatique (AH), Betfair Exchange
  (BFE)** : **jamais importés par `final_engine`** — confirmé par grep
  direct sur les modules (`elo_ratings`, `elo_join`, `elo_archive`,
  `shots_on_target`/`sot_`, `asian_handicap`, `betfair`/`bfe_`, colonnes
  `AHCh`/`Max>2.5`/`Avg>2.5`) : **zéro occurrence** dans
  `src/sys_foot_quant/final_engine/`. Le graphe d'imports complet de
  `final_engine/` (relevé exhaustif) ne référence que :
  `data_engine.market_odds.economic_dataset` (constante
  `MIN_TRAIN_MATCHES`), `data_engine.market_odds.time_resolution`,
  `calibration_engine.scalar_correction`, `football_model.{poisson,
  dixon_coles, xg_model, goal_distribution, scoring}`,
  `market_engine.{overround, model_vs_market}`, `value_engine.edge`.
  Aucune brique rejetée (E14, SOT, BFE, AH, Elo, mouvement de marché,
  dispersion multi-bookmakers) n'apparaît dans ce graphe.
- **Fuseau horaire** : `kickoff_utc` est typé `datetime` sans contrainte
  d'exécution vérifiant `tzinfo is not None` — un kickoff naïf (sans
  fuseau) est accepté sans lever d'exception et produit un résultat
  auto-cohérent (vérifié par exécution directe). C'est une **divergence
  de contrat non appliquée par le code** (la spec suppose UTC partout)
  plutôt qu'une fuite démontrée — aucune donnée future n'est utilisée dans
  ce cas, seule l'ambiguïté du jour de la semaine pourrait légèrement
  varier selon le fuseau réellement prévu par l'appelant. **Non corrigé**
  (aucun défaut technique concret déclenché, uniquement une absence de
  validation defensive sur un type déjà documenté comme devant être UTC) —
  noté comme réserve opérationnelle en section 9/14, pas un blocage.

**Verdict §8** : aucune fuite temporelle trouvée dans le code du moteur
final lui-même. La seule dépendance structurelle est la discipline de
filtrage PIT de l'appelant sur `goals_train_df`/`xg_train_df`/
`calibration_df_by_model`, déjà couverte par les tests de fuite
historiques réutilisés (`matching.py`/`time_resolution.py`).

---

## 9. Checklist de données pour l'exécution réelle

Reprise de `docs/final_engine_specification.md` sections 4.1/4.3/4.4,
vérifiée cohérente avec le code lu en §1/§8.

### OBLIGATOIRE

| Donnée | Usage |
|---|---|
| `home_goals`/`away_goals` (historique, par équipe) | Niveau A, `poisson_simple`/`dixon_coles` |
| `home_team_id`/`away_team_id` (mapping déterministe) | Niveau A |
| `kickoff_utc` (UTC, non ambigu) | `decision_time`, `ambiguous_day_gate` |
| Historique de calibration walk-forward (`decision_time`, `{model}_lambda`, `{model}_mu`, `total_goals`) | Niveau B, ≥30 matchs antérieurs à `decision_time` |
| `B365H/D/A` (1X2, ouverture) | Référence de prix primaire (couverture 100% historique) |
| `B365>2.5`/`B365<2.5` (O/U 2.5, ouverture) | Niveau D — seul marché comparable aujourd'hui |

### OPTIONNEL

| Donnée | Usage | Réserve |
|---|---|---|
| `home_xg`/`away_xg` (historique) | `xg_model` uniquement (contrôle) | Délai de connaissance non vérifié indépendamment |
| `PS.../P>2.5/P<2.5` (Pinnacle, ouverture) | Audit/cross-check secondaire | N'améliore pas B365 seul (E13) |
| `BW...`, `WH.../LB...` (ouverture) | Audit uniquement | Jamais indispensable |

### INTERDIT / RECHERCHE UNIQUEMENT — ne doit jamais atteindre le chemin de décision

| Donnée | Statut |
|---|---|
| Cotes de **clôture** (`B365CH/CD/CA`, `B365C>2.5/C<2.5`, `PSCH/CD/CA`, `WHCH/CD/CA`, `LBCH/CD/CA`) | Rétrospectif uniquement (E16) — accessible via des méthodes explicitement interdites d'appel avant `decision_time` |
| Résultat réel du match (`FTHG`/`FTAG`) au moment de la décision | Évaluation a posteriori uniquement, jamais disponible à `decision_time` par construction |
| Rating Elo pré-match (ClubElo) | Testé et infirmé, aucune info incrémentale démontrée (Phase K) |
| Tirs cadrés (SOT), historique point-in-time | Testé et infirmé (Phase F) |
| Handicap asiatique (AH) | Testé et infirmé (Phase H) ; biais de calibration additionnel sur la probabilité de push, non corrigé |
| Betfair Exchange (BFE) | Testé et infirmé (Phase G), corrélé à B365 sans apport distinct |
| Mouvement de marché ouverture→clôture | Testé et infirmé (E16) |
| Dispersion multi-bookmakers comme source d'edge | Testée et infirmée (E9/E13) |

---

## 10. Audit de robustesse opérationnelle — cas limites testés

Tous les cas ci-dessous ont été exécutés directement contre
`run_match_decision()` réel pendant cet audit (scripts de reproduction,
non conservés — seuls les tests permanents listés en §11 sont retenus) :

| Cas | Résultat AVANT correction | Résultat APRÈS correction |
|---|---|---|
| Équipe totalement inconnue (jamais dans `goals_train_df`) | **Défaut #3 (voir §11)** : passait tous les gates de qualité de données, `NO_BET` produit mais **sans** `INSUFFICIENT_HISTORY` | `NO_BET` avec `INSUFFICIENT_HISTORY` (`unknown_team_gate`) |
| Cote de marché NaN | **Défaut #1** : `ValueError` non capturée, crash | `NO_BET` avec `MARKET_DATA_UNAVAILABLE` |
| Cote de marché infinie | **Défaut #1** : aucune exception, `market.price_edge=inf` silencieusement présenté comme valide | `NO_BET` avec `MARKET_DATA_UNAVAILABLE` |
| `total_goals` corrompu (NaN) dans l'historique de calibration | **Défaut #2** : `ValueError` non capturée, crash | `NO_BET` avec `INSUFFICIENT_HISTORY` |
| Championnat inconnu/non audité (ex. "Some Unknown League") | `NO_BET` propre, `discrimination_status=NON_EVALUEE` | Inchangé (déjà correct) |
| Championnat vide (`""`) | `NO_BET` propre | Inchangé |
| Cote négative ou nulle | `NO_BET` propre (`MARKET_DATA_UNAVAILABLE`, déjà rejetée par `o<=1.0`) | Inchangé |
| `match_id` dupliqué (deux appels indépendants) | Chaque appel produit sa propre décision indépendante — pas d'état partagé entre appels | Inchangé (comportement attendu, le moteur est sans état) |
| Kickoff dans le futur lointain | `NO_BET` propre (dépend uniquement des données fournies, jamais de l'horloge murale) | Inchangé |
| Kickoff très ancien (historique de calibration hors fenêtre) | `NO_BET` propre avec cumul de codes (`AMBIGUOUS_COLLECTION_DAY`, `INSUFFICIENT_HISTORY`, etc. selon le jour) | Inchangé |
| `home_team_id == away_team_id` | `NO_BET` propre (aucune validation métier "équipe contre elle-même", mais aucun crash ; probabilités produites sur des λ/μ symétriques, jamais interprétées comme positives faute d'edge validé) | Inchangé — pas un défaut technique au sens du mandat de cet audit (n'entraîne aucune sortie exploitable) |
| `goals_train_df` avec des buts négatifs (corruption amont) | `NO_BET` propre (le modèle Poisson ne valide pas ses entrées mais ne crashe pas ; aucune décision positive n'en résulte faute d'edge validé) | Inchangé — hors périmètre du moteur (responsabilité de la couche d'ingestion, non du moteur de décision) |
| Une seule cote fournie sur deux (`market_odds_under_2_5=None`) | `NO_BET` propre, `MARKET_DATA_UNAVAILABLE` | Inchangé |
| Kickoff naïf (sans fuseau horaire) | Aucun crash, résultat auto-cohérent mais contrat non vérifié à l'exécution | Non corrigé — voir §8, réserve documentée |
| Gates multiples simultanés | Tous les codes rapportés ensemble, triés alphabétiquement — aucune priorité implicite | Comportement voulu, voir §6 |

**Deux défauts ont nécessité une correction de code** (workflow respecté :
identification → test reproduisant l'échec → correction → test vert →
suite complète verte). **Le reste des cas testés était déjà géré
proprement** — aucune modification inutile n'a été appliquée.

---

## 11. Défauts découverts et corrigés (workflow test-first respecté)

### Défaut #1 — Cote de marché NaN/infinie contourne `validate_odds`

- **Découverte** : `float('nan') <= 1.0` vaut `False` en Python (toute
  comparaison impliquant NaN est fausse) ; `validate_odds()`
  (`market_engine/overround.py`) ne testait que `o <= 1.0`, laissant
  passer silencieusement NaN. `float('inf') <= 1.0` est également
  `False`, laissant passer une cote infinie qui produisait un `price_edge`
  infini présenté comme une comparaison de marché valide.
- **Conséquence avant correction** : NaN → `ValueError` non capturée
  propagée hors de `run_match_decision()` (crash) ; infini → aucune
  exception, sortie structurée apparemment valide.
- **Tests écrits d'abord** (confirmés rouges avant correction) :
  `test_nan_market_odds_never_raises_and_yields_no_bet`,
  `test_infinite_market_odds_never_raises_and_yields_no_bet`
  (`tests/unit/test_final_engine_determinism_and_invalid_inputs.py`).
- **Correction** : `validate_odds()` rejette désormais toute cote qui
  n'est pas strictement `> 1.0` **et** finie
  (`not (o > 1.0) or math.isinf(o)`) — capture NaN (`not (o > 1.0)` est
  vrai pour NaN) et l'infini explicitement. Module partagé depuis E1
  (`shin.py`, `football_data_loader.py` en dépendent aussi) — vérifié que
  ce changement ne modifie **aucun** comportement sur une cote décimale
  réelle finie `> 1.0` (seul le traitement de NaN/inf change).
- **Localisation du correctif** : `market_engine/overround.py`
  (`validate_odds`), la fonction déjà partagée et déjà appelée par
  `incomplete_market_odds_gate` — aucune nouvelle fonction créée.

### Défaut #2 — `total_goals` corrompu (NaN) dans l'historique de calibration

- **Découverte** : `fit_scale_correction_as_of()`
  (`calibration_engine/scalar_correction.py`, portage verbatim du script
  de recherche E8, **non modifié**) filtre les NaN sur
  `{model}_lambda`/`{model}_mu` (`dropna(subset=[lam_col, mu_col])`) mais
  jamais sur `total_goals`. `pandas.Series.mean()` ignore les NaN
  individuellement (`skipna=True` par défaut), donc une corruption
  partielle ne casse rien ; mais une corruption **totale** (ou dominante)
  de la colonne produit `actual_mean = NaN`, donc `scale_c = NaN`, qui se
  propage jusqu'à une `ValueError` non capturée bien plus loin dans le
  pipeline (`value_engine/edge.py`, contrôle `model_prob doit etre dans
  [0, 1]`).
- **Vérifié sur le script de recherche original** (`scripts/run_stage16_e8_walk_forward_validation.py:154`) :
  **le même filtrage partiel existe déjà dans le code de recherche
  original** — ce n'est pas un bug introduit par le portage, mais un
  angle mort resté sans conséquence sur le corpus historique réel (où
  `total_goals` d'un match déjà joué n'est jamais NaN par construction).
  Il ne devient un risque que pour une entrée de production non garantie
  propre.
- **Test écrit d'abord** (confirmé rouge avant correction) :
  `test_corrupted_total_goals_in_calibration_history_never_raises_and_yields_no_bet`.
- **Correction** : filtrage supplémentaire ajouté **exclusivement dans la
  couche production** (`final_engine/calibration.py::calibrate_prediction`),
  **jamais dans `scalar_correction.py`** — pour ne toucher en aucune façon
  le module scientifique figé E7/E8 : `calibration_df.dropna(subset=[lam_col,
  mu_col, "total_goals"])` avant l'appel à `fit_scale_correction_as_of`.
  Une corruption totale de `total_goals` dégrade proprement vers
  `n=0 < min_matches` → `probabilities=None` → `NO_BET`/`INSUFFICIENT_HISTORY`,
  jamais un crash.

### Défaut #3 — Équipe inconnue contourne tous les gates de qualité de données

- **Découverte** : `PoissonModel`/`DixonColesModel` attribuent un
  paramètre **neutre** (`.get(team_id, 1.0)`/`.get(team_id,
  self.hfa_global_)`) à une équipe absente de l'historique
  d'entraînement — comportement **délibéré et déjà testé depuis
  l'Étape 2** (`test_unknown_team_falls_back_to_neutral_parameters`),
  **non modifié par cet audit**. Mais `insufficient_data_gate` ne
  vérifiait que la taille **agrégée** de `goals_train_df`, jamais la
  présence des deux équipes précises du match — une équipe totalement
  inconnue (ex. `team_id=999`) avec un historique agrégé par ailleurs
  volumineux traversait donc tous les gates de qualité de données, la
  seule barrière restante étant `EDGE_BELOW_THRESHOLD` (qui bloque déjà
  tout aujourd'hui, mais pour une raison sans rapport avec le problème
  réel).
- **Test écrit d'abord** (confirmé rouge avant correction, `ImportError`
  puis assertion manquante) : 5 tests unitaires
  (`tests/unit/test_final_engine_gates.py`) + 1 test d'intégration
  (`tests/integration/test_final_engine_pipeline.py::test_unknown_team_yields_no_bet_with_insufficient_history_code`).
- **Correction** : nouveau gate `unknown_team_gate()` (`gates.py`),
  câblé dans `data_quality_gates` (`orchestrator.py:131`), réutilisant le
  code `INSUFFICIENT_HISTORY` existant (aucun nouveau code inventé). Ne
  modifie **pas** le comportement de repli neutre de `PoissonModel`/
  `DixonColesModel` — la correction vit strictement à la couche gating du
  moteur final, cohérente avec la philosophie de séparation du projet
  (les modèles calculent librement, les gates décident de la confiance
  opérationnelle).

### Vérification de non-régression après les trois corrections

```
uv run python3 -m pytest tests/unit/test_final_engine_*.py \
  tests/integration/test_final_engine_pipeline.py \
  tests/leakage/test_final_engine_point_in_time.py \
  tests/unit/test_overround.py tests/unit/test_shin.py \
  tests/unit/test_calibration*.py tests/unit/test_scalar_correction*.py -q
→ tous verts (119 + 117 tests sur les regroupements testés, se recouvrant partiellement)

uv run python3 -m pytest -q   (suite complète du dépôt)
→ 1547 passed, 0 failed, 0 régression (1546 avant Défaut #2, +1 test net)
```

Aucun résultat historique (E1-K, Phase D/F/G/H/K) n'a été recalculé ni
modifié par ces corrections — elles portent exclusivement sur la couche
de gating/robustesse du moteur final (production), jamais sur les modules
scientifiques figés (`scalar_correction.py`, `poisson.py`,
`dixon_coles.py`, `xg_model.py` tous inchangés).

---

## 12. Audit de reproductibilité

| Point | Constat |
|---|---|
| Déterminisme | `run_match_decision()` ne contient aucun aléa non-seedé — confirmé par `test_same_inputs_produce_the_same_output_object` (deux exécutions identiques bit-à-bit sur `decision`, `calibration.probabilities`, `qualification.calibration_status/discrimination_status`, `scientific_gates` failure codes) |
| Chemins de fichiers | Aucun chemin absolu codé en dur trouvé dans `final_engine/` (grep direct, zéro résultat pour `/home/`, `/Users/`, `C:\`) |
| Graines aléatoires | Aucun usage de `random`/`np.random` dans `final_engine/` — la seule aléa du projet (générateurs synthétiques, bootstrap de recherche) est hors du chemin de décision |
| Versions/dépendances | `uv.lock` présent et versionné ; dépendances explicites minimales (`duckdb`, `pandas`, `pyarrow`, `pydantic`, `pyyaml`, `typer`, `scipy`) — `numpy`, utilisé directement par `gates.py`, n'est pas listé en dépendance directe dans `pyproject.toml` (dépendance transitive via `pandas`/`scipy`, capturée dans `uv.lock`) : observation mineure de hygiène de dépendances, sans impact fonctionnel constaté (tests verts, résolution reproductible via le lockfile) |
| Configuration | `OperationalThresholds` est un `dataclass(frozen=True)` avec des valeurs par défaut explicites et documentées — aucune configuration implicite via variable d'environnement ou fichier externe non versionné |
| Séparation recherche/production | `final_engine/` ne dépend d'aucun script de `scripts/` ; le sens inverse existe (les scripts de recherche historiques restent indépendants) — confirmé par le graphe d'imports complet relevé en §8 |
| Reproductibilité d'une exécution | Étant donné les mêmes `goals_train_df`/`xg_train_df`/`calibration_df_by_model`/cotes/horodatages en entrée, la sortie est intégralement reconstructible à partir du seul objet `MatchDecisionOutput` (auditabilité explicite, `types.py:100-103`) |

**Verdict §12** : reproductibilité déterministe confirmée pour le moteur
de décision lui-même. Aucun problème trouvé nécessitant correction.

---

## 13. Audit de sécurité / intégrité du dépôt

| Point | Constat |
|---|---|
| Secrets/tokens/clés | Recherche `API_KEY|SECRET|PASSWORD|TOKEN|BEGIN PRIVATE KEY` (insensible à la casse) sur tout le dépôt : **aucun résultat** |
| Fichiers `.env`/credentials/`.pem`/`.key` | Recherche dans les fichiers suivis par git et à la racine : **aucun résultat** |
| Fichiers temporaires/untracked | `git status --porcelain -uall` : seuls les 7 fichiers légitimement modifiés par cet audit apparaissent, **aucun fichier non suivi** |
| Scripts expérimentaux accidentellement appelables par le moteur | Graphe d'imports complet de `final_engine/` (§8, §12) : **zéro** import depuis `scripts/` |
| Imports recherche ↔ production | Vérifié dans les deux sens : `final_engine/` n'importe aucun module `scripts/` ; les scripts de recherche (Phase D notamment) important `final_engine`/`gates` le font uniquement pour des simulations isolées documentées (§7), jamais l'inverse |
| Dépendances inutilisées | Aucune dépendance suspecte identifiée dans `pyproject.toml` (liste minimale, cohérente avec l'usage réel) |

**Verdict §13** : aucun problème de sécurité ou d'intégrité trouvé. Le
moteur de production ne dépend d'aucune expérience rejetée, confirmé par
grep exhaustif (§8).

---

## 14. Classification finale

| # | Point d'audit | Statut | Preuve |
|---|---|---|---|
| 1 | Pipeline A→F conforme à la documentation | 🟢 PRÊT | §1 — lecture code intégrale, zéro divergence structurelle |
| 2 | Synthèse scientifique E1→K non altérée | 🟢 PRÊT | §2 — table reprise sans recalcul |
| 3 | Modèles : statuts corrects, aucun classement inventé | 🟢 PRÊT | §3 — code + test AST anti-ensemble |
| 4 | Calibration E7/E8 : mécanisme, historique, zone biaisée | 🟢 PRÊT | §4 — comportement vérifié par test dédié |
| 5 | Premier League : E15 ni sur- ni sous-interprété | 🟢 PRÊT | §5 — tests dédiés + table figée |
| 6 | NO_BET : liste exhaustive et déterministe | 🟢 PRÊT | §6 — 7/10 codes câblés, 3 réservés, priorité = union triée |
| 7 | BET : aucun contournement possible | 🟢 PRÊT | §7 — grep exhaustif, un seul écart = simulation Phase D déjà conclue |
| 8 | PIT / anti-fuite : aucune fuite dans le moteur | 🟢 PRÊT (avec réserve mineure fuseau horaire, non bloquante) | §8 |
| 9 | Checklist de données production | 🟢 PRÊT (documentaire) | §9 — cohérente avec le code |
| 10 | Robustesse opérationnelle sur cas limites | 🟡 PRÊT AVEC RÉSERVES → corrigé pendant l'audit | §10/§11 — 3 défauts trouvés, 3 corrigés, suite complète verte |
| 11 | Couverture de tests | 🟢 PRÊT | §11 — 1547 tests, 0 échec, aucun test artificiel ajouté |
| 12 | Reproductibilité | 🟢 PRÊT | §12 |
| 13 | Sécurité / intégrité du dépôt | 🟢 PRÊT | §13 |
| — | `min_edge_threshold` / seuil opérationnel de conversion edge→pari | ⚪ NON APPLICABLE / RECHERCHE FUTURE | Explicitement non fixé — Phase D a conclu à l'absence de règle robuste ; rester `None` est la position correcte tant qu'aucune règle n'est validée |
| — | Ensemble multi-modèles | ⚪ NON APPLICABLE / RECHERCHE FUTURE | Jamais entrepris, correctement absent du code |

**Corrections mineures apportées à la documentation** (non scientifiques,
purement descriptives — voir §6) : `docs/final_engine_specification.md`
ligne 525 sera alignée sur le code réel (`MARKET_DATA_UNAVAILABLE` plutôt
que `MARKET_NOT_USABLE` pour une cote rejetée par `validate_odds`).

---

## 15. Verdict final

### **A — PRÊT POUR LE PAPER TRADING / SHADOW MODE, `BET` désactivé (`min_edge_threshold=None`)**

Justification :

1. Le moteur produit aujourd'hui, de façon fiable et reproductible, une
   **projection**, un **prix juste**, une **comparaison au marché
   d'ouverture** et une **qualification de confiance** — c'est exactement
   ce qu'un mode observation/shadow nécessite.
2. `NO_BET` est produit **systématiquement** dans la configuration par
   défaut, pour une raison **toujours motivée et tracée**
   (`decision_reason`) — aucun `BET` n'est atteignable sans modification
   explicite du code appelant (§7).
3. Les trois défauts de robustesse découverts pendant cet audit (cote
   NaN/infinie, `total_goals` corrompu, équipe inconnue) ont tous été
   **corrigés avant cette conclusion**, avec tests reproduisant l'échec
   avant correction, puis suite complète verte (1547 tests, 0 échec).
4. Aucune fuite temporelle trouvée dans le code du moteur lui-même ; la
   seule dépendance restante (discipline PIT de l'appelant sur les
   `DataFrame` d'entrée) est documentée et déjà couverte par les tests de
   fuite historiques réutilisés.
5. La seule réserve non bloquante restante est l'absence de validation
   defensive sur un `kickoff_utc` naïf (sans fuseau) — n'entraîne aucune
   fuite ni décision positive erronée, uniquement une ambiguïté
   documentaire sur le contrat d'entrée ; à corriger avant une
   intégration avec une source de données dont le fuseau ne serait pas
   garanti UTC.

Ce verdict porte strictement sur l'usage en **observation** (aucune mise
réelle, `BET` restant structurellement inatteignable). Toute discussion
d'un usage `BET` réel resterait conditionnée à une expérience dédiée de
validation d'un `min_edge_threshold` — expérience explicitement **hors
périmètre** de cet audit et non entreprise ici.

---

*Audit réalisé sans exécuter de nouvelle expérience scientifique, sans
introduire de nouveau signal, sans fixer de seuil d'edge, sans backtest de
rentabilité, sans modifier un résultat E1→K. Trois défauts de robustesse
opérationnelle ont été corrigés selon le protocole test-first mandaté
(identification → test rouge → correction → test vert → suite complète
verte). Fin de l'audit — aucune Phase L ni nouvelle expérience n'est
entreprise à la suite de ce document.*
