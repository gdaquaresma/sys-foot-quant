from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sys_foot_quant.polymarket.schemas import Market, Trade
from sys_foot_quant.polymarket.traders import (
    EligibilityRules,
    compute_trader_stats_as_of,
    eligible_traders_as_of,
    token_id_consistent_with_market,
)

_T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _trade(
    wallet="0xabc", market="m1", side="BUY", price=0.5, size=10.0, outcome="Yes", offset_days=0, token_id=None
) -> Trade:
    return Trade(
        wallet_id=wallet,
        market_id=market,
        timestamp_utc=_T0 + timedelta(days=offset_days),
        side=side,
        price=price,
        size=size,
        source="polymarket_data_api",
        outcome=outcome,
        notional=price * size,
        token_id=token_id,
    )


def _resolved_market(market_id="m1", outcome="Yes", resolution_offset_days=0.5, condition_id=None) -> Market:
    return Market(
        market_id=market_id,
        source="polymarket_gamma_api",
        outcome=outcome,
        resolution_time=_T0 + timedelta(days=resolution_offset_days),
        condition_id=condition_id,
    )


def test_winning_buy_trade_yields_positive_realized_pnl() -> None:
    # BUY 10 shares "Yes" a 0.5 ; marche resolu "Yes" -> redemption 1.0/part.
    trades = [_trade(side="BUY", price=0.5, size=10.0, outcome="Yes")]
    markets = {"m1": _resolved_market(outcome="Yes")}
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.n_resolved_trades == 1
    assert stats.realized_pnl == 5.0  # 10 * (1.0 - 0.5)
    assert stats.win_rate == 1.0


def test_losing_buy_trade_yields_negative_realized_pnl() -> None:
    trades = [_trade(side="BUY", price=0.5, size=10.0, outcome="No")]
    markets = {"m1": _resolved_market(outcome="Yes")}  # "Yes" gagne, le trader avait "No"
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.realized_pnl == -5.0  # 10 * (0.0 - 0.5)
    assert stats.win_rate == 0.0


def test_unresolved_market_yields_none_realized_pnl_and_win_rate() -> None:
    trades = [_trade()]
    markets = {"m1": Market(market_id="m1", source="polymarket_gamma_api")}  # jamais resolu
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.n_resolved_trades == 0
    assert stats.realized_pnl is None
    assert stats.win_rate is None


def test_without_markets_argument_stats_stay_none_never_optimistic() -> None:
    trades = [_trade()]
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets=None)
    assert stats.realized_pnl is None
    assert stats.win_rate is None
    assert stats.n_trades == 1  # le volume/nombre de trades restent calculables sans `markets`


def test_resolution_known_only_after_decision_time_is_not_counted() -> None:
    """Une resolution connue APRES decision_time ne doit jamais compter
    comme une information disponible (etape 5)."""
    trades = [_trade(offset_days=0)]
    markets = {"m1": _resolved_market(resolution_offset_days=5)}  # resolu bien apres
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.n_resolved_trades == 0
    assert stats.realized_pnl is None


def test_eligible_traders_as_of_with_no_rules_applies_no_filter() -> None:
    trades_by_wallet = {"0xabc": [_trade(wallet="0xabc")], "0xdef": [_trade(wallet="0xdef", size=1.0)]}
    result = eligible_traders_as_of(_T0 + timedelta(days=1), trades_by_wallet, markets=None, rules=EligibilityRules())
    assert {s.wallet_id for s in result} == {"0xabc", "0xdef"}


def test_eligible_traders_as_of_filters_by_min_volume() -> None:
    trades_by_wallet = {
        "0xabc": [_trade(wallet="0xabc", price=0.5, size=100.0)],
        "0xdef": [_trade(wallet="0xdef", price=0.5, size=1.0)],
    }
    rules = EligibilityRules(min_volume_notional=10.0)
    result = eligible_traders_as_of(_T0 + timedelta(days=1), trades_by_wallet, markets=None, rules=rules)
    assert {s.wallet_id for s in result} == {"0xabc"}


