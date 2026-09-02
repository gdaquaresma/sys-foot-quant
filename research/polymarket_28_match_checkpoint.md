# Checkpoint méthodologique — univers à 28 matchs (STOP obligatoire)

Document décisionnel court, construit exclusivement à partir des données déjà
collectées (`research/polymarket_50_match_collection.md` Étape 2, événements
bruts dans `research/polymarket_raw_exports/`, et l'audit de profondeur /
méthodologie déjà validés sur le panel seed). **Aucun nouveau fetch réseau,
aucune nouvelle pagination, aucun classement de traders, aucune sélection sur
résultat.**

## 1. Composition de l'univers (28 matchs)

| Compétition | Matchs | % |
|---|---:|---:|
| Primera División (Venezuela) | 7 | 25 % |
| Turkey 1. Lig | 4 | 14 % |
| Azerbaijan Premier League | 3 | 11 % |
| LigaPro Primera A (Équateur) | 2 | 7 % |
| USL League One (USA) | 2 | 7 % |
| Betri deildin (Îles Féroé) | 2 | 7 % |
| Netherlands Eerste Divisie (réserves "Jong") | 2 | 7 % |
| Primera B (Colombie), Switzerland Super League, Erovnuli Liga (Géorgie), UAE Pro League, China FA Cup, Club Friendlies (Espagne) | 1 chacun | 21 % |

**13 compétitions distinctes, mais concentration marquée** : 3 ligues
(Venezuela, Turquie, Azerbaïdjan) totalisent 14/28 matchs (50 %). Fenêtre
temporelle très courte — **4 jours calendaires** (2026-08-29 → 2026-09-01),
même limite structurelle déjà signalée dans l'audit de profondeur du panel
seed (§8.5) : impossible de distinguer "récurrence persistante" d'un simple
"pic d'activité sur un week-end".

**Chevauchement avec le panel seed (7 matchs déjà audités)** : seulement
4/28 matchs (14 %) appartiennent à une ligue déjà présente dans le seed
(Azerbaijan Premier League : 3 matchs ; Erovnuli Liga Géorgie : 1 match) — un
terrain où une base de wallets "spécialistes ligue" pourrait plausiblement
recouper le seed. **Les 24 autres (86 %) sont dans des ligues jamais
observées avant** (Venezuela, Turquie, Équateur, Colombie, Suisse, USA, Îles
Féroé, Pays-Bas réserves, UAE, Espagne friendlies) — zéro donnée wallet
préalable pour ces marchés.

**Signal structurel positif à noter** : contrairement au seed (au plus 3
matchs regroupés dans une même ligue/fenêtre — Géorgie), le nouveau panel
regroupe 7 matchs Venezuela et 4 matchs Turquie sur le même week-end de
championnat — configuration plus favorable *a priori* à une récurrence
intra-panel (un wallet actif sur le championnat vénézuélien a mécaniquement
plus d'occasions de retrader) que la dispersion du seed. Ceci reste une
hypothèse structurelle, non vérifiée par des trades réels (section 2).

**Proxy de liquidité (champ `volume` des événements déjà collectés, pas de
nouveau fetch)** :

| | Seed (7 matchs) | Nouveaux (28 matchs) |
|---|---:|---:|
| Volume total | 286 554 $ | 643 393 $ |
| Volume médian / match | 16 621 $ | 3 902 $ |
| Min / Max | 549 $ / 151 244 $ | 0 $ / 207 013 $ |

Le volume total est plus élevé (4× plus de matchs), mais le **volume médian
par match est ~4× plus faible** dans le nouveau panel. C'est un signal de
prudence, pas une preuve : le volume total n'est pas le wallet count, et
aucune causalité volume→profondeur n'a été établie ici — mentionné à titre
indicatif seulement.

## 2. Profondeur disponible

**Limite centrale à énoncer explicitement : aucun trade n'a été collecté
pour 21 des 28 matchs** (seuls les 7 matchs du seed ont des trades PIT
collectés et audités — colonnes Trades/Wallets de l'Étape 2 encore à `—`
pour les lignes 8-28). Il n'existe donc **aucune mesure réelle de profondeur
wallet × match pour l'univers à 28 matchs** — seulement pour le seed. Les
chiffres ci-dessous sont ceux déjà produits dans
`research/polymarket_trader_skill_methodology.md` (§3) et
`research/polymarket_trader_depth_audit.md`, seule base empirique existante :

| Métrique (seed, 7 matchs / 21 marchés, 1 672 trades) | Valeur |
|---|---:|
| Wallets distincts (toute activité) | 529 |
| Wallets avec exposition PIT sur 1 seul match | 295 / 333 (89 %) |
| Wallets avec exposition PIT sur ≥ 2 matchs | 38 |
| Wallets avec exposition PIT sur ≥ 3 matchs | 10 |
| Wallets avec exposition PIT sur ≥ 5 matchs | 5 (max observable = 7) |
| Wallets ≥ 3 matchs **et** notionnel non symbolique (par match, dernier match) | 2 (`0x9e3ed7b6…`, `0xe9076a87…` = `suntori`) |
| Observations wallet × match avec notionnel < 5 $ | 112 / 394 (28,4 %) |
| Observations wallet × match à 1 seul trade | 299 / 394 (75,9 %) |

Extrapoler ces chiffres au panel à 28 matchs serait exactement le type de
raisonnement interdit par les contraintes de ce checkpoint (présenter une
corrélation/extrapolation comme une preuve). **Le seul constat honnête est :
la profondeur du panel à 28 matchs est aujourd'hui inconnue**, faute de
données de trades pour 75 % du panel.

## 3. Comparaison avec `polymarket_trader_skill_methodology.md`

Ce document a **déjà pré-enregistré** (§7, avant de voir les 50 matchs) la
règle de décision suivante : *reproduire l'audit de profondeur une fois les
~50 matchs collectés ; si la population de wallets ≥3-matchs-historiques
et notionnel non symbolique reste de l'ordre de quelques unités (2-7 selon
le match, comme sur le seed), basculer vers l'Option 4 (abandon du signal
trader)*.

