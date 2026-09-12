# Audit d'automatisation des cotes pré-match — sys-foot-quant

**Nature de ce document.** Étude/recommandation pure. Aucun code modifié,
aucune intégration créée, aucune clé API demandée ou utilisée, aucune
collecte Polymarket relancée. `final_engine/` et la méthodologie
scientifique (E7/E8, gates, `min_edge_threshold=None`) ne sont ni
modifiés ni remis en question — cet audit porte exclusivement sur
l'**acquisition** de la seule donnée que R3 prend aujourd'hui en entrée
manuelle : la cote d'ouverture Bet365 Over/Under 2.5.

---

## 1. État actuel du système

- `scripts/predict_match.py` prend `--market-odds-over-2-5`/
  `--market-odds-under-2-5` en arguments CLI **obligatoirement fournis à
  la main** (ou aucun des deux, auquel cas `MARKET_DATA_UNAVAILABLE` →
  `NO_BET`, un mode déjà géré proprement).
- `final_engine/market.py::compare_over_under_to_market` ne compare
  **jamais** qu'une seule ligne : Over/Under 2.5, cote **d'ouverture**
  uniquement (les cotes de clôture existent dans le corpus Football-Data
  mais sont structurellement exclues du chemin de décision depuis E16,
  vérifié par test AST — `tests/leakage/test_final_engine_point_in_time.py`).
- La seule source de cotes déjà intégrée au code (`football_data_loader.py`)
  est **Football-Data.co.uk**, qui ne publie que des cotes de matchs
  **déjà joués** — structurellement inutilisable pour un vrai match futur,
  indépendamment de tout accès réseau.
- Aucune source de cotes pré-match en direct n'a jamais été recherchée ni
  intégrée par ce projet (la question « marché » a été déclarée
  scientifiquement épuisée en Phase I, ce qui a fermé l'incitation à
  chercher un flux temps réel).
- R1/R2/R3/Shadow Mode V1 sont fonctionnels et testés (1751 tests verts,
  `uv run pytest -q` réexécuté pour cet audit).

## 2. Besoin exact en données

Le moteur n'a besoin **que** de :
1. Une cote décimale Over 2.5 buts et une cote décimale Under 2.5 buts,
2. valables à `decision_time` (`kickoff_utc - 2h`, jamais après),
3. pour un match identifié sans ambiguïté (compétition, équipes,
   `kickoff_utc`),
4. avec un timestamp d'observation permettant de vérifier
   `timestamp_cote < decision_time` (règle PIT du projet).

Rien de plus n'est consommé par `final_engine` : pas de handicap
asiatique, pas de multi-bookmaker en décision (E9/E13 : dispersion non
informative), pas de cote de clôture (interdite structurellement).

## 3. Tableau comparatif des fournisseurs