def test_eligible_traders_as_of_top_n_by_realized_pnl() -> None:
    trades_by_wallet = {
        "0xabc": [_trade(wallet="0xabc", outcome="Yes")],  # gagnant
        "0xdef": [_trade(wallet="0xdef", outcome="No")],  # perdant
    }
    markets = {"m1": _resolved_market(outcome="Yes")}
    rules = EligibilityRules(top_n_by="realized_pnl", top_n=1)
    result = eligible_traders_as_of(_T0 + timedelta(days=1), trades_by_wallet, markets, rules)
    assert len(result) == 1
    assert result[0].wallet_id == "0xabc"


def test_eligible_traders_as_of_never_uses_trades_after_decision_time() -> None:
    trades_by_wallet = {
        "0xabc": [_trade(wallet="0xabc", offset_days=0, size=1.0), _trade(wallet="0xabc", offset_days=10, size=999.0)]
    }
    rules = EligibilityRules()
    result = eligible_traders_as_of(_T0 + timedelta(days=1), trades_by_wallet, markets=None, rules=rules)
    assert result[0].n_trades == 1
    assert result[0].volume_notional == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Jointure Trade.market_id <-> Market.condition_id (correctif). Sur un vrai
# payload Data API, Trade.market_id porte le conditionId on-chain, jamais
# l'id Gamma numerique que porte historiquement Market.market_id - voir
# _index_markets_for_join.
# ---------------------------------------------------------------------------

_CONDITION_ID = "0xfe0ebcbb0a3de954dcf08c7d1ef0c1333d94a89d7f0effa03591e1f7bb0a0ebc"


def test_A_trade_keyed_by_condition_id_joins_market_keyed_by_gamma_id() -> None:
    """Market.market_id = id Gamma ("3872870"), Market.condition_id =
    conditionId ; Trade.market_id = conditionId (payload reel) -> la
    jointure doit reussir."""
    market = _resolved_market(market_id="3872870", condition_id=_CONDITION_ID, outcome="Yes")
    trade = _trade(market=_CONDITION_ID, outcome="Yes")
    markets = {"3872870": market}  # dict cle "naturellement" par market_id, non re-cle par l'appelant
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), [trade], markets)
    assert stats.n_resolved_trades == 1
    assert stats.realized_pnl == 5.0  # 10 * (1.0 - 0.5), identique au comportement pre-correctif


def test_B_legacy_fixture_where_trade_and_market_share_the_same_id_still_joins() -> None:
    """Ancienne fixture synthetique : Trade.market_id == Market.market_id,
    aucun condition_id distinct - comportement preexistant inchange."""
    trades = [_trade(side="BUY", price=0.5, size=10.0, outcome="Yes")]  # market="m1", pas de condition_id
    markets = {"m1": _resolved_market(outcome="Yes")}  # condition_id=None par defaut
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), trades, markets)
    assert stats.n_resolved_trades == 1
    assert stats.realized_pnl == 5.0
    assert stats.win_rate == 1.0


def test_C_impossible_join_is_explicit_and_safe_not_silently_wrong() -> None:
    """Aucun Market du dict ne correspond ni par market_id ni par
    condition_id au Trade.market_id fourni - comportement explicite et
    sur (n_resolved_trades=0, realized_pnl=None), jamais une exception ni
    une valeur de P&L inventee."""
    trade = _trade(market="0x_marche_totalement_inconnu", outcome="Yes")
    markets = {"3872870": _resolved_market(market_id="3872870", condition_id=_CONDITION_ID, outcome="Yes")}
    stats = compute_trader_stats_as_of("0xabc", _T0 + timedelta(days=1), [trade], markets)
    assert stats.n_trades == 1  # le trade est bien compte (volume, etc.)
    assert stats.n_resolved_trades == 0  # mais aucun reglement ne lui est attribue
    assert stats.realized_pnl is None
    assert stats.win_rate is None


