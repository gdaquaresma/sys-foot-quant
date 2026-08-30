# Phase K — information incrémentale de l'écart de rating Elo pré-match (ClubElo)

Statut : **expérience unique, terminée**. Verdict officiel (question B) :
**`NON VALIDÉ`**. Aucune modification de `poisson_simple`/`dixon_coles`/
`xg_model`, d'E7/E8/E14/E15/E16, des gates ou de `final_engine`. `BET`
non activé, `min_edge_threshold` non fixé.

Protocole pré-enregistré complet : `docs/elo_experiment_specification.md`
(définition mathématique, règle PIT, matching, split, modèles, contrôles,
métriques, critères de validation/rejet — verrouillé **avant** cette
exécution, y compris l'annexe documentant la source réellement utilisée
et la restriction de corpus, décidées **avant** tout calcul de Brier ou
de test statistique). Nouveaux modules :
`data_engine/market_odds/elo_ratings.py`, `elo_team_mapping.py`,
`elo_join.py`, `elo_archive_ingest.py` (jamais importés par
`final_engine`). Script : `scripts/run_stage30_phase_k_elo_incremental_information.py`.
Tests : 53 tests dédiés Phase K, tous exécutés **avant** l'exécution
réelle (1538 tests au total, suite complète verte).

## 1. Source des données

