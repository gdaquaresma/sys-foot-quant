from __future__ import annotations

from pathlib import Path

import pytest

from sys_foot_quant.final_engine.market import compare_over_under_to_market

_MARKET_MODULE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "sys_foot_quant"
    / "final_engine"
    / "market.py"
)


def test_reproduces_compare_model_to_market_fields() -> None:
    result = compare_over_under_to_market(model_probability_over=0.6, market_odds_over=1.9, market_odds_under=2.0)
    assert result.market_odds == {"Over": 1.9, "Under": 2.0}
    assert result.market_overround == pytest.approx(1 / 1.9 + 1 / 2.0 - 1.0)
    assert sum(result.market_implied_probability_normalized.values()) == pytest.approx(1.0)


def test_raw_edge_is_model_minus_normalized_market_probability() -> None:
    result = compare_over_under_to_market(model_probability_over=0.6, market_odds_over=1.9, market_odds_under=2.0)
    expected_raw_edge = 0.6 - result.market_implied_probability_normalized["Over"]
    assert result.raw_edge["Over"] == pytest.approx(expected_raw_edge)


def test_price_edge_is_expected_value_on_raw_market_odds() -> None:
    result = compare_over_under_to_market(model_probability_over=0.6, market_odds_over=1.9, market_odds_under=2.0)
    assert result.price_edge["Over"] == pytest.approx(0.6 * 1.9 - 1.0)


def test_never_names_a_field_value() -> None:
    """Interdiction structurelle : le mot 'value' ne doit jamais apparaitre
    comme nom de champ ou de variable dans ce module - un edge n'est pas
    automatiquement une 'value' (docs/final_engine_specification.md
    section 11)."""
    source = _MARKET_MODULE_PATH.read_text()
    import ast

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.lower() == "value":
            raise AssertionError("variable nommee 'value' trouvee dans market.py")


def test_never_imports_closing_odds_accessors() -> None:
    """Verification par AST (pas par simple recherche de sous-chaine, qui
    matcherait aussi la mention de ces noms dans le docstring
    d'avertissement du module) : aucun noeud de code (import, attribut,
    nom) ne reference les accesseurs de cloture."""
    import ast

    source = _MARKET_MODULE_PATH.read_text()
    tree = ast.parse(source)
    forbidden = {"closing_odds_1x2_by_bookmaker", "closing_over_under_2_5_by_bookmaker"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue  # ignore les docstrings/commentaires textuels
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            raise AssertionError(f"reference de code interdite trouvee : {node.attr}")
        if isinstance(node, ast.Name) and node.id in forbidden:
            raise AssertionError(f"reference de code interdite trouvee : {node.id}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                assert alias.name not in forbidden
