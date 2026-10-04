# Protocole pré-enregistré — consensus multi-bookmaker Max/Avg Over/Under 2.5

**Nature de ce document.** Cadrage méthodologique pur, figé **avant**
toute exécution sur données réelles. Aucun code de `final_engine/` n'est
modifié, aucun seuil `min_edge_threshold` n'est touché, aucune décision
BET n'est modifiée. Ce document ferme la dernière piste non évaluée de
la catégorie Football-Data (`docs/final_data_strategy.md`,
`docs/next_signal_strategy.md` section 4.A).

Méthodologie réutilisée sans modification : même patron que
`docs/fixture_congestion_experiment_specification.md` (Brique 1) et
`scripts/run_stage30_phase_k_elo_incremental_information.py` (Phase K) -
`split_burn_in_calibration_test`, `fit_logistic`/`walk_forward_logistic`,
`calibrate_prediction`, `paired_bootstrap_test`.

---

## 0. Vérification préalable — Max/Avg représentent-ils une donnée d'ouverture correctement horodatée ?

Effectuée avant toute écriture de code d'expérience (voir docstring
`football_data_loader.py`, section "EXTENSION STAGE32" pour le détail
complet). Résumé :

| Vérification | Résultat empirique |
|---|---|
| Couverture `Max>2.5`/`Max<2.5`/`Avg>2.5`/`Avg<2.5` sur les 6 fichiers | **100%** (2132/2132 lignes) — supérieure à P (49.5-99.5%) |
| `Max>2.5 >= B365>2.5` et `Max<2.5 >= B365<2.5` | **100%** des lignes — confirme un agrégat "meilleur prix" dominant B365 |
| `Max >= Avg` | **100%** des lignes — cohérent (meilleur prix ≥ moyenne) |
| `Avg>2.5` vs `AvgC>2.5` (ouverture vs clôture) | Différent dans 95.5% des lignes, écart médian 0.06 — mouvement de marché réel, pas une colonne dupliquée |
| Convention de suffixe | Identique à toutes les colonnes déjà lues (`B365`/`P`/`BW`/`PS`/`WH`/`LB` sans `C` = ouverture, avec `C` = clôture) — aucune nouvelle règle inventée |
| Overround `Max` | Descend sous 1.0 sur 0.7% des lignes (min 0.861) — signature d'un "meilleur prix par côté à travers un panel", **pas** le prix simultané d'un seul bookmaker |
| Overround `Avg` | 1.037–1.077, profil normal (similaire à B365/BW/PS) |
| Panel exact de bookmakers composant Max/Avg | **Non documenté par la source** — jamais affirmé au-delà de ce qui est démontrable depuis les données elles-mêmes |

**Conclusion de la vérification préalable** : `Max`/`Avg` représentent
bien des agrégats d'**ouverture** correctement distingués de leur
clôture, avec une couverture meilleure que toute colonne déjà utilisée.
**L'expérience est autorisée à procéder.** Réserve retenue : `Avg` est
une covariable de consensus interprétable (overround normal) ; `Max` ne
l'est pas au même titre (overround parfois < 1) — voir section 6.

---

## 1. Définition exacte des variables

- `p_market_B365` : probabilité implicite **normalisée** (marge retirée,
  `remove_overround_proportional`, INCHANGÉ) du prix B365 Over 2.5
  d'ouverture.
- `p_market_Avg` : probabilité implicite normalisée du prix **Avg**
  (consensus multi-bookmaker) Over 2.5 d'ouverture — covariable
  **principale** de l'hypothèse testée.
