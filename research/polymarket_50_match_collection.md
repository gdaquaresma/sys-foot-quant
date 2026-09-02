# Collecte panel élargi — ~50 nouveaux matchs football (checkpoint à 25)

Suite du protocole validé (`research/polymarket_universe_collection_report.md`,
`research/polymarket_trader_depth_audit.md`, `research/polymarket_trader_signal_pilot.md`,
`research/polymarket_trader_skill_methodology.md`). Décision : **Option 2** —
collecter ~50 nouveaux matchs, checkpoint obligatoire à ~25.

**Règles rappelées (contraintes contraignantes pour toute cette collecte)** :
- Sélection des matchs **avant** tout examen des trades — jamais en fonction
  d'un wallet, d'un nombre de trades/wallets, ou d'un résultat.
- Les 7 matchs déjà collectés restent le "seed historique" ; ne pas les
  utiliser pour orienter le choix des nouveaux matchs (ni par résultat, ni
  par fréquence de wallets).
- Marchés moneyline uniquement (Home win / Draw / Away win) — pas
  d'Over/Under, Asian Handicap, props.
- Aucune analyse trader pendant la collecte (pas de classement, P&L, ROI,
  "smart money").
- Accès réseau direct bloqué pour cet agent — protocole manuel navigateur
  inchangé : URL fournie ici → utilisateur fetch → colle le JSON → agent
  sauvegarde + dédup (`transactionHash`) + QC.
- Payloads bruts dans `research/polymarket_raw_exports/` (gitignored).
- Provenance conservée pour chaque match : event id/slug, market id,
  conditionId, token IDs, outcomes, startTime, endDate, resolution, URL de
  fetch, date de collecte.

## Étape 1 — Découverte des événements (sélection neutre, avant tout trade)

Même endpoint et mêmes filtres neutres que pour le premier panel (sport +
statut + tri chronologique uniquement, aucun critère trader) :

```
https://gamma-api.polymarket.com/events?tag_slug=soccer&closed=true&limit=40&order=startDate&ascending=false&offset=<N>
```

Le premier panel (7 matchs) provenait de `offset=0` (40 événements les plus
récents au 2026-09-01, résolus, tag `soccer`). Pour obtenir des matchs
**différents**, on avance `offset` par pas de 40 (événements plus anciens,
même filtre neutre, aucune sélection sur les trades).

| Batch offset | Statut | Événements reçus | Matchs distincts identifiés |
|---|---|---|---|
| 40 | fait | 40 | 3 nouveaux (moneyline complet) — voir note |
| 80 | à faire | — | — |

**Note batch offset=40** : sur les 40 événements reçus, 37 se rattachent à
des matchs déjà connus — soit les 5 événements moneyline eux-mêmes déjà
collectés à `offset=0` (FK Liepaja vs Riga FC, Sumqayit FK vs Qarabag FK,
FC Gagra vs FC Iberia 1999, FC Torpedo Kutaisi vs FC Meshakhte Tkibuli, FC
Dinamo Tbilisi vs FC Dila Gori), soit leurs sous-événements non-moneyline
("More Markets", "Exact Score", "First Team to Score", "Halftime/Second
Half Result", "Total Corners" — hors périmètre §Règles). Ceci confirme le
chevauchement de pagination déjà documenté (le tri par `startDate`
descendant se décale au fil du temps). 3 matchs moneyline **réellement
nouveaux** identifiés (conditionIds complets, résolus) : Umraniyespor vs
Muglaspor, Bandirmaspor vs Antalyaspor, Barranquilla FC vs Boca Juniors de
Cali. 1 match **partiel exclu** : Araz Nakhchivan PFK vs Sabah Masazir —
seul le sous-événement "More Markets" (id 938200) est présent dans ce
batch ; l'événement moneyline de base n'apparaît pas encore (probablement
`offset=80`, `startDate` légèrement antérieur) — à ajouter dans un batch
ultérieur si retrouvé.

## Étape 2 — Matchs sélectionnés pour le nouveau panel

| # | Match | Compétition | Date | Home | Away | Moneyline markets | conditionIds | Trades | Wallets | QC |
|---|---|---|---|---|---|---:|---|---:|---:|---|
| 1 | Umraniyespor vs. Muglaspor | Turkey 1. Lig | 2026-09-01 (closed 2026-09-01T19:57:01Z) | Umraniyespor | Muglaspor | 3 | Home: `0xa68b858c28cf504d65317f11e231b4f05eb6463b48ccb61f3736358128042171` (No/résolu Muglaspor) · Draw: `0xa615042b6fc5441994a410440c9a7dfb33c512e389e16e0362bea5db586faba3` (No) · Away: `0xf6e20281cd939527b805dee17bb56c7119538d91b6eef46a118e517b5e49fc1c` (Yes/résolu) | — | — | event id 941270, slug `tur2-umr-mug-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset40_2026-09-02.json` |
| 2 | Bandirmaspor vs. Antalyaspor | Turkey 1. Lig | 2026-09-01 (closed 2026-09-01T18:58:31Z) | Bandirmaspor | Antalyaspor | 3 | Home: `0x5523513b12613ac3679a8c9614a05ae01777bc3953eb89645fc4ab2db4641da4` (No) · Draw: `0x57835cc26913bdcb10fad9a3fa3746c8ee16c434bfa1d357425534aa732c0546` (No) · Away: `0xf44811114c5b720b342edbc8a97233e94aecdab709d9af95ccd16fcd2dd63535` (Yes/résolu Antalyaspor) | — | — | event id 941269, slug `tur2-bas-ant-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset40_2026-09-02.json` |
| 3 | Barranquilla FC vs. Boca Juniors de Cali | Primera B (Colombie) | 2026-09-01 (closed 2026-09-02T02:27:00Z) | Barranquilla FC | Boca Juniors de Cali | 3 | Home: `0x202f96daa4b4a6655de68efde4cb6d35c0a3c0862bb805fb37fe27070b1cf4fe` (Yes/résolu Barranquilla) · Draw: `0xd76abda59494ef5eb50f2a78a47de39bb05e5056a9bf44375fbb2379a9845e8f` (No) · Away: `0xa1a1c130398aeb3daa66e41d8baee155dc6ac4f842efc1d06802ffac6aade45b` (No) | — | — | event id 940469, slug `col2-bar-boc-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset40_2026-09-02.json` |

*(rempli au fur et à mesure — checkpoint obligatoire après ~25 matchs ;
colonnes Trades/Wallets à compléter lors de la collecte des trades par
marché, étape suivante)*

## Étape 3 — Journal de collecte détaillé (QC par marché)

Voir `research/polymarket_raw_exports/COLLECTION_LOG.md` (fichiers numérotés
en continuité avec la collecte des 7 matchs initiaux, à partir du Fichier 31).

## Checkpoint à ~25 matchs — à calculer, PAS de test de skill

- nombre de matchs, marchés, trades, wallets ;
- wallet × match PIT ;
- wallets ≥2 matchs historiques, ≥3, ≥5 ;
- nombre de traders récurrents actifs ;
- notionnel des positions PIT ;
- distribution des trades par observation ;
- comparaison avec les 7 matchs initiaux.

**STOP obligatoire à ce stade. Pas de classement, pas de P&L, pas de test de
compétence. Décision de continuer jusqu'à ~50 prise avec l'utilisateur après
le checkpoint.**
