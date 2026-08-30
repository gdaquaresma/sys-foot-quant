# Protocole pré-enregistré — Elo pré-match (ClubElo, Phase K)

**Nature de ce document.** Protocole méthodologique complet, verrouillé
**avant** toute exécution sur données réelles et avant tout code de
production. Contient l'audit documentaire (§0), l'audit direct de la
source ClubElo (§0bis — **incluant un blocage opérationnel constaté,
signalé explicitement plutôt que contourné**), l'inventaire des
primitives réutilisables (§1), la définition PIT exacte du rating et de
`elo_diff` (§2), le plan de couverture et de matching (§3-4), le split
(§5), les modèles A/B/C/D (§6), la cible et la métrique (§7-8), le test
statistique principal (§9), les analyses secondaires (§10), le test de
redondance (§11), le traitement edge/prix (§12), les critères de
validation/rejet (§13), la gestion des données manquantes (§14), les
interdictions explicites (§15), et la checklist de tests requis (§16).

---

## 0. Audit documentaire (relu intégralement avant rédaction)

`docs/data_source_research.md` (Phase J), `docs/final_data_strategy.md`
(Phase I), `docs/sot_incremental_information_experiment.md` (Phase F),
`docs/bfe_incremental_information_experiment.md` (Phase G),
`docs/ah_incremental_information_experiment.md` (Phase H),
`docs/operational_validation_specification.md`,
`docs/operational_validation_report.md` (Phase D — source du split
40/30/30 réutilisé ici), `docs/final_engine_specification.md`,
`docs/research_synthesis_e1_e16.md`, `docs/architecture.md`.

**Constats déterminants pour ce protocole** :
- ClubElo a été identifié en Phase J comme la seule piste de cette
  recherche satisfaisant simultanément (a) une information
  potentiellement orthogonale (compétitions hors championnat) et (b) une
  reconstruction PIT immédiatement vérifiable sur le corpus déjà
  existant, sans période d'attente.
- La leçon méthodologique des Phases F/G/H (contrôle de recalibration
  obligatoire, inclus **dès la conception**, jamais ajouté après un
  résultat trompeur) est reprise ici sans exception.
- Le split 40 % rodage / 30 % VALIDATION / 30 % TEST, réutilisé
  **explicitement à la demande de cette Phase K** (contrairement aux
  Phases F/G/H qui utilisaient une seule passe walk-forward sur le
  corpus complet, faute de seuil à protéger), provient de
  `run_stage10_over_under_recalibration.split_burn_in_calibration_test`
  — déjà utilisé sans modification par B1/A2/B2/B3.3/E2/E3/E7/E8/E9/E10
  et par la Phase D (`docs/operational_validation_report.md`,
  pré-enregistrement).

---

## 0bis. Audit direct de ClubElo — ce qui est confirmé, ce qui ne l'est pas

**Blocage opérationnel constaté (signalé avant toute autre chose,
conformément à l'instruction de la Phase K)** : cet environnement
d'exécution ne peut **pas** atteindre `clubelo.com` ni `api.clubelo.com`
— le proxy de sortie réseau de la session renvoie explicitement *"Host
not in allowlist"* pour ces deux domaines (vérifié directement par une
requête `curl` et par l'outil `WebFetch`, tous deux bloqués au niveau du
proxy, pas par le serveur ClubElo lui-même). Conformément à la politique
du proxy (« ne jamais contourner un blocage de politique, le signaler »),
**aucune tentative de contournement n'a été faite**. Conséquence directe,
développée en §16 : l'audit ci-dessous s'appuie exclusivement sur des
**sources secondaires publiques** (dépôts GitHub documentant le format,
articles académiques citant la méthodologie) — jamais sur une
consultation directe de `clubelo.com/API`. Chaque affirmation ci-dessous
est tracée à sa source ; ce qui n'a pu être confirmé que par une source
secondaire est marqué comme tel, jamais présenté comme équivalent à une
vérification directe du fournisseur.

