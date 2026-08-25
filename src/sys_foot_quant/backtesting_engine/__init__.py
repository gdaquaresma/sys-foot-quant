"""Backtester : boucle de simulation chronologique.

Etape 1 uniquement. Ce module ne contient aucune strategie ni aucun
modele : il fournit uniquement la boucle qui garantit qu'a chaque
instant de decision, seules les donnees ``knowledge_time <= T`` sont
exposees (via le Repository), et que ces instants sont traites dans un
ordre strictement chronologique.
"""
