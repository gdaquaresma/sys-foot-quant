# Fixtures futures 2026/27 — OpenFootball (couche de normalisation)

**Nature de ce document.** Rapport factuel de l'implémentation de la couche
isolée de normalisation des fixtures futures (`future_fixture_catalog.py`),
suite à l'étude technique validant OpenFootball comme source (voir le
rapport précédent dans la conversation). Cette couche reste **non intégrée**
au catalogue principal (`match_catalog.py`), au moteur (`final_engine/`) ou
à l'API — elle produit des objets `FutureFixture` autonomes, pas encore
branchés nulle part.

## 1. Provenance exacte des fichiers 2026/27

Téléchargés par appel HTTP réel (`curl` vers `raw.githubusercontent.com`,
confirmé accessible depuis cette session) le **2026-10-05T19:18:49Z** :

| Fichier local | URL source |
|---|---|
| `research/fixture_calendar/openfootball/runs/france/2026-27_fr1.txt` | `openfootball/europe/master/france/2026-27_fr1.txt` |
| `research/fixture_calendar/openfootball/runs/england/2026-27_1-premierleague.txt` | `openfootball/england/master/2026-27/1-premierleague.txt` |
| `research/fixture_calendar/openfootball/runs/espana/2026-27_1-liga.txt` | `openfootball/espana/master/2026-27/1-liga.txt` |

Seules Ligue 1, Premier League et Liga sont concernées à cette étape (pas
de coupe nationale ni de compétition UEFA — hors périmètre demandé). Les 13
fichiers 2024/25 déjà présents ne sont ni supprimés ni modifiés.

## 2. Découverte critique n°1 — le format source n'est pas stable dans le temps

En vérifiant le format réel des fichiers 2025/26 (England/Spain, pour les
besoins du test empirique du fuseau horaire ci-dessous), j'ai constaté que
ces deux fichiers utilisent un format **différent** de celui attendu par le
parseur existant (`openfootball_calendar.py`) : en-tête `"Regular Season -
N"` au lieu de `"Matchday N"`, et séparateur domicile/score/extérieur SANS
le littéral `" v "` que `_parse_match_line` recherche (`re.split(r"\s+v\s+",
...)`). **Les fichiers 2025/26 England/Spain ne sont donc PAS parsables par
le module existant en l'état.**

**Bonne nouvelle vérifiée directement** : les fichiers **2026/27** (ceux
réellement utilisés ici) sont revenus au format `"Matchday N"` / `" v "`
compatible, pour les 3 compétitions — confirmé en exécutant réellement
`_parse_file()` sur chacun des 3 fichiers téléchargés (voir résultats
section 4). Mais cette instabilité démontrée signifie que **toute
réutilisation future de ce mécanisme pour une autre saison doit revérifier
le format avant de faire confiance au parseur**, jamais le supposer stable.

## 3. Découverte critique n°2 — le fuseau horaire n'est PAS fiable uniformément

Avant d'implémenter quoi que ce soit, j'ai croisé des matchs **réels**,
déjà présents dans le catalogue existant (`GET /matches`, backend réel
lancé pour ce test), avec leur ligne correspondante dans les fichiers
OpenFootball :

| Compétition | Match réel | Heure OpenFootball | `kickoff_utc` réel (catalogue) | Écart |
|---|---|---|---|---|
| Ligue 1 (2026/27) | Marseille – Strasbourg, 21 août 2026 | 20:45 | 18:45Z | **+2h (cohérent avec Europe/Paris, CEST)** |
| Ligue 1 (2026/27) | Brest – PSG, 13 sept. 2026 | 20:45 | 18:45Z | **+2h (cohérent)** |
| Liga (2025/26) | Girona – Rayo Vallecano, 15 août 2025 | 19:00 | 17:00Z | **+2h (cohérent avec Europe/Madrid, CEST)** |
| Liga (2025/26) | Villarreal – Real Oviedo, 15 août 2025 | 21:30 | 19:30Z | **+2h (cohérent)** |
| Premier League (2025/26) | Liverpool – Bournemouth, 15 août 2025 | 19:00 | 19:00Z | **+0h (INCOHÉRENT avec Europe/London BST, +1h attendu)** |
| Premier League (2025/26) | Aston Villa – Newcastle, 16 août 2025 | 12:30 | 11:30Z | +1h (cohérent) |
| Premier League (2025/26) | Sunderland – West Ham, 16 août 2025 | 14:00 | 14:00Z | **+0h (INCOHÉRENT)** |
| Premier League (2025/26) | Brighton – Fulham, 16 août 2025 | 15:00 | 14:00Z | +1h (cohérent) |
| Premier League (2025/26) | Tottenham – Burnley, 16 août 2025 | 15:00 | 14:00Z | +1h (cohérent) |

