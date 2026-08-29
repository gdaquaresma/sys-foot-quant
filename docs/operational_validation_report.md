# Rapport de validation expérimentale du mécanisme BET / NO BET (Phase D)

**Nature de ce document.** Rapport d'une expérience réelle, unique,
pré-enregistrée, exécutée une seule fois. Aucun modèle probabiliste,
aucune correction E7/E8/E14/E15/E16 n'a été modifiée. Aucun ensemble de
modèles, aucun coefficient de championnat, aucune cote de clôture n'ont
été introduits. Le test final n'a été exécuté que si un seuil avait été
retenu sur la validation — voir section 10.

Script : `scripts/run_stage26_phase_d_operational_validation.py`. Tests
préalables : `tests/unit/test_phase_d_operational_validation.py` (32
tests unitaires purs) et `tests/leakage/test_phase_d_operational_validation_point_in_time.py`
(garde-fous anti-fuite). Suite complète exécutée avant et après
l'expérience : 1200 tests verts, aucune régression.

---

## Pré-enregistrement (fixé avant toute lecture d'edge ou de résultat réel)

`docs/operational_validation_specification.md` (section 13) définissait
le protocole dans son principe mais ne fixait ni la grille de seuils ni
les bornes exactes de la séparation temporelle, renvoyant explicitement
ce choix à « un protocole final ». Conformément à l'instruction de la
Phase D (« si le protocole ne définit pas suffisamment précisément la
grille, s'arrêter plutôt que d'inventer »), ce point bloquant a été
soumis à validation avant toute exécution. La résolution retenue
(pré-enregistrement dérivé **structurellement**, jamais en observant une
performance) est la suivante :

- **Séparation temporelle** : réutilisation exacte de
  `run_stage10_over_under_recalibration.split_burn_in_calibration_test`
  — 40 % rodage / 30 % VALIDATION / 30 % TEST, tri chronologique **par
  championnat × saison**, la même fonction pure déjà utilisée sans
  modification par B1/A2/B2/B3.3/E2/E3/E7/E8/E9/E10. Le rodage sert de
  pool de calibration walk-forward pour VALIDATION ; VALIDATION sert de
  pool de calibration walk-forward pour TEST — extension à trois étages
  de la discipline à deux étages déjà validée par E8.
