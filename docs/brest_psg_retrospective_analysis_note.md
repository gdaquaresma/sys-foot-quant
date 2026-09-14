# Note — analyse Brest–PSG (13/09/2026) : nature rétrospective, jamais une décision de pari

## Ce que c'est

Le calcul Brest–PSG produit dans `research/temporal_weighting_experiment/brest_psg_analysis.csv`
(et dans les rapports BASELINE/CURRENT précédents) est une **analyse
scientifique rétrospective** : il répond à "qu'aurait calculé le moteur à
`decision_time = kickoff − 2h`", avec les cotes Betclic réellement
observées par l'utilisateur, utilisées uniquement pour mesurer un
edge/EV théorique.

## Ce que ce n'est PAS

**Ce n'est jamais une décision de pari réellement disponible.** Le
mécanisme de snapshot live (`snapshot_engine.schema.create_snapshot`,
INCHANGÉ, jamais modifié) a été testé réellement avec les cotes Betclic
et **a correctement refusé** ce match :

```
SNAPSHOT REFUSE : capture_timestamp (2026-09-13T19:20:17 UTC) doit etre
strictement anterieur a kickoff_utc (2026-09-13T18:45:00 UTC) -
posterieur au coup d'envoi refuse.
```

L'horloge réelle de l'environnement (19:20 UTC au moment du test) avait
dépassé le coup d'envoi réel (18:45 UTC) de 35 minutes. Le garde-fou
temporel — `capture_timestamp` toujours généré par le système, jamais
falsifiable — a fonctionné exactement comme conçu : il empêche de
prétendre qu'une décision est prise "avant le match" alors qu'elle serait
en réalité prise après.

## Conséquence

Tout calcul Brest–PSG produit après ce refus (BASELINE/CURRENT,
comparaison A0-A5) a utilisé `decision_time = kickoff − 2h = 16:45 UTC`
**directement**, en dehors du chemin snapshot live, avec les cotes
Betclic injectées comme simples valeurs numériques — un calcul
analytique, jamais une exécution du pipeline de décision réel tel qu'il
serait utilisé en production. **Le mécanisme snapshot lui-même n'a subi
aucune modification** pour permettre ce contournement — il a simplement
été court-circuité pour l'analyse, ce qui est explicitement documenté ici
pour qu'aucune ambiguïté ne subsiste.

## Règle pour la suite

Toute mention future des chiffres Brest–PSG (λ, P(Over 2.5), cote juste,
edge, EV) doit être présentée comme **analyse rétrospective à but
scientifique uniquement**, jamais comme un pari qui aurait pu ou pourrait
être placé.
