"""Codes de raison stables pour le rattachement Polymarket -> Football-Data
(Phase L, etape 6). Toute correspondance non etablie ou ambigue doit porter
l'un de ces codes - jamais une correspondance forcee silencieuse."""

from __future__ import annotations

POLYMARKET_MATCH_UNMATCHED = "POLYMARKET_MATCH_UNMATCHED"
POLYMARKET_MATCH_AMBIGUOUS = "POLYMARKET_MATCH_AMBIGUOUS"

ALL_CODES = frozenset({POLYMARKET_MATCH_UNMATCHED, POLYMARKET_MATCH_AMBIGUOUS})
