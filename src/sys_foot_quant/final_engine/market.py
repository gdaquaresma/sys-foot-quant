"""Niveau D - Market comparison (docs/final_engine_specification.md
sections 3, 10, 11). Le marche est un PRICE BENCHMARK, jamais un
adversaire ni un oracle (docs/research_synthesis_e1_e16.md section 4).

Reutilise SANS MODIFICATION ``market_engine.model_vs_market.compare_model_to_market``
(retrait d'overround, probabilite implicite) et ``value_engine.edge``
(``edge``/``expected_value``) - aucune nouvelle formule.

RESTRICTION STRUCTURELLE NON NEGOCIABLE (E16, docs/final_engine_specification.md
sections 4.4, 12) : ce module n'importe et ne peut recevoir QUE des cotes
D'OUVERTURE. Aucune fonction ici ne lit ni n'accepte une cote de cloture -
``FootballDataMatchLoader.closing_odds_1x2_by_bookmaker``/
``closing_over_under_2_5_by_bookmaker`` ne sont jamais references, ni ici
ni transitivement (verifie par inspection statique, voir
tests/leakage/test_final_engine_point_in_time.py)."""

from __future__ import annotations

from sys_foot_quant.final_engine.types import MarketComparisonResult
from sys_foot_quant.market_engine.model_vs_market import compare_model_to_market
from sys_foot_quant.value_engine.edge import edge, expected_value


def compare_over_under_to_market(
    model_probability_over: float,
    market_odds_over: float,
    market_odds_under: float,
) -> MarketComparisonResult:
    """Compare la probabilite Over d'UN seuil (typiquement Over 2.5, le
    seul marche O/U pour lequel Football-Data publie une cote, voir
    docs/final_engine_specification.md section 4.3/7) a la cote de marche
    D'OUVERTURE. Ne qualifie rien - produit uniquement les quantites
    definies section 11, jamais un jugement de fiabilite (role du Niveau E)."""
    model_probs = {"Over": model_probability_over, "Under": 1.0 - model_probability_over}
    market_odds = {"Over": market_odds_over, "Under": market_odds_under}

    comparison = compare_model_to_market(model_probs, market_odds)

    raw_edge = {selection: edge(model_probs[selection], comparison["implied_prob_normalized"][selection]) for selection in model_probs}
    price_edge = {selection: expected_value(model_probs[selection], market_odds[selection]) for selection in model_probs}

    return MarketComparisonResult(
        market_odds=market_odds,
        market_implied_probability_raw=comparison["implied_prob_raw"],
        market_implied_probability_normalized=comparison["implied_prob_normalized"],
        market_overround=comparison["overround"],
        raw_edge=raw_edge,
        price_edge=price_edge,
    )
