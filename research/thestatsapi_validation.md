# Validation technique réelle de TheStatsAPI — avant toute implémentation

**Nature de ce document.** Validation/audit uniquement. Aucun code de
production modifié, aucun connecteur créé, `final_engine/` et la
méthodologie scientifique (E7/E8, gates, `min_edge_threshold=None`, règles
PIT) intégralement inchangés. Aucune clé API demandée, affichée ou
utilisée — aucune clé n'était présente dans l'environnement (vérifié).

## 1. Date du test
2026-09-13.

## 2. Environnement
Session Claude Code (sandbox distant), egress réseau soumis à une
politique de liste blanche stricte déjà caractérisée lors des audits
précédents (`research/odds_provider_automation_audit.md` §7) : seuls
quelques domaines d'infrastructure de développement (GitHub API, PyPI,
npm, API Anthropic) sont joignables. Aucune clé API TheStatsAPI ou The
Odds API n'était présente dans les variables d'environnement (vérifié
explicitement, `env | grep -i odds`).

## 3. Connectivité — test réel effectué maintenant

Deux mécanismes indépendants testés (curl via le proxy local de la
session, WebFetch via l'infrastructure Anthropic), sur les domaines
officiels :

| Domaine | curl | WebFetch |
|---|---|---|
| `www.thestatsapi.com` | 403 `CONNECT tunnel failed` (`connect_rejected`, politique d'organisation) | `EGRESS_BLOCKED` |
| `api.thestatsapi.com` | 403 idem | non re-testé séparément (même politique) |
| `www.thestatsapi.com/odds-api/historical-football-odds` | 403 idem | `EGRESS_BLOCKED` |
| `the-odds-api.com` | 403 idem | `EGRESS_BLOCKED` |
| `api.the-odds-api.com` | 403 idem | non re-testé séparément |

**`TEST IMPOSSIBLE DEPUIS CET ENVIRONNEMENT`** — pour les deux
fournisseurs, sans exception. Ce n'est pas une évaluation négative de
TheStatsAPI : le même blocage identique touche des domaines de contrôle
neutres (`example.com`, `en.wikipedia.org`, déjà testés lors de l'audit
précédent) et ne touche pas un domaine explicitement autorisé
(`api.github.com`, 200 OK) — c'est une politique d'egress par défaut-deny
de cette session précise, pas un jugement sur la qualité ou la fiabilité
du fournisseur.

**Ce qui doit être testé depuis un environnement réseau réel** (votre
machine, un serveur, ou une session avec une politique réseau
différente) : un compte TheStatsAPI (essai 7 jours gratuit, selon l'audit
précédent) puis un appel `curl` direct sur l'endpoint historique pour le
match choisi en section 4.

## 4. Match historique utilisé (choisi, pas testé)

**Chelsea vs Arsenal, Premier League 2024/25, kickoff `2024-11-10
16:30:00 UTC`** (identifiant Understat interne `26705`, résultat réel
1-1, déjà présent dans notre corpus `research/xg_feasibility/runs/
epl_2024_datesData.json`). Match choisi pour sa facilité d'identification
(grand club, date précise déjà connue et vérifiable indépendamment) —
recommandé comme cas de test pour la vérification manuelle à faire depuis
un environnement avec accès réseau.

## 5. Endpoint(s) visé(s)
`GET https://www.thestatsapi.com/odds-api/historical-football-odds` (et
son équivalent d'API REST documenté, chemin exact non confirmable sans
compte) — non atteint, voir §3.

## 6. Réponse réelle obtenue
**Aucune** — `TEST IMPOSSIBLE DEPUIS CET ENVIRONNEMENT`. Aucune donnée
n'a été fabriquée ou supposée pour compenser cette impossibilité.

## 7. Bet365
**NON VÉRIFIÉ.** DOCUMENTÉ uniquement (page produit TheStatsAPI annonçant
« Bet365, Pinnacle, Paddy Power, Betfair Sportsbook & Kambi odds » —
`research/odds_provider_automation_audit.md` §3) — jamais observé dans une
réponse réelle.

## 8. Pinnacle
**NON VÉRIFIÉ.** Même statut que Bet365 — DOCUMENTÉ, jamais PROUVÉ.

## 9. Over/Under 2.5
**NON VÉRIFIÉ.** La page produit dédiée « Football Odds API » mentionne
1X2/O-U/BTTS/handicap parmi les marchés — DOCUMENTÉ uniquement.

## 10. Timestamps
**NON VÉRIFIÉ.** Aucune réponse réelle disponible pour inspecter le
format exact du timestamp (Unix, ISO8601, avec ou sans fuseau explicite —
un point pourtant critique pour notre règle PIT, cf. le garde-fou déjà
existant dans `polymarket/trades.py::_parse_timestamp` qui refuse tout
timestamp sans fuseau explicite : la même discipline devra être appliquée
à tout connecteur TheStatsAPI).

## 11. Historique
**NON VÉRIFIÉ.** La documentation publique mentionne des champs
« opening » et « last_seen » (`research/odds_provider_automation_audit.md`
§4) — cela suggère **Niveau A** (deux points fixes) plutôt que **Niveau
B** (série temporelle multi-observations), mais ceci reste une lecture de
documentation, pas une observation d'une réponse réelle. **Ne pas
transformer cette lecture en certitude.**

## 12. Granularité
**NON VÉRIFIÉ / INCONNU.** Impossible de produire le tableau
T-24h/T-12h/T-6h/T-1h/T-30min/T-5min demandé — aucune donnée réelle
disponible. C'est précisément le test à faire en priorité depuis un
environnement réseau réel, car c'est le point qui déterminerait à lui
seul si TheStatsAPI satisfait notre besoin PIT (Niveau C/D) ou seulement
un besoin plus faible (Niveau A/B).

## 13. Reconstruction PIT
**NON VÉRIFIÉ.** La question posée par l'énoncé (« si notre décision
avait été prise 1h avant le kickoff, quelle cote aurait été disponible
selon TheStatsAPI ? ») ne peut pas recevoir de réponse empirique ici.
Elle reste ouverte tant que §11/§12 ne sont pas vérifiés avec une vraie
réponse API.

## 14. Identification automatique du match
**NON VÉRIFIÉ (documentation uniquement).** La documentation publique
(page « Football API for Developers ») mentionne des identifiants de
match/fixture au sein d'une structure REST classique (compétitions →
équipes → matchs), ce qui suggère une identification automatique
possible à partir de `competition`/`home_team`/`away_team`/`kickoff` —
mais aucun champ exact (`fixture_id`, `event_id`...) n'a pu être observé
dans une réponse réelle. **Méthode attendue mais non confirmée : chercher
le fixture par compétition+date, obtenir un ID interne, puis interroger
l'endpoint odds avec cet ID** — schéma à confirmer avec un compte réel.

