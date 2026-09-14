# Conclusion figée — expérience de pondération temporelle (poids égaux vs décroissance exponentielle)

Statut : **expérience terminée, conclusion figée**. Aucune modification de
`final_engine/`, `PoissonModel`/`DixonColesModel`/`XGModel`,
`football_model/weighting.py`, `football_model/recent_form.py`,
`calibration_engine/`, `final_engine/gates.py`, `snapshot_engine/`,
`shadow_mode/journal.py`, `scripts/predict_match.py`. `min_edge_threshold`
non touché, `BET` non activé. Code de l'expérience : isolé sous
`research/temporal_weighting_experiment/` (jamais importé par
`src/sys_foot_quant`).

## 1. Question de recherche

Le moteur de production (`PoissonModel`/`DixonColesModel`/`XGModel` via
`final_engine/prediction.py`) pondère aujourd'hui **tous** les matchs de
l'historique disponible à égalité (`football_model/weighting.flat_weights`
— poids 1.0 partout, jamais de décroissance). Question posée
explicitement par l'utilisateur : **une pondération donnant plus de poids
aux matchs récents améliore-t-elle réellement la prédiction Over/Under 2.5
hors échantillon, par rapport à ce modèle à poids égal ?**

Distinction centrale, à ne jamais confondre :

- **« Les données récentes doivent être incorporées au dataset »** — **DÉMONTRÉ**, indépendamment de cette expérience (voir `docs/current_season_data_contract.md`/`multi_season_dataset.py` : intégrer les matchs 2026/27 déjà joués change mesurablement `attack`/`defense`/`lambda`, cf. rapport BASELINE vs CURRENT du 13/09/2026).
- **« Les données récentes doivent recevoir un poids supérieur aux données anciennes »** — **RÉFUTÉ** par l'expérience documentée ici (walk-forward réel, 2138 matchs dans le run définitif, résultat statistiquement significatif dans le sens défavorable).

Ces deux affirmations sont indépendantes : la première porte sur la
**couverture temporelle** du corpus d'entraînement, la seconde sur la
**pondération relative** des observations à l'intérieur de ce corpus. Le
projet valide la première et réfute la seconde.

## 2. Protocole walk-forward

Pour chaque match cible, trié chronologiquement, sur chacune des 3
compétitions déjà couvertes par le projet (Ligue 1, Liga, Premier League,
2024/25+2025/26, +2026/27 réel pour Ligue 1 uniquement — corpus canonique
`research/xg_feasibility/runs/ligue1_2026_datesData.json`, 36 matchs joués
au 13/09/2026, incluant Brest–PSG id 31975) :

- `decision_time = kickoff_utc − 2h` (`DECISION_OFFSET_HOURS`, déjà
  existant, inchangé) ;
- `TRAIN` = tous les matchs dont le résultat était connu avant
  `decision_time` (réutilise `backtesting_engine.real_data_walk_forward._goals_train_df`,
  INCHANGÉ, exclusion explicite du match cible lui-même) ;
- `MIN_TRAIN_MATCHES = 10` (identique à `economic_dataset.MIN_TRAIN_MATCHES`,
  INCHANGÉ) — sinon la ligne est `NaN` pour tous les schémas, jamais une
  valeur de repli ;
- Pour **chaque schéma de pondération**, EXACTEMENT le même `TRAIN`, seul
  le poids par match diffère ;
- P(Over 2.5) calculée à partir de λ/μ pondérés (`PoissonModel(use_team_hfa=False)`,
  identique au choix de `final_engine/prediction.py`), **sans** la
  correction d'échelle E7/E8 — limite assumée et documentée dans
  `research/temporal_weighting_experiment/weighted_walkforward.py` : cette
  correction n'a été validée scientifiquement que sous pondération plate ;
  l'appliquer sous une autre pondération sans revalidation aurait
  introduit un facteur de confusion non contrôlé. Absence identique pour
  tous les schémas, donc la comparaison RELATIVE reste valide.

## 3. Schémas testés (A0 à A5)

