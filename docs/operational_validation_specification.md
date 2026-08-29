# Cadrage méthodologique de la décision BET / NO BET (Phase C)

**Nature de ce document.** Cadrage méthodologique pur. Aucun code de
moteur n'est modifié. Aucun seuil d'edge n'est fixé. Aucun backtest de
rentabilité n'est lancé. Aucune optimisation n'est effectuée. Aucune
expérience E17 n'est lancée. Aucun résultat d'E1→E16 n'est modifié. Ce
document définit **comment** un seuil opérationnel pourrait un jour être
validé scientifiquement — il ne le valide pas, et ne propose aucune
valeur numérique.

Documents de référence relus intégralement pour ce cadrage :
`docs/research_synthesis_e1_e16.md`, `docs/final_engine_specification.md`,
`docs/final_engine_user_guide.md`, `docs/architecture.md`,
`docs/research_framework.md`, ainsi que le code actuel de
`src/sys_foot_quant/final_engine/` et ses tests.

---

## 1. Constat explicite sur l'état actuel du moteur

Le moteur (Phase B, commit `98d8931`) sait déjà, de bout en bout :

- produire une distribution de buts et des probabilités Over/Under
  (Niveaux A-B, `prediction.py`/`calibration.py`, s'appuyant sur la
  correction E7/E8 validée) ;
- calculer un prix juste (Niveau C, `pricing.py`) ;
- comparer ce prix au marché d'ouverture (Niveau D, `market.py`,
  `compare_over_under_to_market`) ;
- calculer `raw_edge`/`price_edge` (`value_engine.edge`) ;
- appliquer l'ensemble des scientific gates (Niveau E, `gates.py` :
  historique insuffisant, jour ambigu, cote de marché incomplète,
  incohérence de distribution, zone de calibration biaisée, discrimination
  non démontrée) ;
- produire une décision `BET`/`NO_BET` avec code de raison explicite
  (Niveau F, `decision.py`).

Ce qu'il ne possède **pas**, délibérément : une valeur validée de
`OperationalThresholds.min_edge_threshold` (`gates.py`, actuellement
`None`) permettant de transformer un edge positif en décision `BET`. Avec
la configuration par défaut, `edge_threshold_gate` se déclenche
systématiquement (voir `gates.py::edge_threshold_gate` et le test
`tests/unit/test_final_engine_gates.py::test_edge_threshold_gate_always_triggers_when_threshold_unset`)
— le moteur ne produit donc aujourd'hui que des `NO_BET`. C'est un état
**intentionnel**, pas une limitation à corriger dans l'urgence : aucune
des seize expériences de la campagne E1→E16 n'a validé de règle de
conversion edge→pari.

---

## 2. Trois questions à ne jamais confondre

| # | Question | Ce qu'elle mesure | Ce qu'E1→E16 en disent |
|---|---|---|---|
| **A** | **Exactitude probabiliste** — la probabilité est-elle correctement calibrée ? | Écart entre probabilité annoncée et fréquence réelle observée, dans une tranche donnée (`reliability_bins`, décomposition de Murphy) | **Répondue en grande partie** — E2/E3/E7/E8/E11 établissent une calibration démontrée sur les seuils 1.5/2.5/3.5, hors zone [0.6,0.7) d'Over 2.5 (E11, non corrigée par E14) et hors Premier League pour la composante discrimination (E4/E11/E15) |
| **B** | **Existence d'un edge théorique** — le prix modèle diffère-t-il du prix marché ? | `raw_edge`/`price_edge`, une simple différence numérique | **Partiellement répondue** — un edge est calculable partout, mais sa magnitude n'a jamais été démontrée informative : au contraire, E5/E10/E12 montrent que le désaccord modèle/marché ne prédit pas une fréquence réelle plus proche du modèle, et E12 montre même l'inverse (les zones fiables ont des edges plus *petits*) |
| **C** | **Rentabilité opérationnelle** — une règle de sélection donnée produit-elle une performance robuste après marge, variance et coûts ? | ROI, yield, drawdown, robustesse hors échantillon d'une **règle de pari** appliquée à un flux réel de décisions | **Jamais validée** — la seule expérience économique réelle du projet (E1, règle EV>0 brute sur le 1X2) a produit un **signal négatif significatif** (IC95% du profit entièrement négatif, n=1888). Aucune règle de sélection n'a été testée depuis sur l'Over/Under |