- `p_market_Max` (secondaire, descriptif uniquement — section 6) :
  probabilité implicite normalisée du prix **Max** — jamais interprétée
  comme une probabilité de marché standard (réserve d'overround ci-dessus).

Module source : `src/sys_foot_quant/data_engine/market_odds/
multi_bookmaker_over_under.py` (`build_multi_bookmaker_over_under_dataset`),
isolé de `matching.py`/`over_under_2_5_by_bookmaker` (gelés).

## 2. Population et corpus

Identique à Phase D/K/Brique 1 : Liga + Ligue 1 (population primaire,
discrimination démontrée E4/E11/E15), Premier League en contrôle séparé,
2024/25 + 2025/26, `poisson_simple` + E7/E8.

## 3. Règle PIT

Identique à B365 (`matching.opening_over_under_2_5_by_match_id`,
INCHANGÉ) : cotes d'ouverture publiées bien avant `decision_time`
(`kickoff_utc − DECISION_OFFSET_HOURS`), aucun nouveau délai de
connaissance nécessaire. **Jamais** `MaxC`/`AvgC` (absentes de
`_ALLOWED_COLUMNS` — vérifié par
`tests/leakage/test_multi_bookmaker_over_under_point_in_time.py`).

## 4. Exclusions

Mêmes exclusions déjà en vigueur pour le corpus (jour de collecte
ambigu, historique insuffisant `poisson_simple`, cote B365 incomplète -
`has_complete_odds`/`has_complete_over_under_2_5_odds`). Un match sans
`Avg`/`Max` complet serait exclu séparément mais, la couverture étant de
100% sur les six fichiers réels, aucune exclusion supplémentaire n'est
attendue en pratique (jamais supposée impossible pour autant).

## 5. Méthode de construction

`build_multi_bookmaker_over_under_dataset(league, season, understat_raw,
football_data_records)` puis jointure par `match_id` au dataset
walk-forward `p_A` (identique à Phase K/Brique 1 — `e7.
build_lambda_mu_dataframe` + `calibrate_prediction`).

## 6. Modèles de comparaison — FIGÉS avant exécution

- **C — CONTRÔLE (recalibré seul)** : `p_C = sigmoid(a + b·logit(p_A))`
  — identique à Phase K/Brique 1, aucune information de marché.
- **A — test, référence B365** : `p_test_B365 = sigmoid(a + b·logit(p_A)
  + c·logit(p_market_B365))` — le marché déjà utilisé par le moteur de
  production, comme référence de comparaison équitable.
- **B — test, consensus Avg (hypothèse principale)** : `p_test_Avg =
  sigmoid(a + b·logit(p_A) + c·logit(p_market_Avg))` — **structurellement
  identique à A**, seule la source du prix de marché change (B365 →
  consensus élargi). C'est cette symétrie qui rend la comparaison
  "équitable" (section 2 de la demande).
- **Secondaire/descriptif — Max** : `p_test_Max = sigmoid(a +
  b·logit(p_A) + c·logit(p_market_Max))`, rapporté séparément, jamais
  fusionné au verdict primaire (réserve d'overround, section 0).

**Test principal** : `paired_bootstrap_test` sur `Brier(test_Avg) −
Brier(C)`. **Test de comparaison équitable** : `Brier(test_B365) −
Brier(C)`, rapporté côte à côte pour vérifier si B365 seul apporte déjà
quelque chose (auquel cas Avg devrait au moins égaler cet apport, pas
nécessairement le dépasser) — ceci **ne rouvre pas** E9/E13/Phase D
(qui testaient l'edge/la dispersion/un seuil de pari, jamais cette
construction Brier-incrémentale précise).

## 7. Distinction imposée par la demande

- **Apport prédictif incrémental** : `Brier(test_Avg) − Brier(C)`.
- **Simple effet de recalibration** : `Brier(C) − Brier(A brut)`, déjà
  isolé par construction (C ne contient aucune info de marché).
- **Modification mécanique de la marge/dispersion** : rapportée
  séparément (overround B365 vs Avg vs Max, section 0) — jamais
  confondue avec un signal prédictif.

## 8. Métrique, contrôle, échantillon, conclusion

Identiques à Brique 1 (section 7/8/9/10 de
`docs/fixture_congestion_experiment_specification.md`) : Brier +
`paired_bootstrap_test`, contrôle de recalibration C obligatoire,
n≥30, grille à 3 valeurs (`SIGNAL DEMONTRE` / `SIGNAL NON DEMONTRE` /
`DONNEES INSUFFISANTES`) avec réplication sur ≥2 sous-groupes temporels
pour un verdict positif.

## 9. Interdiction explicite

Identique à Brique 1 section 12 : aucun résultat de cette expérience
n'est transformé directement en seuil `min_edge_threshold` ni en
activation de `BET`. Aucune nouvelle variante de consensus (médiane,
pondération) n'est testée après ce résultat sans nouvelle
pré-enregistration.