**Format confirmé** (via un dépôt d'archivage tiers documentant
explicitement les champs ClubElo, et corroboré par plusieurs wrappers
communautaires indépendants — `soccerdata`, `penaltyblog` — référençant
les mêmes noms de colonnes) : chaque ligne d'historique par club contient
`Rank, Club, Country, Level, Elo, From, To`. `From`/`To` délimitent une
**fenêtre de validité contiguë** pendant laquelle le rating `Elo` est
constant — [source : archive GitHub `tonyelhabr/club-rankings`, décrivant
explicitement `From` comme *"starting date from which elo is constant,
presumably the day after a match"*].

**Propriété PIT structurelle qui en découle (démonstration, pas une
hypothèse)** : puisque `From` correspond au **lendemain** du match ayant
produit le changement de rating, la ligne dont la fenêtre
`[From, To]` contient une date `D` donnée représente le rating **tel
qu'il était avant tout match disputé ce jour-là** — le rating du jour `D`
lui-même n'intègre **jamais** le résultat d'un match qui se déroule ce
jour `D` (celui-ci ne serait reflété qu'à partir de `D+1`, dans une
nouvelle ligne). Cette propriété est **structurelle au format
d'archivage lui-même** (immuable, non un artefact d'implémentation côté
projet) — elle justifie directement la règle de sélection de §2.

**Inclusion des compétitions hors championnat — confirmée par une source
indépendante, jamais supposée** : une discussion académique consultée
(portant sur l'utilisation d'Elo pour les tirages de Ligue des Champions)
indique explicitement que le rating ClubElo *"contains information from
games played in the national leagues and cups"*, et documente le
traitement spécifique des confrontations aller-retour de Ligue des
Champions/Europa League (échange de points pondéré par `√2` par rapport
à un match unique) — confirmant que les compétitions européennes sont
bien intégrées au calcul, pas seulement les championnats nationaux
[source : analyse académique référencée en Phase J,
`docs/data_source_research.md` §5.B]. **Ce qui n'est PAS confirmé par une
source primaire** : la liste exhaustive des compétitions couvertes pour
chaque club (ex. couverture des matchs de sélection nationale des
joueurs — non pertinent ici, ClubElo étant un rating de **club**, pas de
joueur) et la fréquence exacte de mise à jour pour les clubs disputant
plusieurs compétitions la même semaine.

