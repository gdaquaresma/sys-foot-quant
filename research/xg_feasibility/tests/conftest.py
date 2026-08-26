"""Ajoute la racine du depot a sys.path pour ces tests uniquement -
delibere pour ne modifier ni pyproject.toml ni la configuration pytest
partagee (testpaths reste ``["tests"]``, inchange)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
