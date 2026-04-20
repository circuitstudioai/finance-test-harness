from __future__ import annotations

import argparse
from pathlib import Path
import yaml
import pandas as pd

from .data import load_prices
from .strategies import REGISTRY
from .backtest import run_backtest, metrics


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
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

    print("\n=== Metrics ===")
    print(metrics_df.round(4))
    print(f"\nSaved: {outdir / 'latest_metrics.csv'}")
    print(f"Saved: {outdir / 'latest_equity.csv'}")


if __name__ == "__main__":
    main()
