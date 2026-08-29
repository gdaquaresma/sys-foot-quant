# Phase H — information incrémentale du handicap asiatique (AH)

Statut : **expérience unique, terminée**. Verdict officiel (question B) :
**`NON VALIDÉ`**. Aucune modification de `poisson_simple`/`dixon_coles`/
`xg_model`, d'E7/E8/E14/E15/E16, des gates ou de `final_engine`. `BET`
non activé, `min_edge_threshold` non fixé.

Protocole pré-enregistré complet : `docs/ah_experiment_specification.md`
(définition mathématique du marché, transformations, split, modèles,
contrôles, métriques, critères de validation/rejet — verrouillé **avant**
cette exécution). Nouvelle primitive pure :
`football_model.goal_distribution.asian_handicap_probabilities`. Module
de données isolé : `data_engine/market_odds/asian_handicap_odds.py`
(jamais importé par `final_engine`). Script :
`scripts/run_stage29_phase_h_ah_incremental_information.py`. Tests :
`tests/unit/test_goal_distribution.py` (209 cas, dont 195 vérifications
paramétrées de la décomposition quart-de-ligne contre un oracle
indépendant), `tests/unit/test_asian_handicap_odds.py`,
`tests/leakage/test_asian_handicap_odds_point_in_time.py`,
`tests/unit/test_run_stage29_phase_h.py` — tous exécutés **avant**
l'exécution réelle.

## 1. Données

Corpus déjà présent dans le dépôt (`research/market_odds/football_data/runs/*.csv`,
2132 lignes ; `research/xg_feasibility/runs/*.json` pour Understat).
Aucune donnée externe téléchargée. Colonnes AH ajoutées à
`football_data_loader.py` — ouverture uniquement (`AHh`, `B365AHH/AHA`,
`PAHH/PAHA`) ; `BFEAHH/AHA` (Betfair Exchange), `Max/AvgAHH/AHA`
(agrégats), et toute colonne de clôture (`AHCh`, `B365CAHH/AHA`,
`PCAHH/AHA`) **non lues** (une seule variable nouvelle par expérience).

## 2. Couverture

