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


def load_earnings_surprises(symbol: str, limit: int = 24) -> pd.DataFrame:
    """Load Yahoo earnings surprises for one symbol.

    This is the public/no-key data path. Yahoo normally returns EPS estimate,
    reported EPS, and surprise percentage. Future rows have missing reported EPS
    and are filtered out by strategy code.
    """
    df = yf.Ticker(symbol).get_earnings_dates(limit=limit)
    if df is None or df.empty:
        return pd.DataFrame(
            columns=["date", "symbol", "eps_estimate", "reported_eps", "surprise_pct"]
        )

    out = df.reset_index().rename(
        columns={
            "Earnings Date": "date",
            "EPS Estimate": "eps_estimate",
            "Reported EPS": "reported_eps",
            "Surprise(%)": "surprise_pct",
        }
    )
    out["date"] = pd.to_datetime(out["date"], utc=True).dt.tz_convert(None).dt.normalize()
    out["symbol"] = symbol.upper()
    for col in ["eps_estimate", "reported_eps", "surprise_pct"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out[["date", "symbol", "eps_estimate", "reported_eps", "surprise_pct"]]