**Constat direct, pas supposé** : Ligue 1 et Liga sont cohérentes à 100 %
(4/4) avec « heure locale civile du pays, règle DST standard UE ». Premier
League présente **deux contradictions réelles sur 5 matchs vérifiés** (40 %
d'écart au lieu de l'offset attendu) — signe probable de reprogrammations
TV entre les deux snapshots de données (phénomène connu en Premier League),
mais la cause exacte n'a pas pu être confirmée avec les outils disponibles.

**Décision prise, conformément au cadrage** : **aucune conversion
automatique vers UTC n'est implémentée**, pour aucune des 3 compétitions —
y compris Ligue 1/Liga, dont l'échantillon vérifié (n=4 chacune) reste trop
petit pour être qualifié de « fiable » selon la discipline déjà en vigueur
dans ce dépôt (des dizaines/centaines de vérifications pour les autres
garanties point-in-time du projet). `FutureFixture` expose uniquement
`kickoff_local_naive` (même champ, même sémantique que
`OpenFootballMatch.kickoff_local_naive`), jamais un `kickoff_utc` fabriqué.
Cette limitation est documentée dans le code, pas seulement ici.

## 4. Couverture réelle obtenue (exécution directe de `_parse_file`)

| Compétition | Matchs déclarés | Matchs avec heure (parsés) | Dont déjà joués | Dont futurs **avec heure confirmée** | Exclus (aucune heure disponible) |
|---|---|---|---|---|---|
| Ligue 1 | 306 | 114 | 45 | **69** | 192 |
| Premier League | 380 | 380 | 50 | **330** | 0 |
| Liga | 380 | 90 | 69 | **21** | 290 |

Les matchs « exclus » ne sont PAS une erreur du parseur : ce sont des
journées de championnat trop éloignées pour que OpenFootball ait déjà reçu
une heure de coup d'envoi confirmée (aucune heure sur la ligne, aucune
héritée) — comportement déjà honnête du parseur existant
(`ParseExclusion`), inchangé ici. Un match sans heure n'a de toute façon
aucune valeur exploitable pour `decision_time = kickoff_utc - 2h`.

## 5. Correction — modèle temporel à 4 états (A/B/C/D)

Suite à un audit dédié (voir conversation), le tableau de la section 4
s'est révélé être **un symptôme, pas une conclusion** : les « exclus » du
tableau ci-dessus étaient en réalité des **fixtures connues** (équipes +
date) perdues par réutilisation stricte d'un mécanisme d'exclusion conçu
pour 2024/25 (où une ligne sans heure était une anomalie rare — 1 cas sur
2565 matchs), pas pour 2026/27 (où c'est la situation normale et
majoritaire pour les journées éloignées).

**Correctif appliqué** : `OpenFootballMatch` expose désormais
`fixture_date: date` (toujours présent) et `kickoff_local_naive: datetime
| None` ; une ligne structurellement valide sans heure devient un match
avec `kickoff_local_naive=None`, jamais une exclusion. `FutureFixture`
suit le même modèle, plus `kickoff_utc: datetime | None` (toujours `None`
aujourd'hui, conformément à la section 3 — rien n'a changé sur ce point).

**Distinction conservée** (demande explicite) : une ligne réellement
invalide (séparateur absent, nom d'équipe vide, aucune date établie,
heure présente mais malformée) reste une `ParseExclusion` — testé
explicitement (`test_match_line_with_an_invalid_time_string_remains_a_genuine_exclusion`).
Cas réel vérifié des DEUX catégories sur le même fichier 2024/25 :
« Tours FC v FC Lorient [awarded] » (Coupe de France) — resultat connu,
heure jamais publiée — est maintenant un match à `kickoff_local_naive=None`
plutôt qu'une exclusion (c'est un match **joué**, preuve qu'un match
peut manquer d'heure indépendamment de `is_played`).

**Couverture Ligue 1, avant/après** :

| | Avant | Après |
|---|---|---|
| Matchs représentés | 114 | **306 (= 100 % du déclaré)** |
| Dont joués (D) | 45 | 45 |
| Dont futurs, heure connue (B) | 69 | 69 |
| Dont futurs, heure inconnue (C) | 0 (invisibles) | **192** |

**Risque de collision d'identifiant analysé** (demande explicite avant de
choisir la clé) : `build_match_id` retombe sur
`competition:season:fixture_date:home_team:away_team` quand l'heure est
absente. Vérifié empiriquement — pas supposé — sur les 16 fichiers réels
enregistrés (2024/25 + 2026/27) : **aucune collision** de
`(home_team, away_team, fixture_date)`, y compris en ignorant l'heure
(`tests/integration/test_openfootball_calendar_real_files.py::test_no_date_level_collision_even_without_kickoff_time`)
— cohérent avec la structure d'un championnat à une seule manche par
journée (deux équipes ne se rencontrent jamais deux fois le même jour).
