"""Gestion de bankroll : Flat Betting, Kelly fractionnaire, limites de mise,
metriques de risque, simulations Monte Carlo.

REGLE STRICTE (cahier des charges etape 4, non negociable) : le systeme
reste en FLAT BETTING UNIQUEMENT en production. Quarter-Kelly et
Half-Kelly sont implementes (voir risk_engine.kelly) mais VERROUILLES par
des quality gates - ``kelly_stake()`` refuse de produire une mise tant
que ces conditions ne sont pas explicitement remplies (echantillon de
CLV suffisant, CLV significativement positif hors echantillon, ET
approbation humaine explicite). Aucun de ces gates n'est leve par ce
projet a ce stade : le calcul de Kelly reste purement informatif.
"""
