# finance-test-harness

Lightweight test harness to evaluate trading ideas before risking capital.

## What it does
- Pulls daily OHLC data from Stooq (no API key required)
- Runs strategy adapters (baseline + placeholder adapters for AI repos)
- Produces comparable metrics:
  - CAGR
  - Sharpe (daily, rf=0)
  - Max Drawdown
  - Win rate
  - Total return
- Writes outputs to `results/`.

## Included strategies
- `buy_hold` (benchmark)
- `momentum_20_100` (simple trend)
- `mean_reversion_5` (simple reversal)
- `tradingagents_proxy` (placeholder adapter)
- `ai_hedge_fund_proxy` (placeholder adapter)
- `daily_stock_analysis_proxy` (placeholder adapter)

> The three `*_proxy` adapters are drop-in placeholders where we’ll wire outputs from your forked repos.

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.harness.run --config config/default.yaml
```

## Output
- `results/latest_metrics.csv`
- `results/latest_equity.csv`

## Next wiring steps
1. Clone and run forked repos in separate folders.
2. Write adapters that read each repo's output signal format.
3. Replace proxy adapters with live adapters and rerun.
