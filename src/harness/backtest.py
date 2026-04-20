from __future__ import annotations

import numpy as np
import pandas as pd


def run_backtest(prices: pd.DataFrame, weights: pd.DataFrame, initial_capital: float = 100000) -> pd.DataFrame:
    rets = prices.pct_change().fillna(0.0)
    w = weights.reindex(prices.index).ffill().fillna(0.0)
    strat_ret = (w.shift(1).fillna(0.0) * rets).sum(axis=1)
    equity = (1 + strat_ret).cumprod() * initial_capital
    out = pd.DataFrame({"ret": strat_ret, "equity": equity}, index=prices.index)
    return out


def metrics(equity_df: pd.DataFrame) -> dict:
    ret = equity_df["ret"]
    eq = equity_df["equity"]
    total_return = eq.iloc[-1] / eq.iloc[0] - 1
    n = len(ret)
    years = max(n / 252, 1e-9)
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    vol = ret.std() * np.sqrt(252)
    sharpe = (ret.mean() * 252) / vol if vol > 0 else 0.0
    dd = eq / eq.cummax() - 1
    max_dd = dd.min()
    win_rate = (ret > 0).mean()
    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "win_rate": float(win_rate),
    }