- **Grille de seuils** (3 candidats primaires, chacun tracé à un artefact
  déjà figé du projet, aucun n'est inventé pour cette occasion) :
  `raw_edge ≥ 0.05` et `raw_edge ≥ 0.10` (bornes « notable »/« marquée »
  de la grille d'anomalie déjà pré-enregistrée en E9/E13) ; `price_edge >
  0.0` (règle EV>0 exacte, seule règle de prix jamais testée dans ce
  projet, E1).
- **Population primaire** : Liga + Ligue 1 uniquement (discrimination
  DEMONTRÉE, E4/E11/E15) — Premier League analysée séparément comme
  contrôle négatif, jamais poolée dans la sélection.

---

## 1. Objectif

Déterminer s'il existe une règle de sélection fondée sur l'edge estimé
qui produit une performance hors échantillon suffisamment robuste pour
autoriser le moteur à produire `BET`.

## 2. Hypothèses

**Hypothèse testée** (falsifiable) : il existe, parmi les 3 candidats
pré-enregistrés, une règle « BET si edge sur Over 2.5 ≥ seuil ET tous les
scientific gates actuels sont satisfaits » qui produit, sur VALIDATION
puis confirmée sur TEST, une performance nette de marge dont l'IC95 % est
entièrement supérieur à zéro **et** à la baseline « marché seul ».
**Ce n'est pas** l'hypothèse « un edge positif est rentable » — c'est
l'hypothèse plus étroite qu'une sélection **suffisamment stricte**
(edge élevé) pourrait l'être. L'hypothèse est rejetée si aucun candidat
ne satisfait la règle de sélection sur VALIDATION.

## 3. Données

Corpus complet E1→E16 (3 championnats × 2 saisons 2024/25+2025/26),
`poisson_simple` uniquement (modèle principal), probabilités Over 2.5
corrigées par le facteur d'échelle walk-forward E7/E8
(`calibrate_prediction`, code réel, inchangé), cotes B365 Over/Under 2.5
d'ouverture (`load_all_multi_bookmaker_records`, E9, inchangé). Aucune
cote de clôture. `n_rodage = 852`, `n_validation = 640`, `n_test = 640`
(par championnat × saison, avant filtrage par ligue/gates).

## 4. Séparation temporelle

Voir « Pré-enregistrement » ci-dessus. Confirmée par les tests de
`tests/leakage/test_phase_d_operational_validation_point_in_time.py` :
les trois segments sont disjoints et exhaustifs par construction : la
calibration de VALIDATION n'utilise que le rodage ; celle de TEST
n'utilise que VALIDATION.

## 5. Définition de l'edge

Définition **déjà implémentée dans le moteur**, jamais redéfinie :
`raw_edge = value_engine.edge.edge(p_model, p_market_normalisé)`,
`price_edge = value_engine.edge.expected_value(p_model, cote_marché)`,
calculés via `final_engine.market.compare_over_under_to_market` (code
réel, appelé tel quel). Conservés séparément tout au long de l'expérience
— `p_model`, `p_market` (brut et normalisé), `fair_price` (dérivable de
`p_model`), `raw_edge`, `price_edge` et le résultat réel n'ont jamais été
fusionnés en une seule quantité. Aucun `edge > 0` n'a été appelé
automatiquement « value ».

## 6. Grille des seuils

Voir « Pré-enregistrement ». 3 candidats primaires sur Over 2.5 :
`raw_edge≥0.05`, `raw_edge≥0.10`, `price_edge≥0.0`. Aucun candidat n'a
été ajouté après observation d'un résultat.

## 7. Méthode de sélection

Sur VALIDATION uniquement (n=342 lignes exploitables Liga+Ligue1, après
gates de données/calibration/discrimination et intersection avec les
cotes B365 O/U 2.5), chaque candidat est retenu **seulement** s'il
satisfait **simultanément** (règle pré-enregistrée, section 7/11 de
`docs/operational_validation_specification.md`) :
1. effectif ≥ 30 paris ;
2. IC95 % bootstrap du profit entièrement > 0 ;
3. IC95 % entièrement supérieur à la borne haute de l'IC95 % de la
   baseline « marché seul ».

Jamais « le meilleur ROI observé ». La fonction `passes_selection_rule`
ne reçoit aucune donnée du segment TEST (vérifié par test structurel).

## 8. Résultats — VALIDATION

Baseline « marché seul » (parier Over 2.5 systématiquement, sans filtre) :
n=342, profit moyen **+0.0043**, IC95 %=[−0.0985, +0.1085], p=0.93 —
comportement proche de neutre, cohérent avec un marché déjà quasi-fair
une fois retiré l'overround.

| Candidat | n | Hit rate | Profit moyen | IC95 % | p |
|---|---|---|---|---|---|
| `raw_edge≥0.05` | 186 | 47.8 % | **−0.1194** | [−0.2518, +0.0162] | 0.088 |
| `raw_edge≥0.10` | 126 | 48.4 % | **−0.1183** | [−0.2807, +0.0509] | 0.164 |
| `price_edge≥0.0` | 211 | 49.3 % | **−0.0849** | [−0.2136, +0.0427] | 0.200 |

**Les trois candidats ont un profit moyen négatif** sur VALIDATION,
aucun IC95 % entièrement positif, et aucun ne dépasse la baseline
« marché seul ». **Les trois sont rejetés par la règle de sélection.**

## 9. Seuil retenu

**Aucun.** Aucun des 3 candidats pré-enregistrés ne satisfait
simultanément les trois conditions de la section 7 sur VALIDATION.

## 10. Test final

**Non exécuté**, conformément au protocole : le TEST reste verrouillé
tant qu'aucun seuil n'est retenu sur VALIDATION (règle non négociable,
sections 4 et 11 de la consigne de Phase D — « ne jamais utiliser le
test final pour choisir un seuil »). Les 640 matchs de TEST (dont la
part Liga+Ligue1) n'ont été ni chargés ni évalués par
`build_backtest_rows` — vérifié par construction du script (le seul appel
à `build_backtest_rows(test_ids, ...)` se trouve après la boucle de
sélection, dans la branche qui n'est atteinte que si `selected is not
None`, jamais empruntée ici).

## 11. Résultats globaux

Faute de seuil retenu, il n'y a pas de « résultat global » au sens d'une
performance de production — seuls les résultats de VALIDATION (section
8) existent. Un résultat complémentaire important, purement descriptif
(section 15) : les matchs que chaque candidat aurait sélectionnés sont
précisément ceux où le modèle est le plus **sur-confiant**, pas les plus
fiables.

## 12. Résultats par saison (VALIDATION)

| Saison | `raw_edge≥0.05` | `raw_edge≥0.10` | `price_edge≥0.0` |
|---|---|---|---|
| 2024/25 | n=105, profit=−0.064, IC95%=[−0.253,+0.124] | n=72, profit=−0.094, IC95%=[−0.314,+0.124] | n=114, profit=−0.058, IC95%=[−0.236,+0.121] |
| 2025/26 | n=81, profit=−0.191, IC95%=[−0.390,+0.007] | n=54, profit=−0.150, IC95%=[−0.391,+0.093] | n=97, profit=−0.117, IC95%=[−0.304,+0.068] |

Les deux saisons sont négatives en point estimate pour les trois
candidats, sans qu'aucune ne porte seule la totalité du signal négatif —
la direction est cohérente entre les deux saisons (jamais un renversement
de signe), même si aucune des deux, prise isolément, n'atteint la
significativité (effectifs plus petits, cohérent avec les limites de
puissance déjà documentées en section G2 de `docs/research_framework.md`).

## 13. Résultats par championnat (VALIDATION)

| Championnat | `raw_edge≥0.05` | `raw_edge≥0.10` | `price_edge≥0.0` |
|---|---|---|---|
| Liga | n=100, profit=−0.039, IC95%=[−0.232,+0.157] | n=61, profit=**+0.024**, IC95%=[−0.213,+0.266] | n=112, profit=−0.013, IC95%=[−0.198,+0.175] |
| Ligue 1 | n=86, profit=**−0.213**, IC95%=[**−0.399,−0.026**], p=0.026 | n=65, profit=**−0.251**, IC95%=[**−0.464,−0.033**], p=0.022 | n=99, profit=−0.167, IC95%=[−0.342,+0.007], p=0.061 |

**Hétérogénéité documentée explicitement (jamais utilisée pour
re-sélectionner)** : le résultat global négatif est **porté
disproportionnellement par la Ligue 1**, où deux des trois candidats
atteignent une significativité négative individuelle (IC95 %
entièrement < 0). La Liga, prise isolément, est proche de neutre (IC95 %
couvrant largement 0 dans les trois cas, y compris un point estimate
légèrement positif pour `raw_edge≥0.10`, non significatif). **Cette
hétérogénéité ne change pas le verdict** : aucun candidat, y compris
restreint à la seule Liga, n'atteint les trois conditions de la section 7
(IC95 % jamais entièrement > 0 ni au-dessus de la baseline). Elle est
rapportée ici en application stricte du protocole (« documenter
explicitement les cas où la performance globale est portée par une seule
sous-population ») — pas comme une invitation à re-tester une règle
spécifique à la Liga sans nouvelle expérience pré-enregistrée.

## 14. Robustesse

- **Par sous-groupe** : voir sections 12-13 — la direction négative est
  cohérente sur 3 des 4 sous-groupes (2 saisons × 2 championnats), avec
  une hétérogénéité Liga/Ligue 1 documentée plutôt que masquée.
- **Contrôle négatif Premier League** (n=191, jamais poolé, jamais
  utilisé pour la sélection) : **aucun match ne franchit un seul des 3
  seuils candidats** (`n_bets=0` pour les trois). Ce résultat est cohérent
  avec le phénomène de « compression des prédictions » déjà documenté en
  E15 pour la Premier League — le modèle y diverge rarement fortement du
  marché. Sans objet pour une décision (`discrimination_gate` bloque
  structurellement tout `BET` en Premier League quel que soit ce
  résultat, E15).
- **Secondaire, Under 2.5** (n=342, jamais fusionné avec Over) : les
  trois candidats sont **rejetés avec un résultat encore plus net que sur
  Over** — IC95 % entièrement négatif pour les trois (`raw_edge≥0.05` :
  [−0.627,−0.179] p=0.0002 ; `raw_edge≥0.10` : [−0.791,−0.211] p=0.003 ;
  `price_edge≥0.0` : [−0.477,−0.082] p=0.006). Le signal négatif n'est
  donc pas spécifique à la sélection « Over » — il se reproduit,
  amplifié, sur la sélection complémentaire.
- **Sensibilité au seuil** : les deux seuils `raw_edge` (0.05 et 0.10)
  produisent un profit moyen quasi identique (−0.119 vs −0.118) malgré un
  effectif très différent (186 vs 126) — la conclusion ne dépend pas
  d'un point de coupure précis, un signe de stabilité (négative) plutôt
  que de fragilité d'un seuil isolé.

## 15. Incertitude

Méthode : `calibration_engine.significance.paired_bootstrap_test`
(10 000 rééchantillonnages, percentile, déjà utilisée depuis E1),
appliquée au vecteur des profits par pari sélectionné. Hypothèses :
échantillonnage i.i.d. par pari (pas un bootstrap par blocs temporels —
même réserve méthodologique que E1) ; les IC95 % rapportés dans les
sections 8, 12, 13, 14 le sont systématiquement, jamais un point estimate
seul. **Limite explicite** : à ces effectifs (n=126 à 342 selon le
candidat), la puissance reste modeste — un effet réel mais petit
resterait indiscernable du bruit ; ceci est cohérent avec, et n'annule
pas, le fait qu'aucun candidat n'ait atteint le seuil de preuve requis.

**Analyse exploratoire de calibration du sous-ensemble sélectionné**
(section 6/9 de `docs/operational_validation_specification.md`, jamais
utilisée pour sélectionner) :

| Candidat | n | p_model moyen | fréquence réelle | écart |
|---|---|---|---|---|
| `raw_edge≥0.05` | 186 | 0.652 | 0.478 | **−0.173** |
| `raw_edge≥0.10` | 126 | 0.683 | 0.484 | **−0.199** |
| `price_edge≥0.0` | 211 | 0.637 | 0.493 | **−0.144** |

**Résultat le plus explicatif de ce rapport** : dans les trois cas, le
sous-ensemble de matchs qu'un seuil d'edge sélectionnerait est
précisément celui où le modèle est **sur-confiant** (probabilité annoncée
~0.64-0.68, fréquence réelle ~0.48-0.49) — reproduisant, cette fois via
une simulation live du moteur réel plutôt qu'un diagnostic a posteriori,
exactement le mécanisme déjà identifié en E11 (sur-confiance
significative dans la zone [0.6,0.7) d'Over 2.5) et en E5/E10/E12 (un
grand écart de prix coïncide avec une zone où le modèle a tort, pas avec
une opportunité). Un edge élevé n'indique donc pas, sur ce corpus, un
« bon » pari — il indique, en moyenne, un pari où le modèle se trompe
plus que d'habitude. Aucun ratio `edge/incertitude` n'a été calculé ni
utilisé pour sélectionner quoi que ce soit (conformément à la
spécification, section 9 — resterait une `HYPOTHÈSE FUTURE`).

## 16. Comparaisons aux baselines

| Baseline | n | Profit moyen | IC95 % |
|---|---|---|---|
| Marché seul (Over, VALIDATION) | 342 | +0.0043 | [−0.099, +0.109] |
| Marché seul (Under, VALIDATION) | 342 | −0.0743 | [−0.183, +0.036] |
| Modèle sans sélection (`raw_edge>0`, Over) | 211* | −0.085 | [−0.214, +0.043] |
| Candidat le plus proche de validé (`raw_edge≥0.10`) | 126 | −0.118 | [−0.281, +0.051] |

*La baseline « modèle sans sélection » utilise ici la même population que
`price_edge≥0.0` par construction algébrique de `strategy_metrics`
(seuil quasi nul) — aucune des baselines ni des candidats ne dépasse le
marché seul.

## 17. Limites

- Bootstrap i.i.d. par pari, pas par bloc temporel (limite héritée d'E1,
  jamais résolue par un nouvel outil dans ce projet).
- Effectifs de VALIDATION modestes une fois restreints à Liga+Ligue1 et
  aux gates existants (126 à 342 selon le candidat) — cohérent avec les
  limites de puissance déjà documentées (section G2 de
  `docs/research_framework.md`).
- La zone [0.6,0.7) d'Over 2.5 (E11/E14, non corrigée) n'a pas été
  exclue séparément dans cette expérience — au vu du tableau de la
  section 15 (p_model moyen des candidats précisément dans ou proche de
  cette zone), il est probable qu'elle contribue significativement au
  résultat négatif observé, mais ceci n'a pas été isolé formellement ici
  (aurait nécessité un candidat supplémentaire non pré-enregistré,
  explicitement exclu par le protocole).
- Seul `poisson_simple` a été testé comme modèle principal, conformément
  au choix architectural actuel — `dixon_coles`/`xg_model` n'ont pas été
  examinés dans cette expérience (auraient constitué des hypothèses
  supplémentaires non pré-enregistrées).
- Le rejet de l'hypothèse ne prouve pas l'absence de tout edge
  exploitable pour toute définition possible — il porte strictement sur
  les 3 candidats pré-enregistrés, sur Over/Under 2.5, Liga+Ligue1,
  `poisson_simple`, avec les gates actuels.

## 18. Verdict officiel

## **`NO BET — EDGE NON VALIDÉ`**

Aucun des 3 candidats pré-enregistrés ne satisfait les critères de
sélection sur VALIDATION. Conformément au protocole (section 13 de
`docs/operational_validation_specification.md`), ce résultat n'est **pas**
un échec de puissance à corriger en relançant un nouveau seuil — c'est un
résultat négatif accompagné d'une explication mécanistique cohérente
(section 15 : l'edge élevé coïncide avec la sur-confiance du modèle, pas
avec une opportunité), reproduisant et renforçant, cette fois via une
simulation directe du moteur de production, les conclusions déjà
établies indépendamment par le diagnostic post-E1, E5, E10 et E12.

## 19. Décision concernant l'activation de `BET`

**`BET` n'est pas activé.** `min_edge_threshold` reste `None` dans
`OperationalThresholds` (aucune modification de `gates.py`/`decision.py`
à l'occasion de cette expérience). Le moteur continue de produire
uniquement des `NO_BET` motivés — l'état `NO BET — EDGE NON VALIDÉ` est
désormais **confirmé expérimentalement**, pas seulement conceptuel.
Conformément au protocole : pas de recherche d'un nouveau seuil, pas de
nouvelle expérience lancée automatiquement.

---

## Annexe — bug corrigé avant exécution réelle

En préparant l'assemblage du corpus (étape 1 de la Phase D), un test
(`tests/unit/test_phase_d_operational_validation.py`, exécuté avant toute
donnée réelle) a révélé que `discrimination_status("ligue1")` — la clé
interne exacte utilisée par tout le pipeline de données réelles depuis E1
(`_SEASONS`/`_load_records`, jamais `"ligue_1"` avec underscore) —
retournait `NON_EVALUEE` au lieu de `DEMONTREE`, à cause d'un décalage
entre la clé attendue par `reference_tables._DISCRIMINATION_TABLE`
(`"ligue_1"`) et la clé réellement produite par le pipeline (`"ligue1"`).
Corrigé dans `src/sys_foot_quant/final_engine/reference_tables.py` (ajout
de la clé `"ligue1"`, sans toucher aux valeurs ni à la conclusion E15) et
couvert par un test de non-régression dédié
(`test_discrimination_status_matches_the_internal_pipeline_league_keys`).
Sans cette correction, la Ligue 1 aurait été incorrectement traitée comme
un championnat non audité, faussant la population primaire de cette
expérience. Une seconde particularité, sans lien avec une fuite ou une
erreur de fuseau horaire, a également été corrigée : `decision_time`
perd son information de fuseau UTC en traversant `Series.map` (pandas) —
corrigé localement dans le script de la Phase D en ré-attachant
explicitement `timezone.utc` avant de reconstruire `kickoff_utc` pour le
gate `ambiguous_day_gate`, sans modifier `time_resolution.py` ni aucune
règle temporelle existante.
