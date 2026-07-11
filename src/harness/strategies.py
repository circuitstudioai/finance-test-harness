from __future__ import annotations

import pandas as pd
import numpy as np

from .adapters import load_signal_csv, weights_from_signals
from .data import load_earnings_surprises


SIGNAL_CONTEXT: dict = {}


def set_signal_context(ctx: dict | None) -> None:
    global SIGNAL_CONTEXT
    SIGNAL_CONTEXT = ctx or {}


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
    # Legacy proxy baseline
    return momentum_20_100(prices)


def ai_hedge_fund_proxy(prices: pd.DataFrame) -> pd.DataFrame:
    # Legacy proxy baseline
    return buy_hold(prices)


def daily_stock_analysis_proxy(prices: pd.DataFrame) -> pd.DataFrame:
    # Legacy proxy baseline
    return mean_reversion_5(prices)


def tradingagents_true(prices: pd.DataFrame) -> pd.DataFrame:
    path = SIGNAL_CONTEXT.get("tradingagents_csv")
    if not path:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    signals = load_signal_csv(path)
    return weights_from_signals(prices, signals)


def daily_stock_analysis_true(prices: pd.DataFrame) -> pd.DataFrame:
    path = SIGNAL_CONTEXT.get("daily_stock_analysis_csv")
    if not path:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    signals = load_signal_csv(path)
    return weights_from_signals(prices, signals)


def pead_yahoo(prices: pd.DataFrame) -> pd.DataFrame:
    """Post-earnings announcement drift using Yahoo's free EPS surprise data.

    Long positive EPS surprises, short negative surprises, hold each signal for
    a small fixed window, and emit an auditable rich-signal CSV.
    """
    holding_days = int(SIGNAL_CONTEXT.get("pead_holding_days", 5))
    min_abs_surprise = float(SIGNAL_CONTEXT.get("pead_min_abs_surprise_pct", 2.0))
    earnings_limit = int(SIGNAL_CONTEXT.get("pead_earnings_limit", 24))
    out_path = SIGNAL_CONTEXT.get("pead_yahoo_csv", "results/signals/pead_yahoo_signals.csv")
    excluded = {
        str(s).upper()
        for s in SIGNAL_CONTEXT.get("pead_exclude_symbols", ["SPY", "QQQ"])
    }

    idx = prices.index.normalize()
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    active = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    signal_rows: list[dict] = []

    for symbol in prices.columns:
        if symbol.upper() in excluded:
            continue
        try:
            events = load_earnings_surprises(symbol, limit=earnings_limit)
        except Exception as exc:
            signal_rows.append(
                {
                    "date": "",
                    "symbol": symbol,
                    "model": "pead_yahoo",
                    "decision": "abstain",
                    "conviction": 0.0,
                    "confidence": 0.0,
                    "reasoning": f"abstained: Yahoo earnings data unavailable ({exc})",
                    "metadata": "{}",
                }
            )
            continue

        events = events.dropna(subset=["reported_eps", "surprise_pct"])
        events = events[events["surprise_pct"].abs() >= min_abs_surprise]
        events = events.sort_values("date")

        for _, event in events.iterrows():
            event_date = pd.to_datetime(event["date"]).normalize()
            if event_date < idx.min() or event_date > idx.max():
                continue
            candidates = idx[idx > event_date]
            if candidates.empty:
                continue
            signal_date = candidates[0]
            start_pos = prices.index.get_loc(signal_date)
            end_pos = min(start_pos + holding_days, len(prices.index) - 1)
            if end_pos <= start_pos:
                continue

            surprise = float(event["surprise_pct"])
            conviction = float(max(-1.0, min(1.0, surprise / 20.0)))
            confidence = float(min(0.95, 0.45 + abs(surprise) / 100.0))
            decision = "buy" if conviction > 0 else "sell"
            active.iloc[start_pos : end_pos + 1, active.columns.get_loc(symbol)] += conviction

            signal_rows.append(
                {
                    "date": signal_date.date().isoformat(),
                    "symbol": symbol,
                    "model": "pead_yahoo",
                    "decision": decision,
                    "conviction": round(conviction, 4),
                    "confidence": round(confidence, 4),
                    "reasoning": (
                        f"EPS surprise {surprise:.2f}% after earnings on "
                        f"{event_date.date().isoformat()}; hold {holding_days} trading days"
                    ),
                    "metadata": (
                        "{"
                        f"\"eps_estimate\":{event['eps_estimate']},"
                        f"\"reported_eps\":{event['reported_eps']},"
                        f"\"surprise_pct\":{surprise:.4f}"
                        "}"
                    ),
                }
            )

    gross = active.abs().sum(axis=1).replace(0, np.nan)
    weights = active.div(gross, axis=0).fillna(0.0)

    out = pd.DataFrame(
        signal_rows,
        columns=[
            "date",
            "symbol",
            "model",
            "decision",
            "conviction",
            "confidence",
            "reasoning",
            "metadata",
        ],
    )
    path = pd.io.common.stringify_path(out_path)
    pd.io.common.check_parent_directory(path)
    out.to_csv(path, index=False)
    return weights


REGISTRY = {
    "buy_hold": buy_hold,
    "momentum_20_100": momentum_20_100,
    "mean_reversion_5": mean_reversion_5,
    "tradingagents_proxy": tradingagents_proxy,
    "ai_hedge_fund_proxy": ai_hedge_fund_proxy,
    "daily_stock_analysis_proxy": daily_stock_analysis_proxy,
    "tradingagents_true": tradingagents_true,
    "daily_stock_analysis_true": daily_stock_analysis_true,
    "pead_yahoo": pead_yahoo,
}
