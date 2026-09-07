# finance-test-harness

Lightweight test harness to evaluate trading ideas before risking capital.

## Evidence contract

Finance engines exchange evidence through the versioned `EvidencePacket` contract
in `src/harness/evidence.py`. Each fact records its ticker, period, units, source,
retrieval/publication timestamps, confidence, freshness, and missing-data state.
Calculated values additionally carry the method, formula, and complete inputs.
Engines should validate packets before emitting them and abstain when required
evidence is unavailable. A stable v1 example lives at
`tests/fixtures/evidence_packet_v1.json`.

`SecClient` in `src/harness/sec_fundamentals.py` retrieves primary-source SEC
Company Facts with the SEC-required identifying user agent. The deterministic
valuation helpers in `src/harness/valuation.py` expose every assumption, formula,
and input. `validate_claims` prevents factual or calculated claims from reaching
the presentation layer without corresponding packet evidence.

The stable Market Desk boundary is `src/harness/engine_adapters.py`. It exposes
three deliberately different engines—technical regime, fundamentals/valuation,
and evidence-constrained AI research—and normalizes each into the existing
Market Desk ingest shape. The AI adapter refuses uncited factual claims.

`config/promotion_gate.yaml` freezes the five benchmark questions, 20-symbol
evaluation universe, required engines, and request budgets. The deterministic
gate in `src/harness/promotion_gate.py` rejects incomplete engine coverage,
failed benchmarks, invalid output contracts, or over-budget runs.

## What it does
- Pulls daily OHLC data from Yahoo Finance (no API key required)
- Runs strategy adapters (baseline, true CSV adapters, and a no-key PEAD strategy)
- Produces comparable metrics:
  - CAGR
  - Sharpe (daily, rf=0)
  - Max Drawdown
  - Win rate
  - Total return
- Produces a signal event-study report for rich signal strategies:
  - 1/5/20 trading-day signed forward returns
  - SPY-adjusted forward returns when SPY is in the universe
  - Hit rate by window
- Writes outputs to `results/`.

## Included strategies
- `buy_hold` (benchmark)
- `momentum_20_100` (simple trend)
- `mean_reversion_5` (simple reversal)
- `pead_yahoo` (real no-key post-earnings drift strategy using Yahoo EPS surprises)
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
- `results/signals/pead_yahoo_signals.csv`
- `results/latest_signal_events.csv`
- `results/latest_signal_event_summary.csv`
- `results/external_bench_latest.csv`

## Circuit Analyst evidence export
Circuit Analyst can display harness-backed evidence badges from the PEAD event
study. After running the harness, export the app fixture with:
```bash
python -m src.harness.export_app_evidence \
  --output ../circuit-analyst-mvp/web/public/research/pead_yahoo_evidence.json
```

The export contains the 1/5/20-day event-study summary plus the latest PEAD
event by symbol. It is safe for the public demo because it contains derived
research output, not provider keys.

## PEAD strategy
`pead_yahoo` is inspired by the ai-hedge-fund v2 alpha-model pattern:
an analyst model emits a directional view, and the harness converts that view
into deterministic portfolio weights.

The public default uses Yahoo earnings data, so it works without paid keys.
For each stock:
- read recent EPS estimate, reported EPS, and surprise percentage
- ignore future/unreported rows
- buy positive surprises and sell negative surprises above the configured threshold
- hold for a fixed number of trading days
- write an auditable rich-signal CSV with conviction, confidence, reasoning, and metadata

Config knobs live under `signal_context` in `config/default.yaml`:
```yaml
pead_yahoo_csv: "results/signals/pead_yahoo_signals.csv"
pead_holding_days: 5
pead_min_abs_surprise_pct: 2.0
pead_earnings_limit: 24
pead_exclude_symbols: ["SPY", "QQQ"]
```

This is decision-support research infrastructure, not financial advice and not
an auto-trading system.

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
- `pead_yahoo` is real but intentionally modest: Yahoo data is convenient, not a professional point-in-time fundamentals feed. A paid Financial Datasets adapter can be added later behind the same signal contract.
