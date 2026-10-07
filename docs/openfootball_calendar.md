# Module `openfootball_calendar` — calendrier multi-compétitions (2024/25)

**Statut.** Couche de données isolée, implémentation contrôlée suite au
`GO PARTIEL` de `docs/multi_competition_calendar_open_data_audit.md`.
**N'est intégrée à aucun pipeline de prédiction** : non importée par
`final_engine/`, `scripts/predict_match.py`, `fixture_congestion.py`, ni
par aucun chemin de décision BET/NO_BET. Aucun seuil, aucune calibration,
aucune expérience ne dépend de ce module à ce stade.

## Ce que ce module fait

Parse les fichiers texte publics (domaine public, CC0) du projet
`openfootball`/`football.db` (`github.com/openfootball/*`), déjà
téléchargés par appel HTTP réel dans
`research/fixture_calendar/openfootball/runs/<pays_ou_uefa>/
2024-25_<competition>.txt`, et expose :

- `load_competition(season, competition) -> ParseReport` — matchs +
  exclusions journalisées pour UNE compétition ;
- `build_team_calendar(season, team_name_by_competition) -> (entries,
  skipped)` — calendrier chronologique d'UN club, toutes compétitions
  combinées, à partir d'un mapping de noms **explicite fourni par
  l'appelant** (jamais de fuzzy matching) ;
- `congestion_preview(calendar, as_of) -> CongestionPreview` — repos et
  fréquence de matchs **préparatoires uniquement**, jamais injectés dans
  un modèle par ce module.

## Compétitions couvertes (2024/25 uniquement)

`ligue1`, `coupe_de_france`, `premier_league`, `fa_cup`, `efl_cup`,
`liga`, `copa_del_rey`, `champions_league`, `champions_league_qualifying`,
`europa_league`, `europa_league_qualifying`, `conference_league`,
`conference_league_qualifying`.

**La saison 2025/26 n'est volontairement pas enregistrée** : au moment de
l'audit, les fichiers de coupe nationale et des phases principales
Europa/Conference League 2025/26 étaient absents du dépôt source (HTTP
404 réel, vérifié) — conformément à la règle « ne jamais supposer qu'un
fichier existe », aucune entrée n'est créée pour une saison dont le
fichier n'a pas été confirmé présent.

## Discipline de parsing

- Toute ligne candidate-match (contenant le séparateur `` v ``) qui ne
  peut pas être interprétée sans ambiguïté est **exclue explicitement et
  journalisée** (`ParseExclusion`), jamais ignorée silencieusement ni
  devinée.
- Les scores portant un qualificatif (`pen.`, `a.e.t.`, `[awarded]`) sont
  conservés comme matchs joués (`is_played=True`), mais `home_goals`/
  `away_goals` restent `None` — le nombre de buts « normal » serait
  ambigu à extraire, jamais inventé.
- Une compétition demandée mais non enregistrée/absente du disque est
  **ignorée et journalisée** (`SkippedCompetition`) au niveau de
  `build_team_calendar`, jamais simulée.
- Aucun fuzzy matching : `build_team_calendar` ne retrouve un club que
  si son nom correspond **exactement** à la chaîne telle qu'elle apparaît
  dans le fichier de la compétition concernée (vérifié par un test dédié
  prouvant qu'une variante de nom proche — sans tiret — ne retrouve
  aucun match).

## Limites connues (documentées, pas masquées)

1. **Fuseau horaire non confirmé.** L'heure publiée (ex. `20:45`) est
   exposée telle quelle dans `kickoff_local_naive` (`datetime` **sans**
   fuseau horaire) — elle n'est PAS présentée comme UTC, car ce point
   n'a pas pu être vérifié auprès de la source. Toute comparaison
   inter-fuseaux resterait approximative.
2. **Aucun cas réel de match reporté observé** dans les fichiers
   utilisés. L'argument de robustesse PIT (voir docstring du module,
   section "HYPOTHESE PIT EXPLICITE") repose sur le mode de production
   vérifié (mises à jour hebdomadaires automatisées pendant la saison,
   historique de commits réel — `docs/multi_competition_calendar_open_data_audit.md`
   section 2.4), **pas** sur l'observation directe d'un report
   correctement traité.
3. **Couverture 2025/26 non disponible** pour les coupes nationales et
   les phases principales Europa/Conference League à ce jour.
4. **Mapping de noms à construire manuellement** pour chaque club
   suivi — un même club s'écrit différemment selon le fichier
   (ex. « AS Monaco FC » en Ligue 1, « AS Monaco » en Coupe de France,
   « Monaco FC (MCO) » en Ligue des Champions).
5. **Aucune intégration production.** Ce module ne modifie, n'importe ni
   n'est importé par aucun module de `final_engine/`, `predict_match.py`,
   ou tout chemin de décision BET/NO_BET.

## Provenance exacte des fichiers utilisés

Téléchargés par appel HTTP réel (`curl` vers `raw.githubusercontent.com`,
confirmé accessible depuis cette session) lors de cette implémentation :

| Fichier local | URL source |
|---|---|
| `france/2024-25_fr1.txt` | `openfootball/europe/master/france/2024-25_fr1.txt` |
| `france/2024-25_frcup.txt` | `openfootball/europe/master/france/2024-25_frcup.txt` |
| `england/2024-25_1-premierleague.txt` | `openfootball/england/master/2024-25/1-premierleague.txt` |
| `england/2024-25_facup.txt` | `openfootball/england/master/2024-25/facup.txt` |
| `england/2024-25_eflcup.txt` | `openfootball/england/master/2024-25/eflcup.txt` |
| `espana/2024-25_1-liga.txt` | `openfootball/espana/master/2024-25/1-liga.txt` |
| `espana/2024-25_cup.txt` | `openfootball/espana/master/2024-25/cup.txt` |
| `uefa/2024-25_cl.txt`, `clq.txt`, `el.txt`, `elq.txt`, `conf.txt`, `confq.txt` | `openfootball/champions-league/master/2024-25/*.txt` |

Note : La Liga a été incluse bien que le périmètre demandé pour cette
étape ne la nommait pas explicitement (seul Copa del Rey y figurait) —
ajout délibéré pour garder la cohérence des 3 championnats historiques du
projet (Liga/Ligue 1/Premier League) et parce que Copa del Rey est
difficile à interpréter sans le référentiel Liga. Coût/risque nul (simple
fichier texte supplémentaire déjà public).