# ---------------------------------------------------------------------------
# Cas reel : Philadelphia Phillies vs. Arizona Diamondbacks (MLB,
# 2026-09-01), wallet 0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6 - donnees
# collectees manuellement (Gamma + Data API reels), demonstration de bout
# en bout deja verifiee avant correctif (jointure re-cleee en memoire) :
# le correctif doit reproduire EXACTEMENT le meme P&L sans aucun
# contournement cote appelant.
# ---------------------------------------------------------------------------

_PHI_MARKET_GAMMA_ID = "3872870"
_PHI_CONDITION_ID = "0xfe0ebcbb0a3de954dcf08c7d1ef0c1333d94a89d7f0effa03591e1f7bb0a0ebc"
_PHI_TOKEN_ID = "20076506283589584596606774059885927045312670930336534845403126008074405160402"
_ARI_TOKEN_ID = "38799544922506389300068682933916779393348159762839076736852549763705619491187"
_PHI_WALLET = "0xe9076a87c5ed90ef16e6fe6529c943baeca0cff6"
_PHI_RESOLUTION_TIME = datetime(2026, 9, 1, 4, 54, 33, tzinfo=timezone.utc)


def _phi_ari_market() -> Market:
    return Market(
        market_id=_PHI_MARKET_GAMMA_ID,
        source="polymarket_gamma_api_manual_browser",
        outcome="Philadelphia Phillies",
        resolution_time=_PHI_RESOLUTION_TIME,
        condition_id=_PHI_CONDITION_ID,
        token_ids=(_PHI_TOKEN_ID, _ARI_TOKEN_ID),
    )


def _phi_ari_trades() -> list[Trade]:
    def t(ts, side, price, size, outcome, token_id):
        return Trade(
            wallet_id=_PHI_WALLET,
            market_id=_PHI_CONDITION_ID,  # payload reel : conditionId, jamais l'id Gamma
            timestamp_utc=ts,
            side=side,
            price=price,
            size=size,
            source="polymarket_data_api_manual_browser",
            outcome=outcome,
            notional=price * size,
            token_id=token_id,
        )

    d = lambda h, m, s: datetime(2026, 9, 1, h, m, s, tzinfo=timezone.utc)
    return [
        # Jambe "Philadelphia Phillies" (issue gagnante) - 7 trades
        t(d(2, 26, 37), "BUY", 0.70, 4081.6286, "Philadelphia Phillies", _PHI_TOKEN_ID),
        t(d(2, 38, 18), "BUY", 0.60, 402.0333, "Philadelphia Phillies", _PHI_TOKEN_ID),
        t(d(3, 27, 28), "BUY", 0.48, 13.8750, "Philadelphia Phillies", _PHI_TOKEN_ID),
        t(d(3, 38, 55), "BUY", 0.69, 710.8261, "Philadelphia Phillies", _PHI_TOKEN_ID),
        t(d(4, 26, 24), "BUY", 0.83, 5.7349, "Philadelphia Phillies", _PHI_TOKEN_ID),
        t(d(4, 33, 19), "BUY", 0.93, 2.0430, "Philadelphia Phillies", _PHI_TOKEN_ID),
        t(d(4, 55, 21), "SELL", 0.999, 4497.5300, "Philadelphia Phillies", _PHI_TOKEN_ID),
        # Jambe "Arizona Diamondbacks" (issue perdante) - 7 trades
        t(d(2, 52, 37), "BUY", 0.38, 37.5789, "Arizona Diamondbacks", _ARI_TOKEN_ID),
        t(d(3, 8, 40), "BUY", 0.36, 7.9167, "Arizona Diamondbacks", _ARI_TOKEN_ID),
        t(d(3, 19, 28), "BUY", 0.38, 5.7100, "Arizona Diamondbacks", _ARI_TOKEN_ID),
        t(d(3, 33, 46), "SELL", 0.27, 7.9100, "Arizona Diamondbacks", _ARI_TOKEN_ID),
        t(d(3, 34, 45), "BUY", 0.28, 23.7857, "Arizona Diamondbacks", _ARI_TOKEN_ID),
        t(d(3, 50, 16), "BUY", 0.27, 52.8889, "Arizona Diamondbacks", _ARI_TOKEN_ID),
        t(d(3, 58, 49), "SELL", 0.18, 5.7100, "Arizona Diamondbacks", _ARI_TOKEN_ID),
    ]