| Fournisseur | API publique | Auth | Plan gratuit | Football | Nos 3 compétitions | Marchés pertinents | Bookmakers | Pinnacle | Bet365 | Betfair |
|---|---|---|---|---|---|---|---|---|---|---|
| **The Odds API** | Oui, REST, doc claire | Clé API | 500 crédits/mois | Oui, `soccer_epl` et équivalents Liga/Ligue 1 | Oui (confirmé EPL ; La Liga/Ligue 1 confirmés par la documentation produit, clé exacte non vérifiable sans compte) | h2h, spreads, **totals (O/U)** | Multi (US/UK/EU/AU) | **Oui** | **Incertain pour la version UK/EU** (Bet365 refuse généralement la redistribution par des agrégateurs hors marché australien — seul « Bet365 AU » est mentionné dans la documentation trouvée) | Non confirmé en marché standard (existe via agrégateurs tiers, pas nativement) |
| **TheStatsAPI** | Oui, REST | Clé API | Essai 7 jours, pas de tier gratuit permanent | Oui, dédié football | Oui (couverture "1000+ compétitions") | 1X2, **O/U**, BTTS, handicap asiatique, corners | **Bet365, Pinnacle, Paddy Power, Betfair Sportsbook, Kambi** | **Oui** | **Oui** | **Oui (Sportsbook, pas Exchange)** |
| **OddsPapi** | Oui, REST + WebSocket | Clé API | 250 req/mois, historique inclus gratuitement | Oui, tous championnats | Oui | 1X2, **O/U**, handicaps, 460+ marchés | 140+ (grandes ligues) / 30-50 (ligues mineures) | Oui (via agrégation) | Oui (via agrégation, cf. leur propre article "Bet365 Historical Odds Guide") | Non confirmé |
| **Sportmonks (add-on Premium Odds Feed)** | Oui, REST | Clé API | Non — add-on payant sur plan payant | Oui, cœur de métier football | Oui (2200+ ligues) | 1X2, O/U, handicap asiatique, score correct | 120+ (partenariat TXODDS) | Non confirmé nommément | Non confirmé nommément | Non confirmé nommément |
| **Betfair (API officielle)** | Oui, mais lourde (certificats SSL, session tokens, process non-interactif) | Compte financé + application | Non — frais d'application historiquement (~£299) | Oui | Oui | Cote Exchange (pas un O/U bookmaker classique) | Betfair Exchange uniquement | — | — | Oui (natif, mais Exchange ≠ Bet365) |
| **Pinnacle (API officielle)** | **Fermée au public depuis le 23/07/2025** | — | — | — | — | — | — | Directement inaccessible désormais | — | — |
| **Sportsgameodds.com** | Oui, REST | Clé API | Oui, "free" annoncé | Oui | Probable (85+ sportsbooks, 67+ ligues — à vérifier précisément) | O/U, moneyline, etc. | 85+ | Non vérifié précisément | Non vérifié précisément | Non vérifié précisément |

