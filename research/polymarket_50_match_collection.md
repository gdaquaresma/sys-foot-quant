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
| 80 | fait | 40 | 6 nouveaux (moneyline complet) + 2 partiels exclus — voir note |

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
`offset=80`, `startDate` légèrement antérieur) — retrouvé et ajouté au
batch `offset=80` (voir note ci-dessous).

**Note batch offset=80** : sur les 40 événements reçus, 6 événements
moneyline de base (3 marchés chacun, résolus) sont **nouveaux et complets** :
Araz Nakhchivan PFK vs Sabah Masazir (confirmant le match partiel repéré à
`offset=40`), LDU Quito vs Mushuc Runa SC, Delfin SC vs CD Tecnico
Universitario, FC Zurich vs Young Boys Bern, Academia Puerto Cabello vs
Academia Anzoategui FC, FK Kapaz vs Turan Tovuz. Le reste des 40 événements
correspond à des sous-marchés hors périmètre (Total Corners, Exact Score,
First to Score, Halftime/Second Half Result, More Markets) de ces mêmes
matchs. 2 matchs **partiels exclus** : Sariyer SK vs Pendikspor et Boluspor
vs Ankara Keciorengucu — seul le sous-événement "More Markets" (ids 932440
et 932439) est présent dans ce batch ; l'événement moneyline de base
n'apparaît pas — à rechercher dans un batch ultérieur si retrouvé.

## Étape 2 — Matchs sélectionnés pour le nouveau panel

