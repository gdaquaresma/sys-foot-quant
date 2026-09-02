# Rapport de collecte — univers neutre Polymarket football (21 marchés)

Date de génération : 2026-09-02. Collecte réalisée manuellement (accès réseau direct bloqué pour cet agent), un marché à la fois, via `data-api.polymarket.com/trades?market=<conditionId>&limit=1000`, l'utilisateur récupérant chaque page dans son navigateur. Aucun marché n'a nécessité de pagination au-delà de la première page (aucune page n'a atteint 1000 résultats).

## Rappel des contraintes méthodologiques

- Les marchés ont été sélectionnés **avant** tout examen des trades ou des wallets (univers neutre construit à l'étape 1, indépendamment des traders).
- Aucun classement de performance des traders n'a été effectué. Les statistiques wallet ci-dessous portent **uniquement** sur le nombre de marchés tradés, jamais sur un P&L ou une performance quelconque.
- Le wallet `suntori` (`0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6`) a été suivi car repéré fortuitement lors d'une trace antérieure — sa présence est documentée par marché mais n'a influencé aucune sélection de marché.
- Aucun code de production n'a été modifié. Tous les payloads bruts restent dans `research/polymarket_raw_exports/` (gitignored).

## Tableau consolidé des 21 marchés

| # | Match | Marché | conditionId | Trades (bruts=dédup) | Wallets | Première trade (UTC) | Dernière trade (UTC) | Résolution | `suntori` overlap (flag / réel) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Sumqayit FK vs. Qarabag FK | Will Qarabag FK win on 2026-08-31? | `0x59fdb4ab41…` | 69 | 22 | 2026-08-30 20:26 | 2026-08-31 18:13 | Yes | False / 0x |
| 2 | Lanzhou Longyuan Athletic vs. Beijing Guoan | Will Lanzhou Longyuan Athletic win on 2026-09-01? | `0xfa748d5447…` | 121 | 56 | 2026-09-01 01:05 | 2026-09-01 16:36 | No | False / 4x |
| 3 | Lanzhou Longyuan Athletic vs. Beijing Guoan | Will Lanzhou Longyuan Athletic vs. Beijing Guoan end in a draw? | `0x69bcfe7e56…` | 66 | 47 | 2026-08-31 17:18 | 2026-09-01 15:38 | No | False / 1x |
| 4 | Lanzhou Longyuan Athletic vs. Beijing Guoan | Will Beijing Guoan win on 2026-09-01? | `0xf69fbd421e…` | 598 | 267 | 2026-08-31 18:03 | 2026-09-01 17:11 | Yes | False / 46x |
| 5 | Dalian Yingbo FC vs. Shanghai Shenhua FC | Will Dalian Yingbo FC win on 2026-09-01? | `0x0a529ab12b…` | 139 | 59 | 2026-08-31 15:39 | 2026-09-01 16:21 | Yes | True / 1x |
| 6 | Dalian Yingbo FC vs. Shanghai Shenhua FC | Will Dalian Yingbo FC vs. Shanghai Shenhua FC end in a draw? | `0x5c3c171e0e…` | 49 | 34 | 2026-09-01 03:37 | 2026-09-01 15:06 | No | True / 4x |
| 7 | Dalian Yingbo FC vs. Shanghai Shenhua FC | Will Shanghai Shenhua FC win on 2026-09-01? | `0x7c98095d33…` | 312 | 118 | 2026-08-31 13:41 | 2026-09-01 16:35 | No | True / 11x |
| 8 | FC Dinamo Tbilisi vs. FC Dila Gori | Will FC Dinamo Tbilisi win on 2026-08-31? | `0xe8706a060c…` | 25 | 19 | 2026-08-31 10:41 | 2026-08-31 18:57 | Yes | False / 1x |
| 9 | FC Dinamo Tbilisi vs. FC Dila Gori | Will FC Dinamo Tbilisi vs. FC Dila Gori end in a draw? | `0x3f462b5338…` | 24 | 19 | 2026-08-31 10:42 | 2026-08-31 17:31 | No | False / 0x |
| 10 | FC Dinamo Tbilisi vs. FC Dila Gori | Will FC Dila Gori win on 2026-08-31? | `0xe90c53898c…` | 4 | 3 | 2026-08-31 16:30 | 2026-08-31 17:18 | No | False / 0x |
| 11 | FC Gagra vs. FC Iberia 1999 | Will FC Gagra win on 2026-08-31? | `0x893a54a0d2…` | 9 | 6 | 2026-08-31 15:14 | 2026-08-31 18:01 | Yes | False / 0x |
| 12 | FC Gagra vs. FC Iberia 1999 | Will FC Gagra vs. FC Iberia 1999 end in a draw? | `0xaf6f4f940c…` | 4 | 3 | 2026-08-31 10:43 | 2026-08-31 16:07 | No | False / 0x |
| 13 | FC Gagra vs. FC Iberia 1999 | Will FC Iberia 1999 win on 2026-08-31? | `0xdac059fb1d…` | 13 | 10 | 2026-08-31 10:43 | 2026-08-31 16:06 | No | False / 0x |
| 14 | FC Torpedo Kutaisi vs. FC Meshakhte Tkibuli | Will FC Torpedo Kutaisi win on 2026-08-31? | `0xfa7e093dac…` | 32 | 23 | 2026-08-31 10:43 | 2026-08-31 17:01 | No | False / 2x |
| 15 | FC Torpedo Kutaisi vs. FC Meshakhte Tkibuli | Will FC Torpedo Kutaisi vs. FC Meshakhte Tkibuli end in a draw? | `0x01764da622…` | 5 | 5 | 2026-08-31 10:43 | 2026-08-31 16:07 | No | False / 0x |
| 16 | FC Torpedo Kutaisi vs. FC Meshakhte Tkibuli | Will FC Meshakhte Tkibuli win on 2026-08-31? | `0xec6f843663…` | 15 | 7 | 2026-08-31 12:25 | 2026-08-31 17:06 | Yes | False / 0x |
| 17 | FK Liepaja vs. Riga FC | Will FK Liepaja win on 2026-08-31? | `0x4ec28eeed1…` | 79 | 40 | 2026-08-30 21:54 | 2026-08-31 16:33 | Yes | False / 0x |
| 18 | FK Liepaja vs. Riga FC | Will FK Liepaja vs. Riga FC end in a draw? | `0x37df1f93c1…` | 25 | 15 | 2026-08-30 22:04 | 2026-08-31 16:33 | No | False / 0x |
| 19 | FK Liepaja vs. Riga FC | Will Riga FC win on 2026-08-31? | `0x4d8a8fb101…` | 48 | 33 | 2026-08-30 22:04 | 2026-08-31 16:33 | No | False / 1x |
| 20 | Sumqayit FK vs. Qarabag FK | Will Sumqayit FK win on 2026-08-31? | `0x3efd468f83…` | 28 | 12 | 2026-08-30 20:26 | 2026-08-31 17:50 | No | False / 0x |
| 21 | Sumqayit FK vs. Qarabag FK | Will Sumqayit FK vs. Qarabag FK end in a draw? | `0x9e3708f065…` | 7 | 6 | 2026-08-30 20:26 | 2026-08-31 16:41 | No | False / 0x |

**Total : 21/21 marchés collectés, 1672 trades dédupliqués au total (aucun doublon détecté sur aucun marché : bruts = dédupliqués partout).**

## Contrôles qualité effectués (tous marchés)

- **Jointure conditionId** : chaque payload de trades a été validé contre le `conditionId` demandé (aucune contamination croisée).
- **Cohérence token↔outcome** : pour chaque marché, chaque `asset` (token ID) correspond à un seul `outcome` label sur l'ensemble des trades — 21/21 marchés cohérents.
- **Timestamps vs résolution** : `timestamp_utc` de chaque trade comparé à `resolution_time_closedTime` des métadonnées — **0 trade post-résolution sur les 21 marchés**.
- **Pagination** : aucun marché n'a retourné exactement 1000 trades sur la première page (maximum observé : 598, Beijing Guoan win) — la première page couvre donc l'intégralité des trades disponibles pour chaque marché.
- **Déduplication** : `deduplicate_trades` (clé `transactionHash`) appliqué à tous les marchés — 0 doublon détecté sur les 21 marchés (bruts = dédupliqués partout).
- **Cohérence des résultats internes par match** : pour les 7 matchs (21 marchés), le trio win/draw/win a systématiquement un seul `resolved_outcome="Yes"` et deux `"No"`, cohérent avec un résultat de match unique — validé sur les 7 matchs.

## Anomalies et points d'attention

- **Flag `suntori_overlap` des métadonnées incomplet** : ce flag précalculé n'avait été positionné `true` que sur le match `chfa-dy-shs-2026-09-01`. Or les données réelles montrent `suntori` actif sur **9 des 21 marchés** (tous les marchés de `chfa-lan-bjg`, `chfa-dy-shs`, `geo1-tku-met` et `lva1-lie-rfc`), avec jusqu'à 46 trades sur un seul marché (Beijing Guoan win). Le flag ne doit donc plus être utilisé comme seule source de vérité — la détection réelle doit toujours se faire sur les données de trades.
- **Marchés à très faible profondeur** (≤10 wallets) : FC Dila Gori win (3 wallets, 4 trades), Gagra vs Iberia draw (3 wallets), FC Gagra win (6 wallets), Torpedo vs Meshakhte draw (5 wallets), FC Meshakhte Tkibuli win (7 wallets), FC Iberia 1999 win (10 wallets). Ces marchés restent QC-valides (aucune anomalie de jointure/timestamp) mais tout signal wallet qui en serait tiré aura une significativité statistique très limitée.
- **Incident de collecte corrigé (Fichier 13)** : la première tentative de sauvegarde du marché "Beijing Guoan win" (598 trades) par retype manuel a été tronquée à ~60 entrées ; détecté avant tout calcul QC et corrigé par extraction directe depuis le transcript de session. Tous les marchés suivants ont utilisé cette méthode d'extraction directe, éliminant ce risque.

## Univers de wallets (union sur les 21 marchés)

- **Total wallets uniques ayant tradé au moins un marché de l'univers : 529**
- Distribution du nombre de marchés tradés par wallet :

| Marchés tradés | Nombre de wallets |
|---|---|
| 1 | 377 |
| 2 | 105 |
| 3 | 28 |
| 4+ | 19 |

- **BUY uniquement** : 362 wallets
- **SELL uniquement** : 23 wallets
- **BUY et SELL (les deux côtés)** : 144 wallets

### Top 20 wallets par nombre de marchés tradés (jamais par performance)

| Wallet | Marchés tradés (sur 21) |
|---|---|
| `0xd9c9651b…` | 15 |
| `0x0346afae…` | 14 |
| `0x821dab05…` | 13 |
| `0x9e3ed7b6…` | 9 |
| `0xbb6bfa0b…` | 9 |
| `0xe9076a87…` | 9 |
| `0x076daa87…` | 7 |
| `0x87e891be…` | 6 |
| `0xdbdd4515…` | 6 |
| `0x84cfffc3…` | 6 |
| `0xebf7fc75…` | 6 |
| `0x26a30305…` | 5 |
| `0x0ad69cbc…` | 4 |
| `0xef80a2f6…` | 4 |
| `0x5b6331e7…` | 4 |
| `0x893575c7…` | 4 |
| `0x5ebdbf0a…` | 4 |
| `0xafe307d5…` | 4 |
| `0x1f624696…` | 4 |
| `0x294fb7ee…` | 3 |

*Rappel : ce classement est uniquement descriptif (nombre de marchés de l'univers effectivement tradés). Il ne s'agit en aucun cas d'un classement de performance ou d'un "top traders" — la sélection future d'un trader pour la phase suivante devra se faire sur ce critère de présence dans l'univers, jamais sur un P&L.*

## Verdict : exploitabilité pour la phase suivante

**21/21 marchés sont effectivement exploitables pour la phase PIT suivante.**

Tous les marchés ont passé l'intégralité des contrôles qualité (jointure conditionId, cohérence token↔outcome, 0 trade post-résolution, pagination complète, déduplication propre, cohérence interne des résultats par match). Aucun marché n'a été écarté. Les seules réserves à porter à la connaissance de la phase suivante sont : (1) 6 marchés à très faible profondeur (≤10 wallets) dont le poids statistique sera limité, et (2) le match `chfa-dy-shs-2026-09-01` qui reste marqué `suntori_overlap` dans les métadonnées pour permettre une analyse de sensibilité avec/sans ce match si besoin — étant entendu que `suntori` est en réalité présent sur 4 matchs différents de cet univers, pas seulement celui-ci.

---
*Payloads bruts et journal détaillé marché-par-marché : `research/polymarket_raw_exports/` (gitignored, non commité). Ce rapport de synthèse est la seule pièce destinée à être committée si l'utilisateur le souhaite.*