Deux faits s'imposent :

1. **Nous sommes à 28/50 (56 %)**, pas à 50 — le point de contrôle
   pré-enregistré n'est pas encore atteint.
2. **L'audit de profondeur n'a pas été reproduit** sur le nouveau panel
   (aucun trade collecté) — la condition posée par la règle elle-même
   (« une fois l'audit reproduit ») n'est pas remplie.

Trancher A ou C maintenant reviendrait à statuer sans les données que la
méthodologie a explicitement prévu de collecter avant de trancher — le type
de décision biaisée a posteriori que le §7 du document cherchait à éviter.

## 4. Décision

### **Option B — profondeur non mesurée mais composition prometteuse : continuer la collecte jusqu'à ~50 matchs avant de reproduire l'audit de profondeur.**

Justification quantitative :

- **Pas Option A** : aucune donnée de trades n'existe pour 21/28 matchs
  (75 %) ; affirmer que "la profondeur est suffisante" sans une seule mesure
  de wallet × match sur le nouveau panel n'est pas défendable.
- **Pas Option C** : la seule mesure de profondeur disponible (seed, 7
  matchs) avait déjà conclu "insuffisant mais prometteur, élargir à 50"
  (`polymarket_trader_depth_audit.md` §9) — rien dans les données
  actuellement disponibles (composition, volume) ne contredit ni ne
  confirme cette hypothèse pour le nouveau panel ; le proxy volume est même
  un signal de prudence (médiane 4× plus faible), pas un signal d'abandon.
  Abandonner sur cette seule base violerait la contrainte « ne pas présenter
  une corrélation exploratoire comme une preuve ».
- **Option B est la seule cohérente avec le protocole déjà pré-enregistré** :
  atteindre ~50 matchs, puis reproduire l'audit de profondeur (sections 2-6
  de `polymarket_trader_depth_audit.md`) sur l'ensemble du panel avant toute
  décision A/C.

**Action concrète recommandée** : reprendre la pagination (offset=240+)
pour compléter le panel jusqu'à ~50 matchs — **hors périmètre de ce
document**, à faire dans une prochaine tâche. Une fois 50 matchs atteints,
prioriser la collecte de trades sur les clusters intra-ligue les plus denses
identifiés en section 1 (Venezuela ×7+, Turquie ×4+) pour maximiser la
chance de détecter une récurrence intra-panel avant de conclure.

---
*Aucune donnée nouvelle collectée pour ce document. Sources : Étape 2 de
`research/polymarket_50_match_collection.md`, champs `volume` des payloads
déjà commités/gitignorés dans `research/polymarket_raw_exports/`,
`research/polymarket_trader_depth_audit.md`,
`research/polymarket_trader_skill_methodology.md`.*
