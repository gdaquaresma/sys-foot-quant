"""Verifie l'isolation totale entre `polymarket/` et `final_engine/`
(Phase L, etape 3/13) : le moteur de production reste GELE et ne doit
jamais dependre, meme transitivement, d'une source de donnees en cours
d'audit. Meme methode (inspection AST des imports) que
tests/unit/test_final_engine_scientific_non_regression.py pour les
exclusions scientifiques."""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "sys_foot_quant"


def _imported_module_names(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_final_engine_never_imports_polymarket() -> None:
    final_engine_dir = _SRC / "final_engine"
    for py_file in final_engine_dir.glob("*.py"):
        imported = _imported_module_names(py_file)
        offending = {m for m in imported if "polymarket" in m}
        assert not offending, f"{py_file} importe polymarket (interdit, etape 3) : {offending}"


def test_polymarket_never_imports_final_engine() -> None:
    polymarket_dir = _SRC / "polymarket"
    for py_file in polymarket_dir.glob("*.py"):
        imported = _imported_module_names(py_file)
        offending = {m for m in imported if "final_engine" in m}
        assert not offending, f"{py_file} importe final_engine (interdit, etape 3) : {offending}"


def test_polymarket_package_exists_and_is_non_empty() -> None:
    polymarket_dir = _SRC / "polymarket"
    assert polymarket_dir.is_dir()
    modules = [p for p in polymarket_dir.glob("*.py") if p.name != "__init__.py"]
    assert len(modules) >= 6