`clubelo.com`/`api.clubelo.com` (source native, format `Rank, Club,
Country, Level, Elo, From, To`) se sont révélés inaccessibles au moment
de cette phase — timeout constaté indépendamment par l'utilisateur
(capture d'écran Chrome, "a mis trop de temps à répondre") et par cet
environnement (`curl` direct). Conformément à la décision explicite de
l'utilisateur (« option b »), la source réellement utilisée est
l'archive quotidienne publique du dépôt GitHub
`tonyelhabr/club-rankings` (581 279 lignes, alimentée automatiquement
depuis 2023 par un robot interrogeant l'API ClubElo en direct),
téléchargée le 2026-08-30 et filtrée aux 67 clubs des 3 championnats
déjà couverts par ce projet (`research/market_odds/clubelo/runs/clubelo_daily_archive.csv`,
61 394 lignes, 5,2 Mo).

Le fichier brut est un **journal de scrapes quotidiens** (une ligne par
jour de collecte), pas une table de fenêtres déjà dédupliquées.
`data_engine/market_odds/elo_archive_ingest.py` reconstruit des fenêtres
`[From, To]` propres et non chevauchantes à partir de la seule séquence
des valeurs **distinctes** de `From` par club (vérifiée stable : un
changement de `From` correspond toujours à un match réel) — la colonne
`To` brute n'est **jamais** utilisée directement (elle dérive légèrement
d'un jour de scrape à l'autre pour la fenêtre encore « en cours »).

## 2. Couverture

- **914/914 jours de collecte présents pour chacun des 67 clubs**
  (couverture quotidienne totale), du **2023-03-27 au 2026-01-14**.
- **Mapping d'équipes vérifié à la main** par l'utilisateur directement
  contre les pages réelles `clubelo.com/ENG`, `clubelo.com/ESP`,
  `clubelo.com/FRA` (captures d'écran et texte copié-collé) — corrections
  notables par rapport à une ébauche non vérifiée : `Man City`/
  `Man United` (pas « Manchester… »), `Forest` (pas « Nottingham »),
  `Saint-Etienne` (pas « St Etienne »), `Athletic Club`/`Atlético`/
  `Real Sociedad` (pas les formes abrégées). Trois noms supplémentaires,
  spécifiques à cette archive précisément, traduits explicitement :
  `Bilbao`→`Athletic Club`, `Atletico`→`Atlético`, `Sociedad`→
  `Real Sociedad`.
- **Restriction de corpus, décidée explicitement par l'utilisateur** :
  l'archive s'arrêtant au 2026-01-14, tout match dont `decision_time`
  tombe après cette date est exclu. Sur les 2123 matchs déjà appariés
  (Understat×Football-Data), la couverture Elo par championnat×saison
  (avant restriction de corpus, après appariement/jour ambigu) :

| Championnat/saison | Matchs appariés | Elo exploitable (avant cutoff) | Exclu (pas de rating à la date) |
|---|---|---|---|
| Premier League 2024/25 | 380 | 335 | 0 |
| Premier League 2025/26 | 380 | 186 | 140 |
| Ligue 1 2024/25 | 306 | 266 | 0 |
| Ligue 1 2025/26 | 298 | 136 | 128 |
| Liga 2024/25 | 380 | 311 | 0 |
| Liga 2025/26 | 379 | 149 | 155 |

La dégradation de couverture 2025/26 provient exactement de la
restriction de corpus (les matchs après le 2026-01-14 n'ont, par
construction, aucun rating disponible dans l'archive) — cohérent avec
l'estimation faite avant exécution (44,7-50,3% de la saison 2025/26).

**Corpus final (après jointure Elo, `poisson_simple`/E7-E8 disponible,
et restriction de corpus)** : **n=1313**. Exclus par la seule
restriction de corpus (matchs dont `decision_time` > 2026-01-14, déjà
comptés dans la couverture Elo ci-dessus mais rapportés séparément par
le pipeline) : 514.

## 3. Point-in-time

Règle verrouillée avant exécution (`docs/elo_experiment_specification.md`
§2) : `elo_lookup_date = decision_time.date()` (UTC), sélection de la
fenêtre `[From, To]` la contenant, jamais d'interpolation ni de valeur
future. Propriété structurelle du format d'archive (`From` = lendemain
du match ayant produit le changement de rating) : une date `D` ne
reflète jamais un match disputé ce jour `D` lui-même — vérifiée par 3
tests dédiés (`tests/leakage/test_elo_join_point_in_time.py`), dont un
test simulant explicitement un changement massif de rating le lendemain
d'un match et démontrant que l'ancien rating (pré-match) est bien celui
retenu.

**Choix PIT supplémentaire, mesuré sur les données réelles (annexe du
protocole)** : la valeur d'Elo retenue par fenêtre est la **première**
observée dans l'archive pour cette fenêtre, jamais une observation
ultérieure — 19,3% des fenêtres (3213/16 644) montrent un raffinement
rétroactif mesurable du moteur ClubElo lui-même (médiane ~6,2 points,
max 34,5 points), documenté et neutralisé par ce choix, jamais ignoré.

## 4. Matching

`elo_team_mapping.py` (66 clubs — 23 Premier League, 21 Ligue 1, 23
Liga), vérifié à la main entrée par entrée contre les données réelles
(§2). Aucune correspondance approximative : `resolve_clubelo_name` lève
une erreur explicite pour toute équipe non couverte. Aucune équipe non
mappée rencontrée sur le corpus réel (`n_excluded_team_not_mapped = 0`
pour les six championnats×saisons).

## 5. Méthodologie

**Modèle A** = `p_over_2_5` (probabilité Over 2.5, `calibrate_prediction`,
E7/E8, INCHANGÉE) — 0 paramètre, passe-plat. **Modèle B** = `sigmoid(a0 +
1·logit(p_A) + c·elo_diff)` (offset, coefficient de `logit(p_A)` **fixé
à 1**, comparaison naïve). **Modèle C** = `sigmoid(a + b·logit(p_A))`
(recalibration seule, **CONTRÔLE OBLIGATOIRE**). **Modèle D** =
`sigmoid(a + b·logit(p_A) + c·elo_diff)` (recalibration + Elo, **TEST**).
Tous walk-forward (`_MIN_TRAIN=30`, `fit_logistic`/`fit_logistic_with_offset`,
E16 étendue par une nouvelle fonction d'offset-regression testée
isolément — 3 tests dédiés).

**Split** : `split_burn_in_calibration_test` (Phase D, INCHANGÉE),
40% rodage / 30% VALIDATION / 30% TEST, par championnat×saison — rodage
=661, VALIDATION=374, TEST=278 (sur les 1313 lignes du corpus final).
Le rodage sert de pool d'historique walk-forward, jamais évalué
lui-même. Population d'évaluation (`eval_pool` = VALIDATION+TEST, après
rodage de la régression logistique elle-même) : **n=652**.

**Cible** : Over 2.5, définition identique à E11/E14/E16/Phases F/G/H.
Aucune cible secondaire testée (espérance de buts, 1X2) — conformément
au protocole.

## 6. Résultats

| | Modèle A (brut) | Modèle B (naïf) | Modèle C (recalibré) | Modèle D (recalibré+Elo) |
|---|---|---|---|---|
| Brier (n=652) | 0.2620 | 0.2628 | 0.2489 | 0.2489 |

Les modèles **C et D sont identiques à la 4ᵉ décimale** — l'ajout
d'`elo_diff` au modèle déjà recalibré n'apporte, en pratique, aucune
information supplémentaire mesurable.

## 7. IC95% et test statistique principal

**Test principal pré-spécifié** : `paired_bootstrap_test` (10 000
rééchantillonnages) sur `Brier(D) − Brier(C)`.

| Périmètre | n | diff. moyenne | IC95% | p |
|---|---|---|---|---|
| **Primaire (VALIDATION+TEST)** | 652 | +0.0000631 | **[-0.00094, +0.00108]** | 0.893 |
| VALIDATION seule | 374 | +0.000464 | [-0.00091, +0.00183] | 0.497 |
| TEST seul | 278 | -0.000477 | [-0.00198, +0.00104] | 0.533 |

Aucune contradiction de direction significative entre VALIDATION et
TEST (les deux CI couvrent largement zéro) — condition de robustesse
temporelle du protocole satisfaite, dans le sens négatif (absence
d'effet stable dans le temps).

## 8. Comparaisons secondaires

| Comparaison | diff. moyenne | IC95% | p | Interprétation |
|---|---|---|---|---|
| A vs C (Brier C − Brier A) | -0.01307 | **[-0.02223, -0.00371]** | 0.0062 | Recalibration seule : amélioration significative, comme Phases F/G/H |
| A vs B (Brier B − Brier A) | +0.00085 | [-0.00004, +0.00174] | 0.062 | Elo ajouté SANS recalibrer le modèle de base : aucune amélioration (limite de significativité franchie dans le sens défavorable) |
| B vs D (Brier B − Brier D) | +0.01386 | **[+0.00476, +0.02310]** | 0.0026 | D (recalibré+Elo) bat B (naïf+Elo) : confirme que c'est la **recalibration**, pas Elo, qui explique l'écart |

Ces trois comparaisons, prises ensemble, isolent proprement l'effet :
la recalibration générique du modèle de base explique la quasi-totalité
de tout gain observable ; Elo, qu'il soit ajouté avant ou après cette
recalibration, ne produit aucun gain supplémentaire mesurable.

## 9. Test de redondance

Corrélation entre `logit(p_A)` et `elo_diff` sur la population propre :
**0.1254** — faible, cohérent avec une source d'information
partiellement mais pas fortement chevauchante. Coefficient d'`elo_diff`
dans une régression logistique en pleine information (diagnostic non
walk-forward, jamais utilisé pour le verdict) : **0.000665** — signe
positif attendu (un écart Elo favorable au domicile est associé à une
probabilité Over 2.5 très légèrement supérieure) mais d'une ampleur
négligeable au regard de la variance déjà expliquée par `p_A`.

## 10. Question A — calibration du modèle sur la population complète

`p_A` moyen sur `eval_pool` = 0.5461, fréquence réelle observée =
0.5322 — écart de 1,4 point, modeste, cohérent avec la calibration déjà
démontrée par E7/E8/E11 sur Over 2.5 (pas une anomalie propre à cette
population).

## 11. Robustesse

Décomposée par championnat et par saison (diagnostics uniquement,
jamais une nouvelle sélection) :

| Périmètre | n | diff. moyenne (D-C) | IC95% | p |
|---|---|---|---|---|
| Liga | 221 | -0.00154 | [-0.00325, +0.00021] | 0.084 |
| Ligue 1 | 189 | +0.00115 | [-0.00073, +0.00303] | 0.225 |
| Premier League | 242 | +0.00067 | [-0.00104, +0.00237] | 0.439 |
| Saison 2024/25 | 547 | -0.00004 | [-0.00107, +0.00098] | 0.932 |
| Saison 2025/26 | 105 | +0.00061 | [-0.00267, +0.00397] | 0.735 |

**Aucun** des cinq sous-groupes n'atteint un IC95% entièrement négatif
(le critère `VALIDÉ` l'exigerait). Le résultat est remarquablement
homogène — aucun sous-groupe « gagnant » n'apparaît.

## 12. Limites

- La restriction de corpus (matchs après le 2026-01-14 exclus, ~45-50%
  de la saison 2025/26) réduit l'effectif disponible par rapport à ce
  qu'aurait permis une source d'historique complète — décidée
  explicitement par l'utilisateur avant toute exécution, jamais après
  observation d'un résultat.
- La source réelle (archive communautaire GitHub, pas l'API officielle
  directement) introduit une dépendance à un tiers non contractuel —
  documentée en détail (`docs/elo_experiment_specification.md` §0ter),
  jamais présentée comme équivalente à un accès direct au fournisseur.
- Le raffinement rétroactif mesuré du moteur ClubElo (19,3% des
  fenêtres, médiane ~6,2 points) est neutralisé par le choix de la
  première observation, mais introduit un bruit de mesure résiduel non
  quantifié plus finement ici.
- Question C (rentabilité opérationnelle) n'a **pas** été testée — hors
  périmètre explicite, nécessiterait le protocole complet de
  `docs/operational_validation_specification.md`.

## 13. Verdict officiel

## Question B : **`NON VALIDÉ`**

Critère appliqué mécaniquement (grille figée avant observation, §13 du
protocole) : l'IC95% de la différence de Brier (Modèle D vs **Modèle C**,
le contrôle isolant l'effet spécifique d'Elo) ne se situe pas
entièrement sous zéro sur la population primaire (p=0.893), ni sur
VALIDATION seule, ni sur TEST seul, ni sur aucun des cinq sous-groupes
de robustesse. Les modèles C et D sont statistiquement indiscernables
(Brier identique à la 4ᵉ décimale). La comparaison B vs D confirme que
l'essentiel de tout gain apparent provient de la recalibration
générique du modèle de base, pas d'Elo lui-même — reproduisant, une
quatrième fois consécutive, le schéma déjà établi en Phases F, G et H.

## Question C : **hors périmètre** — non exécutée, quel que soit le résultat de B

## 14. Conséquence architecturale

Conformément au protocole (§13/§15) : l'information incrémentale n'étant
pas démontrée, **l'avenue Elo/ClubElo est gelée**, au même titre que les
tirs cadrés (Phase F), Betfair Exchange (Phase G) et le handicap
asiatique (Phase H). **Aucune intégration au moteur de production** —
le code écrit (`elo_ratings.py`, `elo_team_mapping.py`, `elo_join.py`,
`elo_archive_ingest.py`) reste isolé, jamais importé par `final_engine`.
`min_edge_threshold` reste `None`, `BET` reste non activé. Conformément
à la Phase I (`docs/final_data_strategy.md`), Elo était la seule piste
de données pré-match immédiatement testable identifiée par la Phase J —
son résultat négatif referme ce fil sans en ouvrir automatiquement un
autre (compositions/blessures restent, comme documenté en Phase J, une
piste nécessitant une journalisation prospective non encore démarrée).

**Arrêt.** Conformément à l'instruction explicite de la Phase K, cette
expérience était la seule autorisée. Aucune expérience suivante n'est
lancée automatiquement — la suite reste à décider séparément par
l'utilisateur à partir de ce résultat.
