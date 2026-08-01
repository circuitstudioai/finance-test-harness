from __future__ import annotations

import argparse
from pathlib import Path
import yaml
import pandas as pd

from .data import load_prices
from .strategies import REGISTRY, set_signal_context
from .backtest import run_backtest, metrics
from .event_study import build_signal_event_report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    set_signal_context(cfg.get("signal_context") or {})
    prices = load_prices(cfg["symbols"], cfg.get("start"), cfg.get("end"))

    results = []
    equity_cols = {}

    for name in cfg["strategies"]:
        fn = REGISTRY[name]
        w = fn(prices)
        eq = run_backtest(prices, w, initial_capital=cfg.get("initial_capital", 100000))
        m = metrics(eq)
        m["strategy"] = name
        results.append(m)
        equity_cols[name] = eq["equity"]

    outdir = Path("results")
    outdir.mkdir(exist_ok=True)

    metrics_df = pd.DataFrame(results).set_index("strategy").sort_values("sharpe", ascending=False)
    metrics_df.to_csv(outdir / "latest_metrics.csv")

    equity_df = pd.DataFrame(equity_cols)
    equity_df.to_csv(outdir / "latest_equity.csv")

    pead_path = (cfg.get("signal_context") or {}).get(
        "pead_yahoo_csv", "results/signals/pead_yahoo_signals.csv"
    )
    event_detail, event_summary = build_signal_event_report(prices, pead_path, outdir=outdir)

    print("\n=== Metrics ===")
    print(metrics_df.round(4))
    if not event_summary.empty:
        print("\n=== Signal Event Study ===")
        print(event_summary.round(4))
    print(f"\nSaved: {outdir / 'latest_metrics.csv'}")
    print(f"Saved: {outdir / 'latest_equity.csv'}")
    if not event_detail.empty:
        print(f"Saved: {outdir / 'latest_signal_events.csv'}")
        print(f"Saved: {outdir / 'latest_signal_event_summary.csv'}")


if __name__ == "__main__":
    main()
