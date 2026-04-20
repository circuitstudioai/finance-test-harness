from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_yahoo_daily(symbol: str, period: str = "5y") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise ValueError(f"No data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance sometimes returns multiindex on single ticker
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns={"Adj Close": "AdjClose"})
    df.index = pd.to_datetime(df.index)
    return df


def load_prices(symbols: list[str], start: str | None, end: str | None) -> pd.DataFrame:
    close_frames = []
    for sym in symbols:
        df = fetch_yahoo_daily(sym)
        if start:
            df = df[df.index >= pd.to_datetime(start)]
        if end:
            df = df[df.index <= pd.to_datetime(end)]
        close_frames.append(df[["Close"]].rename(columns={"Close": sym}))
    prices = pd.concat(close_frames, axis=1).dropna(how="all")
    return prices.ffill().dropna(how="all")
