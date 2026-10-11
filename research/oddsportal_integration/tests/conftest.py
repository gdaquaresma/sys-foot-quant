"""Ajoute la racine du depot a sys.path pour ces tests uniquement - meme
convention que ``research/xg_feasibility/tests/conftest.py`` (delibere pour
ne modifier ni pyproject.toml ni la configuration pytest partagee,
``testpaths`` reste ``["tests"]`` : ces tests ne sont PAS ramasses par
``make test`` / ``uv run pytest -v``, invocation manuelle uniquement, meme
statut "recherche isolee" que le module teste)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