| Élément | Valeur mesurée |
|---|---|
| `n` apparié (Understat × Football-Data) | 2123 |
| `n` avec AH B365 complet et PIT valide (`n_ah_records`) | 1804 |
| B365 AH complet sur les matchs appariés | 2118/2123 (99.8% — résidu de 5, cohérent avec l'audit direct) |
| Pinnacle AH | ~76% (même profil de dégradation par saison que les autres marchés Pinnacle, déjà documenté) |
| Répartition par type de ligne (population d'analyse walk-forward, n=1804) | entier/demi/quart, voir `docs/ah_experiment_specification.md` §3 |
| Corpus avec `poisson_simple` disponible (`n_corpus`) | 2072 |

Aucune catégorie trop peu représentée pour être exclue — même le plus
petit sous-groupe de robustesse (lignes entières, n=279 sur la
population propre) dépasse le seuil `n≥30` déjà utilisé dans le projet.

## 3. Méthodologie

**Modèle_AH** = `P(Home | h, not push)` (§2.3-2.4 du protocole), dérivée
d'une transformation déterministe (nouvelle primitive pure,
`asian_handicap_probabilities`) de la **même** matrice de score
`poisson_simple` déjà corrigée walk-forward par E7/E8
(`fit_scale_correction_as_of`, INCHANGÉE) — zéro paramètre
supplémentaire. **Marché_AH** = probabilité B365 normalisée
(`remove_overround_proportional`, INCHANGÉE). **Contrôle obligatoire —
Modèle_AH-recalibré** : régression logistique walk-forward à 2
paramètres sur `logit(Modèle_AH)` seul (E16, `fit_logistic`/
`walk_forward_logistic`, INCHANGÉES), introduite **dès la conception du
protocole** (contrairement à Phase F où elle avait été ajoutée après un
premier résultat trompeur) — directement issue de la leçon
méthodologique des Phases F/G. **Modèle+Marché_AH** = même mécanique à 3
paramètres, `logit(Modèle_AH)` + `logit(Marché_AH)`.

Population du test principal (question B) : matchs à **règlement
propre** uniquement (`settle=±1`, ni push, ni demi-gain, ni demi-perte)
— exclusion structurelle, pas un seuil inventé (cf. l'exclusion
d'« Under » comme complémentaire dégénéré d'« Over », E13). Une seule
passe walk-forward sur le corpus complet trié par `decision_time`
(`_MIN_TRAIN=30`), pas de split rodage/validation/test — aucun seuil à
protéger, effectif maximisé (même justification que Phases F/G).

## 4. Résultats

**Question A — le modèle est-il correctement calibré sur l'AH ?**
Brier à 3 classes (Home/Push/Away), population complète (n=1734) :
**Brier=0.6059, log loss=1.1110**. Écart notable de calibration sur le
push : taux observé **6.3%**, taux moyen prédit par le modèle **11.7%**
— le modèle **surestime substantiellement** la probabilité de push
(quasiment le double de sa fréquence réelle). **Réponse à la question A :
non, le modèle n'est pas correctement calibré sur l'AH tel quel** —
constat qui motive directement la nécessité du contrôle de recalibration
(question B).

**Question B — information incrémentale au-dessus du marché AH (population
propre, n=1354 après rodage walk-forward)** :

| | Modèle brut | Modèle-recalibré | Modèle+Marché |
|---|---|---|---|
| Brier | 0.2882 | 0.2507 | 0.2514 |

L'essentiel de l'amélioration (0.2882 → 0.2507, soit 97% de l'écart
total) provient de la **seule recalibration**, sans aucune information
de marché — cohérent avec la miscalibration massive détectée en question
A (surestimation du push). L'ajout du marché (0.2507 → 0.2514) ne
produit **aucune** amélioration supplémentaire — au contraire, un très
léger renchérissement du Brier.

## 5. IC95%

Test principal (bootstrap apparié, 10 000 rééchantillonnages, Brier
Modèle+Marché − Modèle-recalibré) :

| Périmètre | n | diff. moyenne | IC95% | p |
|---|---|---|---|---|
| **Global** | 1354 | +0.0007 | **[-0.0007, +0.0022]** | 0.340 |
| Liga | 454 | +0.0016 | [-0.0012, +0.0045] | 0.262 |
| Ligue 1 | 403 | +0.0004 | [-0.0020, +0.0030] | 0.706 |
| Premier League | 497 | +0.0001 | [-0.0022, +0.0024] | 0.905 |
| Saison 2024/25 | 671 | +0.0011 | [-0.0015, +0.0038] | 0.414 |
| Saison 2025/26 | 683 | +0.0004 | [-0.0008, +0.0015] | 0.533 |
| Ligne entière | 279 | +0.0002 | [-0.0030, +0.0035] | 0.893 |
| Ligne demi-entière | 414 | +0.0011 | [-0.0011, +0.0034] | 0.286 |
| Ligne quart | 661 | +0.0006 | [-0.0016, +0.0028] | 0.590 |

**Aucun** des neuf périmètres (global + 8 décompositions de robustesse)
n'atteint un IC95% entièrement négatif — le critère `VALIDÉ` (§8 du
protocole) exige cette condition au niveau global **et** sur chaque
sous-groupe.

## 6. Tests statistiques

`paired_bootstrap_test` (réutilisé sans modification,
`calibration_engine.significance`), même méthode que dans toutes les
expériences précédentes. Une seule hypothèse primaire pré-enregistrée
(Modèle+Marché_AH vs Modèle_AH-recalibré, B365, population globale
propre) — aucune correction pour comparaisons multiples n'est
nécessaire pour cette hypothèse unique (§8 du protocole) ; les
décompositions championnat/saison/type de ligne restent des diagnostics
de robustesse, jamais des tests de significativité indépendants utilisés
pour le verdict.

## 7. Comparaisons

