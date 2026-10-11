# Connecteur OddsPortal — note factuelle (recherche isolée, pas production)

**Nature de ce document.** Rapport factuel du connecteur de recherche
`research/oddsportal_integration/` : résultats de matchs + cotes
consensus brutes extraits des pages publiques "results" d'oddsportal.com.
Ce connecteur n'est **jamais importé par `src/sys_foot_quant`** et ne
modifie **jamais** les fichiers canoniques Understat
(`research/xg_feasibility/runs/*_datesData.json`) ni aucun fichier lu par
l'API. Il produit des fichiers JSON autonomes
(`research/oddsportal_integration/runs/*_results.json`), pas encore
branchés nulle part.

## 1. Contexte — contredit un audit précédent de ce dépôt

`research/oddsportal_validation.md` concluait "refusé pour cette session"
car l'accès réseau à oddsportal.com était bloqué par la politique d'egress
de l'environnement d'exécution de *cette session-là*. Vérifié réellement
depuis la session courante (requête HTTP réelle, réponse HTTP 200, le
2026-10-10) : oddsportal.com **est** accessible. De même, le POC vendorisé
précédent (`scripts/poc_oddsportal_oddsharvester.py`) ciblait un "modal"
d'historique de cotes nécessitant un navigateur piloté via Playwright —
piste différente de celle retenue ici (page "results" en liste, pas le
modal détail d'un match).

## 2. Découverte — format source (reverse-engineering direct)

Au moins une fois (capture réelle du 2026-10-10, préservée verbatim dans
`research/oddsportal_integration/tests/fixtures/results_page_sample.html`
pour les tests), la page "results" d'une compétition a exposé les données
nécessaires (équipes, score, horaire, venue, cotes 1X2 consensus
multi-bookmaker) directement dans le HTML servi par le serveur, sans
exécution JavaScript : rendu Next.js App Router, streaming RSC — chaque
page embarque plusieurs appels `self.__next_f.push([1,"<chaîne JS
échappée>"])`, et un de ces blocs, une fois dé-échappé, contient un grand
nombre d'objets JSON `{"id": <int>, "is-double": ..., "home-name": ...,
"away-name": ..., ...}`, un par match.

`oddsportal_results_source.py` implémente l'extraction complète :
- `_find_next_f_string_literals` : scanner respectant les échappements
  `\"`/`\\` (un regex `.*?` naïf tronquerait le contenu au premier
  guillemet échappé rencontré).
- `_select_match_bearing_chunk` : sélectionne le bon bloc parmi plusieurs
  (navigation, scripts divers) — IMPORTANT, le bloc est encore échappé à
  ce stade, donc la recherche se fait sur `home-name` SANS les guillemets
  qui l'encadrent (bug initial corrigé : chercher `"home-name"` avec
  guillemets ne matche jamais un texte encore échappé).
- `_extract_balanced_json_object` : extraction par équilibrage d'accolades
  (pas un regex non-greedy fragile) respectant les limites de chaînes
  JSON internes.
- `extract_match_objects` : un objet corrompu/tronqué est ignoré, jamais
  fabriqué ni ne fait échouer le reste du lot.

Limites documentées en tête du module (non résumées ici, voir le
docstring) : sémantique des cotes home/draw/away **non confirmée**
(`outcomeResultId` observé à 1, 2, 2 pour les 3 lignes attendues — PAS
1/2/3), `partialresult` non interprété, une seule page par appel (pas de
pagination), CGU/robots.txt non vérifiées (risque accepté explicitement
par l'utilisateur, 2026-10-10), fuseau horaire supposé UTC pour
`date-start-timestamp` (sémantique standard d'un timestamp Unix, pas une
confirmation OddsPortal explicite).

## 3. Correctif critique — la récupération en direct n'est PAS fiable

Découvert **le jour même**, en re-testant la robustesse avant de brancher
une tâche planifiée : plusieurs tentatives ultérieures de
`fetch_results_page` contre la **même URL** (`curl` simple, plusieurs
jeux d'en-têtes essayés, avec et sans cookies) ont systématiquement
renvoyé une page HTTP 200 **sans** les données de match — une page ~329 Ko
(contre ~1.4 Mo pour la capture réussie) dont l'inspection confirme qu'il
s'agit du fallback React Suspense de chargement (`"aria-busy":true`,
`"aria-label":"Loading page"`, ~120 occurrences de la classe
`animate-pulse`) — pas une page d'erreur/CAPTCHA, mais un tableau de
résultats qui, dans ce cas, ne se résout que côté client (après exécution
JavaScript dans un vrai navigateur, via un appel réseau non identifié).

`parse_results_page` lève correctement `OddsPortalParsingError` dans ce
cas (fail-closed, comportement voulu — jamais une liste vide silencieuse).
Mais cela signifie concrètement que **la fiabilité d'un rafraîchissement
automatisé n'est pas établie** : le format de données existe et est
parsable (d'où les 30 tests unitaires, tous verts, basés sur la capture
réelle réussie), mais une requête HTTP simple ne le récupère pas de façon
garantie.

Deux pistes non explorées par manque de temps à ce stade :
1. Identifier l'appel fetch/XHR réel déclenché côté client pour résoudre
   ce Suspense (probablement un point de terminaison JSON plus propre
   qu'un scraping HTML, mais nécessite d'analyser les bundles JS minifiés
   référencés par la page, ex. `/_next/static/chunks/1129vlj2svyid.js`).
2. Repasser par un navigateur piloté (Playwright/CDP) — ce qui annule
   l'argument "pas besoin de Playwright" du point 2 ci-dessus.

## 4. Décision opérationnelle retenue (2026-10-11)

Automatiser quand même, en tolérant les échecs : la tâche planifiée
récurrente appelle `cli_fetch_oddsportal_results.py` pour chaque
compétition suivie de façon indépendante — un échec (`OddsPortalFetchError`
/ `OddsPortalParsingError`) sur une compétition ou un passage de la tâche
n'empêche ni les autres compétitions, ni le rafraîchissement Understat
(fiable, lui) de se dérouler. Aucune donnée fabriquée n'est jamais écrite
en cas d'échec — le fichier de sortie n'est simplement pas mis à jour pour
ce passage.

## 5. Fichiers

- `research/oddsportal_integration/oddsportal_results_source.py` — module
  de production (du point de vue de ce connecteur isolé) : fetch + parse.
- `research/oddsportal_integration/cli_fetch_oddsportal_results.py` — CLI
  d'invocation manuelle ou planifiée, écrit un JSON par compétition sous
  `research/oddsportal_integration/runs/`.
- `research/oddsportal_integration/tests/` — 30 tests, aucun réseau réel,
  fixture `fixtures/results_page_sample.html` extrait verbatim d'une
  capture réelle (2 matchs réels : Brest–Angers à venir, Lens–Lyon 2-1
  terminé). Invocation manuelle (`uv run pytest
  research/oddsportal_integration/tests/ -v`) — **pas** ramassés par
  `make test` (`testpaths` reste `["tests"]`, même convention que
  `research/xg_feasibility/tests/`).
