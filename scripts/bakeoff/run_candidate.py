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

MODEL = "gemini-3.5-flash"
MAX_OUTPUT_TOKENS = 1200
MAX_PROMPT_CHARS = 60_000


class BudgetExceeded(RuntimeError):
    """Raised before a provider call that exceeds the harness request ceiling."""


def bounded_prompt(messages: Any) -> None:
    size = len(json.dumps(json_safe(messages), ensure_ascii=False))
    if size > MAX_PROMPT_CHARS:
        raise BudgetExceeded(
            f"prompt is {size} characters; harness ceiling is {MAX_PROMPT_CHARS}"
        )


def install_litellm_guard(max_calls: int = 3) -> dict[str, int]:
    """Bound LiteLLM calls before they leave the process."""
    import litellm

    state = {"calls": 0, "depth": 0}

    def wrap(original):
        def guarded(*args, **kwargs):
            outermost = state["depth"] == 0
            if outermost:
                if state["calls"] >= max_calls:
                    raise BudgetExceeded(f"candidate exceeded {max_calls} LLM calls")
                bounded_prompt(kwargs.get("messages", args[1] if len(args) > 1 else []))
                state["calls"] += 1
                requested = kwargs.get("max_tokens", MAX_OUTPUT_TOKENS)
                kwargs["max_tokens"] = min(requested, MAX_OUTPUT_TOKENS)
            state["depth"] += 1
            try:
                return original(*args, **kwargs)
            finally:
                state["depth"] -= 1
        return guarded

    litellm.completion = wrap(litellm.completion)
    litellm.Router.completion = wrap(litellm.Router.completion)
    return state


