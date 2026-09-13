# Validation OddsPortal + OddsHarvester — piste de repli gratuite après TheStatsAPI

**Nature de ce document.** POC/test isolé uniquement. Aucun code de
production modifié, aucun module `odds_provider` créé, aucune intégration
au moteur, `final_engine/`, `predict_match.py`, R1/R2/R3/R4, Shadow Mode et
la méthodologie scientifique (E7/E8, gates, `min_edge_threshold=None`,
règles PIT) intégralement inchangés. Seuls trois fichiers hors production
ont été créés/modifiés : `scripts/poc_oddsportal_oddsharvester.py`,
`tests/unit/test_poc_oddsportal_oddsharvester.py`, et l'ajout de
`beautifulsoup4` au groupe `dev` (uniquement pour reproduire fidèlement,
à des fins de test, le parsing réel d'un outil tiers — voir §5). Aucun
contournement de la politique réseau/proxy de cette session n'a été
tenté, conformément à la consigne explicite reçue.

---

## VERDICT COURT

**REFUSÉ pour cette session — accès réseau à OddsPortal bloqué, aucune
observation réelle possible. Distinct d'un jugement sur la qualité
d'OddsPortal/OddsHarvester eux-mêmes**, qui restent structurellement
prometteurs (voir §5-§6) mais dont le comportement réel sur une vraie
page n'a jamais pu être observé, et dont le code contient deux défauts
réels et confirmés (bug d'année, absence de fuseau horaire) qui
devraient de toute façon être corrigés avant tout usage PIT — même si le
réseau était débloqué demain.

---

## 1. Accès réseau

**Test réel effectué depuis cette session, couche par couche (même
méthode que pour TheStatsAPI/The Odds API), sans aucune tentative de
contournement du proxy obligatoire** :

| Couche | Résultat |
|---|---|
| DNS (`www.oddsportal.com`) | **RÉUSSI** — résout vers une adresse IP réelle |
| TCP brut, port 443, hors `HTTPS_PROXY` | **RÉUSSI** — `TCP CONNECT SUCCESS` |
| HTTPS via le proxy d'egress obligatoire de la session | **ÉCHEC** — `curl: (56) CONNECT tunnel failed, response 403` |

**Preuve indépendante et décisive**, identique à la méthode qui a
tranché la question pour TheStatsAPI : `curl -sS
"$HTTPS_PROXY/__agentproxy/status"` montre, dans `recentRelayFailures`,
une entrée horodatée exactement au moment du test :

```json
{
  "kind": "connect_rejected",
  "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
  "host": "www.oddsportal.com:443"
}
```

**Conclusion : `oddsportal.com` est bloqué par la même politique
d'organisation que tous les autres fournisseurs testés dans cette
session (TheStatsAPI, The Odds API, Polymarket, Understat,
Football-Data, ClubElo)** — DNS et réseau bas niveau fonctionnent, seul
le tunnel HTTPS applicatif via le proxy obligatoire est refusé. Ce n'est
ni un problème DNS, ni un problème réseau générique, ni un jugement sur
OddsPortal. **Aucune tentative de contournement n'a été faite**
(conforme à la consigne explicite reçue et à la règle déjà établie de
cette session : « do not retry organization policy denials »).

## 2. Outil utilisé

**OddsHarvester** (PyPI : `oddsharvester`, version `0.12.0` au moment du
test, auteur Jordan TETE, licence MIT, dépôt
`https://github.com/jordantete/OddsHarvester`). Choisi car c'est le
seul outil open source pertinent trouvé pour scraper OddsPortal, avec un
projet actif (CI, tests unitaires, codecov, releases régulières) — pas
un script isolé abandonné.

**Vérifié réellement** : le paquet existe sur PyPI (`pypi.org` est
accessible depuis cette session, contrairement à `oddsportal.com`
lui-même) — métadonnées et wheel (`oddsharvester-0.12.0-py3-none-any.whl`)
téléchargés et extraits pour inspection directe du code source réel
(pas seulement la description marketing du README).

**Contraintes supplémentaires, indépendantes du blocage réseau,
confirmées par les métadonnées du paquet** :
- Nécessite **Python ≥ 3.12** (cet environnement de développement est en
  Python 3.11) — un `pip install`/`pip download` direct échoue ici pour
  cette raison, indépendamment du réseau.
- Dépend de **Playwright** (automatisation de navigateur réelle, pas une
  API REST) — même avec un accès réseau à OddsPortal, l'exécution
  complète nécessiterait un navigateur Chromium piloté et des délais
  d'attente réels (hover, chargement de page), pas un simple appel HTTP.

Ces deux points n'ont **pas** empêché la partie utile de ce test (voir
§5 : inspection du code source, faisable sans exécuter l'outil), mais
auraient de toute façon bloqué une exécution complète même si le réseau
avait été ouvert.

## 3. Matchs testés

Les 3 mêmes matchs de référence que pour TheStatsAPI (comparabilité
demandée explicitement) :

| # | Compétition | Match | Kickoff (UTC) |
|---|---|---|---|
| 1 | Premier League 2024/25 | Chelsea vs Arsenal | 2024-11-10 16:30 |
| 2 | La Liga 2024/25 | Real Madrid vs Barcelona | 2024-10-26 20:00 |
| 3 | Ligue 1 2024/25 | Paris SG vs Marseille | 2025-03-16 19:45 |

**Aucun des trois n'a pu être interrogé sur la vraie page OddsPortal**
(accès bloqué, §1). Les trois ligues (`england-premier-league`,
`spain-laliga`, `france-ligue-1`) sont bien des slugs supportés par
OddsHarvester (confirmé dans son code source,
`oddsharvester/utils/sport_league_constants.py`), donc rien n'indique
un problème de couverture — seulement l'impossibilité de le vérifier
depuis cette session.

## 4. Bookmakers disponibles

**NON VÉRIFIÉ empiriquement** — aucune page réelle consultée. Le code
source d'OddsHarvester ne restreint à aucun bookmaker particulier : il
extrait génériquement toute ligne bookmaker présente sur la page
(`_extract_bookmaker_name`), donc s'appuie entièrement sur ce
qu'OddsPortal affiche réellement pour chaque match — impossible à
confirmer sans accès réel. Aucune mention spécifique de Bet365/Pinnacle
dans le code (contrairement à TheStatsAPI où c'était documenté par le
fournisseur) : leur présence dépend uniquement de la couverture réelle
d'OddsPortal pour chaque match, marché connu pour afficher un grand
nombre de bookmakers (souvent 15-20+) mais jamais confirmé ici.

## 5. Marchés disponibles

**DOCUMENTÉ par le code source** (pas par une simple page marketing) :
`over_under` est un marché supporté nativement pour le football, avec un
mécanisme de « market token umbrella » qui, au moment du scraping,
s'étend vers chaque ligne réellement rendue par OddsPortal
(`over_under_1_5_market`, `over_under_2_5_market`, etc.) — donc Over/Under
2.5 est un marché structurellement demandable, mais sa présence réelle
pour nos 3 matchs précis n'a pas pu être observée.

## 6. Exemples réels de données récupérées

**Aucun.** Zéro appel réel n'a atteint OddsPortal (§1). Aucune donnée
n'a été fabriquée pour combler cette absence — voir le rapport produit
par `scripts/poc_oddsportal_oddsharvester.py` (exécuté réellement dans
cette session, sortie ci-dessous, tronquée) :

```
=== Diagnostic reseau reel vers www.oddsportal.com ===
  DNS       : OK - 3 enregistrement(s) resolu(s).
  TCP brut  : OK - connexion TCP brute reussie (hors proxy).
  HTTPS (via le proxy obligatoire) : ECHEC - echec de connexion via le
  proxy obligatoire : Tunnel connection failed: 403 Forbidden.

ACCES BLOQUE : acces reseau a oddsportal.com bloque depuis cet environnement.
Aucune tentative de contournement du proxy obligatoire n'a ete faite.
Aucune donnee n'est fabriquee pour compenser cette absence d'acces reel.

=== Chelsea vs Arsenal (Premier League 2024/25) ===
  T-24h avant kickoff : NON VERIFIE (acces reseau a oddsportal.com bloque depuis cet environnement)
  T-12h avant kickoff : NON VERIFIE (...)
  T-6h avant kickoff  : NON VERIFIE (...)
  T-3h avant kickoff  : NON VERIFIE (...)
  T-1h avant kickoff  : NON VERIFIE (...)
  T-30min avant kickoff : NON VERIFIE (...)
  T-10min avant kickoff : NON VERIFIE (...)
  [... identique pour Real Madrid vs Barcelona et Paris SG vs Marseille ...]
```

**Ce qui a en revanche pu être vérifié réellement, sans toucher au
réseau : le code source d'OddsHarvester 0.12.0 lui-même**, en
téléchargeant son wheel PyPI (accessible, contrairement à
`oddsportal.com`) et en l'inspectant directement :

- `oddsharvester/core/market_extraction/odds_history_extractor.py` :
  l'option `--odds-history` déclenche, pour chaque bookmaker et chaque
  cellule de cote (Over et Under **séparément**), un survol (hover)
  Playwright qui ouvre une modale « odds movement » sur la page réelle
  d'OddsPortal.
- `oddsharvester/core/market_extraction/odds_parser.py::parse_odds_history_modal`
  (lignes 105-159) parse cette modale en un objet structuré :
  ```json
  {
    "odds_history": [
      {"timestamp": "...", "odds": 1.85},
      {"timestamp": "...", "odds": 1.73}
    ],
    "opening_odds": {"timestamp": "...", "odds": 1.90}
  }
  ```
  C'est un mécanisme **réel, documenté par le code**, pas une promesse
  marketing — mais le **nombre réel** de points que retourne une vraie
  page OddsPortal pour un match donné (2 points ? 10 ? 50 ?) reste
  **NON VÉRIFIÉ**, puisqu'aucune page réelle n'a pu être chargée.

**Démonstration reproductible de deux défauts réels du code**, en
rejouant une reproduction fidèle et attribuée (MIT, voir en-tête de
`scripts/poc_oddsportal_oddsharvester.py`) de cette fonction sur une
entrée HTML **synthétique construite pour respecter exactement les
sélecteurs CSS réels du code** (jamais pour fabriquer une conclusion sur
des données OddsPortal réelles — uniquement pour tester le comportement
du CODE tiers, vérifié par `tests/unit/test_poc_oddsportal_oddsharvester.py`,
16 tests, tous verts) :

1. **Bug d'année confirmé.** OddsPortal affiche ses timestamps sans
   année (`"08 Nov, 09:00"`), et le code d'OddsHarvester complète avec
   `datetime.now(UTC).year` — **l'année d'exécution du scraping, jamais
   l'année réelle du mouvement de cote.** Pour un usage historique (notre
   cas exact : scraper aujourd'hui un match de 2024), la sortie brute
   contiendrait systématiquement la mauvaise année, sans avertissement.
2. **Aucun fuseau horaire.** Les timestamps produits sont **naïfs**
   (`datetime.strptime(...).isoformat()` sans `tzinfo`). Le fuseau réel
   d'affichage d'OddsPortal n'a jamais pu être confirmé empiriquement
   (accès bloqué) — un risque de fuite/décalage PIT si un futur
   connecteur suppose silencieusement UTC.

Ces deux défauts sont **corrigibles côté appelant** (voir
`correct_oddsharvester_year` et `attach_assumed_timezone` dans le POC,
tous deux testés), mais prouvent que le résultat brut d'OddsHarvester ne
peut **jamais** être utilisé tel quel pour du PIT — une correction
explicite et documentée serait obligatoire dans tout futur connecteur.

## 7. Timestamps réellement disponibles

**NON VÉRIFIÉ sur une vraie page** (accès bloqué). **Confirmé par le
code source** : un timestamp est associé à chaque point de
`odds_history` et à `opening_odds`, mais toujours au format naïf
`"DD Mon, HH:MM"` (sans année, sans fuseau) — voir §6.

## 8. Granularité observée

**Impossible à observer réellement.** Le code est structurellement
capable de retourner une liste de longueur arbitraire (`zip(timestamps,
odds_values)`), donc rien n'indique une limitation à seulement
« ouverture/fermeture » côté code — mais **le nombre réel de points que
la page OddsPortal affiche pour un match donné reste totalement inconnu
depuis cette session.** Ne jamais confondre « le code peut renvoyer une
série » avec « OddsPortal fournit réellement une série dense » — cette
dernière affirmation n'est PAS vérifiée.

## 9. Capacité ou incapacité à respecter le PIT

**Ni confirmée, ni infirmée empiriquement** — le test décisif (charger
une vraie page, vérifier `odds_timestamp < decision_time < kickoff` sur
des données réellement observées) n'a pas pu avoir lieu. Ce qui EST
établi avec certitude, indépendamment du réseau :

- Le bug d'année (§6.1) rendrait toute reconstruction PIT **fausse par
  défaut** si le correctif n'est pas appliqué — un vrai risque de
  méthodologie silencieusement corrompue, pas une hypothèse.
- L'absence de fuseau horaire (§6.2) empêche de garantir
  `odds_timestamp < decision_time` avec la précision qu'exige notre
  méthodologie (l'écart entre deux fuseaux plausibles peut suffire à
  faire basculer un mouvement de cote de l'avant à l'après
  `decision_time`).
- La règle de sélection elle-même (`select_last_snapshot_before`,
  `<` strict, jamais `<=`) est correcte et testée (voir §5 du POC) —
  mais elle ne sert à rien sans des timestamps fiables en amont.

## 10. Limites

- **Accès réseau bloqué depuis cette session précise** — même
  classification (`BLOQUANT ENVIRONNEMENT`) que pour tous les
  fournisseurs précédents. Rien ne garantit que l'accès serait ouvert
  depuis un autre environnement, mais rien ne l'exclut non plus — c'est,
  comme toujours, spécifique à cette session.
- **Python ≥ 3.12 requis**, cet environnement de développement est en
  3.11 — contrainte supplémentaire indépendante du réseau.
- **Playwright/navigateur réel requis** — pas une simple API HTTP,
  scraping potentiellement fragile aux changements de mise en page
  d'OddsPortal (risque structurel de tout scraper HTML, contrairement à
  une API stable).
- **Performance** : l'extraction d'historique se fait par survol
  (hover) un par un, avec des délais fixes (`ODDS_HISTORY_PRE_WAIT_MS`
  = 2000 ms, `ODDS_HISTORY_HOVER_WAIT_MS` = 2000 ms par cellule) — pour
  un marché Over/Under 2.5 avec 15-20 bookmakers, cela représente
  potentiellement plusieurs minutes **par match**, uniquement pour
  l'historique d'un seul marché.
- **Zone grise juridique/CGU** : le scraping d'OddsPortal (site tiers)
  n'a fait l'objet d'aucune vérification de ses conditions
  d'utilisation dans le cadre de ce test — point non traité ici, à
  examiner séparément si cette piste est un jour ré-ouverte.
- **Deux défauts de code confirmés** (§6.1, §6.2) qui, à eux seuls,
  interdisent un usage PIT direct sans correctif côté appelant — déjà
  écrits et testés dans le POC, mais jamais exercés sur une vraie
  donnée.

## 11. Recommandation pour la suite

**Ne pas poursuivre cette piste dans l'immédiat.** Le blocage est
environnemental (comme pour TheStatsAPI), pas une conclusion sur la
qualité de la source. Si cette piste doit être ré-évaluée un jour,
depuis un environnement avec accès réseau réel :

1. Utiliser un environnement Python ≥ 3.12 avec Playwright installé
   (`playwright install chromium`).
2. Lancer `oddsharvester historic -s football -l england-premier-league
   --season 2024-2025 --market over_under --odds-history -f json` pour
   un seul match connu (Chelsea vs Arsenal) et inspecter réellement le
   nombre de points retournés dans `odds_history` — c'est la seule
   façon de trancher la question de granularité (§8), impossible à
   deviner depuis le code seul.
3. Si des points multiples et rapprochés (heures, pas seulement
   ouverture/fermeture) sont réellement observés : appliquer
   systématiquement `correct_oddsharvester_year` (déjà écrit et testé
   dans `scripts/poc_oddsportal_oddsharvester.py`) et déterminer
   empiriquement le fuseau horaire réel d'OddsPortal (comparer un
   timestamp observé à une heure connue par ailleurs) avant tout usage
   PIT.
4. Comparer la charge opérationnelle réelle (temps par match, taux
   d'échec du scraping) à la valeur ajoutée avant toute décision
   d'intégration — ne jamais intégrer au moteur sans un deuxième tour de
   validation empirique complet, dans l'esprit des audits déjà menés
   pour TheStatsAPI/The Odds API.

---

*Aucune donnée n'a été fabriquée pour produire ce document. Aucun
fichier de production modifié — vérifié par `git diff` avant commit.
Aucune tentative de contournement de la politique réseau de cette
session.*