## 15. Tableau des exigences

| Besoin | TheStatsAPI | Vérifié réellement ? | Commentaire |
|---|---|---|---|
| Identifier le match | Probable (structure REST classique) | **NON — documentation seulement** | Nécessite un test avec compte réel |
| Bet365 | Annoncé | **NON — documentation seulement** | — |
| Pinnacle | Annoncé | **NON — documentation seulement** | — |
| Over 2.5 | Annoncé | **NON — documentation seulement** | — |
| Under 2.5 | Annoncé | **NON — documentation seulement** | — |
| Timestamp | Annoncé (implicite) | **NON** | Format/fuseau horaire à confirmer impérativement (risque PIT si fuseau absent) |
| Historique | Annoncé | **NON** | Champs "opening"/"last_seen" suggèrent Niveau A, à confirmer |
| Plusieurs snapshots | Incertain | **NON** | Point le plus critique, non tranché |
| PIT (timestamp < kickoff exploitable) | Incertain | **NON** | Dépend entièrement de §11/§12 |
| T-1h reconstructible | Incertain | **NON** | — |
| T-30min reconstructible | Incertain | **NON** | — |
| T-5min reconstructible | Incertain | **NON** | — |

## 16. Problèmes éventuels
- **Blocage réseau total de cette session** (déjà documenté, confirmé de
  nouveau ici) — aucun contournement tenté, conformément à la consigne.
- **Risque de sur-confiance dans la documentation** : les pages produit
  de TheStatsAPI sont des pages marketing, pas une spécification
  d'API formelle avec schéma JSON exhaustif — le champ exact retourné
  par l'endpoint historique (et sa granularité réelle) reste une
  inconnue tant qu'aucun appel réel n'a été fait.
- Aucun problème de méthodologie ou de PIT introduit par ce document
  lui-même — aucune donnée n'a été utilisée pour une prédiction,
  aucun code modifié.

## 17. Comparaison rapide — The Odds API (contrôle secondaire)
Identiquement bloqué (§3). Rappel de ce qui reste **DOCUMENTÉ** (déjà établi
dans l'audit précédent, non re-vérifié ici) :
- Endpoint historique avec paramètre `date` (ISO8601) → renvoie le
  snapshot le plus récent ≤ cette date — mécanisme **contractuel**, donc
  a priori plus proche du Niveau D que ce que suggère la documentation
  TheStatsAPI, mais toujours **NON VÉRIFIÉ** par un appel réel.
- Snapshots documentés toutes les 10 min (depuis 06/2020) puis 5 min
  (depuis 09/2022).
- Bet365 confirmé présent dans la documentation seulement pour la
  version « AU » (Australie) dans les extraits trouvés — **présence
  Bet365 UK/EU non confirmée**, ni documentée avec certitude, ni testée.
- Pinnacle documenté comme présent.

**Aucune nouvelle conclusion** par rapport à l'audit précédent — ce
contrôle confirme seulement que le blocage réseau touche les deux
fournisseurs de façon identique, donc que le choix entre eux ne peut pas
être tranché empiriquement depuis cette session.

## 18. Recommandation finale
**Ne pas coder de connecteur avant qu'au moins une des deux vérifications
suivantes ait été faite depuis un environnement avec accès réseau réel :**
1. Un appel réel à l'endpoint historique TheStatsAPI pour le match de la
   section 4, avec inspection du nombre réel d'observations temporelles
   et de leur format de timestamp.
2. À défaut, le même test sur The Odds API (paramètre `date`), qui a une
   probabilité a priori plus élevée de satisfaire le Niveau C/D compte
   tenu de son contrat d'API documenté plus explicite — mais avec le
   risque connu de l'absence de Bet365 UK/EU (Pinnacle resterait alors
   le bookmaker de repli, déjà légitime dans ce projet depuis E9/E13/E16).

---

*Aucune clé API n'a été demandée, affichée ou utilisée pour produire ce
document. Aucun fichier de production modifié. Aucune collecte
Polymarket relancée.*
