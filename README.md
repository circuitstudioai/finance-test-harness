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
- `results/external_bench_latest.csv`

## True signal adapters (implemented)
The harness now supports **real signal CSV adapters**:
- `tradingagents_true`
- `daily_stock_analysis_true`

Signal files expected:
- `results/signals/tradingagents_signals.csv`
- `results/signals/daily_stock_analysis_signals.csv`

CSV schema:
```csv
date,symbol,decision
2026-04-15,AMD,buy
2026-04-15,SOFI,hold
2026-04-15,HIMS,sell
```
Allowed decisions: `buy|hold|sell` (case-insensitive variants accepted).

### Build signal CSVs from external outputs
TradingAgents report extractor:
```bash
python -m src.harness.signal_extractors tradingagents \
  --reports-root external/TradingAgents \
  --out results/signals/tradingagents_signals.csv
```

Daily-stock-analysis JSON extractor:
```bash
python -m src.harness.signal_extractors daily \
  --json-root external/daily_stock_analysis \
  --out results/signals/daily_stock_analysis_signals.csv
```

Then run:
```bash
python -m src.harness.run --config config/default.yaml
```

## Metric definitions (plain English)
- **Total return**: overall gain/loss over test period.
- **CAGR** (Compound Annual Growth Rate): annualized growth rate if growth were smooth. Good for comparing different periods.
- **Sharpe**: return per unit of volatility (higher is generally better).
- **Max drawdown**: worst peak-to-trough drop. This is your pain metric.
- **Win rate**: % of days with positive return (not the same as profitability by itself).

## Notes on current results
- Proxy strategies are baseline placeholders.
- True adapters only become meaningful once signal CSVs contain real model decisions across many dates.
- If a true adapter has no signals, it stays in cash for those dates.
