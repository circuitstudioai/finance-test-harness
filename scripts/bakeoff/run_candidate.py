from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path
from typing import Any


QUESTION = (
    "Build a plain-English investment thesis for AAPL for a self-directed investor "
    "with a three-year horizon. Separate facts from interpretation, give bull/base/bear "
    "cases, identify the strongest risks, and state measurable thesis-invalidation conditions."
)


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_safe(v) for v in value]
        return str(value)


def run_tradingagents(root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(root))
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "llm_provider": "google",
            "quick_think_llm": "gemini-3-flash-preview",
            "deep_think_llm": "gemini-3-flash-preview",
            "google_thinking_level": "low",
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "max_recur_limit": 40,
            "results_dir": str(Path.cwd() / "candidate-output"),
        }
    )
    graph = TradingAgentsGraph(
        selected_analysts=["market", "fundamentals"],
        debug=False,
        config=config,
    )
    state, decision = graph.propagate("AAPL", str(date.today()))
    return {
        "question": QUESTION,
        "native_task": "Full AAPL research with market and fundamentals analysts plus built-in bull/bear and risk review",
        "answer": decision,
        "evidence": {
            "market_report": state.get("market_report"),
            "fundamentals_report": state.get("fundamentals_report"),
            "bull_bear_judgment": (state.get("investment_debate_state") or {}).get("judge_decision"),
            "risk_judgment": (state.get("risk_debate_state") or {}).get("judge_decision"),
            "investment_plan": state.get("investment_plan"),
        },
        "usage": {"reported": False, "note": "Candidate does not expose aggregate tokens/cost in this entry point"},
    }


def run_ai_hedge_fund(root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(root))
    from src.main import run_hedge_fund

    ticker = "AAPL"
    portfolio = {
        "cash": 100000.0,
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": {ticker: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0, "short_margin_used": 0.0}},
        "realized_gains": {ticker: {"long": 0.0, "short": 0.0}},
    }
    result = run_hedge_fund(
        tickers=[ticker],
        start_date=str(date.today() - timedelta(days=120)),
        end_date=str(date.today()),
        portfolio=portfolio,
        show_reasoning=False,
        selected_analysts=["technical_analyst", "fundamentals_analyst", "valuation_analyst"],
        model_name="gemini-3-flash-preview",
        model_provider="Google",
    )
    return {
        "question": QUESTION,
        "native_task": "AAPL technical, fundamental, and valuation analysis plus built-in risk and portfolio decision",
        "answer": result.get("decisions"),
        "evidence": result.get("analyst_signals"),
        "usage": {"reported": False, "note": "Candidate does not expose aggregate tokens/cost in this entry point"},
    }


def run_daily_stock_analysis(root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(root))
    from src.agent.factory import build_agent_executor
    from src.config import get_config

    config = get_config()
    executor = build_agent_executor(config=config, skills=[])
    result = executor.chat(
        message=QUESTION,
        session_id="finance-harness-bakeoff-aapl",
        context={"stock_code": "AAPL", "stock_name": "Apple Inc."},
    )
    return {
        "question": QUESTION,
        "native_task": "Direct conversational AAPL thesis request using the repository's finance tool registry",
        "answer": result.content,
        "evidence": {"tool_calls": result.tool_calls_log, "dashboard": result.dashboard},
        "usage": {
            "reported": True,
            "total_tokens": result.total_tokens,
            "steps": result.total_steps,
            "provider": result.provider,
            "model": result.model,
        },
        "success": result.success,
        "error": result.error,
    }


RUNNERS = {
    "tradingagents": run_tradingagents,
    "ai-hedge-fund": run_ai_hedge_fund,
    "daily-stock-analysis": run_daily_stock_analysis,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", choices=sorted(RUNNERS))
    parser.add_argument("candidate_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    started = time.monotonic()
    payload: dict[str, Any] = {
        "candidate": args.candidate,
        "status": "failed",
        "model": "gemini-3-flash-preview",
        "date": str(date.today()),
    }
    try:
        payload.update(RUNNERS[args.candidate](args.candidate_root.resolve()))
        payload["status"] = "completed"
    except Exception as exc:  # Preserve failures as comparable bake-off evidence.
        payload["error"] = f"{type(exc).__name__}: {exc}"
        payload["traceback"] = traceback.format_exc()
    finally:
        payload["latency_seconds"] = round(time.monotonic() - started, 2)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(json_safe(payload), indent=2), encoding="utf-8")
        print(json.dumps(json_safe(payload), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
