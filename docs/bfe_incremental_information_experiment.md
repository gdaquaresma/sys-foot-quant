# Phase G — information incrémentale de Betfair Exchange (BFE) sur B365

Statut : **expérience unique, terminée**. Verdict : **`NON VALIDÉ`** sur
les quatre sélections testées (1X2 : H, D, A ; Over/Under 2.5 : Over).
Aucune modification de `poisson_simple`/`dixon_coles`/`xg_model`,
d'E7/E8/E14/E15/E16 ou des gates. `BET` non activé, `min_edge_threshold`
non fixé.

Module de données : `src/sys_foot_quant/data_engine/market_odds/betfair_exchange_odds.py`
(isolé, jamais importé par `final_engine`). Script :
`scripts/run_stage28_phase_g_bfe_incremental_information.py`. Tests :
`tests/unit/test_betfair_exchange_odds.py`,
`tests/leakage/test_betfair_exchange_odds_point_in_time.py`,
`tests/unit/test_run_stage28_phase_g.py` (35 tests, tous exécutés
**avant** l'exécution sur données réelles).

## 1. Objectif

Question posée (protocole Phase G) : *les prix Betfair Exchange (BFE)
apportent-ils une information de marché supplémentaire que B365
(déjà exploité depuis E1) ne contient pas déjà ?* — pas « peut-on gagner
de l'argent avec BFE », pas « BFE est-il meilleur que B365 ».

## 2. Définition exacte des données BFE/BFD

Audit direct (inspection de l'en-tête brut + calcul d'overround sur les
2132 lignes réelles) des colonnes Betfair, **jamais lues avant Phase G**
(`BFE` était explicitement exclu depuis E9/E13, « nature d'exchange non
clarifiée »). Deux instruments **distincts** ont été identifiés :

| Instrument | Colonnes | Renommage inter-saison | Overround moyen | Marchés couverts |
|---|---|---|---|---|
| **« BF »/« BFD »** | `BFH/D/A` (2024/25) → `BFDH/D/A` (2025/26) | Oui — identique au précédent WH→LB (E13) | **1.045–1.060** (identique à B365 : 1.055–1.056) | 1X2 uniquement |
| **« BFE »** | `BFEH/D/A`, `BFE>2.5/<2.5` | Non — constant sur les 6 fichiers | **1.006–1.013** (proche de 1.0) | 1X2 + Over/Under 2.5 + handicap asiatique (`BFEAHH/AHA`) |

**Interprétation retenue** (documentée comme HYPOTHÈSE, jamais vérifiée
auprès de la source externe — aucune requête à football-data.co.uk,
aucun téléchargement supplémentaire) : « BF »/« BFD » = **Betfair
Sportsbook**, un bookmaker à marge fixe classique, renommé d'une saison
à l'autre exactement comme Football-Data l'a déjà fait pour William
Hill/Ladbrokes. « BFE » = **Betfair Exchange** proprement dit (prix
d'échange, « best back price », sans marge de bookmaker centralisée) —
cohérent avec son overround quasi nul et sa couverture de marché plus
large (typique d'un exchange). Cette interprétation repose sur **deux
preuves structurelles indépendantes trouvées dans les données
elles-mêmes** (le renommage identique au précédent WH/LB déjà accepté ;
la signature d'overround radicalement différente), jamais une simple
supposition sur le nom des colonnes — jugée suffisamment certaine pour
procéder (le protocole demandait d'arrêter seulement si la sémantique
restait incertaine).

**Scope retenu pour cette expérience** : **seul BFE** est lu et testé —
« BF »/« BFD » est un bookmaker à marge standard, structurellement
redondant par construction avec BW/PS/WH/LB déjà démontrés
non-informatifs (E9/E13), et hors périmètre de l'hypothèse Phase G (une
seule variable nouvelle). `BFEAHH/AHA` (handicap asiatique) et toute
colonne de clôture (`BFCH`, `BFECH`, `BFEC>2.5`, ...) existent mais ne
sont **jamais lues** — hors périmètre explicite (protocole étape 12).

## 3. Couverture

`BFEH/D/A`/`BFE>2.5/<2.5` sont des colonnes garanties présentes dans les
six fichiers (`_ALLOWED_COLUMNS`, échec explicite si absentes). Couverture
**par ligne**, parmi les matchs exploitables (jour non ambigu, PIT
valide, n=1806) :

| | 1X2 | Over/Under 2.5 |
|---|---|---|
| BFE disponible | 1756 (97.2%) | 1743 (96.5%) |

Coverage à 100% sur les fichiers 2024/25, dégradée à 92–95% sur les
fichiers 2025/26 (asymétrie déjà observée pour d'autres bookmakers
secondaires, ex. Pinnacle O/U). Jamais imputée — un match sans BFE reste
exploitable pour B365 seul, simplement absent des comparaisons BFE.

## 4. Audit temporel (point-in-time)

BFE provient de la **même ligne source** que B365 (même moment de
collecte supposé, même fichier CSV) — **aucune nouvelle règle
temporelle**. Réutilise exactement `matching.build_understat_keys`/
`match_league_season`, `time_resolution.conservative_knowledge_time_utc`,
`DECISION_OFFSET_HOURS` (INCHANGÉS depuis E5/E9). Seules les colonnes
d'**ouverture** (`BFEH/D/A`, `BFE>2.5/<2.5`) sont lues — les variantes de
clôture (`BFECH/D/A`, `BFEC>2.5/<2.5`) ne sont **jamais** chargées par ce
module (vérifié structurellement : `BetfairExchangeMatchRecord` ne porte
aucun champ contenant `close`), donc aucun mélange ouverture/clôture n'est
possible par construction.

## 5. Transformation en probabilités

`remove_overround_proportional` (réutilisé sans modification,
`market_engine.overround`) — fonction **agnostique à la taille de la
marge** : `p_i = (1/cote_i) / Σ_j(1/cote_j)`, valide pour tout ensemble
de cotes décimales complètes quelle que soit la marge intégrée. **Aucune
correction différente n'est appliquée à BFE** au prétexte que son
overround est plus proche de 1.0 — ce serait supposer une propriété non
vérifiée ; la même formule fonctionne identiquement dans les deux cas
(margeur élevé ou quasi nul).

## 6. Baseline B365

`p_B365` = probabilité normalisée B365 (zéro paramètre). Reconnu depuis
E1-E16 comme le benchmark le mieux établi du projet (couverture 100%,
seul bookmaker à cote garantie sur les six fichiers).

**Contrôle obligatoire ajouté — « B365-recalibré »** (lecon directement
tirée de Phase F/SOT, où l'omission de ce contrôle aurait produit un
verdict `VALIDÉ` erroné) : régression logistique walk-forward avec pour
seule covariable `logit(p_B365)` (intercept + pente, **sans** BFE) — 2
paramètres, `fit_logistic`/`predict_logistic`/`walk_forward_logistic`
(E16, INCHANGÉS), `min_train=30`. Isole tout effet de recalibration
générique d'un effet spécifique à BFE. Le test principal (section 10)
compare B365+BFE à **ce contrôle**, jamais à B365 brut.

## 7. BFE

`p_BFE` = probabilité normalisée BFE (zéro paramètre), disponible
uniquement sur les matchs où BFE est présent (section 3).

## 8. B365+BFE

`p = sigmoid(a + b·logit(p_B365) + c·logit(p_BFE))` — 3 paramètres,
walk-forward expansif, mêmes primitives E16 (`min_train=30`), sur le
corpus complet trié par `decision_time` (une seule passe, comme Phase F
— pas de découpage rodage/calibration/test, aucun seuil à protéger).

## 9. Résultats 1X2

Effectifs (après appariement, exclusion jour ambigu, PIT, BFE disponible,
rodage de la régression walk-forward) : **n=1726** pour H, D et A.

| Sélection | Brier B365 | Brier B365-recal | Brier B365+BFE |
|---|---|---|---|
| H | 0.2098 | 0.2106 | 0.2112 |
| D | 0.1818 | 0.1826 | 0.1832 |
| A | 0.1864 | 0.1873 | 0.1876 |

Dans les trois cas, B365+BFE ne fait pas mieux que le contrôle
B365-recalibré — la direction de la différence est même légèrement
défavorable à BFE (Brier très légèrement plus élevé), cohérent avec
l'ajout d'une covariable fortement corrélée qui n'apporte que du bruit
supplémentaire à l'estimation walk-forward.

## 10. Résultats O/U 2.5

BFE publie bien `BFE>2.5`/`BFE<2.5` (colonnes existantes, couverture
96.5%) — testé, contrairement à BW/PS/WH/LB qui n'ont jamais eu ce
marché. Effectif : **n=1713** (sélection Over, Under exclu par
degénérescence complémentaire déjà démontrée en E13).

| | B365 | B365-recalibré | B365+BFE |
|---|---|---|---|
| Brier | 0.2402 | 0.2417 | 0.2427 |

Même constat que pour le 1X2 : aucune amélioration de B365+BFE sur le
contrôle.

## 11. Tests statistiques

**Test principal** (diff. de Brier, B365+BFE vs **B365-recalibré**,
bootstrap apparié 10 000 rééchantillonnages) :

| Sélection | n | diff. moyenne | IC95% | p |
|---|---|---|---|---|
| H | 1726 | +0.0006 | [+0.0000, +0.0012] | 0.043 |
| D | 1726 | +0.0006 | [-0.0000, +0.0011] | 0.072 |
| A | 1726 | +0.0004 | [-0.0003, +0.0009] | 0.378 |
| Over | 1713 | +0.0010 | [-0.0005, +0.0026] | 0.217 |

Un seul cas (H) atteint tout juste p<0.05 — et dans la direction **opposée**
à celle requise pour `VALIDÉ` (l'IC95% est entièrement **> 0**, c'est-à-dire
une **dégradation** significative, pas une amélioration). Les trois
autres sélections (D, A, Over) ont un IC95% chevauchant zéro : aucune
preuve. Aucune des quatre sélections ne satisfait le critère `VALIDÉ`
(IC95% entièrement **< 0**).

## 12. Robustesse

Décomposée par championnat et par saison pour chaque sélection (24
sous-groupes au total) — **diagnostic uniquement, jamais une nouvelle
sélection**. Le signe de la différence B365+BFE vs B365-recalibré varie
d'un sous-groupe à l'autre sans motif cohérent (parfois légèrement
positif, parfois légèrement négatif), et aucune décomposition n'atteint
une amélioration statistiquement significative dans le sens attendu —
cohérent avec une absence totale d'information incrémentale plutôt
qu'avec un effet localisé masqué au niveau global.

## 13. Audit leakage

Garde-fous testés **avant** l'exécution réelle
(`tests/leakage/test_betfair_exchange_odds_point_in_time.py`, 6 tests +
2 tests de fuite dédiés dans `test_run_stage28_phase_g.py`) :

- `knowledge_time <= decision_time` toujours vérifié sur les matchs
  exploitables (test direct + propriété Hypothesis, 100 exemples).
- Les cotes BFE sont indépendantes du résultat réel du match (deux
  matchs mêmes cotes, scores différents → cotes identiques).
- `BetfairExchangeMatchRecord` ne porte structurellement **aucun** champ
  de clôture (vérifié par introspection des champs du dataclass) — aucun
  mélange ouverture/clôture possible.
- Le module ne touche jamais au handicap asiatique (vérifié par
  inspection du code source du module — aucune occurrence de `AH` ou
  `handicap`).
- **Garde-fou walk-forward** (mirroir du garde-fou absolu de Phase F,
  transposé à la régression logistique de marché) : un test perturbe la
  toute dernière ligne (future) d'un DataFrame trié et démontre que
  **aucune** prédiction antérieure à cette ligne ne change — ce test
  échouerait si `walk_forward_logistic` utilisait une information
  postérieure à la ligne évaluée.
- BFE isolé structurellement de `odds_1x2_by_bookmaker`/
  `over_under_2_5_by_bookmaker`/`BOOKMAKERS_1X2` (déjà utilisés par des
  scripts gelés E9/E13) — vérifié par test dédié, garantissant que cette
  extension n'altère la reproductibilité d'aucun résultat déjà publié.

Aucune fuite détectée. 35 tests Phase G, tous exécutés avant l'exécution
réelle ; suite complète du projet : 1259 tests verts après Phase G.

## 14. Limites

- L'interprétation « BF/BFD = Sportsbook, BFE = Exchange » (section 2)
  reste une hypothèse documentée, jamais confirmée par une source externe
  — cohérente avec deux preuves structurelles indépendantes, mais pas un
  fait vérifié au sens strict (même discipline que la règle de
  connaissance conservatrice de l'ADR 0006).
- Le contrôle « B365-recalibré » a été inclus dès la conception du
  script (contrairement à Phase F où il avait été ajouté après un
  premier résultat brut) — directement issu de la leçon méthodologique
  de Phase F, pas une réaction à un résultat déjà observé ici.
- Le handicap asiatique BFE (`BFEAHH`/`BFEAHA`), pourtant disponible avec
  une couverture comparable, n'a délibérément pas été testé (une seule
  variable nouvelle par expérience, protocole étape 12) — reste une piste
  distincte, non explorée ici.
- « BF »/« BFD » (Betfair Sportsbook) n'a pas été testé empiriquement
  contre B365 — son profil d'overround identique à B365 rend cette
  vérification peu prioritaire (résultat attendu : redondant, comme
  BW/PS/WH/LB), mais ceci reste une inférence, pas un test réalisé.

## 15. Verdict

## **`NON VALIDÉ`** (les quatre sélections : H, D, A, Over)

Critère appliqué mécaniquement (grille figée avant observation, protocole
étape 11) : aucune des quatre sélections ne montre un IC95% de la
différence de Brier (B365+BFE vs **B365-recalibré**) entièrement inférieur
à zéro. Dans le seul cas marginalement significatif (H, p=0.043), l'effet
est dans la direction **opposée** (dégradation). BFE se comporte comme un
bookmaker fortement corrélé à B365, sans apport d'information distincte —
conforme à l'hypothèse nulle attendue compte tenu de la forte homogénéité
déjà démontrée entre B365 et Pinnacle (E9/E13).

## 16. Conséquence architecturale

Conformément au protocole étape 12 : le résultat n'étant démontré sur
aucune sélection, **l'avenue Betfair Exchange est gelée**, au même titre
que les autres pistes non concluantes déjà identifiées (dispersion
multi-bookmaker E9/E13, mouvement de marché E16, désaccord modèle/marché,
tirs cadrés Phase F). **Aucune intégration au moteur de production**
(`final_engine`) — le code écrit (`betfair_exchange_odds.py`) reste isolé,
jamais importé par `final_engine`, et structurellement séparé de la
couche multi-bookmaker déjà utilisée par E9/E13 (aucun risque pour leur
reproductibilité). `min_edge_threshold` reste `None`, `BET` reste non
activé. Aucune autre extension Betfair (handicap asiatique, Betfair
Sportsbook, clôture) n'est explorée à la suite de ce résultat négatif —
le protocole interdit explicitement de multiplier les expériences jusqu'à
obtenir un résultat positif.

**Arrêt.** Conformément à l'instruction explicite de la Phase G, cette
expérience était la seule autorisée. Aucune expérience suivante (handicap
asiatique, nouvelles lignes O/U, compositions, blessures, nouveaux
fournisseurs, analyse de rentabilité, activation de `BET`) n'est lancée
automatiquement — la suite reste à décider séparément par l'utilisateur à
partir de ce résultat.
