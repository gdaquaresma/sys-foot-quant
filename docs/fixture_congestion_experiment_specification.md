# Protocole pré-enregistré — congestion intra-championnat (Brique 1)

**Nature de ce document.** Cadrage méthodologique pur, figé **avant**
toute exécution sur données réelles. Aucune expérience n'est lancée ici,
aucun résultat n'est rapporté, aucun code de `final_engine/` n'est
modifié, aucun seuil `min_edge_threshold` n'est touché. Ce document
définit le protocole que l'expérience future devra suivre
**exactement** — toute exécution qui s'en écarterait devrait d'abord
amender ce document, jamais improviser en cours de route.

**Amendement figé avant exécution (étape expérimentale).** La section 6
laissait initialement ouvert le choix entre une covariable unique
(`rest_days_diff`) et deux covariables séparées. Décision retenue,
AVANT toute exécution sur données réelles : **modèle principal à deux
covariables séparées** (`home_rest_days`, `away_rest_days`), pour
permettre au modèle d'identifier un éventuel effet asymétrique du repos
(un repos supplémentaire à domicile n'a pas de raison d'avoir le même
effet qu'à l'extérieur). `rest_days_diff` est conservée comme variante
**secondaire et strictement descriptive** (section 6bis) — elle
n'intervient jamais dans le modèle principal ni dans le verdict
primaire.

Documents de référence (méthodologie réutilisée, jamais réinventée) :
`docs/operational_validation_specification.md` (section 13, protocole
train/validation/test), `docs/operational_validation_report.md` (Phase
D, méthode de sélection et contrôle de recalibration), `scripts/
run_stage25_e16_market_movement_information.py` (`fit_logistic`/
`walk_forward_logistic`), `scripts/run_stage30_phase_k_elo_incremental_
information.py` (même mécanique à offset, dernière application en
date), `scripts/run_stage10_over_under_recalibration.py`
(`split_burn_in_calibration_test`). Module source du signal :
`src/sys_foot_quant/data_engine/market_odds/fixture_congestion.py`.

---

## 1. Définition exacte de la variable

Pour un match cible et une équipe (domicile ou extérieur) : nombre de
jours (flottant, `(kickoff_cible − kickoff_dernier_match) / 86400s`)
écoulés depuis le dernier match de cette équipe **dans le même
(compétition, saison)** que le match cible — calculé par
`fixture_congestion.rest_days_before_match`. Deux variables dérivées :

- `home_rest_days`, `away_rest_days` (une par équipe du match cible).
- `rest_days_diff = home_rest_days − away_rest_days` (`fixture_congestion.rest_days_diff`) — indicateur symétrique optionnel, `None` si l'un des deux côtés a un historique insuffisant.

**Portée explicitement partielle ("Brique 1")** : seuls les matchs du
même championnat comptent. Les matchs de coupe et de compétitions
européennes sont absents du corpus actuel
(`docs/final_data_strategy.md` section 3) et ne sont **jamais** comptés
— cette variable **sous-estime mécaniquement** le repos réel d'une
équipe engagée sur plusieurs compétitions. Ce n'est pas une variable de
congestion complète ; c'est un pilote à coût nul destiné à vérifier s'il
vaut la peine d'investir dans la variante complète (calendrier
multi-compétitions, nouvelle source — hors périmètre de ce document).

## 2. Population et corpus

Identique au corpus déjà utilisé par E1→E16/Phase D : Liga, Ligue 1,
Premier League, 2024/25 + 2025/26, via `match_catalog.list_matches`
(déjà catalogué, aucune acquisition). Population primaire pour la
sélection d'un éventuel seuil de signification : Liga + Ligue 1
(discrimination démontrée, E4/E11/E15) ; Premier League analysée
séparément comme contrôle, jamais poolée dans la sélection — même
convention que Phase D.

## 3. Règle PIT

