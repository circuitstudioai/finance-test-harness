from __future__ import annotations

import pandas as pd
import numpy as np


def buy_hold(prices: pd.DataFrame) -> pd.DataFrame:
    w = pd.DataFrame(1.0 / prices.shape[1], index=prices.index, columns=prices.columns)
    return w


def momentum_20_100(prices: pd.DataFrame) -> pd.DataFrame:
    ma20 = prices.rolling(20).mean()
    ma100 = prices.rolling(100).mean()
    signal = (ma20 > ma100).astype(float)
    denom = signal.sum(axis=1).replace(0, np.nan)
    weights = signal.div(denom, axis=0).fillna(0.0)
    return weights


def mean_reversion_5(prices: pd.DataFrame) -> pd.DataFrame:
    ret5 = prices.pct_change(5)
    ranks = ret5.rank(axis=1, ascending=True, method="average")
    n = prices.shape[1]
    pick = (ranks <= max(1, n // 3)).astype(float)
    denom = pick.sum(axis=1).replace(0, np.nan)
    return pick.div(denom, axis=0).fillna(0.0)


# Placeholder adapters to wire external repo outputs

def tradingagents_proxy(prices: pd.DataFrame) -> pd.DataFrame:
    # TODO: replace with real adapter reading TradingAgents signals
    return momentum_20_100(prices)


def ai_hedge_fund_proxy(prices: pd.DataFrame) -> pd.DataFrame:
    # TODO: replace with real adapter reading ai-hedge-fund signals
    return buy_hold(prices)


def daily_stock_analysis_proxy(prices: pd.DataFrame) -> pd.DataFrame:
    # TODO: replace with real adapter reading daily_stock_analysis outputs
    return mean_reversion_5(prices)


REGISTRY = {
    "buy_hold": buy_hold,
    "momentum_20_100": momentum_20_100,
    "mean_reversion_5": mean_reversion_5,
    "tradingagents_proxy": tradingagents_proxy,
    "ai_hedge_fund_proxy": ai_hedge_fund_proxy,
    "daily_stock_analysis_proxy": daily_stock_analysis_proxy,
}
