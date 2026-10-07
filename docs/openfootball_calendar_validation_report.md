# Rapport de validation — module `openfootball_calendar` (2024/25)

**Nature de ce document.** Rapport factuel des résultats obtenus par
l'implémentation contrôlée du module `openfootball_calendar.py`, suite au
`GO PARTIEL` de `docs/multi_competition_calendar_open_data_audit.md`.
Aucun résultat ici ne constitue une validation statistique d'un signal
prédictif — ce module reste une couche de données, non intégrée.

## 1. Fichiers créés/modifiés

**Créés (nouveaux, aucun fichier existant modifié) :**

- `src/sys_foot_quant/data_engine/market_odds/openfootball_calendar.py` — module de parsing/reconstruction.
- `tests/unit/test_openfootball_calendar.py` — 28 tests unitaires (fixtures synthétiques).
- `tests/integration/test_openfootball_calendar_real_files.py` — 85 tests d'intégration paramétrés sur les fichiers réels.
- `docs/openfootball_calendar.md` — documentation courte du module.
- `docs/openfootball_calendar_validation_report.md` — ce rapport.
- `research/fixture_calendar/openfootball/runs/{france,england,espana,uefa}/*.txt` — 13 fichiers bruts réels téléchargés (`raw.githubusercontent.com`), ~230 Ko au total.

**Modifiés :** aucun fichier existant.

## 2. Couverture réelle obtenue (2024/25, 13 fichiers)

| Compétition | Matchs parsés | Exclusions | Déclaré par l'en-tête source |
|---|---|---|---|
| `ligue1` | 306 | 0 | 306 |
| `coupe_de_france` | 199 | 1 | 200 |
| `premier_league` | 380 | 0 | 380 |
| `fa_cup` | 123 | 0 | 123 |
| `efl_cup` | 93 | 0 | 93 |
| `liga` | 380 | 0 | 380 |
| `copa_del_rey` | 126 | 0 | 126 |
| `champions_league` | 189 | 0 | 189 |
| `champions_league_qualifying` | 90 | 0 | 90 |
| `europa_league` | 189 | 0 | 189 |
| `europa_league_qualifying` | 80 | 0 | 80 |
| `conference_league` | 153 | 0 | 153 |
| `conference_league_qualifying` | 256 | 0 | 256 |
| **Total** | **2564** | **1** | **2565** |