Reprend exactement l'architecture de contrôle des Phases F/G : Modèle
brut (0 paramètre) / Modèle-recalibré (2 paramètres, CONTRÔLE) /
Modèle+Marché (3 paramètres, TEST). `Modèle+1X2+AH` (mentionnée dans
l'énoncé comme comparaison éventuelle) : **non exécutée** — combiner un
espace de probabilité AH (Home/Away conditionnel au non-push) avec un
espace 1X2 (Home/Draw/Away à 3 issues strictement complémentaires)
exigerait une reformulation d'espace d'état non balisée par un précédent
du projet ; documentée mais hors périmètre (§5 du protocole), cohérent
avec la discipline « une seule variable nouvelle à la fois ».

## 8. Robustesse

Décomposée par championnat, saison, et type de ligne (entier/demi/quart)
— **diagnostics uniquement, jamais une nouvelle sélection**. Le résultat
est **remarquablement homogène** : dans les neuf périmètres testés, la
différence de Brier (Modèle+Marché vs Modèle-recalibré) reste toujours
proche de zéro et jamais significativement négative — aucun sous-groupe
« gagnant » n'apparaît, aucune sélection a posteriori n'a été nécessaire
ni tentée.

## 9. Limites

- Le contrôle de recalibration a été inclus **dès la conception** du
  protocole (avant toute exécution), directement issu de la leçon des
  Phases F/G — jamais une réaction à un résultat déjà observé ici.
- Pinnacle AH (couverture ~76%) n'a pas été testé comme source
  d'information indépendante — retenu comme secondaire/hors périmètre
  (une seule variable nouvelle par expérience, §5 du protocole).
- La miscalibration du push (question A) n'a fait l'objet d'aucune
  correction (aucune recalibration locale n'est introduite, conformément
  à l'interdiction E14/section 10 du protocole) — documentée comme
  limite structurelle, pas corrigée.
- `Modèle+1X2+AH` (question C partielle de l'énoncé) reste non exécutée
  (§7).
- Question C (rentabilité opérationnelle) n'a **pas** été testée —
  hors périmètre explicite, nécessiterait le protocole complet de
  `docs/operational_validation_specification.md`.

## 10. Verdict officiel

## Question A : le modèle n'est **pas** correctement calibré sur l'AH brut (surestimation substantielle du push, 11.7% prédit vs 6.3% observé)

## Question B : **`NON VALIDÉ`**

Critère appliqué mécaniquement (grille figée avant observation, §8 du
protocole) : l'IC95% global de la différence de Brier (Modèle+Marché vs
**Modèle-recalibré**, le contrôle isolant l'effet spécifique du marché
AH) ne se situe pas entièrement sous zéro (p=0.340), et aucun des huit
sous-groupes de robustesse n'y parvient non plus. L'essentiel du gain
apparent entre le modèle brut et « Modèle+Marché » (Brier 0.2882 →
0.2514) provient d'une **recalibration générique** (0.2882 → 0.2507) —
pas du marché AH lui-même. Sans ce contrôle, imposé dès la conception du
protocole par la leçon des Phases F/G, cette expérience aurait
probablement conclu, à tort, `VALIDÉ`.

## Question C : **hors périmètre** — non exécutée, quel que soit le résultat de B

## 11. Conséquence architecturale

Conformément au protocole (§10) : l'information incrémentale n'étant pas
démontrée, **l'avenue du handicap asiatique est gelée**, au même titre
que les tirs cadrés (Phase F) et Betfair Exchange (Phase G). **Aucune
intégration au moteur de production** — le code écrit
(`asian_handicap_odds.py`, `asian_handicap_probabilities`) reste isolé,
jamais importé par `final_engine`. `min_edge_threshold` reste `None`,
`BET` reste non activé. La miscalibration du push détectée en question A
est documentée comme limite structurelle connue du modèle sur ce marché,
jamais corrigée ici (aucune recalibration locale, conformément à
l'interdiction E14). Aucune autre extension AH (Pinnacle comme source
indépendante, combinaison avec le 1X2, handicap Betfair Exchange) n'est
explorée à la suite de ce résultat négatif.

**Arrêt.** Conformément à l'instruction explicite de la Phase H, cette
expérience était la seule autorisée. Aucune expérience suivante n'est
lancée automatiquement — la suite reste à décider séparément par
l'utilisateur à partir de ce résultat.
