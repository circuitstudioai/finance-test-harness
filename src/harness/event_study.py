from __future__ import annotations

from pathlib import Path

import pandas as pd


WINDOWS = (1, 5, 20)


def build_signal_event_report(
    prices: pd.DataFrame,
    signals_path: str | Path,
    *,
    benchmark: str = "SPY",
    outdir: str | Path = "results",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Measure forward returns after each rich signal.

    This is intentionally modest: it gives public users a quick event-study
    sanity check without paid point-in-time fundamentals. For each signal we
    report raw signed return and benchmark-adjusted signed return for 1/5/20
    trading-day windows.
    """
    signals_file = Path(signals_path)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    if not signals_file.exists():
        empty = pd.DataFrame()
        return empty, empty

    signals = pd.read_csv(signals_file)
    if signals.empty:
        empty = pd.DataFrame()
        return empty, empty

    px = prices.copy()
    px.index = pd.to_datetime(px.index).normalize()
    bench_available = benchmark in px.columns

    rows: list[dict] = []
    for _, sig in signals.iterrows():
        symbol = str(sig["symbol"]).upper()
        if symbol not in px.columns:
            continue
        signal_date = pd.to_datetime(sig["date"]).normalize()
        if signal_date not in px.index:
            later = px.index[px.index > signal_date]
            if later.empty:
                continue
            signal_date = later[0]

        idx = px.index.get_loc(signal_date)
        direction = 1 if float(sig["conviction"]) > 0 else -1
        entry = px.iloc[idx][symbol]
        if pd.isna(entry) or entry <= 0:
            continue

        row = {
            "date": signal_date.date().isoformat(),
            "symbol": symbol,
            "model": sig.get("model", ""),
            "decision": sig.get("decision", ""),
            "conviction": sig.get("conviction", ""),
            "confidence": sig.get("confidence", ""),
            "reasoning": sig.get("reasoning", ""),
        }

        for days in WINDOWS:
            exit_idx = idx + days
            if exit_idx >= len(px.index):
                row[f"signed_return_{days}d"] = ""
                row[f"benchmark_adjusted_{days}d"] = ""
                continue
            exit_price = px.iloc[exit_idx][symbol]
            raw = exit_price / entry - 1
            signed = direction * raw
            row[f"signed_return_{days}d"] = signed

            if bench_available:
                b_entry = px.iloc[idx][benchmark]
                b_exit = px.iloc[exit_idx][benchmark]
                bench_ret = b_exit / b_entry - 1 if b_entry > 0 else 0.0
                row[f"benchmark_adjusted_{days}d"] = signed - bench_ret
            else:
                row[f"benchmark_adjusted_{days}d"] = ""

        rows.append(row)

    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail, pd.DataFrame()

    summary_rows = []
    for days in WINDOWS:
        col = f"signed_return_{days}d"
        adj_col = f"benchmark_adjusted_{days}d"
        vals = pd.to_numeric(detail[col], errors="coerce").dropna()
        adj = pd.to_numeric(detail[adj_col], errors="coerce").dropna()
        summary_rows.append(
            {
                "window": f"{days}d",
                "n_events": int(vals.count()),
                "mean_signed_return": float(vals.mean()) if not vals.empty else 0.0,
                "hit_rate": float((vals > 0).mean()) if not vals.empty else 0.0,
                "mean_benchmark_adjusted": float(adj.mean()) if not adj.empty else 0.0,
            }
        )

    summary = pd.DataFrame(summary_rows)
    detail.to_csv(out / "latest_signal_events.csv", index=False)
    summary.to_csv(out / "latest_signal_event_summary.csv", index=False)
    return detail, summary
