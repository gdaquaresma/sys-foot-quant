"""Moteur de donnees : schemas, generation synthetique, stockage point-in-time.

Etape 1 uniquement : pas de connecteurs vers des sources reelles, pas de
nettoyage avance. Le but est de poser le contrat de donnees (chaque fait
porte un ``knowledge_time``) et le mecanisme de lecture point-in-time.
"""