**2564 matchs sur 2565 déclarés par les en-têtes sources (99.96 %).**
L'unique exclusion (Coupe de France, `Tours FC v FC Lorient`) est un
défaut documenté du fichier source lui-même (aucune heure de coup
d'envoi fournie, ni sur la ligne ni héritée) — exclue explicitement et
journalisée plutôt que devinée, conformément au garde-fou « donnée
ambiguë = exclusion explicite ».

## 3. Reconstruction de calendrier — clubs français testés

Mapping de noms vérifié à la main par lecture directe des fichiers réels
(aucun deviné) :

| Club | Matchs reconstruits (2024/25) | Compétitions trouvées |
|---|---|---|
| Paris Saint-Germain | 57 | `ligue1`, `coupe_de_france`, `champions_league` |
| Olympique de Marseille | 36 | `ligue1`, `coupe_de_france` |
| Olympique Lyonnais | 48 | `ligue1`, `coupe_de_france`, `europa_league` |
| Lille OSC | 47 | `ligue1`, `coupe_de_france`, `champions_league` |
| AS Monaco | 46 | `ligue1`, `coupe_de_france`, `champions_league` |

### Exemple chronologique — PSG, 14 premiers matchs (championnat + C1 + coupe mêlés)

```
2024-08-16 20:45  ligue1            vs Le Havre AC              ext  rest_days=None (1er match de la saison)
2024-08-23 20:45  ligue1            vs Montpellier HSC          dom  rest_days=7.0
2024-09-01 20:45  ligue1            vs Lille OSC                ext  rest_days=9.0
2024-09-14 21:00  ligue1            vs Stade Brestois 29        dom  rest_days=13.01
2024-09-18 21:00  champions_league  vs Girona FC                dom  rest_days=4.0
2024-09-21 21:00  ligue1            vs Stade de Reims           ext  rest_days=3.0
2024-09-27 21:00  ligue1            vs Stade Rennais FC 1901    dom  rest_days=6.0
2024-10-01 21:00  champions_league  vs Arsenal FC               ext  rest_days=4.0
2024-10-06 20:45  ligue1            vs OGC Nice                 ext  rest_days=4.99
2024-10-19 21:00  ligue1            vs RC Strasbourg Alsace     dom  rest_days=13.01
2024-10-22 21:00  champions_league  vs PSV                      dom  rest_days=3.0
2024-10-27 20:45  ligue1            vs Olympique de Marseille   ext  rest_days=4.99
2024-11-02 17:00  ligue1            vs Racing Club de Lens      dom  rest_days=5.84
2024-11-06 21:00  champions_league  vs Club Atlético de Madrid  dom  rest_days=4.17
```

**Vérification manuelle demandée confirmée** : les matchs de Champions
League s'intercalent bien chronologiquement avec les matchs de Ligue 1
(ex. le 18/09 et le 01/10 entre les journées de championnat), chose que
`fixture_congestion.py` (Brique 1, intra-championnat) ne pouvait pas
voir — c'est exactement l'écart que ce chantier cherchait à combler.

## 4. Résultats des tests

- **113 tests** créés pour ce module (28 unitaires + 85 d'intégration
  paramétrés sur les 13 compétitions réelles), **tous passent**.
- Couvrent explicitement : ligne valide, ligne invalide/ambiguë (plusieurs
  cas : pas d'heure, équipe vide, pas de date courante), rollover d'année
  (avec et sans restitution explicite par la source), date hors de la
  plage déclarée, extraction d'équipe avec/sans code pays, score simple,
  score avec qualificatif (`pen.`/`a.e.t.`), match `[awarded]`, match non
  joué, fichier absent, compétition/saison inconnue, mapping explicite
  sans fuzzy matching (avec une preuve négative explicite : un nom
  légèrement différent ne retrouve aucun match), compétition non
  enregistrée journalisée comme `SkippedCompetition`, et le garde-fou PIT
  de `congestion_preview` (jamais le match cible, jamais un match
  postérieur).
- **Suite complète du projet** (tests pré-existants) : lancée en tâche de
  fond au moment de la rédaction de ce rapport pour confirmer l'absence
  de régression ; résultat à rapporter séparément dès qu'elle se termine
  (processus long, >1485 tests selon `docs/final_data_strategy.md`).

## 5. Limites (rappel, voir aussi `docs/openfootball_calendar.md`)

1. Fuseau horaire des heures de coup d'envoi non confirmé (exposé en
   `datetime` naïf, jamais présenté comme UTC).
2. Aucun cas réel de match reporté observé dans les fichiers utilisés —
   l'argument PIT reste structurel (mode de production hebdomadaire
   vérifié), pas une observation directe.
3. Couverture 2025/26 non disponible à ce jour pour les coupes
   nationales et les phases principales Europa/Conference League.
4. Une seule anomalie de source (match sans heure) a nécessité une
   exclusion — comportement attendu et correctement journalisé, pas une
   défaillance du parseur.

## 6. Confirmation explicite

- `final_engine/` : **aucune modification, aucun import, aucun appel**
  (`git diff --stat -- src/sys_foot_quant/final_engine/` vide).
- `scripts/predict_match.py` / `run_prediction` : **inchangés**.
- Décision BET/NO_BET, `min_edge_threshold`, calibration : **inchangés**.
- `poisson_simple`, `dixon_coles` : **inchangés, aucun import**.
- `fixture_congestion.py` (Brique 1) : **inchangé** — module strictement
  séparé, jamais fusionné.
- Aucune donnée inventée, aucun match manquant simulé, aucun fuzzy
  matching.
- Aucun commit, aucun push effectué.

## 7. Prochaine étape recommandée (non exécutée)

1. Étendre le mapping explicite de noms à l'ensemble des clubs des 3
   championnats (actuellement limité à 5 clubs français pour la
   démonstration), en le construisant comme fichier dédié analogue à
   `team_mapping.py`/`elo_team_mapping.py`, vérifié à la main.
2. Chercher activement, dans les fichiers déjà téléchargés ou une source
   de contrôle externe, un cas réel de match reporté pour transformer
   l'argument PIT structurel (section 2.4 de l'audit précédent) en
   vérification empirique directe.
3. Attendre/revérifier périodiquement la disponibilité des fichiers
   2025/26 de coupe nationale et des phases principales Europa/Conference
   League avant d'étendre ce module à cette saison.
4. Seulement après ces étapes, envisager une éventuelle intégration à
   `fixture_congestion.py` sous forme d'une **nouvelle variante
   explicitement nommée** (jamais une modification silencieuse de la
   Brique 1 existante) — décision qui reste entièrement à la discrétion de
   l'utilisateur, non entamée ici.

Aucun commit, aucun push. En attente de la décision de l'utilisateur sur
la suite.