Pour le match cible `M` de coup d'envoi `kickoff(M)` : seuls les matchs
`m` de la même (compétition, saison) tels que `kickoff(m) < kickoff(M)`
sont éligibles comme "dernier match" d'une équipe — jamais `M`
lui-même (exclu explicitement par `match_id`, garde-fou redondant),
jamais un match postérieur. Contrairement aux signaux déjà testés en
Phases F/G (tirs cadrés, cotes Betfair — connus seulement après le coup
d'envoi, nécessitant un délai de connaissance explicite), une date de
coup d'envoi future est **par construction** connue bien avant
`decision_time` — aucun délai de connaissance (`knowledge_delay_hours`)
n'est nécessaire ici, contrairement à `shots_on_target.py`. Preuve du
caractère PIT : `tests/leakage/test_fixture_congestion_point_in_time.py`
(invariance par ajout/modification d'un match futur, exclusion explicite
du match cible et de tout match postérieur).

## 4. Exclusions

- Premier match d'une équipe dans le (compétition, saison) : aucun match
  antérieur disponible → `rest_days = None` explicitement (**jamais 0,
  jamais une valeur imputée**) — le match est exclu de l'échantillon
  d'analyse pour ce côté, jamais traité comme "repos nul".
- Aucune autre exclusion spécifique à cette variable. Les exclusions déjà
  en vigueur pour le corpus (jour de collecte ambigu, historique
  insuffisant pour `poisson_simple`, cote de marché incomplète) restent
  gouvernées par les modules existants, inchangés — ce protocole ne leur
  ajoute ni ne leur retire rien.

## 5. Méthode de construction

`fixture_congestion.congestion_dataset_for_season(competition, matches)`
avec `matches = match_catalog.list_matches(competition, season)` —
aucune fonction supplémentaire à écrire pour la construction du signal
lui-même. Jointure au reste du corpus économique (`p_model`, marché,
résultat réel) par `match_id` Understat — même clé que tous les modules
déjà en place (`economic_dataset.py`, `shots_on_target.py`).

## 6. Modèle de comparaison — FIGÉ avant exécution

Même patron que Phases F/G/H/K (translittéré de
`run_stage30_phase_k_elo_incremental_information.py`), jamais un nouveau
design. Quatre séries, exactement comme A/B/C/D en Phase K :

- **A — brut** : `p_A = calibrate_prediction(poisson_simple)` (E7/E8,
  INCHANGÉ), 0 paramètre.
- **B — naïf + congestion (offset)** : `p_B = sigmoid(a0 + 1·logit(p_A) +
  c1·home_rest_days + c2·away_rest_days)` — coefficient de `logit(p_A)`
  FIXÉ à 1, jamais réestimé (`fit_logistic_with_offset`, translittéré
  sans modification de Phase K). Diagnostique uniquement, jamais le test
  principal.
- **C — CONTRÔLE (recalibré seul)** : `p_C = sigmoid(a + b·logit(p_A))`
  — régression logistique walk-forward à 2 paramètres libres
  (`fit_logistic`/`walk_forward_logistic`, E16, INCHANGÉES), isole
  l'effet de pure recalibration. Condition **obligatoire** depuis la
  leçon de Phase F (sans ce contrôle, un gain apparent peut provenir à
  97-100 % de la seule recalibration, jamais de la nouvelle variable).
- **D — TEST (principal)** : `p_D = sigmoid(a + b·logit(p_A) +
  c1·home_rest_days + c2·away_rest_days)` — 4 paramètres libres, **deux
  covariables séparées** (jamais `rest_days_diff` en principal — voir
  amendement en tête de document). Permet au modèle d'identifier un
  effet asymétrique domicile/extérieur, plutôt que de l'imposer en
  figeant un coefficient unique.

**Test principal** : `paired_bootstrap_test` sur `Brier(D) − Brier(C)`
— **jamais** D seul contre le marché, **jamais** D contre A directement
(même discipline que F/G/H/K : le contrôle de recalibration C est
toujours le comparant, jamais A).

## 6bis. Covariable secondaire descriptive — `rest_days_diff`

`rest_days_diff = home_rest_days − away_rest_days` (module
`fixture_congestion.rest_days_diff`) est calculée et rapportée comme
**variante descriptive uniquement**, jamais comme remplacement des deux
covariables principales : un modèle **E** optionnel, `p_E = sigmoid(a +
b·logit(p_A) + c·rest_days_diff)`, comparé lui aussi à C
(`Brier(E) − Brier(C)`), rapporté **séparément** du verdict primaire
(D vs C) — jamais fusionné avec lui, jamais substitué à lui si le
résultat de E est plus favorable (interdiction explicite de choisir la
covariable après observation du résultat — même principe anti-data-
dredging que tout le reste du projet).

## 7. Métrique principale

Différence de Brier score (Test − Contrôle) sur Over 2.5, walk-forward,
avec IC95 % bootstrap (`calibration_engine.significance.paired_bootstrap_test`,
réutilisé sans modification) — identique à F/G/H/K. Log-loss rapporté en
complément, jamais comme métrique de décision.

## 8. Contrôle de recalibration

**Obligatoire dès la conception** (jamais ajouté après un premier
résultat trompeur — leçon explicite de Phase F, déjà appliquée dès le
départ en Phases G/H/K). Voir section 6 : le Modèle C (Contrôle) porte
déjà la recalibration (logit(p_A), 2 paramètres libres), sans les
covariables de congestion — toute différence Brier(D) − Brier(C) est
donc attribuable à `home_rest_days`/`away_rest_days` seules, jamais à un
effet de recalibration générique confondu avec elles.

## 9. Taille minimale d'échantillon

`n ≥ 30` par sous-groupe analysé (même convention documentée que
E5-E16/Phase D, `_MIN_BETS_FOR_POWERED_ANALYSIS`). En deçà, le résultat
est déclaré **sous-puissant**, jamais interprété comme une preuve
d'absence d'effet.

## 10. Règle de conclusion

Reprend **exactement** la règle de sélection de Phase D (section 7 de
`docs/operational_validation_report.md`), transposée à une comparaison
de Brier plutôt qu'à un profit :

- **Positif** : IC95 % de la différence de Brier (Test − Contrôle)
  entièrement **négatif** (Test meilleur que Contrôle) **et** effectif
  ≥ 30 **et** réplication dans le même sens sur au moins deux
  sous-groupes temporels disjoints (même principe que Phase D section
  3/12).
- **Négatif** : IC95 % chevauchant zéro ou entièrement positif (Test pas
  meilleur, ou pire) sur la population primaire.
- **Insuffisant** : effectif < 30 sur la population primaire, ou
  direction instable entre sous-groupes (jamais assimilé à un rejet
  définitif ni à une validation).

## 11. Distinction positif / négatif / insuffisant — jamais confondus

Un résultat **positif** sur cette métrique répond à la question A
(exactitude probabiliste améliorée), **pas** à la question C
(rentabilité opérationnelle) — même distinction stricte que la section 2
de `docs/operational_validation_specification.md`. Un résultat positif
ici ne produirait **aucun** changement de `min_edge_threshold` ni
d'activation de `BET` : il justifierait seulement l'intégration
éventuelle de la variable dans le moteur de probabilité, suivie d'une
**nouvelle** validation opérationnelle dédiée (une Phase D bis, jamais
un raccourci direct).

## 12. Interdiction explicite — jamais un raccourci vers BET

**Un résultat positif sur cette expérience ne doit, en aucun cas, être
transformé directement en seuil `min_edge_threshold` ou en activation de
`BET`.** Toute intégration de `home_rest_days`/`away_rest_days` (ou de
`rest_days_diff`) au moteur de probabilité (`final_engine/`) nécessiterait une décision séparée, explicitement
autorisée, suivie d'une nouvelle expérience de validation opérationnelle
dédiée selon le protocole de `docs/operational_validation_specification.md`
— exactement comme Phase D a validé (négativement) la conversion
edge→pari pour le signal déjà existant. Ce document ne pré-enregistre
que la question A (information incrémentale), jamais la question C
(rentabilité).

## 13. Condition d'arrêt

Comme toutes les expériences F/G/H/K : ce protocole, une fois exécuté,
s'exécute **une seule fois** jusqu'à son verdict. Un résultat négatif ou
insuffisant n'est pas suivi d'une nouvelle tentative avec une variable
dérivée différente (ex. repos moyen sur 3 matchs, fenêtre glissante)
sans une nouvelle pré-enregistration explicite et une justification
écrite de ce qui a changé.

---

## 14. Ce que ce document ne fait pas

Aucune exécution, aucun chargement de données réelles au-delà de ce qui
est déjà fait par les tests unitaires du module (fixtures synthétiques
minimales). Le script d'expérience (`scripts/run_stageXX_fixture_
congestion_incremental_information.py`, nom à réserver au moment de
l'exécution) reste à écrire dans une étape séparée, explicitement
autorisée après lecture de ce protocole.