def test_D_real_phillies_diamondbacks_case_yields_exact_expected_pnl() -> None:
    market = _phi_ari_market()
    trades = _phi_ari_trades()
    # Dict des marches cle "naturellement" (par market_id, comme le
    # produirait un simple {m.market_id: m for m in parse_markets(...)})
    # - aucun re-cle manuel par l'appelant (contrainte : pas de
    # contournement metier).
    markets = {market.market_id: market}
    decision_time = datetime(2026, 9, 1, 6, 0, 0, tzinfo=timezone.utc)  # bien apres la resolution

    stats = compute_trader_stats_as_of(_PHI_WALLET, decision_time, trades, markets)

    assert stats.n_trades == 14
    assert stats.n_resolved_trades == 14
    assert stats.realized_pnl == pytest.approx(1572.4171, abs=1e-3)

    # Coherence best-effort via le token ID (contrainte 7) : chaque trade
    # de la jambe gagnante porte bien un token appartenant au marche.
    assert token_id_consistent_with_market(trades[0], market) is True
    assert token_id_consistent_with_market(trades[7], market) is True  # jambe Arizona Diamondbacks


def test_E_pit_settlement_pnl_unavailable_strictly_before_resolution_time() -> None:
    """Avant resolution_time : aucun P&L de reglement disponible. A/apres
    resolution_time : le meme P&L reel exact devient calculable - aucune
    fuite temporelle introduite par le correctif de jointure."""
    market = _phi_ari_market()
    trades = _phi_ari_trades()
    markets = {market.market_id: market}

    decision_before = datetime(2026, 9, 1, 4, 0, 0, tzinfo=timezone.utc)  # < resolution_time (04:54:33)
    stats_before = compute_trader_stats_as_of(_PHI_WALLET, decision_before, trades, markets)
    assert stats_before.n_resolved_trades == 0
    assert stats_before.realized_pnl is None

    decision_after = datetime(2026, 9, 1, 5, 0, 0, tzinfo=timezone.utc)  # >= resolution_time
    stats_after = compute_trader_stats_as_of(_PHI_WALLET, decision_after, trades, markets)
    assert stats_after.n_resolved_trades == 14
    assert stats_after.realized_pnl == pytest.approx(1572.4171, abs=1e-3)


# ---------------------------------------------------------------------------
# token_id_consistent_with_market : verification best-effort independante,
# jamais bloquante faute de donnee.
# ---------------------------------------------------------------------------


def test_token_id_consistent_with_market_true_when_token_belongs_to_market() -> None:
    market = Market(market_id="3872870", source="s", condition_id=_PHI_CONDITION_ID, token_ids=(_PHI_TOKEN_ID, _ARI_TOKEN_ID))
    trade = _trade(market=_PHI_CONDITION_ID, token_id=_PHI_TOKEN_ID)
    assert token_id_consistent_with_market(trade, market) is True


def test_token_id_consistent_with_market_false_when_token_foreign_to_market() -> None:
    market = Market(market_id="3872870", source="s", condition_id=_PHI_CONDITION_ID, token_ids=(_PHI_TOKEN_ID, _ARI_TOKEN_ID))
    trade = _trade(market=_PHI_CONDITION_ID, token_id="0xtoken_dun_autre_marche")
    assert token_id_consistent_with_market(trade, market) is False


def test_token_id_consistent_with_market_none_when_data_missing() -> None:
    market = Market(market_id="m1", source="s")  # pas de token_ids
    trade = _trade()  # pas de token_id
    assert token_id_consistent_with_market(trade, market) is None
