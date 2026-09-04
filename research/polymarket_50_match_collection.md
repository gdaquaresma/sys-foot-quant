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
| 120 | fait | 40 | 6 nouveaux (moneyline complet) + 2 partiels exclus — voir note |
| 160 | fait | 40 | 6 nouveaux (moneyline complet) + 2 partiels exclus — voir note |
| 200 | fait | 40 | 7 nouveaux (moneyline complet) + 1 partiel exclu — voir note |
| 240 | fait | 40 | 0 nouveau — chevauchement complet, voir note |
| 280 | fait | 40 | 1 nouveau (moneyline complet) — voir note |
| 320 | fait | 40 | 5 nouveaux (moneyline complet) + 2 partiels exclus — voir note |

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

**Note batch offset=120** : sur les 40 événements reçus, 6 événements
moneyline de base (3 marchés chacun, résolus) sont **nouveaux et complets** :
Boluspor vs Ankara Keciorengucu et Sariyer SK vs Pendikspor (les deux
matchs partiels repérés à `offset=80` — l'événement moneyline de base
apparaît bien dans ce batch, confirmant le décalage de pagination déjà
documenté), Trujillanos FC vs Monagas SC, UCV FC vs Deportivo Rayo Zuliano,
FC Dinamo Batumi vs FC Spaeri, Union Omaha SC vs New York Cosmos. Le reste
des 40 événements correspond à des sous-marchés hors périmètre (More
Markets, Exact Score, First to Score, Halftime/Second Half Result) de ces
mêmes matchs, plus 2 matchs **partiels exclus** dans ce batch : Hatta SC vs
Sharjah FC (UAE Pro League, ids 930955/930956/930957/930958/930959 — seuls
les sous-événements sont présents) et Shandong Taishan FC vs Shanghai Port
FC (China FA Cup, id 930991 "More Markets" seul présent) — l'événement
moneyline de base n'apparaît pas pour ces deux matchs dans ce batch ; à
rechercher dans un batch ultérieur si retrouvé. Aucun doublon avec les 9
matchs déjà présents dans le tableau Étape 2 (vérifié par event id/slug et
noms d'équipes, pas par position de pagination).

**Note batch offset=160** : sur les 40 événements reçus, 6 événements
moneyline de base (3 marchés chacun, résolus) sont **nouveaux et complets** :
Hatta SC vs Sharjah FC (UAE Pro League — confirmant le premier match partiel
repéré à `offset=120`), Shandong Taishan FC vs Shanghai Port FC (China FA
Cup — confirmant le second match partiel repéré à `offset=120`), KI
Klaksvik vs Eb/Streymur (Betri deildin, Îles Féroé), Skala IF vs 07 Vestur
Sorvagur (Betri deildin, Îles Féroé), Westchester SC vs Spokane Velocity FC
(USL League One), Deportivo Maritimo vs CD Cieza (Club Friendlies,
Espagne). Le reste des 40 événements correspond à des sous-marchés hors
périmètre (More Markets, Exact Score, First to Score, Halftime/Second Half
Result, Total Corners) de ces mêmes matchs, plus 2 matchs **partiels
exclus** dans ce batch : Vólos NPS vs PS Kalamáta (event parent id 925706
absent de ce batch — seul le sous-événement "More Markets" id 929442 est
présent) et Zira FK vs Neftchi Baku PFC (event parent id 928727 absent de
ce batch — seuls 6 sous-événements sont présents : ids 928807 More Markets,
928774 Total Corners, 928730 Exact Score, 928731 First to Score, 928729
Second Half Result, 928728 Halftime Result) — à rechercher dans un batch
ultérieur si retrouvé. Aucun doublon avec les 15 matchs déjà présents dans
le tableau Étape 2 (vérifié par event id/slug et noms d'équipes, pas par
position de pagination).

**Note batch offset=200** : sur les 40 événements reçus, 7 événements
moneyline de base (3 marchés chacun, résolus) sont **nouveaux et complets** :
Zira FK vs Neftchi Baku PFC (Azerbaijan Premier League — confirme le match
partiel repéré à `offset=160`, l'événement moneyline de base id 928727
apparaît bien dans ce batch), Deportivo Tachira vs Caracas FC, Portuguesa FC
vs Metropolitanos FC, Carabobo FC vs Zamora FC, Deportivo La Guaira vs
Estudiantes de Merida (les 4 précédents en Primera División, Venezuela),
Jong AZ Alkmaar vs Jong FC Utrecht, Jong PSV Eindhoven vs Jong Ajax
Amsterdam (Netherlands Eerste Divisie, équipes réserve "Jong"). Le reste des
40 événements correspond à des sous-marchés hors périmètre (More Markets,
Exact Score, First to Score, Halftime/Second Half Result) de ces mêmes
matchs. 1 match **partiel exclu** dans ce batch : Al Duhail SC vs Al Arabi
Doha SC (event parent id 927173 absent de ce batch — seuls 3
sous-événements sont présents : ids 927535 More Markets, 927176 Exact
Score, 927177 First Team to Score) — à rechercher dans un batch ultérieur si
retrouvé. Le match partiel Vólos NPS vs PS Kalamáta (repéré à `offset=160`,
event parent id 925706) n'apparaît toujours pas dans ce batch — reste en
attente pour un batch ultérieur. Aucun doublon avec les 21 matchs déjà
présents dans le tableau Étape 2 (vérifié par event id/slug et noms
d'équipes, pas par position de pagination).

**Note batch offset=240** : sur les 40 événements reçus, **0 événement
moneyline de base nouveau**. Les 6 événements moneyline dont l'id apparaît
dans ce batch (933806 LDU Quito vs. Mushuc Runa SC, 933460 Delfin SC vs. CD
Tecnico Universitario, 932786 FC Zurich vs. Young Boys Bern, 932750
Academia Puerto Cabello vs. Academia Anzoategui FC, 932457 FK Kapaz vs.
Turan Tovuz, 932006 Boluspor vs. Ankara Keciorengucu) correspondent tous à
des matchs **déjà présents** dans le tableau Étape 2 (lignes 5-10). Les 40
événements du batch sont exclusivement des sous-événements hors périmètre
(More Markets, Exact Score, First Team to Score, Halftime/Second Half
Result, Total Corners) de ces mêmes 6 matchs plus Sariyer SK vs. Pendikspor
(ligne 11, event parent id 932003 — absent de ce batch mais déjà tracké).
Chevauchement total attendu : ces matchs ont accumulé des arbres de
sous-marchés plus profonds (ex. Delfin SC et Academia Puerto Cabello ont
chacun un "More Markets" à 33 sous-marchés, FC Zurich et FK Kapaz ont
gagné un marché "Total Corners"), ce qui ralentit l'avancée de la
pagination en termes de matchs distincts couverts par tranche de 40
événements. Source : `events_neutral_soccer_tagslug_closed_offset240_2026-09-03.json`.
Aucune modification du tableau Étape 2 pour ce batch — poursuite prévue à
`offset=280`.

**Note batch offset=280** : sur les 40 événements reçus, **7 événements
moneyline de base** identifiés (id sans `parentEventId`, 3 marchés tous
`sportsMarketType: "moneyline"`) : 932003 Sariyer SK vs. Pendikspor, 931998
Trujillanos FC vs. Monagas SC, 931812 PFC Slavia Sofia vs. PFC Levski
Sofia, 931189 UCV FC vs. Deportivo Rayo Zuliano, 931183 FC Dinamo Batumi
vs. FC Spaeri, 930986 Union Omaha SC vs. New York Cosmos, 930955 Hatta SC
vs. Sharjah FC. Six de ces sept correspondent à des matchs **déjà
présents** dans le tableau Étape 2 (lignes 11 à 16) ; leur réapparition
dans ce batch reflète le même phénomène de chevauchement que celui déjà
documenté pour `offset=240` (arbres de sous-marchés plus profonds
ralentissant la progression de la pagination en matchs distincts).
**Un seul match nouveau** : PFC Slavia Sofia vs. PFC Levski Sofia
(Bulgaria Parva Liga, event id 931812, slug `bul-sla-lev-2026-09-02`),
ajouté au tableau Étape 2 en ligne 29. Aucun doublon avec les 28 matchs
déjà présents (vérifié par event id/slug et noms d'équipes). Source :
`events_neutral_soccer_tagslug_closed_offset280_2026-09-03.json`.
Poursuite prévue à `offset=320`.

**Note batch offset=320** : sur les 40 événements reçus, **5 événements
moneyline de base** identifiés (id sans `parentEventId`, 3 marchés tous
`sportsMarketType: "moneyline"`) : 937608 Fatih Karagumruk Istanbul vs.
Kayserispor (Turkey 1. Lig), 937595 St. Truidense VV vs. Union
Saint-Gilloise (Belgium Pro League), 937472 RKS Rakow Czestochowa vs.
Gornik Zabrze (Poland Ekstraklasa), 937118 FC Thun vs. Lausanne-Sport
(Switzerland Super League), 937119 Grasshopper Club Zurich vs. FC St.
Gallen 1879 (Switzerland Super League). Aucun doublon avec les 29 matchs
déjà présents (vérifié par event id/slug et noms d'équipes) ; les 5 ont
été ajoutés au tableau Étape 2 en lignes 30 à 34. **Deux candidats
qatariens exclus** : Al Ahli Doha SC vs. Qatar SC (id 937090) et
Al-Sailiya SC vs. Al Arabi Doha SC (id 937091), Qatar Stars League —
seuls leurs sous-marchés (`-more-markets`, `-exact-score`,
`-first-to-score`, `-second-half-result`, `-halftime-result`,
référençant `parentEventId: 937090`/`937091`) sont présents dans ce
batch ; l'événement de base moneyline lui-même est absent du payload.
Conformément à la règle d'intégrité des données, ces deux matchs ne sont
**pas** ajoutés au tableau (aucune donnée fabriquée) ; à récupérer si un
futur batch de pagination expose l'événement de base. Source :
`events_neutral_soccer_tagslug_closed_offset320_2026-09-04.json`.
Poursuite prévue à `offset=360`.

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
| 10 | Boluspor vs. Ankara Keciorengucu | Turkey 1. Lig | 2026-09-01 (closed 2026-09-01T22:54:19Z) | Boluspor | Ankara Keciorengucu | 3 | Home: `0xf0f0f2508bfabd0968cd7bad57b31b4938a64987732b1dc9407349583820e043` (No) · Draw: `0x19b49db85743266b4daaf8c1c84e8dbc595e82674f16e93cf40645e0020388e3` (No) · Away: `0xa2b004bac99f84ff51d5c3e1637a89d3913193f385a3ec8758686aca8bf73f92` (Yes/résolu Ankara Keciorengucu) | — | — | event id 932006, slug `tur2-bol-kec-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset120_2026-09-02.json` |
| 11 | Sariyer SK vs. Pendikspor | Turkey 1. Lig | 2026-09-01 (closed 2026-09-01T22:58:01Z) | Sariyer SK | Pendikspor | 3 | Home: `0x62d35c534853efe82634850e2c6890a7ee61a51cfc8b8794062dde3b6d547406` (Yes/résolu Sariyer SK) · Draw: `0xfcce7fc1f7b2dcec99eb323a1d81a49daa6f8612c456f3e69aa06b9285d0465d` (No) · Away: `0x7aa0c9b96cc31cb7fdf2e1766c0d58d11d8fe153afda5c8edfd9ca37a9c17c28` (No) | — | — | event id 932003, slug `tur2-sar-pen-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset120_2026-09-02.json` |
| 12 | Trujillanos FC vs. Monagas SC | Primera División (Venezuela) | 2026-08-30 (closed 2026-08-31T07:45:28Z) | Trujillanos FC | Monagas SC | 3 | Home: `0x80e347db54693af0159a351fee831e0dcdb40d6837ef0d1bb1816b3a09082602` (Yes/résolu Trujillanos FC) · Draw: `0x1a88ae3fcc88891d949cb6a43937bc915af0f81e3554ae40b0584200aee7c4dd` (No) · Away: `0x730ea13ee130101f45cce60b0c6557181248bf23cc126f150a83df43fdd84f3f` (No) | — | — | event id 931998, slug `ven1-tru-msc-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset120_2026-09-02.json` |
| 13 | UCV FC vs. Deportivo Rayo Zuliano | Primera División (Venezuela) | 2026-08-31 (closed 2026-09-01T04:29:03Z) | UCV FC | Deportivo Rayo Zuliano | 3 | Home: `0xdb7a62813f6e0ca24c75a6d38c706ef6ddb2df02ae133b5e591aaabc8c01a09e` (Yes/résolu UCV FC) · Draw: `0xf50a39147cba185de4779c6a7103a2fcb2307de4599e0c76e46d75def15edbd5` (No) · Away: `0xe472a0bdf05955f8f40365bb3870af50497536f9279fd7364e88238af41a0c51` (No) | — | — | event id 931189, slug `ven1-ucv-drz-2026-08-31` ; source `events_neutral_soccer_tagslug_closed_offset120_2026-09-02.json` |
| 14 | FC Dinamo Batumi vs. FC Spaeri | Erovnuli Liga (Géorgie) | 2026-08-30 (closed 2026-08-30T22:47:01Z) | FC Dinamo Batumi | FC Spaeri | 3 | Home: `0x6e67647f9d2f4feaf86d14d77bb9a54a54d9c2336f8118d3912c30351561aa75` (Yes/résolu FC Dinamo Batumi) · Draw: `0xee60c67f2cd92a74ed5175791ae96d051552cf77af76c634c706226ccbc8f2c8` (No) · Away: `0xd1c4466acd0e5aa79aa29dd619e9d01f6dee03f9f90c017716cfc36581ac86e9` (No) | — | — | event id 931183, slug `geo1-bat-spa-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset120_2026-09-02.json` |
| 15 | Union Omaha SC vs. New York Cosmos | USL League One | 2026-08-29 (closed 2026-08-30T04:05:33Z) | Union Omaha SC | New York Cosmos | 3 | Home: `0x7ed0001c4507a7855c750d288b607e09d47b09a91a825aba623dc19fd0a13b53` (No) · Draw: `0x010f56746335b15b1153da9cbcea8aa9b0e2767acf839b479cfb239f496cb185` (Yes/résolu — match nul) · Away: `0x08880c2729fa2c47d7b834423f77cb00219fbdbf6a8c0a75c5da57d0a72e742c` (No) | — | — | event id 930986, slug `usl1-uni-nyc-2026-08-29` ; source `events_neutral_soccer_tagslug_closed_offset120_2026-09-02.json` |
| 16 | Hatta SC vs. Sharjah FC | UAE Pro League | 2026-08-30 (closed 2026-08-30T17:55:30Z) | Hatta SC | Sharjah FC | 3 | Home: `0xd5f3589b8c78c6ba901fd0115e2a9611e654a2fab3bbe50d2dcf9eb0be7a7a7e` (No) · Draw: `0xb3ccd4d659e0a24ac0d203b17e6ced4ebc805c3c22a5d66d1059b09705cb2c55` (No) · Away: `0xb25f5e7b6469bdc4d952251fa2c26a4553b936e36042f605836f60007bdd330c` (Yes/résolu Sharjah FC) | — | — | event id 930955, slug `uae1-hat-shj-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset160_2026-09-02.json` |
| 17 | Shandong Taishan FC vs. Shanghai Port FC | China FA Cup | 2026-09-01 (closed 2026-09-01T17:29:28Z) | Shandong Taishan FC | Shanghai Port FC | 3 | Home: `0x60754e5dc2d13377fc799683f436ae12f35c0bb2a4ecf2cffed2398ed5928b47` (No) · Draw: `0x121471a352f42862cdc6fa49c3e95d81d4b8e3c6d24a729ecd0b2622cfa487ee` (No) · Away: `0xe50839434d169d9f05c1ab11a336bb50ee6b5bad79d0c69952e4125f072640e9` (Yes/résolu Shanghai Port FC) | — | — | event id 930896, slug `chfa-sht-shp-2026-09-01` ; source `events_neutral_soccer_tagslug_closed_offset160_2026-09-02.json` |
| 18 | KI Klaksvik vs. Eb/Streymur | Betri deildin (Îles Féroé) | 2026-08-31 (closed 2026-08-31T21:42:01Z) | KI Klaksvik | Eb/Streymur | 3 | Home: `0x1818bc4ab8028daa0b27f2fa61b8121d3e712d6f2106400dfed13ab55d6d7ea5` (Yes/résolu KI Klaksvik) · Draw: `0x447577eef0068f0be320ecb17b93252377d98b20d90aa72a618ee3b6ac445599` (No) · Away: `0x3ba02c6b6a5c867bd43584597b2814597e1442e94ee516c91149f32b3fb03766` (No) | — | — | event id 930578, slug `fro1-ki-ebs-2026-08-31` ; source `events_neutral_soccer_tagslug_closed_offset160_2026-09-02.json` |
| 19 | Skala IF vs. 07 Vestur Sorvagur | Betri deildin (Îles Féroé) | 2026-08-30 (closed 2026-08-30T22:13:19Z) | Skala IF | 07 Vestur Sorvagur | 3 | Home: `0x9de3c4207e0355b9dd82a6d3fb45f9c00809454a37804822000849e3b1acec55` (No) · Draw: `0xc87c7bee7689c50ad1acc9c81fa4e0649e243b161a6d224dc3a6ce50bc1a6069` (Yes/résolu — match nul) · Away: `0x2219ebff271a5dcd70d9862e3b180d81b6f51498a81a1dfa48e2415773208572` (No) | — | — | event id 930231, slug `fro1-sif-ves-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset160_2026-09-02.json` |
| 20 | Westchester SC vs. Spokane Velocity FC | USL League One | 2026-08-29 (closed 2026-08-30T03:09:19Z) | Westchester SC | Spokane Velocity FC | 3 | Home: `0x5b189a719c56dcaf624316515a22ce5b585f3b3d9814d428c62f93fcda027fc5` (No) · Draw: `0x1821baa8ca5f316d64fc919debeafef3372fbc89b5bb27fc91a9913cd5a6bd7c` (No) · Away: `0x915dedf1042ad7d28b84719c63f8e1e06fc133347db375508917d3d9e669833d` (Yes/résolu Spokane Velocity FC) | — | — | event id 929891, slug `usl1-wes-spo-2026-08-29` ; source `events_neutral_soccer_tagslug_closed_offset160_2026-09-02.json` |
| 21 | Deportivo Maritimo vs. CD Cieza | Club Friendlies (Espagne) | 2026-08-29 (closed 2026-08-30T00:13:19Z) | Deportivo Maritimo | CD Cieza | 3 | Home: `0xa121089ff7fcc1d9101338ce33333561b4b13390215ec2232a1f1d98cf9362ea` (No) · Draw: `0xc61b741bee652524416f0b0caf3ecb4520a6f8a27d1f2083acae003b1cfb44fb` (No) · Away: `0x193a28b95dedf4d813977978b013a70f4560e2f54ad69e7ddf1ad60c33164645` (Yes/résolu CD Cieza) | — | — | event id 929084, slug `clf-dm-cie-2026-08-29` ; source `events_neutral_soccer_tagslug_closed_offset160_2026-09-02.json` |
| 22 | Zira FK vs. Neftchi Baku PFC | Azerbaijan Premier League | 2026-08-30 (closed 2026-08-30T20:18:28Z) | Zira FK | Neftchi Baku PFC | 3 | Home: `0x6e25abea1bd55b22c6e427acb2e04991a442b0c37eca5e3e98bd86c5da488c49` (Yes/résolu Zira FK) · Draw: `0xce95af6bf5e0fe81779871574b0e26fe0abd4cbd712c0e772b0052177077574a` (No) · Away: `0x3e96716fc8424416d9b175ff6d2516d58d00b7a64d87062d5935e7266367770c` (No) | — | — | event id 928727, slug `aze1-zir-neb-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset200_2026-09-02.json` |
| 23 | Deportivo Tachira vs. Caracas FC | Primera División (Venezuela) | 2026-08-30 (closed 2026-08-31T07:52:30Z) | Deportivo Tachira | Caracas FC | 3 | Home: `0x47875ac59f3c74906792301c8c1a52f7e71d760a555ef6ec5bac1f5e0d42eaf7` (No) · Draw: `0xe44fb5cf72953a974831974891ee5f138d4c89c59f1dc16117add0c8956ccffd` (Yes/résolu — match nul) · Away: `0x9e7f8cd830267450323da22c82aac0da87c4153586ae32530571ebcd96d0fadf` (No) | — | — | event id 928452, slug `ven1-tac-car-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset200_2026-09-02.json` |
| 24 | Portuguesa FC vs. Metropolitanos FC | Primera División (Venezuela) | 2026-08-30 (closed 2026-08-31T07:55:58Z) | Portuguesa FC | Metropolitanos FC | 3 | Home: `0xda59976dcb5291fbfe1e1ead258f8318ef0006a772757ec8873cf0616e8fe1d0` (No) · Draw: `0x8c24f04a979a1928ca2b1e5b4c22069a97e54b3a80167c86fd854a18e2bae369` (Yes/résolu — match nul) · Away: `0x58ec3ccd59a3e73ed35bcecc19648737b0b8e77a8c61b95a899a6d9d57ff17a6` (No) | — | — | event id 928453, slug `ven1-por-met-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset200_2026-09-02.json` |
| 25 | Carabobo FC vs. Zamora FC | Primera División (Venezuela) | 2026-08-30 (closed 2026-08-31T05:36:30Z) | Carabobo FC | Zamora FC | 3 | Home: `0x93d554f4d51509d00f6d2c53fb1323870287fa08e104fcefd6e47e34f000674f` (No) · Draw: `0x584fa0a75776b6ce9b552bf29e9a2e0ea08a90f92db004d95c180c8a7268858f` (Yes/résolu — match nul) · Away: `0x98674ca45943bdf42d43c8a953559851ac07b98a32ee17983ecbd0fa76ae78af` (No) | — | — | event id 928454, slug `ven1-cfc-zam-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset200_2026-09-02.json` |
| 26 | Deportivo La Guaira vs. Estudiantes de Merida | Primera División (Venezuela) | 2026-08-30 (closed 2026-08-31T05:26:30Z) | Deportivo La Guaira | Estudiantes de Merida | 3 | Home: `0x2d05d21999c71dd4b829c9ba1e425860da91112648f07d80476780e1a52134a3` (No) · Draw: `0x40e97bef31491c152d1481ef63373b7ce4d036d7dea4cc8d5236068766275f71` (No) · Away: `0x02628955c99bb36022561c78515e0d57cb6e62e33606916fde224ff025faae5e` (Yes/résolu Estudiantes de Merida) | — | — | event id 928455, slug `ven1-dlg-edm-2026-08-30` ; source `events_neutral_soccer_tagslug_closed_offset200_2026-09-02.json` |
| 27 | Jong AZ Alkmaar vs. Jong FC Utrecht | Netherlands Eerste Divisie | 2026-08-31 (closed 2026-08-31T22:33:04Z) | Jong AZ Alkmaar | Jong FC Utrecht | 3 | Home: `0x3dabf3d0e39c15d0c1b3499df73e0ac07df078e28c9f681fcacc3cc398b6f72c` (Yes/résolu Jong AZ Alkmaar) · Draw: `0x8d757eb9a9eaa9e92e048457960823b11cafb219b87b454f7eae330ec42fa3ab` (No) · Away: `0xc6cbffb402672c2a773ffd0ff13dd4a225c96fdccde2c21ee997da3f13f823ad` (No) | — | — | event id 927432, slug `ned2-az-utr-2026-08-31` ; source `events_neutral_soccer_tagslug_closed_offset200_2026-09-02.json` |
| 28 | Jong PSV Eindhoven vs. Jong Ajax Amsterdam | Netherlands Eerste Divisie | 2026-08-31 (closed 2026-08-31T23:53:33Z) | Jong PSV Eindhoven | Jong Ajax Amsterdam | 3 | Home: `0x3aac440bc07a0ebf62c79244af147437f8945d84c36974f277a8dc1ebd3cf5dc` (No) · Draw: `0xe835490a22f096a55f701c1f3fe4aa16486040bc83d11e0513815e4cc11252bf` (Yes/résolu — match nul) · Away: `0xe24e12da7bbfaaa8309cc3539ea73b7ec4d5c09ec5eafb7a1a18db6da2285901` (No) | — | — | event id 927433, slug `ned2-psv-aja-2026-08-31` ; source `events_neutral_soccer_tagslug_closed_offset200_2026-09-02.json` |
| 29 | PFC Slavia Sofia vs. PFC Levski Sofia | Bulgaria Parva Liga | 2026-09-02 (closed 2026-09-02T23:00:01Z) | PFC Slavia Sofia | PFC Levski Sofia | 3 | Home: `0xbb120e59cfadfa90fb3011f417c3cd99acdf3351e22875b6d58826f35045acf8` (No) · Draw: `0xb5680c484a0fa9f38175e058c7b3a63bcc87a01880697da0c892e8b07425aa6f` (No) · Away: `0xef337f0aa94567a97518692f8604dc957ea91ee1b59a0773b76edb52a98ed6f9` (Yes/résolu PFC Levski Sofia) | — | — | event id 931812, slug `bul-sla-lev-2026-09-02` ; source `events_neutral_soccer_tagslug_closed_offset280_2026-09-03.json` |
| 30 | Fatih Karagumruk Istanbul vs. Kayserispor | Turkey 1. Lig | 2026-09-02 (closed 2026-09-02T23:01:45Z) | Fatih Karagumruk Istanbul | Kayserispor | 3 | Home: `0x2b767ef81d80a244377394835ecb308284f69e3c19010c6fb8a1b7e66bace7e1` (No) · Draw: `0x729da5ffecc7ac8fb06fcc2c8bc1f7525fe3cd526dd4cea655deecd9465cb38f` (Yes/résolu — match nul) · Away: `0x0954a0b6fabd7dee391c14f2dc308c577bc197745a3c29ca1475cd20332bcdd3` (No) | — | — | event id 937608, slug `tur2-kar-kay-2026-09-02` ; source `events_neutral_soccer_tagslug_closed_offset320_2026-09-04.json` |
| 31 | St. Truidense VV vs. Union Saint-Gilloise | Belgium Pro League | 2026-09-02 (closed 2026-09-02T22:24:49Z) | St. Truidense VV | Union Saint-Gilloise | 3 | Home: `0x3440a7b2feadf25570abad53000a6831aafe53bd43f152b970da611a505e2435` (No) · Draw: `0x4ebd4517c4b752cb08896556980d905979717b25077d5f5e3ee7cbae8b023eee` (No) · Away: `0x2864cc17fe35d19dac514b4b45bb1001ae35b2434d5529e72cdd88b80251e2d8` (Yes/résolu Union Saint-Gilloise) | — | — | event id 937595, slug `bel1-stt-usg-2026-09-02` ; source `events_neutral_soccer_tagslug_closed_offset320_2026-09-04.json` |
| 32 | RKS Rakow Czestochowa vs. Gornik Zabrze | Poland Ekstraklasa | 2026-09-03 (closed 2026-09-03T22:51:06Z) | RKS Rakow Czestochowa | Gornik Zabrze | 3 | Home: `0x4c760892ad8c9464bc60339f1c01fe68552648b8f06c3cf0a699020df83ab78b` (No) · Draw: `0x520d1601f4b0922547849a5508d02fc855501a9c513b0610a123ec1c168fd3ac` (No) · Away: `0x6690e606d07b65b65c7d930ae2249148156334ef324d5734730cfe578af6f7d6` (Yes/résolu Gornik Zabrze) | — | — | event id 937472, slug `pol-cze-gor-2026-09-03` ; source `events_neutral_soccer_tagslug_closed_offset320_2026-09-04.json` |
| 33 | FC Thun vs. Lausanne-Sport | Switzerland Super League | 2026-09-02 (closed 2026-09-02T22:31:01Z) | FC Thun | Lausanne-Sport | 3 | Home: `0x79c846d46e0a95a50f0dcb098041596305d5e1b5119e42e42ee5198d019623d6` (No) · Draw: `0x85dc4dd49cc210a1b891ba95cc47c09efe6287f2c7cfde350411818a32d18119` (Yes/résolu — match nul) · Away: `0xcbddc81c7056eb9d5a223f3dd6f25e636e8edc8292bb408882f87953c682431f` (No) | — | — | event id 937118, slug `sui-thu-lau-2026-09-02` ; source `events_neutral_soccer_tagslug_closed_offset320_2026-09-04.json` |
| 34 | Grasshopper Club Zurich vs. FC St. Gallen 1879 | Switzerland Super League | 2026-09-02 (closed 2026-09-02T22:23:19Z) | Grasshopper Club Zurich | FC St. Gallen 1879 | 3 | Home: `0xef718ed8fefdca7b97279a41a5a3d29afbebeb24d363d1334234e250a0352800` (Yes/résolu Grasshopper Club Zurich) · Draw: `0xe7edc4274e4560fd07b86c4ebb3243f8113f746a12d11e722936fa6000b6b891` (No) · Away: `0x6825c2f1c7265d82bc079dcd8585b18a37395c950acc829f352733c7d5d8ff5a` (No) | — | — | event id 937119, slug `sui-gcz-stg-2026-09-02` ; source `events_neutral_soccer_tagslug_closed_offset320_2026-09-04.json` |

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