def install_langchain_google_guard(max_calls: int = 14) -> dict[str, int]:
    """Bound direct LangChain Gemini requests used by the other candidates."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    state = {"calls": 0}

    def wrap(original):
        def guarded(self, messages, *args, **kwargs):
            if state["calls"] >= max_calls:
                raise BudgetExceeded(f"candidate exceeded {max_calls} LLM calls")
            bounded_prompt(messages)
            state["calls"] += 1
            return original(self, messages, *args, **kwargs)
        return guarded

    ChatGoogleGenerativeAI.invoke = wrap(ChatGoogleGenerativeAI.invoke)
    ChatGoogleGenerativeAI.stream = wrap(ChatGoogleGenerativeAI.stream)
    return state


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
    budget = install_langchain_google_guard()
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "llm_provider": "google",
            "quick_think_llm": MODEL,
            "deep_think_llm": MODEL,
            "google_thinking_level": "low",
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "max_recur_limit": 40,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "llm_max_retries": 0,
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
        "usage": {
            "reported": False,
            "provider_calls": budget["calls"],
            "ceilings": {"max_calls": 14, "max_prompt_chars_per_call": MAX_PROMPT_CHARS, "max_output_tokens_per_call": MAX_OUTPUT_TOKENS},
        },
    }


def run_ai_hedge_fund(root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(root))
    import requests
    import hedge_fund.llm.client as hedge_fund_llm
    from hedge_fund.brokers import SimBroker
    from hedge_fund.data.models import CompanyFacts, Price
    from hedge_fund.fund import Fund, FundSpec
    from hedge_fund.pipeline import run_cycle

    # The v2 registry lags the provider's current model catalog and otherwise
    # treats an unknown Gemini id as Anthropic. Keep routing explicit in the
    # harness rather than changing the candidate checkout.
    hedge_fund_llm.provider_for = lambda _: "Google"

    class YahooPriceOnlyClient:
        """Keyless live-price adapter; unsupported fundamentals stay explicitly absent."""

        def get_prices(self, ticker: str, start_date: str, end_date: str, **_: Any) -> list[Price]:
            response = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                params={"range": "1y", "interval": "1d"},
                headers={"User-Agent": "finance-test-harness/1.0"},
                timeout=20,
            )
            response.raise_for_status()
            chart = response.json()["chart"]["result"][0]
            quote = chart["indicators"]["quote"][0]
            rows = []
            for index, timestamp in enumerate(chart["timestamp"]):
                values = {key: quote[key][index] for key in ("open", "close", "high", "low", "volume")}
                if any(value is None for value in values.values()):
                    continue
                rows.append(Price(time=str(timestamp), **values))
            return rows

        def get_financial_metrics(self, *_: Any, **__: Any) -> list[Any]: return []
        def get_news(self, *_: Any, **__: Any) -> list[Any]: return []
        def get_insider_trades(self, *_: Any, **__: Any) -> list[Any]: return []
        def get_earnings_history(self, *_: Any, **__: Any) -> list[Any]: return []
        def get_earnings(self, *_: Any, **__: Any) -> None: return None
        def get_market_cap(self, *_: Any, **__: Any) -> None: return None
        def get_company_facts(self, ticker: str) -> CompanyFacts:
            return CompanyFacts(ticker=ticker, name="Apple Inc.")

    spec = FundSpec.model_validate(
        {
            "name": "harness-value-review",
            "strategies": [{"name": "value", "models": [{"name": "graham"}]}],
            "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1.0},
            "capital": 100000,
            "rebalance": "weekly",
            "benchmark": "SPY",
        }
    )
    result = run_cycle(
        Fund(spec), str(date.today()), SimBroker(cash=spec.capital), YahooPriceOnlyClient(), ["AAPL"]
    )
    return {
        "question": QUESTION,
        "native_task": "AAPL Graham-style value review through the repository's v2 fund pipeline",
        "answer": {"final_weights": result.final_weights, "orders": result.orders, "skipped": result.skipped},
        "evidence": {"strategies": result.strategies, "clamps": result.clamps},
        "usage": {"reported": False, "note": "No LLM call is made when the typed fundamentals snapshot is unavailable"},
    }


def run_daily_stock_analysis(root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(root))
    budget = install_litellm_guard(max_calls=4)
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
            "provider_calls": budget["calls"],
            "ceilings": {
                "max_calls": 4,
                "max_prompt_chars_per_call": MAX_PROMPT_CHARS,
                "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
            },
        },
        "success": result.success,
        "error": result.error,
    }


RUNNERS = {
    "tradingagents": run_tradingagents,
    "ai-hedge-fund": run_ai_hedge_fund,
    "daily-stock-analysis": run_daily_stock_analysis,
}


def smoke_candidate(candidate: str, root: Path) -> dict[str, Any]:
    """Import the integration boundary without constructing clients or calling an LLM."""
    sys.path.insert(0, str(root))
    if candidate == "tradingagents":
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        return {
            "imports": ["tradingagents.default_config", "tradingagents.graph.trading_graph"],
            "entrypoint": TradingAgentsGraph.__name__,
            "configured_provider": DEFAULT_CONFIG.get("llm_provider"),
        }
    if candidate == "ai-hedge-fund":
        from hedge_fund.pipeline import run_cycle

        return {
            "imports": ["hedge_fund.pipeline"],
            "entrypoint": run_cycle.__name__,
            "note": "The upstream v2 package replaced the legacy src.main.run_hedge_fund API; the paid adapter must be migrated.",
        }
    from src.agent.factory import build_agent_executor
    from src.config import get_config

    return {
        "imports": ["src.agent.factory", "src.config"],
        "entrypoint": build_agent_executor.__name__,
        "config_loader": get_config.__name__,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", choices=sorted(RUNNERS))
    parser.add_argument("candidate_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("smoke", "evaluate"), default="smoke")
    args = parser.parse_args()

    started = time.monotonic()
    payload: dict[str, Any] = {
        "candidate": args.candidate,
        "status": "failed",
        "model": MODEL,
        "date": str(date.today()),
        "mode": args.mode,
    }
    try:
        if args.mode == "smoke":
            payload.update(smoke_candidate(args.candidate, args.candidate_root.resolve()))
        else:
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