**Conséquence directe pour la Phase C** : le moteur actuel répond
correctement à A et calcule B, mais rien ne permet aujourd'hui de
répondre à C. Le cadrage ci-dessous porte exclusivement sur la manière de
répondre un jour à C sans répéter l'erreur de logique qui consisterait à
déduire une conclusion de type C directement d'un résultat de type A ou B
(ex. « la probabilité est bien calibrée, donc parier dessus est
rentable » — un raisonnement non valide, que le principe d'abstention du
moteur interdit déjà structurellement).

---

## 3. Propriétés qu'un futur seuil opérationnel devra démontrer

Sans tester ni chiffrer quoi que ce soit, un futur seuil d'edge (ou toute
autre règle de conversion edge→pari) devra démontrer, au minimum, les
propriétés suivantes avant d'être considéré pour la production :

- **Performance hors échantillon (OOS)** — mesurée sur des données
  strictement postérieures à celles ayant servi à choisir le seuil, jamais
  sur l'échantillon d'ajustement (section 6).
- **Stabilité temporelle** — la performance ne doit pas être portée par
  une seule fenêtre temporelle courte ; elle doit se répliquer sur
  plusieurs sous-périodes disjointes.
- **Stabilité par championnat** — testée séparément pour chaque
  championnat, jamais poolée aveuglément (voir section 10 sur la Premier
  League spécifiquement).
- **Stabilité par saison** — testée séparément par saison, comme c'est
  déjà la discipline systématique d'E1→E16.
- **Nombre de paris suffisant** — un résultat porté par un petit nombre
  de décisions n'est jamais concluant, quelle que soit son amplitude
  apparente (cohérent avec la convention `n≥30` déjà utilisée dans
  E5-E16 pour les tests de fiabilité, et avec les leçons de puissance
  documentées en section G2 de `docs/research_framework.md`).
- **Incertitude statistique explicite** — tout résultat de performance
  doit être accompagné d'un intervalle de confiance (bootstrap ou
  équivalent), jamais d'un point estimate seul.
- **Sensibilité au choix exact du seuil** — un seuil dont la performance
  s'effondre pour une variation minime (ex. 5 % au lieu de 6 %) est un
  signe de surajustement, pas de robustesse.
- **Sensibilité aux hypothèses de prix** — la performance ne doit pas
  dépendre d'une hypothèse de prix non vérifiable (ex. cote disponible à
  un horaire précis non garanti par les données Football-Data — voir la
  réserve `TIMESTAMP_STATUS_HYPOTHETICAL` déjà documentée depuis E1).
- **Comparaison à une baseline** — jamais interprétée en absolu (section
  5).
- **Prise en compte de la marge bookmaker** — toute mesure de
  performance doit utiliser la cote réelle (avec marge), pas seulement la
  probabilité implicite normalisée, pour ne jamais surestimer un edge net
  de coût de transaction.
- **Robustesse aux petites erreurs de probabilité** — le modèle
  `poisson_simple` n'est pas parfaitement calibré partout (section 3 de
  `docs/research_synthesis_e1_e16.md`) ; un seuil qui ne fonctionnerait
  que si la probabilité modèle était exacte au dixième de point près
  serait, par construction, non robuste aux limites déjà documentées du
  moteur.

---

## 4. Benchmarks nécessaires (protocole décrit, jamais exécuté)

Avant toute validation opérationnelle, la performance d'un seuil candidat
devra être comparée, au minimum, aux baselines suivantes — décrites ici
uniquement en tant que protocole :

