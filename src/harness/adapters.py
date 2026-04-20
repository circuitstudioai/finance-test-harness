from __future__ import annotations

from pathlib import Path
import pandas as pd


BULLISH = {"buy", "strong_buy", "overweight", "long"}
NEUTRAL = {"hold", "neutral"}
BEARISH = {"sell", "strong_sell", "underweight", "short"}


def normalize_decision(x: str) -> str:
    v = (x or "").strip().lower()
    if v in BULLISH:
        return "buy"
    if v in BEARISH:
        return "sell"
    if v in NEUTRAL:
        return "hold"
    # Some report text variants
    if "buy" in v:
        return "buy"
    if "sell" in v:
        return "sell"
    return "hold"


def load_signal_csv(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["date", "symbol", "decision"])
    df = pd.read_csv(p)
    required = {"date", "symbol", "decision"}
    if not required.issubset(df.columns):
        raise ValueError(f"Signal file missing columns {required}: {p}")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["decision"] = df["decision"].astype(str).map(normalize_decision)
    return df[["date", "symbol", "decision"]]


def weights_from_signals(prices: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    idx = prices.index.normalize()
    cols = prices.columns
    w = pd.DataFrame(0.0, index=prices.index, columns=cols)

    if signals.empty:
        return w

    signals = signals.sort_values(["date", "symbol"])  # deterministic

    for dt in sorted(signals["date"].unique()):
        dmask = idx == dt
        if not dmask.any():
            continue
        day = signals[signals["date"] == dt]
        buys = [s for s in day.loc[day["decision"] == "buy", "symbol"].tolist() if s in cols]
        # If no buys, stay in cash for that day.
        if buys:
            weight = 1.0 / len(buys)
            w.loc[dmask, buys] = weight
    return w
