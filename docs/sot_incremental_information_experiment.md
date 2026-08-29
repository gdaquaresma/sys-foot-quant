# Phase F — information incrémentale des tirs cadrés (SOT) sur Over/Under 2.5

Statut : **expérience unique, terminée**. Verdict : **`NON VALIDÉ`**.
Aucune modification de `poisson_simple`/`dixon_coles`/`xg_model`, d'E7/E8/
E14/E15/E16 ou des gates. `BET` non activé, `min_edge_threshold` non fixé.

Script : `scripts/run_stage27_phase_f_sot_incremental_information.py`.
Module de features : `src/sys_foot_quant/data_engine/market_odds/shots_on_target.py`.
Tests : `tests/unit/test_shots_on_target.py`,
`tests/leakage/test_shots_on_target_point_in_time.py`,
`tests/unit/test_run_stage27_phase_f.py` (40 tests, tous exécutés
**avant** l'exécution sur données réelles).

## 1. Objectif

Question posée (`docs/next_signal_strategy.md`, direction validée par
l'utilisateur) : *les tirs cadrés (AST/HST, Football-Data) contiennent-ils
une information prédictive **incrémentale** sur le résultat O/U 2.5,
au-delà de l'information déjà contenue dans le moteur actuel
(`poisson_simple` + correction E7/E8) ?* Expérience strictement
diagnostique — pas une construction de modèle de production, pas une
recherche de seuil d'edge ou de ROI.

## 2. Données utilisées

Exclusivement les six fichiers Football-Data déjà présents dans le dépôt
(`research/market_odds/football_data/runs/{E0,F1,SP1}_{2024_25,2025_26}.csv`)
et les six fichiers Understat déjà présents
(`research/xg_feasibility/runs/*_datesData.json`). **Aucun téléchargement
nouveau.** Corpus total : 2132 matchs (identique au corpus E1-E16).

## 3. Inventaire des statistiques disponibles

Audit direct (pandas, avant toute écriture de code) des douze colonnes de
statistiques de match présentes dans les six fichiers, jamais lues avant
Phase F :

| Colonne | Signification | Couverture (2132 lignes) | Cohérence |
|---|---|---|---|
| `HS`/`AS` | tirs totaux dom./ext. | 100% (0 manquant) | — |
| `HST`/`AST` | **tirs cadrés dom./ext.** | **100% (0 manquant)** | `HST<=HS`, `AST<=AS` toujours vrai |
| `HC`/`AC` | corners | 100% | — |
| `HF`/`AF` | fautes | 100% | — |
| `HY`/`AY`/`HR`/`AR` | cartons jaunes/rouges | 100% | — |
| `HTHG`/`HTAG`/`HTR` | score/résultat mi-temps | 100% | — |

`Referee` (arbitre) manquant uniquement sur les fichiers F1/SP1 (non
pertinent ici). `HST` : min 0, moyenne 4.75, max 16. `AST` : min 0,
moyenne 3.93, max 13 — cohérent avec un avantage du terrain visible.
**Seules `HST`/`AST` sont retenues** (hypothèse prioritaire — une seule
nouvelle source d'information à la fois, protocole étape 5/11) ; `HS`,
`AS`, `HC`, `AC`, `HF`, `AF`, `HY`, `AY`, `HR`, `AR` restent non lues.

Extension du loader (`football_data_loader.py`) : `HST`/`AST` ajoutées à
`_ALLOWED_COLUMNS` (colonnes garanties, échec explicite si absentes) et
au dataclass `FootballDataMatchRecord` (`home_shots_on_target`,
`away_shots_on_target`).

**Réserve absolue (non négociable)** : `HST`/`AST` sont des statistiques
de match, connues seulement **après** le coup d'envoi (même ligne source
que le score final). Elles ne sont **jamais** un feature du match
qu'elles décrivent elles-mêmes — uniquement exploitables comme entrée
**historique** (moyenne d'un match antérieur) d'un futur match.

## 4. Définition exacte des features

Fixée avant toute exécution sur données réelles (`shots_on_target.py`,
docstring de module). Exactement **deux scalaires**, jamais multipliés :

```
sot_produced_total = moyenne_historique(tirs_cadrés_marqués, domicile)
                    + moyenne_historique(tirs_cadrés_marqués, extérieur)
sot_conceded_total = moyenne_historique(tirs_cadrés_encaissés, domicile)
                    + moyenne_historique(tirs_cadrés_encaissés, extérieur)
```

Moyenne calculée sur un pool **poolé** (championnat × saison), walk-
forward, matchs strictement antérieurs à `decision_time`. Seuil minimal
du pool : **réutilisé exactement** `MIN_TRAIN_MATCHES` (=10,
`economic_dataset.py`) — même convention que `poisson_simple`/
`xg_model` (`_goals_train_df`/`_xg_train_df`, `predict_match`), jamais un
seuil distinct inventé. Une équipe sans historique dans un pool suffisant
reçoit la **moyenne du pool** (repli neutre translittéré de
`XGModel.fit`, jamais une exclusion ni une valeur inventée).

## 5. Protocole point-in-time

`sot_knowledge_time = kickoff_utc + 2h` — réutilise **exactement**
`DEFAULT_GOALS_KNOWLEDGE_DELAY_HOURS` (`real_data_walk_forward.py`),
aucun nouveau délai inventé (même moment de publication que le score
final, même ligne source Football-Data). `sot_training_pool` exclut :
(a) le match évalué lui-même (`exclude_match_id`, garde-fou redondant
explicite) ; (b) tout enregistrement dont `sot_knowledge_time >
decision_time`. Vérifié par 9 tests unitaires + 6 tests de fuite dédiés
(section 12).

## 6. Baseline (Modèle O)

**Modèle O** = le moteur actuel : `poisson_simple` walk-forward
(`e7.build_lambda_mu_dataframe`, INCHANGÉ) puis calibration E7/E8
(`final_engine.calibration.calibrate_prediction`, INCHANGÉE — même code
que la production, réutilisé sans modification). **Zéro paramètre
supplémentaire**, pur passe-plat de la probabilité Over 2.5 déjà produite
par le moteur. Contrairement à la Phase D (rodage/VALIDATION/TEST, pour
protéger un *seuil* du surapprentissage), cette expérience ne sélectionne
aucun seuil : une seule passe walk-forward sur le corpus complet (2132
matchs), chaque prédiction n'utilisant que les matchs strictement
antérieurs — même logique de fond qu'E8/E16, effectif maximisé.

**Contrôle obligatoire ajouté en cours d'expérience — `O-recalibré`** :
en observant les premiers résultats bruts (Brier O=0.265, erreur de
calibration pondérée O=0.094 — une miscalibration importante), une
question méthodologique s'est posée **avant** toute interprétation du
résultat SOT : le modèle O+SOT enveloppe `logit(p_O)` dans une régression
logistique à intercept et pente **libres** ; si O est mal calibré, cette
enveloppe peut à elle seule corriger une grande partie de l'erreur, **sans
aucun rapport avec les tirs cadrés**. Le protocole exige explicitement de
ne jamais conclure à une information incrémentale si elle est
« *déjà redondante avec le moteur actuel* » (étape 10, critère NON
VALIDÉ) — un contrôle qui isole cet effet est donc une exigence du
protocole, pas une variante ajoutée pour améliorer le résultat. `O-
recalibré` = la **même** régression logistique walk-forward
(`fit_logistic`/`predict_logistic`/`_safe_logit`/`walk_forward_logistic`,
E16, INCHANGÉS) avec pour seule covariable `logit(p_O)` (intercept +
pente, **sans** les deux covariables SOT). Le test principal (section 10)
compare **O+SOT à ce contrôle**, jamais à O brut.

## 7. Modèle O+SOT

`p = sigmoid(a + b·logit(p_O) + c·sot_produced_total +
d·sot_conceded_total)` — 4 paramètres, ajustés en fenêtre glissante
expansive (walk-forward), **réutilise sans modification**
`fit_logistic`/`predict_logistic`/`_safe_logit`/`walk_forward_logistic`
d'E16 (`run_stage25_e16_market_movement_information.py`), même
`_MIN_TRAIN=30`. Aucun marché n'intervient dans cette comparaison (le
« moteur actuel », au sens strict du protocole, est `poisson_simple`
calibré — la comparaison au marché est un niveau séparé du pipeline,
hors périmètre de cette question).

## 8. Métriques

Brier score, log loss, erreur de calibration pondérée
(`_calibration_weighted_error`, réutilisée de `run_stage8...py`),
résolution/discrimination (`brier_decomposition`, réutilisée de
`calibration_engine.decomposition`), et le test statistique principal :
`paired_bootstrap_test` (réutilisé sans modification,
`calibration_engine.significance`) sur les différences appariées de
Brier et de log loss, IC95% et p-value.

## 9. Résultats

Effectifs : corpus avec `poisson_simple` disponible = 2072 ; éligibles
(Modèle O **et** features SOT disponibles) = 2042 ; comparables (après
rodage de la régression logistique, `min_train=30`) = **2012**.

**Global (n=2012)** :

| | O (brut) | O-recalibré | O+SOT |
|---|---|---|---|
| Brier | 0.2648 | 0.2490 | 0.2470 |
| Log loss | 0.8029 | 0.6919 | 0.6875 |
| Calibration (erreur pondérée) | 0.0942 | 0.0180 | 0.0146 |
| Résolution | 0.0023 | 0.0005 | 0.0036 |

L'essentiel de l'amélioration observée entre O brut et O+SOT (Brier
0.2648 → 0.2470) est déjà obtenu par la **recalibration seule**, sans
aucune information SOT (0.2648 → 0.2490 — soit ~89% de l'écart total).
L'incrément spécifiquement attribuable aux tirs cadrés (O+SOT vs
O-recalibré) est faible : Brier 0.2490 → 0.2470 (diff = -0.0020).

## 10. Tests statistiques

**Test principal** (protocole étape 7 : « information incrémentale »,
jamais « meilleur score ») — diff. de Brier, O+SOT vs **O-recalibré**,
bootstrap apparié (10 000 rééchantillonnages) :

| Périmètre | n | diff. moyenne | IC95% | p |
|---|---|---|---|---|
| **Global** | 2012 | -0.0020 | **[-0.0041, +0.0002]** | 0.073 |
| Liga | 714 | -0.0043 | [-0.0083, -0.0002] | 0.039 |
| Ligue 1 | 578 | -0.0011 | [-0.0050, +0.0029] | 0.593 |
| Premier League | 720 | -0.0005 | [-0.0038, +0.0028] | 0.775 |
| Saison 2024/25 | 976 | -0.0004 | [-0.0034, +0.0027] | 0.812 |
| Saison 2025/26 | 1036 | -0.0035 | [-0.0065, -0.0005] | 0.021 |

L'IC95% **global** chevauche 0 (**p = 0.073**, non significatif au seuil
usuel de 5%). Seul un sous-groupe sur cinq (Liga, et la saison 2025/26)
atteint la significativité à 5% — les trois autres (Ligue 1, Premier
League, saison 2024/25) ne montrent aucune preuve d'amélioration. Une
amélioration numérique non significative, ou significative dans un seul
sous-groupe sur plusieurs, est explicitement classée par le protocole
comme **absence de preuve d'information incrémentale**, jamais un signal.

## 11. Robustesse

Décomposée par championnat et par saison (tableau ci-dessus) —
**diagnostic uniquement, jamais une nouvelle sélection**. Le résultat
n'est stable dans aucune des deux dimensions : ni par championnat (2/3
non significatifs), ni par saison (1/2 non significatif). Aucun
sous-groupe n'a été choisi après observation ; les deux décompositions
étaient prévues avant exécution (protocole étape 8).