| Baseline | Rôle |
|---|---|
| **Marché seul** | Suivre systématiquement le prix implicite du marché (ou une règle triviale de type « toujours Over » / « toujours Under ») — établit le niveau de performance qu'obtiendrait un acteur n'utilisant aucune information du modèle |
| **Modèle seul, sans sélection** | Émettre une décision sur 100 % des matchs qualifiables (aucun filtre d'edge) — mesure ce qu'apporterait le modèle brut, avant tout filtrage |
| **Modèle + edge threshold** | La règle réellement candidate à la validation — comparée aux deux baselines précédentes, jamais évaluée isolément |
| **Marché implicite comme benchmark de prix** | Déjà utilisé structurellement par le moteur (Niveau D) — à conserver comme référence de prix dans toute évaluation future, jamais remplacé par une hypothèse de prix non observée |

Aucune de ces comparaisons n'est exécutée dans ce document. Le protocole
qui les rendrait exploitables sans data snooping est décrit en section 6
et formalisé en section 12.

---

## 5. Futur protocole de validation — principes

Un futur protocole de validation opérationnelle (jamais exécuté ici)
devra respecter, sans exception :

**Séparation temporelle stricte.** Quatre segments chronologiques
disjoints et ordonnés — entraînement des modèles, calibration (walk-
forward E7/E8, déjà en place), **validation** (où un ou plusieurs seuils
candidats sont examinés) et **test** (où le seuil retenu, et lui seul,
est évalué une seule fois). Aucun de ces segments ne doit se recouvrir
avec un autre pour le même match.

**Sélection du seuil hors de l'échantillon de test.** Le seuil ne doit
**jamais** être choisi en observant sa performance sur l'échantillon qui
servira ensuite à annoncer cette même performance — c'est la règle
anti-data-snooping la plus fondamentale du projet, déjà appliquée à
chaque expérience d'E1→E16 (aucun seuil, aucune fenêtre, aucun hyper
paramètre n'y a jamais été ajusté après observation du résultat final).

**Comparaisons multiples corrigées.** Si plusieurs seuils candidats (ou
plusieurs variantes : par championnat, par tranche d'edge, etc.) sont
examinés en phase de validation, une correction adaptée (Holm-Bonferroni,
déjà utilisée en E16, ou équivalent) devra être appliquée avant toute
déclaration de significativité en phase de test.

**Robustesse, jamais un pic isolé.** Un seuil ne doit jamais être retenu
parce qu'une seule tranche, un seul championnat ou une seule saison
produit un résultat spectaculaire — exactement la discipline déjà
appliquée en E1→E16 (ex. E16 §12 : une seule cellule exploratoire
favorable, explicitement signalée comme non concluante, jamais utilisée
pour infléchir le verdict global).

**Incertitude quantifiée.** IC95% bootstrap (ou méthode équivalente déjà
disponible dans `calibration_engine/significance.py`) sur toute métrique
de performance annoncée — jamais un point estimate seul, cohérent avec la
pratique systématique d'E1→E16.

**Stabilité par sous-groupe.** Championnats et saisons testés séparément,
jamais uniquement en agrégat — cohérent avec la section 3 ci-dessus et
avec la pratique déjà établie du projet.

---

## 6. Métriques futures à rendre disponibles (non calculées ici)

| Métrique | Rôle |
|---|---|
| ROI | Retour sur investissement — **insuffisant seul** (voir section 8) |
| Profit moyen par pari | Grandeur déjà utilisée en E1 (`paired_bootstrap_test` sur le profit), à reconduire |
| Hit rate | Taux de réussite brut — à ne jamais interpréter sans le prix associé (un hit rate élevé à des cotes basses peut être non rentable) |
| Yield | Profit rapporté à la mise totale engagée, distinct du ROI par pari |
| Nombre de paris | Condition de puissance statistique (section 3) |
| Maximum drawdown | Déjà disponible dans `risk_engine/metrics.py` — pertinent pour juger la praticabilité d'une règle, pas seulement sa rentabilité moyenne |
| Volatilité | Idem — dispersion du résultat, pas seulement sa moyenne |
| Intervalles de confiance | Sur chacune des métriques ci-dessus, jamais un point estimate seul |
| Performance par championnat | Section 3, 10 |
| Performance par saison | Section 3 |
| Performance par tranche d'edge | Nécessaire pour étudier la sensibilité au seuil (section 3) sans présumer qu'un edge plus grand est nécessairement plus fiable (rappel : E12 a montré l'inverse dans le cas testé) |
| Calibration des paris sélectionnés | Vérifier que le sous-ensemble de matchs qui passeraient le futur filtre reste lui-même bien calibré — un filtre pourrait en principe sélectionner un sous-ensemble moins bien calibré que la population globale, ce qui devrait être détecté, pas supposé impossible |

**Rappel explicite du protocole** : le ROI seul n'est jamais suffisant. Un
ROI positif porté par un faible nombre de paris, une volatilité extrême,
un drawdown sévère, ou une performance concentrée sur un seul
championnat/une seule saison ne constitue pas une validation.

---

## 7. Le problème de la sélection de seuil

**Risque identifié explicitement** : un seuil d'edge plus élevé réduit
mécaniquement le nombre de paris retenus tout en pouvant, par pur hasard
d'échantillonnage, augmenter leur ROI apparent — un phénomène statistique
attendu (moins d'observations, plus de variance, plus de chances qu'un
sous-échantillon extrême affiche un résultat favorable), pas
nécessairement un signe de qualité réelle. **« Le seuil qui donne le
meilleur ROI historique » est donc explicitement écarté comme critère de
sélection** — ce serait la définition même du surajustement, et
reproduirait exactement l'erreur que le protocole d'E1→E16 a
systématiquement évitée (aucun seuil, aucune fenêtre, aucun sous-groupe
n'y a jamais été retenu sur la base d'un critère de performance observée
après coup).

**Règle de sélection alternative, définie ici sans être appliquée** : un
seuil candidat ne devrait être considéré que s'il satisfait
**simultanément** :
- une performance démontrée hors échantillon (section 5) ;
- une robustesse across sous-groupes (section 3) ;
- un intervalle de confiance de la performance qui exclue le point nul
  (ou la baseline pertinente) après correction pour comparaisons
  multiples (section 5) ;
- une taille d'échantillon suffisante pour que cet intervalle de
  confiance soit lui-même informatif (pas simplement large et couvrant
  tout) ;
- une stabilité de conclusion si le seuil est légèrement perturbé
  (section 3, sensibilité).

Un seuil qui maximise le ROI historique mais échoue sur un seul de ces
critères ne serait **pas** retenu par cette règle — c'est précisément
l'objectif : préférer un signal plus modeste mais reproductible à un
signal plus spectaculaire mais fragile.

---

## 8. Edge et incertitude — ne jamais confondre les deux

Le moteur actuel calcule `raw_edge`/`price_edge` comme des différences
numériques ponctuelles. Rien dans leur calcul n'incorpore aujourd'hui une
notion d'incertitude — c'est un choix de conception assumé du MVP
(`docs/final_engine_specification.md` section 11 : « une différence de
probabilité n'est jamais, à elle seule, une edge exploitable »). Pour
toute validation opérationnelle future, il est nécessaire de documenter
la distinction, jamais de la confondre implicitement :

- `estimated_edge` — la valeur actuellement calculée par
  `value_engine.edge.edge`/`expected_value`, une estimation ponctuelle.
- `uncertainty_of_edge` — une mesure, encore à concevoir, de la
  précision de cette estimation (dépendant au minimum de l'incertitude
  sur `p_model` elle-même — fonction de la taille de l'historique de
  calibration, `n_calibration_used`, déjà exposée dans la sortie du
  moteur — et de l'incertitude sur le prix de marché lui-même).

Une **piste conceptuelle**, explicitement non implémentée et non
testée — un ratio du type `estimated_edge / uncertainty_of_edge`, ou un
intervalle de confiance direct sur l'edge plutôt que sur sa seule valeur
ponctuelle — est envisageable pour une future itération, mais reste
marquée sans ambiguïté :

> **HYPOTHÈSE FUTURE** — aucune définition de `uncertainty_of_edge`,
> aucun ratio edge/incertitude, n'a été conçue en détail, testée, ou
> intégrée au moteur. Rien n'est ajouté au code à ce stade.

---

## 9. Cas Premier League

La conclusion d'E15 est strictement conservée : **absence de
discrimination confirmée mais inexpliquée**, calibration correcte
(classe B). Aucun coefficient Premier League n'existe ni ne doit être
créé sans une nouvelle expérience dédiée (interdiction déjà actée dans
`docs/final_engine_specification.md` section 9 et reprise ici).

**Conséquence pour le futur protocole de validation opérationnelle** :
il ne doit **jamais** supposer qu'un seuil d'edge validé sur un
championnat où la discrimination est démontrée (Liga, Ligue 1)
s'appliquerait automatiquement à la Premier League. Le protocole décrit
en section 12 traite donc explicitement la Premier League comme un
sous-groupe à évaluer séparément — et, si aucune performance robuste n'y
est démontrée, la conclusion attendue serait de **maintenir l'abstention
sur ce championnat** (le gate `discrimination_gate` continuerait à
produire `NON_DEMONTREE` pour la Premier League), jamais de lui appliquer
par défaut un seuil calibré ailleurs, et jamais non plus de créer un
seuil spécifique à la Premier League sans qu'une validation dédiée à ce
championnat ne l'ait démontré.

---

## 10. Zone Over 2.5 [0.6,0.7)

La conclusion d'E14 est strictement conservée : **recalibration locale
non validée**, zone documentée comme limite structurelle non corrigée.
Aucune isotonic/logistic calibration locale n'est ni n'a été réintroduite
à l'occasion de ce cadrage.

**Ce qu'un futur protocole de validation opérationnelle devra
déterminer** — sans qu'aucune décision ne soit prise ici : si les
matchs dont la probabilité modèle tombe dans cette zone doivent (a) être
inclus dans le calcul de performance globale d'un seuil (au risque de
diluer un signal potentiellement réel avec du bruit de calibration
connu), (b) être explicitement exclus de toute validation opérationnelle
tant que la zone reste non corrigée, ou (c) recevoir un traitement
distinct (ex. un seuil d'edge propre à cette zone, ou une exigence de
confiance supplémentaire). **Aucune de ces trois options n'est retenue
ici** — la retenir reviendrait à choisir un traitement ad hoc sans
expérience dédiée, exactement ce que ce cadrage doit éviter. Le
protocole de la section 12 prévoit explicitement de traiter cette zone
comme un sous-groupe séparé de l'analyse de robustesse, jamais fusionné
silencieusement avec le reste du corpus.

---

## 11. Question fondamentale

> **« Qu'est-ce qui permettrait de dire scientifiquement qu'un moteur
> probabiliste calibré est suffisamment robuste pour être utilisé comme
> filtre de paris ? »**

**Réponse opérationnelle et falsifiable** : un moteur probabiliste
calibré serait suffisamment robuste pour servir de filtre de paris si,
et seulement si, il existe au moins une règle de sélection (un seuil
d'edge, potentiellement conditionné par championnat/tranche) telle que,
sur un échantillon de **test** jamais utilisé pour choisir cette règle :

1. la performance nette de marge (ROI ou profit moyen par pari) a un
   intervalle de confiance (bootstrap, comparaisons multiples corrigées)
   **entièrement supérieur à celui de la baseline « marché seul »** et
   **entièrement supérieur à zéro** ;
2. cette performance se **réplique**, dans le même sens (jamais
   nécessairement avec la même magnitude), sur au moins deux sous-périodes
   temporelles disjointes et sur chaque championnat pour lequel elle est
   revendiquée ;
3. l'effectif de paris sur lequel elle repose est suffisant pour que
   l'intervalle de confiance ci-dessus soit informatif (pas simplement
   large au point de ne rien exclure) ;
4. le sous-ensemble de matchs sélectionnés par la règle reste
   lui-même correctement calibré (section 6, dernière ligne) — une règle
   qui ne fonctionnerait qu'en sélectionnant un sous-ensemble mal calibré
   serait le signe d'un artefact, pas d'un edge réel.

**Condition de falsifiabilité explicite** : si, pour toute règle
candidate testée selon le protocole de la section 12, au moins une de ces
quatre conditions échoue, le résultat attendu est `TARGETED RESEARCH
REQUIRED` ou `RESEARCH PHASE CLOSED` sur cette question précise (pas une
réitération indéfinie de nouveaux seuils) — exactement la discipline déjà
appliquée à la clôture de la campagne E1→E16
(`docs/research_synthesis_e1_e16.md` section 15).

---

## 12. Les trois états futurs de la décision

Le système doit pouvoir distinguer conceptuellement trois états, dont
deux seulement sont activables aujourd'hui :

| État | Signification | Activable aujourd'hui ? |
|---|---|---|
| `NO BET — NO EDGE` | Le modèle et le marché sont en accord (`raw_edge`/`price_edge` proche de zéro ou de signe non favorable) — aucune divergence à qualifier | **Oui**, dérivable dès aujourd'hui de `raw_edge`/`price_edge` déjà calculés, mais **non encore distingué explicitement** du cas ci-dessous par le code actuel (voir note ci-dessous) |
| `NO BET — EDGE NON VALIDÉ` | Une divergence modèle/marché existe, mais aucune règle validée ne permet de dire si elle est exploitable | **Oui — c'est l'état produit systématiquement aujourd'hui** (`edge_threshold_gate` toujours déclenché tant que `min_edge_threshold` reste `None`, code `EDGE_BELOW_THRESHOLD`) |
| `BET — EDGE OPÉRATIONNELLEMENT VALIDÉ` | Une divergence existe, ET une règle de conversion a été validée selon le protocole de la section 13, ET les conditions d'application de cette règle sont satisfaites pour ce match précis | **Non — doit rester indisponible** tant qu'aucun protocole OOS dédié (section 13) n'a été exécuté et n'a satisfait les critères de la section 11 |

**Note de cohérence documentaire (aucune modification de code)** : le
code actuel (`gates.py::edge_threshold_gate`) ne distingue pas
aujourd'hui `NO BET — NO EDGE` de `NO BET — EDGE NON VALIDÉ` — il émet le
même code `EDGE_BELOW_THRESHOLD` que l'edge observé soit nul, négatif, ou
franchement positif, puisque `min_edge_threshold` reste `None`. Ce n'est
**pas une incohérence** au regard de la spécification actuelle (le MVP
n'a jamais prétendu distinguer ces deux cas — `docs/final_engine_specification.md`
section 13/19 ne les distingue pas non plus) ; c'est une granularité
supplémentaire qu'un futur raffinement du moteur pourrait introduire
**après** — jamais avant — qu'un protocole comme celui de la section 13
ait statué sur l'existence d'un seuil opérationnel. Introduire cette
distinction dans le code aujourd'hui, avant toute validation, reviendrait
à afficher une information (« il existe un edge non nul ») sans que sa
pertinence soit établie — un risque déjà écarté par la conception
actuelle du moteur (section 11 de `docs/final_engine_specification.md` :
« ne jamais afficher automatiquement VALUE »). Aucune modification n'est
donc apportée à `gates.py`/`decision.py` à l'occasion de ce cadrage.

---

## 13. Futur protocole expérimental unique et pré-spécifié (non exécuté)

Ce protocole est décrit intégralement mais **n'est exécuté à aucun
degré** dans le cadre de cette Phase C. Il constitue la référence unique
pour toute future Phase C expérimentale, si elle est un jour décidée.

- **Hypothèse (pré-enregistrée)** : il existe un seuil `t` d'edge
  (`raw_edge` ou `price_edge`, à fixer explicitement dans le protocole
  final, pas ici) tel que la règle « BET si edge sur Over 2.5 ≥ `t` ET
  tous les scientific gates actuels sont satisfaits » produit, hors
  échantillon, une performance nette de marge statistiquement supérieure
  à la baseline « marché seul » (section 4).
- **Population** : tous les matchs des trois championnats déjà couverts
  (Liga, Ligue 1, Premier League) disposant d'une cote B365 Over/Under
  2.5 d'ouverture point-in-time complète — mêmes règles d'exclusion que
  E1→E16 (jour ambigu, historique insuffisant, cote incomplète).
- **Période** : l'intégralité du corpus actuellement disponible
  (2024/25 + 2025/26), avec une **réserve explicite** : si de nouvelles
  saisons deviennent disponibles avant l'exécution de ce protocole, la
  période de test devra être définie sur les données **les plus
  récentes non encore examinées** au moment de la pré-enregistration, pas
  choisies après coup.
- **Variables** : `p_model` (probabilité Over 2.5 corrigée E7/E8),
  `p_market` (probabilité implicite normalisée B365 ouverture),
  `raw_edge`/`price_edge` (section 12 de `docs/final_engine_specification.md`),
  `calibration_status`/`discrimination_status` (gates déjà en place),
  résultat réel du match.
- **Définition exacte de l'edge testée** : figée **avant** toute
  exécution — `raw_edge` (différence de probabilités) et `price_edge`
  (`expected_value` sur cote brute) seront testés comme **deux
  hypothèses séparées**, jamais mélangées ni choisies après observation
  de celle qui « marche le mieux ».
- **Candidats seuils éventuels** : une grille **fixée avant exécution**
  (jamais choisie après avoir vu les résultats), suffisamment fine pour
  étudier la sensibilité (section 3) sans être si fine qu'elle
  multiplierait artificiellement les comparaisons sans les corriger.
- **Méthode de sélection** : le seuil retenu pour l'annonce finale de
  performance est choisi **exclusivement** sur le segment de
  **validation**, selon la règle de la section 8 (jamais « le meilleur
  ROI observé ») ; le segment de **test** ne sert **qu'à** une évaluation
  unique et finale du seuil ainsi choisi — jamais à en choisir un autre a
  posteriori.
- **Séparation train/validation/test** : chronologique et stricte
  (section 6) — à titre d'illustration du principe, pas comme valeur
  fixée ici, une proportion de type 50/25/25 ou équivalente devra être
  actée dans le protocole final, avant toute exécution, jamais ajustée en
  cours de route.
- **Métriques** : l'ensemble de la section 7, systématiquement.
- **Critères d'acceptation** : les quatre conditions de la section 11,
  toutes simultanément satisfaites sur le segment de test.
- **Critères de rejet** : l'échec d'au moins une des quatre conditions de
  la section 11 ; ou une direction de performance instable entre
  segments/championnats/saisons ; ou un effectif de test insuffisant pour
  trancher (auquel cas le verdict est « preuve insuffisante », jamais
  assimilé à un rejet définitif ni à une validation).
- **Correction des comparaisons multiples** : Holm-Bonferroni (ou
  équivalent), appliquée à l'ensemble des hypothèses primaires
  pré-enregistrées (grille de seuils × définition d'edge ×
  eventuellement championnat) — exactement la discipline déjà appliquée
  en E16.
- **Robustesse** : re-vérification de la conclusion sur chaque
  championnat séparément (avec un traitement dédié pour la Premier
  League, section 9) et chaque saison séparément (section 3), et sur le
  sous-ensemble excluant la zone [0.6,0.7) d'Over 2.5 (section 10) en
  complément de l'analyse principale.
- **Condition d'arrêt** : conformément à la discipline systématique du
  projet, ce protocole s'exécute **une seule fois** jusqu'à son verdict ;
  un résultat négatif ou de preuve insuffisante n'est jamais suivi d'un
  nouvel essai avec un seuil ou une définition d'edge différente sans une
  nouvelle pré-enregistration explicite et une justification écrite de ce
  qui a changé.

---

## 14. Livrables et validation documentaire

- `docs/operational_validation_specification.md` (ce document) — créé.
- `docs/final_engine_specification.md` — mis à jour (section 13) pour
  pointer vers ce cadrage, sans modifier aucune conclusion existante.
- `docs/architecture.md` — mis à jour (voir section 2.0) pour référencer
  ce cadrage comme étape méthodologique intermédiaire entre la Phase B
  (MVP implémenté) et une future Phase C expérimentale, non encore
  décidée.
- Aucun code de production modifié.
- Aucun nouveau test requis : aucune incohérence entre ce document et le
  comportement actuel du moteur n'a été détectée (section 12 documente
  une granularité future possible, pas un bug présent).
- Suite de tests complète exécutée en contrôle de non-régression
  uniquement (aucune modification de code attendue).