| Schéma | Formule | Nature |
|---|---|---|
| **A0 (référence)** | poids = 1 pour tous | Poids égal, méthode de production actuelle |
| A1 | `0.5 ** (age_days / 30)` | Décroissance exponentielle, demi-vie 30 jours |
| A2 | `0.5 ** (age_days / 60)` | demi-vie 60 jours |
| A3 | `0.5 ** (age_days / 90)` | demi-vie 90 jours |
| A4 | `0.5 ** (age_days / 180)` | demi-vie 180 jours |
| A5 | `0.5 ** (age_days / 365)` | demi-vie 365 jours |

Formule et fonctions (`flat_weights`, `exponential_decay_weights`) **déjà
présentes** dans `football_model/weighting.py` avant cette expérience —
réutilisées telles quelles, aucune nouvelle formule de pondération
écrite. `age_days = (decision_time − kickoff_time_du_match_d_entrainement)`
en jours, calculé uniquement à partir de dates déjà connues à
`decision_time` (jamais une information future).

## 4. Résultat (2138 matchs walk-forward, run définitif)

**Note de recalcul (14/09/2026)** : ce résultat a été initialement calculé
sur `n=2137` (corpus Ligue 1 2026/27 à 35 matchs, avant l'ingestion du
match Brest–PSG, id `31975`, par le connecteur d'auto-alimentation
saison courante). Après ajout de ce 36ᵉ match au fichier canonique,
l'expérience a été intégralement réexécutée via `run_experiment.py`
(**code inchangé**) : le tableau ci-dessous présente le **run définitif
à n=2138**. Les deux runs sont statistiquement équivalents (variation de
Brier en 4ᵉ-5ᵉ décimale, significativité inchangée pour chaque schéma) —
**ce recalcul confirme le verdict initial, il ne constitue pas une
nouvelle observation scientifique.** Ancien run (n=2137, pour mémoire) :
A0=0.261381, A1=0.278039, A2=0.267141, A3=0.264036, A4=0.261886,
A5=0.261389 (Brier) — cohérent avec les valeurs définitives ci-dessous à
la 4ᵉ décimale près.

| Méthode | N | Brier | Log Loss | Δ Brier vs A0 | IC95% | p-value |
|---|---|---|---|---|---|---|
| A0 (flat) | 2138 | 0.261521 | 0.762977 | — | — | — |
| A1 (30j) | 2138 | 0.278115 | 0.810735 | **+0.01659** | [0.0108, 0.0223] | **<0.0001** |
| A2 (60j) | 2138 | 0.267215 | 0.777847 | **+0.00569** | [0.0021, 0.0092] | **0.0014** |
| A3 (90j) | 2138 | 0.264120 | 0.769821 | **+0.00260** | [0.0000, 0.0051] | **0.0484** |
| A4 (180j) | 2138 | 0.261990 | 0.764334 | +0.00047 | [−0.0009, 0.0018] | 0.5136 |
| A5 (365j) | 2138 | 0.261510 | 0.763048 | −0.00001 | [−0.0007, 0.0007] | 0.9626 |

Test : `paired_bootstrap_test` (réutilisé, INCHANGÉ, 10 000
rééchantillonnages, même protocole que Phases K/SOT/BFE). Résultat
**cohérent sur les 3 compétitions et sur les tiers début/milieu/fin de
saison de chacune** (`research/temporal_weighting_experiment/regime_analysis.csv`)
— pas un artefact d'une sous-période isolée.

## 5. Conclusion figée

**A0 (poids égal) reste la référence.** A1/A2/A3 dégradent
significativement Brier ET log loss (IC95% entièrement positif = pire).
A4/A5 ne montrent aucun avantage crédible (IC95% couvrant 0). Décomposition
de Murphy : la dégradation d'A1-A3 vient d'une fiabilité PIRE (biais accru)
ET d'une résolution PIRE (discrimination réduite) — cohérent avec une
réduction de l'échantillon effectif par équipe sous décroissance agressive.

**Aucune pondération temporelle testée ne doit être intégrée au moteur de
production.** `football_model/recent_form.py` ne doit pas être rouvert -
ce résultat (décroissance exponentielle explicite, données réelles) est
cohérent avec son verdict déjà existant (A1-bis, dominé par
`poisson_simple` sur synthétique).

Détail complet, données brutes et code : `research/temporal_weighting_experiment/`
(`run_experiment.py`, `weighted_walkforward.py`, `*.csv`).