## 12. Audit leakage

Garde-fous testés **avant** l'exécution réelle
(`tests/leakage/test_shots_on_target_point_in_time.py`, 6 tests) :

- (a)/(d)/(e) aucune statistique d'un match futur (`sot_knowledge_time >
  decision_time`) n'entre dans un pool d'entraînement — vérifié
  directement et par une propriété Hypothesis (50 exemples).
- (b) le match évalué lui-même est toujours exclu de son propre pool
  (`exclude_match_id`), même redondamment avec (a).
- (c) `ShotsOnTargetMatchRecord` ne porte structurellement aucun champ de
  cote (ouverture ou clôture) — vérifié par introspection des champs du
  dataclass.
- **Garde-fou absolu** (protocole étape 9) : un test injecte
  artificiellement une observation future avec une valeur extrême (15
  tirs cadrés) et démontre à la fois qu'elle est exclue par le code réel
  **et** qu'elle aurait changé le résultat si elle ne l'était pas
  (moyenne passant de 3.0 à 9.0) — ce test échouerait si le filtre
  `sot_knowledge_time <= decision_time` se rompait. Un second test
  reproduit la même démonstration via `sot_features_for_match` (la
  fonction réellement utilisée par le script).

Aucune fuite détectée. 40 tests Phase F, tous exécutés avant l'exécution
réelle ; suite complète du projet : 1240 tests verts après Phase F.

## 13. Limites

- Le contrôle « O-recalibré » n'a été introduit qu'après observation des
  **premiers** résultats bruts (documenté en section 6) — décision
  méthodologique, pas un choix de résultat : la question qu'il résout
  (« l'amélioration est-elle spécifique à SOT ou n'importe quelle
  recalibration l'aurait produite ? ») est directement dictée par le
  critère NON VALIDÉ du protocole (« information déjà redondante »), pas
  inventée pour faire baisser un résultat positif. Le protocole
  n'interdit pas d'ajouter un contrôle nécessaire à la validité du test
  principal — il interdit de tester des dizaines de variantes de
  *features* et de garder la meilleure, ce qui n'a pas été fait ici (les
  deux features SOT sont restées strictement celles figées en section 4).
- Pas de test formel « la baseline reproduit un résultat déjà publié » :
  cette expérience utilise une conception à une seule passe walk-forward
  sur le corpus complet (section 6), structurellement différente du
  découpage rodage/calibration/test d'E7/E8 (justifiée section 6) — une
  comparaison numérique directe aux chiffres déjà publiés d'E8 n'aurait
  donc pas de sens. La validité de l'intégration à `calibrate_prediction`
  elle-même reste couverte par les 106 tests de la Phase B (non
  ré-exécutés ici, non modifiés).
- Les deux features restent des moyennes historiques simples (pas de
  pondération temporelle, pas de fenêtre glissante courte) — un design
  différent pourrait en théorie capter un signal plus fort, mais le
  protocole interdit explicitement de tester plusieurs variantes.

## 14. Verdict

## **`NON VALIDÉ`**

Critère appliqué mécaniquement (grille figée avant observation,
protocole étape 10) : l'IC95% global de la différence de Brier (O+SOT
vs **O-recalibré**, le contrôle isolant l'effet spécifique de SOT) **ne
se situe pas entièrement sous zéro** (p = 0.073) et le résultat est
instable entre championnats et entre saisons (2 sous-groupes sur 5
significatifs, 3 non). Conformément au protocole : une amélioration
numérique non significative, ou significative dans un sous-ensemble
isolé, est classée comme **absence de preuve d'information
incrémentale** — jamais un signal.

L'essentiel du gain apparent de Brier entre le modèle actuel brut et
« O+SOT » (0.2648 → 0.2470) provient d'une **recalibration générique**
(0.2648 → 0.2490, un contrôle sans aucune information SOT) — pas des
tirs cadrés eux-mêmes. Sans ce contrôle, cette expérience aurait
conclu, à tort, `VALIDÉ`.

## 15. Conséquence architecturale

Conformément au protocole étape 12 : le résultat n'étant pas démontré,
**l'avenue des tirs cadrés (SOT) est gelée définitivement**, au même
titre que les autres pistes non concluantes déjà identifiées (E14 —
correction locale de la zone [0.6,0.7) ; E1/E5/E10/E12 — désaccord
modèle/marché comme signal ; E16 — mouvement de marché ouverture→clôture ;
Phase D — sélection par edge). **Aucune intégration au moteur de
production** (`final_engine`) n'est effectuée — le code écrit
(`shots_on_target.py`, `football_data_loader.py` étendu) reste isolé de
`final_engine`, jamais importé par lui. `min_edge_threshold` reste
`None`, `BET` reste non activé. Aucune autre statistique de match (`HS`,
`AS`, `HC`, `AC`, `HF`, `AF`, cartons) n'est explorée à la suite de ce
résultat négatif — le protocole interdit explicitement de multiplier les
expériences jusqu'à obtenir un résultat positif.

**Arrêt.** Conformément à l'instruction explicite de la Phase F, cette
expérience était la seule autorisée après E1-E16 et la Phase E. Aucune
expérience suivante (BFE, Handicap Asiatique, multi-bookmaker, lignes O/U
multiples, nouvelle saison, compositions d'équipe, blessures, E17) n'est
lancée automatiquement — la suite reste à décider séparément par
l'utilisateur à partir de ce résultat.