**Sources** (recherche web du jour, pas d'inspection primaire possible — voir section 7) :
[The Odds API](https://the-odds-api.com/), [The Odds API — Historical Odds](https://the-odds-api.com/historical-odds-data/), [The Odds API — Docs V4](https://the-odds-api.com/liveapi/guides/v4/), [TheStatsAPI — Odds API](https://www.thestatsapi.com/odds-api), [TheStatsAPI — Historical Football Odds](https://www.thestatsapi.com/odds-api/historical-football-odds), [OddsPapi](https://oddspapi.io/en/docs), [OddsPapi — Historical Odds Docs](https://oddspapi.io/us/docs/get-historical-odds), [OddsPapi — Odds API Pricing 2026](https://oddspapi.io/blog/odds-api-pricing-2026-comparison/), [Sportmonks — Premium Pre-match Odds](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/premium-odds-feed/premium-pre-match-odds), [Sportmonks — Pricing](https://www.sportmonks.com/football-api/plans-pricing/), [Betfair Developers](https://developer.betfair.com/), [pinnapi — Pinnacle API alternative 2026](https://pinnapi.com/blog/pinnacle-api-alternative-2026), [Sportsgameodds.com](https://sportsgameodds.com/).

## 4. Analyse historique/PIT (le point critique)

| Fournisseur | Classe (A/B/C/D) | Justification |
|---|---|---|
| **The Odds API** | **D** — la plus solide trouvée | Endpoint historique dédié : paramètre `date` (ISO8601) → renvoie **le snapshot le plus récent ≤ cette date**, exactement le contrat PIT du projet (`timestamp < decision_time`). Snapshots toutes les 10 min (depuis juin 2020) puis 5 min (depuis sept. 2022). Reconstruire T-24h/T-12h/T-6h/T-1h est directement supporté par le paramètre de requête, pas une bidouille côté client. |
| **OddsPapi** | **D, avec travail client** | Renvoie l'historique **complet** des mouvements de prix par ligne avec `createdAt` — reconstruire "la cote connue avant T" est possible mais demande un filtrage côté client (prendre le dernier point avec `createdAt < T`), pas un paramètre serveur dédié comme The Odds API. |
| **TheStatsAPI** | **B, probablement C pour un T arbitraire** | Documentation trouvée mentionne des champs "opening" et "last_seen" — cela ressemble à **deux points fixes**, pas une série temporelle interrogeable à un instant quelconque. Ne permet probablement pas de reconstruire précisément T-6h sauf si "opening" coïncide par hasard avec la fenêtre voulue. **À vérifier avec un compte** avant tout choix définitif. |
| **Sportmonks** | **C pour un usage rétroactif au-delà d'une semaine** | Historique complet **mais purgé 7 jours après le match** — inutilisable pour reconstituer un historique de plusieurs mois, parfaitement suffisant en revanche pour le seul usage Shadow Mode (le règlement a lieu presque immédiatement après le match). |
| **Betfair officiel** | **D en théorie, coût et complexité élevés** | Service "Historical Data" horodaté vendu séparément — cadre PIT réel, mais lourdeur d'intégration et coût la rendent disproportionnée pour ce besoin. |
| **Pinnacle officiel** | **Non applicable** | API fermée au public depuis juillet 2025. |

**Risque de survivorship/look-ahead** : pour tous les fournisseurs
"agrégateurs" (The Odds API, OddsPapi, TheStatsAPI, Sportsgameodds), le
risque principal n'est pas le look-ahead au sens strict (les timestamps
sont fournis), mais un **historique reconstruit rétroactivement par le
fournisseur lui-même** sans garantie contractuelle qu'aucune révision
silencieuse n'a eu lieu — même réserve déjà documentée par ce projet pour
Football-Data (`TIMESTAMP_STATUS_HYPOTHETICAL`). Aucun fournisseur audité
ici ne publie de garantie formelle plus forte que Football-Data à ce
sujet ; The Odds API est le plus crédible car son mécanisme de requête
(`date` → snapshot ≤ date) est un contrat d'API explicite, pas une
déduction a posteriori.

## 5. Couverture de nos compétitions

Premier League, La Liga, Ligue 1 : couvertes par **tous** les
fournisseurs listés (championnats majeurs, jamais un problème de
couverture pour ce trio spécifiquement). Aucun changement de périmètre
championnat nécessaire.

## 6. Coûts et limites

| Fournisseur | Coût d'entrée | Limite pratique |
|---|---|---|
| The Odds API | Gratuit (500 crédits) → $29/mois (20 000 crédits, marchés de base) | Historique coûte 6-10 crédits/appel — le tier gratuit s'épuise vite (<85 appels historiques) |
| TheStatsAPI | $50/mois (Starter, 100k req/mois, tout inclus dès ce palier) | Pas de tier gratuit permanent, seulement un essai |
| OddsPapi | Gratuit (250 req/mois, historique inclus) → jusqu'à $499/mois selon volume/bookmakers | Très généreux en entrée, mais 250 req/mois est juste pour un usage quotidien multi-matchs |
| Sportmonks | Odds add-on €14-69 en plus d'un plan de base (à partir de €29/mois) | Historique limité à 7 jours post-match |
| Betfair officiel | Frais d'application historiques (~£299) + coût séparé pour l'historique | Lourdeur d'intégration (certificats, tokens) disproportionnée ici |
| Pinnacle officiel | Fermé | — |

## 7. Faisabilité technique — test réel effectué

**Test de connectivité direct, effectué depuis cette session, deux
mécanismes indépendants (curl via le proxy local, WebFetch via
l'infrastructure Anthropic)** :

| Domaine testé | Résultat |
|---|---|
| `the-odds-api.com` | `EGRESS_BLOCKED` / 403 `connect_rejected` |
| `www.thestatsapi.com` | 403 `connect_rejected` |
| `oddspapi.io` | 403 `connect_rejected` |
| `www.sportmonks.com` | 403 `connect_rejected` |
| Témoins de contrôle : `example.com`, `en.wikipedia.org` | **Également bloqués** |
| Témoin positif : `api.github.com` | 200 OK |

**Conclusion du test** : ce n'est pas un blocage ciblant les sites de
cotes — c'est une **politique d'egress par défaut-deny** de cette
session précise, qui ne laisse passer qu'une liste blanche restreinte
(infrastructure de développement : GitHub, PyPI, npm, API Anthropic).
Aucun fournisseur, quel qu'il soit, n'est testable en direct depuis
cette session. Ce constat ne dépend donc pas du choix du fournisseur —
il faudra de toute façon exécuter l'intégration réelle depuis un
environnement avec un accès réseau sortant normal (votre machine, un
serveur, une session avec une politique réseau différente) pour la
valider avec une vraie clé.

Ce qui reste à vérifier avec une clé, une fois un environnement réseau
disponible :
- Présence réelle de Bet365 (marché UK/EU, pas seulement AU) sur The Odds API.
- Nature exacte des champs "opening"/"last_seen" de TheStatsAPI (série
  temporelle interrogeable ou deux points fixes seulement).
- Couverture réelle et fraîcheur des cotes Ligue 1/Liga sur chaque
  fournisseur (la documentation l'affirme, un test réel le confirmerait).

## 8. Risques

- **Dépendance à un fournisseur unique** : tous les agrégateurs listés
  sont des sociétés tierces qui pourraient fermer, changer de prix, ou
  perdre l'accès à un bookmaker (précédent direct et récent : fermeture
  de l'API Pinnacle publique en juillet 2025). Une abstraction simple
  (un seul point d'entrée Python, remplaçable) limite ce risque sans
  complexité.
- **Bet365 potentiellement absent en direct** pour la ligne UK/EU chez
  la plupart des agrégateurs (Bet365 limite activement la
  redistribution de ses cotes) — un changement de bookmaker de référence
  serait alors une **décision produit**, jamais un contournement
  silencieux de `final_engine` (qui reste agnostique au nom du
  bookmaker, il attend juste "Over"/"Under" 2.5).
- **Coût récurrent** — même le moins cher (The Odds API, OddsPapi)
  implique un budget mensuel pour un usage quotidien multi-matchs.
- **Fiabilité du timestamp** — aucun fournisseur ne garantit
  contractuellement l'absence de révision rétroactive de son historique
  (réserve déjà documentée pour Football-Data, à reconduire à l'identique).

## 9. Recommandation principale

**TheStatsAPI**, pour trois raisons concrètes :
1. C'est le **seul** fournisseur qui annonce explicitement **Bet365 ET
   Pinnacle dans la même API** — exactement les deux bookmakers déjà
   utilisés par le projet (Bet365 primaire, Pinnacle secondaire depuis
   E9/E13/E16) — pas de changement de référence de prix à décider.
2. Prix fixe et simple ($50/mois, tout inclus dès le premier palier payant) —
   pas de comptabilité de crédits par requête/région comme The Odds API.
3. Endpoints dédiés historique + pré-match + live avec la même structure —
   intégration Python simple (REST/JSON standard).

**Réserve explicite** : la granularité exacte de son historique
("opening"/"last_seen") n'a pas pu être vérifiée en détail (accès
bloqué) — **à confirmer avec un compte avant intégration définitive**,
car si elle s'avère être seulement deux points fixes, elle ne suffira
pas à reconstruire un T-6h/T-1h précis.

## 10. Alternative de secours

**The Odds API**, si la vérification ci-dessus montre que TheStatsAPI ne
permet pas de requêter un instant `T` précis. Argument : son endpoint
historique est **contractuellement** un mécanisme "closest snapshot ≤ T"
— la garantie PIT la plus explicite et la mieux documentée trouvée dans
cette recherche, granularité 5-10 minutes, historique depuis 2020. Le
tier gratuit (500 crédits) suffit pour valider le mécanisme avant de
payer. Inconvénient : Bet365 UK/EU incertain — accepter Pinnacle (déjà
une référence légitime dans ce projet) comme bookmaker de repli si Bet365
s'avère indisponible.

## 11. Architecture cible proposée (sans toucher `final_engine`)

```text
Calendrier des matchs (Understat, déjà réutilisable — cf. audits précédents)
        ↓
Identification du match (competition + home_team + away_team + kickoff_utc,
        déjà le contrat exact de resolve_match_team_ids / build_match_train_dataframes)
        ↓
NOUVEAU : petit module data_engine/market_odds/<provider>_live_odds.py
   - un appel HTTP (clé API en variable d'environnement, jamais en dur)
   - normalise vers exactement deux floats : over_2_5, under_2_5
   - horodate l'observation (recorded_at)
        ↓
Contrôle PIT (déjà existant en principe : vérifier timestamp_cote < decision_time
   — même discipline que ambiguous_day_gate/incomplete_market_odds_gate, jamais
   un nouveau mécanisme PIT, juste un appel du même principe)
        ↓
predict_match.py (INCHANGÉ dans sa logique — le nouveau module remplace
   simplement la saisie manuelle des deux mêmes floats)
        ↓
Shadow Journal (INCHANGÉ)
        ↓
Settlement (déjà audité séparément — Understat)
        ↓
Évaluation (INCHANGÉE)
```

**Le moteur scientifique et son interface (`run_match_decision`) ne
changent pas d'un caractère** — seul un nouveau petit module de
récupération de données vient remplacer la saisie manuelle en amont de
R3, exactement comme `football_data_loader.py` le fait déjà pour
l'historique.

## 12. Ce qui peut être automatisé immédiatement

- Rien, **sans clé API** — chaque fournisseur sérieux exige une
  inscription (même gratuite). Ce n'est cependant qu'une formalité
  d'inscription, pas un développement.
- Une fois une clé obtenue (gratuite pour commencer, The Odds API ou
  OddsPapi) : la construction du petit module de normalisation
  (structure déjà connue, calquée sur `football_data_loader.py`) est
  immédiatement faisable.

## 13. Ce qui nécessite une API payante/clé

- Un usage quotidien multi-matchs dépassera rapidement les tiers
  gratuits (The Odds API : 500 crédits ; OddsPapi : 250 req/mois) — un
  plan payant ($29-50/mois selon le fournisseur retenu) sera nécessaire
  pour un usage soutenu, pas pour un test initial.

## 14. Ce qui nécessite encore une décision

- Choix définitif du fournisseur (TheStatsAPI vs The Odds API), après
  vérification directe de la granularité historique et de la présence
  réelle de Bet365/Pinnacle avec un compte réel.
- Acceptation ou non de Pinnacle comme bookmaker de référence si Bet365
  s'avère indisponible en direct — **décision produit, pas une
  modification scientifique** (le moteur ne code en dur aucun nom de
  bookmaker).
- Où exécuter l'intégration réelle, puisque cette session ne peut
  atteindre aucun fournisseur (section 7).

## 15. Proposition de prochaine étape technique

**Ne pas coder immédiatement.** Prochaine étape suggérée, dans l'ordre :
1. Créer un compte gratuit TheStatsAPI (ou The Odds API) **depuis un
   environnement avec accès réseau réel** (pas cette session).
2. Faire un seul appel manuel (`curl`/Postman) sur l'endpoint historique
   pour un match déjà joué de Premier League, et vérifier concrètement :
   présence de Bet365, granularité temporelle réelle, format du
   timestamp.
3. Seulement après cette vérification empirique : écrire le petit module
   de normalisation (quelques dizaines de lignes, calqué sur
   `football_data_loader.py`), avec ses tests, sans toucher à
   `predict_match.py` au-delà de brancher cette nouvelle source à la
   place de la saisie manuelle des deux mêmes deux floats.

---

*Audit réalisé par recherche web (aucune inspection primaire des APIs
n'a été possible, accès réseau bloqué pour tout domaine externe non
listé dans la politique d'egress de cette session — voir section 7).
Aucune clé API demandée ou utilisée. Aucune modification de code.
Aucune collecte Polymarket relancée.*
