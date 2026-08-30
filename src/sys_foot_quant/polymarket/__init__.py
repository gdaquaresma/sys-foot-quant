"""Couche d'ingestion/normalisation Polymarket (Phase L).

Isolee de ``final_engine`` : ce package n'est importe par aucun module de
``final_engine`` et n'importe lui-meme aucun module de ``final_engine``
(verifie par test dedie, ``tests/unit/test_polymarket_no_final_engine_dependency.py``).
Le moteur de production reste GELE - voir docs/polymarket_pomet_data_audit.md
pour le contexte complet de cette phase (audit + preparation de donnees
uniquement, aucune experience de performance).
"""

from __future__ import annotations