**Ce qui n'a pu être vérifié ni confirmé ni infirmé** (marqué
explicitement, jamais supposé) :
- Une politique de révision rétroactive documentée par le fournisseur
  (aucune mention trouvée, dans un sens ou dans l'autre, d'une
  correction a posteriori d'une fenêtre `[From, To]` déjà close) — traité
  par précaution comme un **risque résiduel non nul mais non quantifiable
  à ce stade**, jamais comme une garantie absolue.
- La stabilité exacte des chaînes de caractères utilisées pour nommer
  chaque club (ex. `"Paris Saint Germain"` vs `"Paris SG"` vs `"PSG"`) —
  seules des occurrences indirectes ont été observées dans des wrappers
  tiers, jamais une liste exhaustive et à jour des noms exacts utilisés
  par le fournisseur pour les 3 championnats de ce projet.
- La couverture réelle, saison par saison, des équipes des trois
  championnats déjà utilisés (Liga, Ligue 1, Premier League) — y compris
  les clubs promus/relégués, susceptibles de ne pas avoir d'historique
  ClubElo suffisant.

**Conséquence directe et non négociable** : le mapping d'équipes (§4) et
l'audit de couverture (§3) ne peuvent être **verrouillés avec certitude**
qu'après obtention réelle des fichiers ClubElo — ce protocole fige la
**méthode** de construction de ce mapping et de cet audit, jamais les
valeurs elles-mêmes tant qu'elles n'ont pas été mesurées sur les données
réelles (cohérent avec la discipline déjà appliquée à chaque expérience
précédente : « ne jamais supposer une couverture, toujours la mesurer »).

---

## 1. Primitives réutilisées (aucune réimplémentation)

| Besoin | Primitive | Emplacement | Modification |
|---|---|---|---|
| Matrice λ/μ par match | `build_lambda_mu_dataframe` | `run_stage15_e7_total_goals_distribution.py` | Aucune |
| Correction E7/E8 walk-forward | `calibrate_prediction`, `fit_scale_correction_as_of` | `final_engine/calibration.py`, `calibration_engine/scalar_correction.py` | Aucune — réutilisé exactement comme Phase F pour produire `p_over_2_5` |
| Régression logistique walk-forward | `fit_logistic`, `predict_logistic`, `_safe_logit`, `walk_forward_logistic` | `run_stage25_e16_market_movement_information.py` | Aucune sur les fonctions existantes — une **nouvelle** fonction d'offset-regression est ajoutée dans le script de la Phase K, §6 (justifiée, pas une modification des fonctions E16) |
| Split rodage/validation/test | `split_burn_in_calibration_test` | `run_stage10_over_under_recalibration.py` | Aucune — réutilisée **telle quelle**, par championnat × saison, exactement comme Phase D |
| Test statistique | `paired_bootstrap_test` | `calibration_engine/significance.py` | Aucune |
| Brier score | `brier_score` | `calibration_engine/metrics.py` | Aucune |
| Matching Understat/Football-Data | `build_understat_keys`, `match_league_season` | `data_engine/market_odds/matching.py` | Aucune |
| Résolution des timestamps | `conservative_knowledge_time_utc` | `data_engine/market_odds/time_resolution.py` | Aucune |
| Mapping d'équipes déterministe | `team_mapping.py` (Understat) | `data_engine/market_odds/team_mapping.py` | **Nouveau module analogue**, `elo_team_mapping.py` — même discipline (dict explicite par championnat, échec explicite si équipe absente, jamais de fuzzy matching), §4 |

**Nouvelles primitives nécessaires, aucun équivalent existant** :
1. `elo_ratings.py` — parseur du format CSV ClubElo (`Rank, Club,
   Country, Level, Elo, From, To`) et fonction pure
   `elo_as_of(rows, date) -> float | None` (§2).
2. `elo_team_mapping.py` — dict explicite Football-Data → ClubElo par
   championnat (§4).
3. `elo_join.py` (ou module équivalent, mirroir de
   `asian_handicap_odds.py`/`betfair_exchange_odds.py`) — construit le
   dataset apparié `elo_home`/`elo_away`/`elo_diff` par match, point-in-time.
4. Une fonction d'**offset-regression logistique** (§6, modèle B) —
   construction standard (régression logistique avec un terme à
   coefficient fixé à 1), pas une modification de `fit_logistic`
   (fonction générique, réutilisée telle quelle avec une matrice de
   conception différente pour le résidu à ajuster).

---

## 2. Définition PIT du rating et de `elo_diff`

**Règle de sélection, fixée avant toute exécution (jamais choisie en
observant un résultat)** :

```
elo_lookup_date = decision_time.date()   # UTC, decision_time = kickoff_utc - DECISION_OFFSET_HOURS (2.0h, INCHANGE)
Elo_home = valeur de la ligne où From <= elo_lookup_date <= To, pour le club domicile
Elo_away = idem, club exterieur
elo_diff = Elo_home - Elo_away
```

**Justification du choix de `decision_time.date()` plutôt que
`kickoff_utc.date()`** : `decision_time` est, dans tout le reste du
projet, la référence temporelle unique de connaissance (jamais
`kickoff_utc` directement) — utiliser sa date est cohérent avec cette
discipline. Puisque `decision_time <= kickoff_utc` par construction
(`DECISION_OFFSET_HOURS=2.0` strictement positif), `elo_lookup_date` est
**toujours** antérieure ou égale à la date du coup d'envoi — un choix
**strictement plus conservateur** que d'utiliser la date de coup d'envoi
elle-même (déjà démontrée sûre par construction du format, §0bis), jamais
moins sûr.

**Si aucune ligne ne satisfait `From <= elo_lookup_date <= To`** (aucune
interpolation, aucune extrapolation, jamais la ligne la plus proche) :
le match est **exclu** du dataset Elo (§14) — jamais une valeur par
défaut inventée.

**Si ClubElo publie plusieurs entrées ambiguës pour un même club à une
même date** (ne devrait pas se produire si les fenêtres sont
correctement contiguës et non chevauchantes, propriété vérifiée par un
test dédié, §16) : la présence de **plus d'une** ligne satisfaisant la
condition ci-dessus pour un même club/date est traitée comme une
**anomalie de données**, jamais résolue en choisissant celle donnant le
meilleur résultat — le match concerné est exclu et l'anomalie est
comptée et rapportée explicitement dans le rapport de couverture (§3).

**Aucune valeur post-match n'est jamais utilisée** — la propriété
structurelle démontrée en §0bis garantit que la ligne sélectionnée pour
la date `D` n'intègre jamais un match disputé le jour `D` lui-même ;
vérifié en outre par un test dédié (injection d'une observation future,
§16, même discipline que Phases F/G/H).

---

## 3. Données et couverture (plan — valeurs à mesurer, jamais supposées)

**Ce protocole fige la méthode de mesure, pas les valeurs** (§0bis :
aucun fichier ClubElo réel n'a pu être obtenu à ce stade). Une fois les
fichiers réels obtenus, le rapport de couverture (`docs/elo_incremental_information_experiment.md`,
§5 de l'énoncé) devra présenter, sans exception :

| Élément | À mesurer |
|---|---|
| Matchs totaux (corpus déjà utilisé, appariés Understat×Football-Data) | 2123 (valeur déjà connue, non redérivée) |
| Matchs avec `Elo_home` disponible | À mesurer |
| Matchs avec `Elo_away` disponible | À mesurer |
| Matchs exploitables (les deux disponibles, PIT valide) | À mesurer |
| Matchs exclus, par cause (club non mappé / rating absent à la date / anomalie de lignes multiples / historique de calibration E7-E8 insuffisant) | À mesurer, cause par cause, jamais fusionné en un seul total |
| Équipes non mappées (§4) | À mesurer, listées nominativement |
| Couverture par championnat | À mesurer — **si elle diffère fortement d'un championnat à l'autre, ce doit être signalé avant toute lecture du résultat de l'expérience** (instruction explicite de la Phase K, §6) |
| Couverture par saison | Idem |
| Dates problématiques (ex. club promu sans historique ClubElo suffisant, club en interruption de fenêtre `[From,To]`) | À mesurer et lister |

**Interdiction explicite reprise de l'énoncé (§6)** : le dataset final
ne doit **jamais** être constitué en sélectionnant, de façon
opportuniste, les matchs où la donnée est disponible sans en documenter
les conséquences — chaque exclusion doit être **comptée et motivée**,
jamais silencieusement absorbée dans un total global.

---

## 4. Matching Football-Data → ClubElo (déterministe, auditable)

**Méthode, fixée avant toute exécution** : un module dédié
`elo_team_mapping.py`, strictement analogue à `team_mapping.py`
(mapping Understat déjà en production) : un dictionnaire Python explicite
par championnat, `{nom_football_data: nom_clubelo}`, construit et
vérifié **à la main**, entrée par entrée, contre la liste réelle des
clubs ClubElo obtenue lors de l'acquisition des fichiers — **jamais par
correspondance floue (fuzzy matching), jamais par une règle de
normalisation automatique** (ex. suppression d'accents, troncature). Une
équipe absente du mapping **lève une erreur explicite** au chargement,
exactement comme `resolve_understat_name` — jamais associée par défaut à
l'entrée la plus proche alphabétiquement.

**État actuel de ce mapping (§0bis)** : une ébauche fondée sur les
conventions de nommage observées dans les wrappers communautaires
(`soccerdata`, archives GitHub) est produite dans le code (§6 de
l'énoncé), mais **marquée explicitement comme NON VÉRIFIÉE** contre les
données réelles — condition bloquante pour toute exécution réelle
(§16). Chaque entrée ambiguë (ex. accents, orthographe alternative,
clubs ayant changé de nom) devra être vérifiée manuellement, un par un,
contre la liste réelle des clubs présents dans les fichiers ClubElo
effectivement obtenus, avant tout chargement réel du dataset.

**Rapport de couverture du matching** (§3, à produire lors de
l'exécution réelle) : nombre d'équipes mappées avec succès, liste
nominative de toute équipe non mappée, et confirmation qu'aucune
correspondance n'a été résolue par une méthode approximative.

---

## 5. Split (réutilisé sans modification des proportions)

`split_burn_in_calibration_test` (INCHANGÉE), appliquée **par
championnat × saison**, exactement comme Phase D — 40 % rodage / 30 %
VALIDATION / 30 % TEST, tri chronologique par `kickoff_utc`. Le rodage
n'est **jamais** évalué directement — il sert de pool historique pour le
calcul walk-forward des modèles B/C/D (§6), exactement comme « le rodage
sert de pool de calibration walk-forward pour VALIDATION » (Phase D,
`docs/operational_validation_report.md`).

**Résolution d'une ambiguïté méthodologique non bloquante, documentée ici
avant exécution** (précédent direct : Phases F/G/H ont résolu des
ambiguïtés analogues sans s'arrêter, en documentant la justification) :
contrairement à la Phase D, cette expérience ne sélectionne **aucun
seuil** — il n'y a donc rien à protéger d'un data snooping de sélection.
Le test statistique principal (§9) est en conséquence calculé sur la
population **VALIDATION + TEST regroupées** (maximisant l'effectif
disponible, cohérent avec le choix déjà fait par E16/Phases F/G/H de ne
jamais restreindre artificiellement l'effectif en l'absence de seuil à
protéger), tandis que VALIDATION et TEST sont **également rapportées
séparément** comme un contrôle de robustesse temporelle obligatoire
(§9-10) : la conclusion ne doit **jamais** être portée par un seul des
deux segments dans une direction que l'autre contredirait. Le rodage,
lui, ne contribue **jamais** au calcul du test principal ni aux segments
de robustesse — uniquement à l'historique walk-forward des modèles B/C/D
et à la calibration E7/E8 (déjà valable dès `_MIN_CALIBRATION_MATCHES_FOR_SCALE=30`,
avant même le début du rodage).

`elo_diff` reste, en toute circonstance, calculé selon la règle PIT de
§2 **indépendamment** du split — le split ne détermine que la population
d'évaluation d'un modèle déjà walk-forward, jamais la manière dont
`elo_diff` lui-même est construit.

---

## 6. Modèles A/B/C/D (figés avant exécution)

Conception factorielle **2×2** (recalibration × Elo), résolvant
explicitement l'instruction de l'énoncé et directement inspirée du
principe de contrôle des Phases F/G/H, mais rendue explicite à quatre
modèles distincts (plutôt que trois) comme demandé :

| Modèle | Définition | Paramètres libres | Rôle |
|---|---|---|---|
| **A** — Modèle actuel corrigé E7/E8 | `p_A = p_over_2_5` (`calibrate_prediction`, INCHANGÉE) | 0 (passe-plat) | Baseline brute |
| **B** — Modèle actuel + Elo | `p_B = sigmoid(a0 + logit(p_A) + c·elo_diff)` — coefficient de `logit(p_A)` **fixé à 1** (offset), seuls `a0` et `c` sont ajustés | 2, walk-forward | Comparaison **naïve** : Elo ajouté sans laisser le modèle de base se recalibrer lui-même |
| **C** — Modèle actuel recalibré sans Elo (CONTRÔLE OBLIGATOIRE) | `p_C = sigmoid(a + b·logit(p_A))`, `a` et `b` libres | 2, walk-forward | Isole l'effet de la seule recalibration générique |
| **D** — Modèle recalibré + Elo (TEST) | `p_D = sigmoid(a + b·logit(p_A) + c·elo_diff)`, `a`, `b`, `c` tous libres | 3, walk-forward | Test propre de l'information incrémentale d'Elo, **après** recalibration |

**Justification du modèle B comme offset-regression** : une régression
logistique standard (tous coefficients libres) ne permettrait pas de
distinguer B de D — les deux convergeraient vers la même solution ajustée
si `logit(p_A)` et `elo_diff` étaient tous deux laissés libres. Fixer le
coefficient de `logit(p_A)` à 1 dans B (construction statistique standard,
dite régression à « offset » — un terme dont l'effet est connu et non
réestimé) est la seule façon de construire un modèle « Elo ajouté sans
recalibration du modèle de base » réellement distinct de D. Ceci
**réutilise** `fit_logistic`/`predict_logistic` (E16, INCHANGÉES) en leur
passant, pour B, une matrice de conception ne contenant qu'une constante
et `elo_diff`, appliquée au **résidu** `logit(y_proxy) - logit(p_A)`... —
**note de simplification retenue** : par souci de rester strictement
dans le cadre déjà validé de `fit_logistic` (régression logistique
standard, pas une regression sur résidu continu), B est implémenté comme
`sigmoid(a0 + 1·logit(p_A) + c·elo_diff)` en ajustant `(a0, c)` par
`fit_logistic` sur une matrice à 2 colonnes `[1, elo_diff]` avec
**`logit(p_A)` inclus comme terme constant additionnel dans le calcul de
la vraisemblance** (implémentation détaillée : nouvelle fonction pure
`fit_logistic_with_offset(offset, X, y)`, appelée avec `offset =
logit(p_A)`, `X = [1, elo_diff]` — généralisation directe et minimale de
`fit_logistic`, testée isolément avant tout usage, §16).

**Reprend** `_MIN_TRAIN=30` (E16, INCHANGÉE) pour B/C/D. Le modèle A ne
dépend que de `_MIN_CALIBRATION_MATCHES_FOR_SCALE=30` (E7/E8, INCHANGÉE).

---

## 7. Cible principale

**Over 2.5**, définition **exactement identique** à E11/E14/E16/Phases
F/G/H : `y = 1[total_goals > 2.5]`, `p_over_2_5` dérivée de la même
matrice de score corrigée E7/E8 (`calibrate_prediction`, seuil `2.5` de
`DEFAULT_OU_THRESHOLDS`). **Aucune cible secondaire n'est testée dans
cette expérience** (espérance totale de buts, 1X2) — choix délibéré pour
éviter toute correction de comparaisons multiples superflue et rester
strictement fidèle à la discipline « une seule hypothèse primaire par
expérience » déjà appliquée en Phases F/G/H. Si une extension à d'autres
cibles est un jour décidée, elle nécessitera un **nouveau**
pré-enregistrement dédié, jamais un ajout a posteriori à ce protocole.

---

## 8. Métrique

Brier score (formule binaire standard `(p-y)²`, comme Phases F/G/H) sur
`p_A`, `p_B`, `p_C`, `p_D` — population éligible (les quatre modèles
disponibles pour le même match, après rodage walk-forward et exclusions
Elo, §3/§14).

---

## 9. Test statistique principal (pré-spécifié)

**Hypothèse primaire unique** : le modèle **D** (recalibré + Elo)
améliore-t-il significativement le modèle **C** (recalibré seul) au sens
du Brier score ?

`paired_bootstrap_test` (INCHANGÉ, 10 000 rééchantillonnages) sur la
différence appariée de Brier `Brier(D) - Brier(C)`, calculée :
1. **Population primaire** : VALIDATION + TEST regroupées (§5) — décide
   seule du verdict A vs D/C (mais voir condition de robustesse
   ci-dessous, non négociable).
2. **Contrôle de robustesse temporelle obligatoire** : la même
   comparaison, calculée **séparément** sur VALIDATION seule et sur TEST
   seul. Si les deux segments montrent une direction significativement
   **contradictoire** (l'un IC95 % entièrement < 0, l'autre entièrement
   > 0), le résultat global ne peut **pas** être classé `VALIDÉ`, quel
   que soit le résultat sur la population regroupée (critère de rejet
   explicite, §13).

**Comparaisons secondaires, toujours rapportées mais jamais utilisées
seules pour le verdict** : `Brier(A)` vs `Brier(C)` (quantifie l'effet de
la seule recalibration, comme Phases F/G/H) ; `Brier(B)` vs `Brier(A)`
(comparaison naïve, attendue trompeuse si le schéma des Phases F/G/H se
reproduit) ; `Brier(B)` vs `Brier(D)` (si B ≈ D, le coefficient fixe de
recalibration dans B n'était pas contraignant — diagnostic, jamais un
critère de verdict).

**Aucune correction Holm-Bonferroni n'est nécessaire pour l'hypothèse
primaire unique** (D vs C) — même discipline que Phases F/G/H. Les
décompositions de robustesse (§10) restent des diagnostics, jamais des
tests de significativité indépendants utilisés pour le verdict.

---

## 10. Analyses secondaires (robustesse, jamais suffisantes seules)

Si l'effectif le permet (`n≥30` par cellule, convention constante du
projet) : championnat, saison, première/deuxième moitié temporelle du
corpus (tri par `decision_time`, coupure à la médiane), amplitude de
`elo_diff` (tranches à définir **après** observation de la distribution
réelle de `elo_diff`, jamais avant — une répartition en tranches de
`elo_diff` ne peut pas être fixée sans connaître sa distribution
empirique, contrairement aux autres découpes qui sont structurelles ;
**si cette tranche devait influencer le verdict, elle ne le pourra
jamais seule**, conformément à l'énoncé), couverture Elo (ex. matchs où
les deux clubs ont un historique ClubElo long vs court). **Aucune cellule
secondaire ne peut, à elle seule, valider Elo** (règle mécanique,
identique à Phases F/G/H).

---

## 11. Test de redondance

Objectif : déterminer si `elo_diff` apporte une information qui n'est
**pas déjà contenue** dans les variables du modèle actuel — jamais une
simple régression Elo+prédiction sans contrôle. Deux vérifications,
toutes deux rapportées, aucune utilisée seule pour le verdict (celui-ci
reste défini exclusivement par §9) :
1. **Coefficient `c` de `elo_diff` dans le modèle D**, sur la dernière
   fenêtre walk-forward complète (tout le corpus comme historique) :
   son signe et son ordre de grandeur sont rapportés, mais **aucun seuil
   de significativité du coefficient lui-même n'est utilisé comme
   critère de verdict** (le verdict repose exclusivement sur le Brier
   hors-échantillon, §9 — un coefficient significatif en échantillon
   plein ne garantit pas une amélioration hors-échantillon, et
   inversement).
2. **Corrélation descriptive** entre `elo_diff` et `logit(p_A)` (le
   modèle actuel) sur la population exploitable — si cette corrélation
   est déjà très élevée, elle constituerait une explication *a priori*
   plausible d'une éventuelle absence d'information incrémentale
   (`elo_diff` reformulerait ce que `poisson_simple` capture déjà via les
   forces d'attaque/défense) — rapportée à titre de contexte
   interprétatif, jamais comme un critère de rejet automatique.

---

## 12. Edge / prix (descriptif uniquement)

Conformément à l'instruction explicite : **aucun seuil de pari n'est fixé
dans cette expérience.** Si, et seulement si, le verdict de §13 est
`VALIDÉ`, une section **strictement descriptive** du rapport final
pourra présenter la distribution de `raw_edge`/`price_edge` (réutilisation
inchangée de `value_engine.edge`) pour le sous-ensemble où Elo modifie la
probabilité de façon notable — **jamais un seuil recommandé, jamais une
stratégie, jamais une activation de `BET`**. `min_edge_threshold` reste
`None` quel que soit le résultat de cette expérience (§15).

---

## 13. Critères de validation et de rejet (grille figée avant observation)

- **`VALIDÉ`** — **toutes les conditions suivantes, simultanément** :
  IC95 % de `Brier(D) - Brier(C)` **entièrement < 0** sur la population
  primaire (VALIDATION+TEST) ; **aucune contradiction de direction**
  entre VALIDATION seule et TEST seul (§9) ; robustesse confirmée sur
  chaque championnat et chaque saison (aucune inversion significative,
  IC95 % `ci_low > 0`, dans aucune décomposition) ; couverture Elo
  suffisante et non fortement déséquilibrée entre championnats/saisons
  sans explication documentée (§3) ; aucune fuite détectée (§16) ;
  effectif ≥ 30 dans chaque sous-groupe examiné pour le verdict.
- **`NON VALIDÉ`** — IC95 % de `Brier(D) - Brier(C)` chevauchant zéro
  sur la population primaire, **et** direction du point estimate stable
  (pas d'inversion nette entre VALIDATION et TEST) — résultat le plus
  probable au vu des précédents Phases F/G/H (redondance/absence d'apport
  spécifique après isolement de la recalibration).
- **`ABSENCE DE PREUVE`** — effectif insuffisant dans un sous-groupe clé
  (`< 30`) empêchant une conclusion robuste, sans que la population
  globale ne soit elle-même trop restreinte (auquel cas voir `DONNÉES
  INSUFFISANTES`) ; ou IC95 % très large sans direction nette ; ou
  contradiction de direction entre VALIDATION et TEST sans qu'aucun des
  deux segments ne soit lui-même significatif (signal instable, pas un
  rejet net).
- **`DONNÉES INSUFFISANTES`** — si la couverture ou l'effectif global
  s'avéraient, une fois les fichiers réels obtenus, insuffisants pour
  toute conclusion (`n` global exploitable `< 30`, ou couverture Elo trop
  dégradée sur un championnat entier pour permettre son inclusion).
- **`PROBLÈME MÉTHODOLOGIQUE`** — si un test de fuite (§16) échoue, si le
  blocage réseau documenté en §0bis empêche toute exécution réelle (état
  actuel de cette Phase K, voir §16), si une anomalie de mapping ou de
  lignes `[From,To]` chevauchantes est détectée sans pouvoir être
  résolue de façon déterministe, ou si la propriété PIT démontrée en §0bis
  ne se vérifie pas empiriquement sur les données réelles une fois
  obtenues.

**Aucune formulation intermédiaire n'est autorisée.**

---

## 14. Gestion des données manquantes

Un match sans `Elo_home` ou sans `Elo_away` disponible à la date PIT
(§2) est **exclu** (jamais imputé, jamais remplacé par une moyenne de
championnat ou une valeur par défaut) — comptabilisé et motivé
explicitement dans le rapport de couverture (§3). Un club absent du
mapping (§4) lève une erreur explicite au chargement — jamais une
correspondance approximative silencieuse. Une anomalie de lignes
`[From,To]` multiples/chevauchantes pour une même date exclut le match
concerné et est comptée séparément (§2).

---

## 15. Interdictions explicites (non négociables pour cette Phase K)

- Aucune modification de `poisson_simple`/`dixon_coles`/`xg_model`,
  d'E7/E8/E14/E15/E16, des gates ou de `final_engine`.
- Aucune activation de `BET`. `min_edge_threshold` reste `None`.
- Aucun seuil d'Elo, aucune tranche (bins), aucun seuil d'edge, aucune
  taille minimale d'effet, aucun hyperparamètre, aucune fenêtre
  historique inventés — tout paramètre déjà fixé ci-dessus est tracé à
  une règle structurelle préexistante (`_MIN_TRAIN=30`,
  `_MIN_CALIBRATION_MATCHES_FOR_SCALE=30`, `DECISION_OFFSET_HOURS=2.0`,
  split 40/30/30) ou à une propriété démontrée du format ClubElo (§0bis).
- Aucune sélection a posteriori de championnat/saison/tranche « gagnante ».
- Aucune multiplication de cibles pour fabriquer un résultat positif
  (§7 : Over 2.5 uniquement).
- Aucune conclusion de rentabilité opérationnelle tirée de cette
  expérience (§12).
- Cette expérience est la seule autorisée pour cette Phase — aucun
  enchaînement automatique sur une nouvelle expérience après le rapport
  final.

---

## 16. Tests requis avant exécution réelle (checklist)

- `elo_as_of` : sélectionne exactement la ligne `From <= date <= To` ;
  retourne `None` si aucune ligne ne correspond ; lève/signale une
  anomalie si plusieurs lignes correspondent.
- Propriété PIT : un rating dont `From` est postérieur à
  `decision_time.date()` n'est **jamais** sélectionné (test direct +
  test de propriété Hypothesis, comme Phases F/G/H).
- Garde-fou absolu : injection d'une observation ClubElo future (rating
  extrême, `From` postérieur au match) et démonstration qu'elle est
  exclue par le code réel **et** qu'elle changerait le résultat si le
  filtre était retiré (même discipline que Phases F/G/H).
- Absence de fuite entre saisons : le pool walk-forward des modèles B/C/D
  ne mélange jamais un match futur (test « déplacer une ligne dans le
  futur ne change jamais une prédiction antérieure », comme E16).
- Matching déterministe : `elo_team_mapping` lève une erreur explicite
  sur une équipe absente, jamais une résolution approximative.
- Comportement des équipes absentes : un match sans mapping ou sans
  rating à la date PIT est exclu, jamais imputé (test dédié).
- Calcul correct de `elo_diff` : `Elo_home - Elo_away`, signe vérifié sur
  des cas construits à la main.
- Contrôle de recalibration : test reproduisant exactement le schéma
  Phases F/G/H (« la recalibration seule explique le gain apparent,
  Elo n'ajoute rien ») sur des données synthétiques construites pour ce
  cas — vérifie que le pipeline de verdict classerait correctement ce
  scénario `NON VALIDÉ`.
- Cohérence des datasets A/B/C/D : mêmes lignes évaluées pour les quatre
  modèles (population identique), jamais une comparaison sur des
  échantillons différents.
- `fit_logistic_with_offset` : testée isolément contre un cas où
  `offset=0` (doit reproduire exactement `fit_logistic` standard) et
  contre un cas de recalibration pure (offset non trivial, coefficient
  du terme forcé à 1 vérifié algébriquement).
- Exclusion correcte des observations sans Elo : comptage exact,
  jamais une valeur par défaut.
- Absence d'utilisation de la clôture : sans objet pour ClubElo (aucune
  notion de cote de clôture) — vérifié que le module `elo_ratings.py` ne
  contient aucun champ de cote de marché d'aucune sorte (garde-fou
  structurel, comme Phases F/G/H pour les modules de marché).
- Split : `split_burn_in_calibration_test` produit des ensembles
  disjoints et exhaustifs (rodage/validation/test) pour chaque
  championnat × saison — non-régression, réutilise directement les tests
  déjà existants pour cette fonction (aucun nouveau test requis sur la
  fonction elle-même, seulement sur son intégration).
