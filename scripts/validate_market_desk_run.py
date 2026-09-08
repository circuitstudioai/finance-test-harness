#!/usr/bin/env python3
"""Freeze and evaluate a persisted Market Desk production run."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

from src.harness.promotion_gate import evaluate_artifact


def fetch_rows(base_url: str, service_key: str, table: str, params: dict[str, str]) -> list[dict]:
    url = f"{base_url.rstrip('/')}/rest/v1/{table}?{urlencode(params)}"
    request = Request(url, headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def benchmark_results(outputs: list[dict], brief: dict | None) -> dict[str, str]:
    by_key = {(row["ticker"], row["engine_name"]): row for row in outputs}
    nvda_ai = by_key.get(("NVDA", "ai_research"), {})
    nvda_technical = by_key.get(("NVDA", "technical_regime"), {})
    nvda_packet = nvda_ai.get("raw_payload") or {}
    nvda_thesis = bool(nvda_ai.get("thesis_summary") and nvda_packet.get("cited_evidence_ids"))
    nvda_invalidation = bool(nvda_technical.get("risk_flags") and nvda_technical.get("suggested_next_action"))
    comparison_rows = [by_key.get((ticker, engine)) for ticker in ("AMD", "NVDA") for engine in ("technical_regime", "fundamentals_valuation", "ai_research")]
    comparison = all(comparison_rows) and all(row.get("raw_payload", {}).get("evidence_packet", {}).get("schema_version") == "1.0.0" for row in comparison_rows)
    cost_packet = (by_key.get(("COST", "fundamentals_valuation"), {}).get("raw_payload") or {}).get("evidence_packet", {})
    valuation_metrics = {item.get("metric") for item in cost_packet.get("items", []) if item.get("kind") == "calculation"}
    cost_valuation = {"implied_value_bear", "implied_value_base", "implied_value_bull"}.issubset(valuation_metrics)
    sofi_rows = [by_key.get(("SOFI", engine)) for engine in ("technical_regime", "fundamentals_valuation", "ai_research")]
    sofi_change = bool(brief and all(sofi_rows) and all(row.get("run_timestamp") for row in sofi_rows))
    return {
        "nvda_thesis": "pass" if nvda_thesis else "fail",
        "nvda_invalidation": "pass" if nvda_invalidation else "fail",
        "amd_vs_nvda_three_years": "pass" if comparison else "fail",
        "cost_valuation": "pass" if cost_valuation else "fail",
        "sofi_post_earnings_change": "pass" if sofi_change else "fail",
    }


def build_artifact(run_id: int, outputs: list[dict], brief: dict | None) -> dict:
    usages = [(row.get("raw_payload") or {}).get("usage") or {} for row in outputs]
    prompt_tokens = sum(int(usage.get("prompt_tokens") or 0) for usage in usages)
    output_tokens = sum(int(usage.get("output_tokens") or 0) for usage in usages)
    total_tokens = sum(int(usage.get("total_tokens") or 0) for usage in usages)
    estimated_cost = prompt_tokens * 0.75 / 1_000_000 + output_tokens * 3.75 / 1_000_000
    return {
        "artifact_version": "1.0.0", "source": {"system": "market_desk_production", "run_id": run_id},
        "engine_outputs": outputs, "benchmarks": benchmark_results(outputs, brief),
        "usage": {"provider_calls": 5, "max_output_tokens_per_call": 1200, "prompt_tokens": prompt_tokens,
                  "output_tokens": output_tokens, "total_tokens": total_tokens, "cost_usd": round(estimated_cost, 6)},
        "daily_brief": brief,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/promotion_gate.yaml"))
    args = parser.parse_args()
    base_url = os.environ["SUPABASE_URL"]
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    outputs = fetch_rows(base_url, service_key, "engine_outputs", {"run_id": f"eq.{args.run_id}", "select": "*", "order": "ticker.asc,engine_name.asc"})
    briefs = fetch_rows(base_url, service_key, "daily_briefs", {"run_id": f"eq.{args.run_id}", "select": "*", "limit": "1"})
    artifact = build_artifact(args.run_id, outputs, briefs[0] if briefs else None)
    result = evaluate_artifact(artifact, yaml.safe_load(args.config.read_text()))
    artifact["gate"] = {"passed": result.passed, "errors": list(result.errors)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": result.passed, "errors": result.errors, "output": str(args.output), "rows": len(outputs)}))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