| # | Match | Compétition | Date | Home | Away | Moneyline markets | conditionIds | Trades | Wallets | QC |
|---|---|---|---|---|---|---:|---|---:|---:|---|
| 1 | Umraniyespor vs. Muglaspor | Turkey 1. Lig | 2026-09-01 (closed 2026-09-01T19:57:01Z) | Umraniyespor | Muglaspor | 3 | Home: `0xa68b858c28cf504d65317f11e231b4f05eb6463b48ccb61f3736358128042171` (No/résolu Muglaspor) · Draw: `0xa615042b6fc5441994a410440c9a7dfb33c512e389e16e0362bea5db586faba3` (No) · Away: `0xf6e20281cd939527b805dee17bb56c7119538d91b6eef46a118e517b5e49fc1c` (Yes/résolu) | — | — | event id 941270, slug `tur2-umr-mug-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset40_2026-09-02.json` |
| 2 | Bandirmaspor vs. Antalyaspor | Turkey 1. Lig | 2026-09-01 (closed 2026-09-01T18:58:31Z) | Bandirmaspor | Antalyaspor | 3 | Home: `0x5523513b12613ac3679a8c9614a05ae01777bc3953eb89645fc4ab2db4641da4` (No) · Draw: `0x57835cc26913bdcb10fad9a3fa3746c8ee16c434bfa1d357425534aa732c0546` (No) · Away: `0xf44811114c5b720b342edbc8a97233e94aecdab709d9af95ccd16fcd2dd63535` (Yes/résolu Antalyaspor) | — | — | event id 941269, slug `tur2-bas-ant-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset40_2026-09-02.json` |
| 3 | Barranquilla FC vs. Boca Juniors de Cali | Primera B (Colombie) | 2026-09-01 (closed 2026-09-02T02:27:00Z) | Barranquilla FC | Boca Juniors de Cali | 3 | Home: `0x202f96daa4b4a6655de68efde4cb6d35c0a3c0862bb805fb37fe27070b1cf4fe` (Yes/résolu Barranquilla) · Draw: `0xd76abda59494ef5eb50f2a78a47de39bb05e5056a9bf44375fbb2379a9845e8f` (No) · Away: `0xa1a1c130398aeb3daa66e41d8baee155dc6ac4f842efc1d06802ffac6aade45b` (No) | — | — | event id 940469, slug `col2-bar-boc-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset40_2026-09-02.json` |
| 4 | Araz Nakhchivan PFK vs. Sabah Masazir | Azerbaijan Premier League | 2026-08-31 (closed 2026-08-31T17:56:03Z) | Araz Nakhchivan PFK | Sabah Masazir | 3 | Home: `0x10c900c8149a7d7eb0eecb78cb3e68007cafb675845d728acf039300b33cf617` (No) · Draw: `0xad13dda33216a5914a9e73588926fae244fcf85d0627a5d04f1688a50a9dca26` (No) · Away: `0x3d97b4548f70db388d0a61954d016100edd7d6b4f2b9c86ee6463a35c6d25b25` (Yes/résolu Sabah Masazir) | — | — | event id 938077, slug `aze1-pfk-sbh-2026-08-31` ; source `events_neutral_soccer_tagslug_closed_offset80_2026-09-02.json` |
| 5 | LDU Quito vs. Mushuc Runa SC | LigaPro Primera A (Équateur) | 2026-09-01 (closed 2026-09-02T09:05:00Z) | LDU Quito | Mushuc Runa SC | 3 | Home: `0xd07a02c25c95967fd674d17dfe78ffed9ef78ffacd810e742b38d4ea4c1315a8` (No) · Draw: `0xf318680f5c69faebe180c6083fde3872fcff503a387c1d66b4507f40fb3b0d59` (Yes/résolu — match nul) · Away: `0x82bfb867c4a7dae22e3126a71965309f611de3854c5d0f77af2fb2b552524a95` (No) | — | — | event id 933806, slug `ecu1-ldu-mur-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset80_2026-09-02.json` |
| 6 | Delfin SC vs. CD Tecnico Universitario | LigaPro Primera A (Équateur) | 2026-09-01 (closed 2026-09-02T03:30:01Z) | Delfin SC | CD Tecnico Universitario | 3 | Home: `0x9eb074e57f1fd53867fc62f0cc6757f0de0b9f1553999fd88e62544b951ccb2c` (Yes/résolu Delfin SC) · Draw: `0x4b94faf48f3003b9c08e5f751ca87f84754cc068bc96beeaf70f8e14d7262a26` (No) · Away: `0x2d784f9e0f28fb0a1ddfc06b2a8c7972aec109710cb42197a1d76af26c444f63` (No) | — | — | event id 933460, slug `ecu1-dsc-tec-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset80_2026-09-02.json` |
| 7 | FC Zurich vs. Young Boys Bern | Switzerland Super League | 2026-09-01 (closed 2026-09-01T22:32:03Z) | FC Zurich | Young Boys Bern | 3 | Home: `0xea2a5e688b8535ad955b31502d58b5739e4dbd3baa2d2481653625f4b409585c` (No) · Draw: `0x9995763edc5b2369070b458b2dc634d079ea69b0f219fe7dbb90b2528e412e2f` (No) · Away: `0xa488dfeb4d85773d15af7b17efaff9087250d834cc99869b659ef4f76f4c2cb0` (Yes/résolu Young Boys Bern) | — | — | event id 932786, slug `sui-fcz-yb-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset80_2026-09-02.json` |
| 8 | Academia Puerto Cabello vs. Academia Anzoategui FC | Primera División (Venezuela) | 2026-08-31 (closed 2026-09-01T05:27:31Z) | Academia Puerto Cabello | Academia Anzoategui FC | 3 | Home: `0x36c912c28e1459b9f4d909afa46c3599fe1cb41fc931ddc3af9ab6b2407d80d2` (Yes/résolu Academia Puerto Cabello) · Draw: `0x869a6f1b1ba8e37ae1f94403739484115df12c0dc9ff293e3feadcff3e2d0c54` (No) · Away: `0x51abae0d2be11d3394692c2a62a39cf022cf517bd6e9854dfcfc51f30c539b1f` (No) | — | — | event id 932750, slug `ven1-apc-aca-2026-08-31` ; source `events_neutral_soccer_tagslug_closed_offset80_2026-09-02.json` |
| 9 | FK Kapaz vs. Turan Tovuz | Azerbaijan Premier League | 2026-08-30 (closed 2026-08-30T18:04:51Z) | FK Kapaz | Turan Tovuz | 3 | Home: `0x699d24759291e009704ebdcab8c282792561bf80b1fe269250bbe29af7e81ca6` (Yes/résolu FK Kapaz) · Draw: `0x5f59bb51bca4ac076fe9b79230f9e1ed1ac271a879e714c6c7aa933ae451a213` (No) · Away: `0xeff8bf03a41991764bdbabbdef2e172060045e151f3bed8a878561a9cc62ebb5` (No) | — | — | event id 932457, slug `aze1-kap-tto-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset80_2026-09-02.json` |

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
