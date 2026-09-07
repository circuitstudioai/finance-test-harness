"""Deterministic release gate for integrated multi-engine artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GateResult:
    passed: bool
    errors: tuple[str, ...]


def evaluate_artifact(artifact: dict[str, Any], config: dict[str, Any]) -> GateResult:
    errors: list[str] = []
    outputs = artifact.get("engine_outputs")
    if not isinstance(outputs, list):
        return GateResult(False, ("engine_outputs must be a list",))

    required_engines = set(config["required_engines"])
    required_benchmarks = set(config["required_benchmarks"])
    required_tickers = set(config["multi_stock_universe"])
    limits = config["limits"]

    engines = {row.get("engine_name") for row in outputs}
    tickers = {row.get("ticker") for row in outputs}
    missing_engines = sorted(required_engines - engines)
    missing_tickers = sorted(required_tickers - tickers)
    if missing_engines:
        errors.append("missing engines: " + ", ".join(missing_engines))
    if missing_tickers:
        errors.append("missing tickers: " + ", ".join(missing_tickers))

    benchmarks = artifact.get("benchmarks", {})
    failed_benchmarks = sorted(name for name in required_benchmarks if benchmarks.get(name) != "pass")
    if failed_benchmarks:
        errors.append("benchmarks not passing: " + ", ".join(failed_benchmarks))

    usage = artifact.get("usage", {})
    for key in ("provider_calls", "max_output_tokens_per_call", "total_tokens", "cost_usd"):
        if not isinstance(usage.get(key), (int, float)):
            errors.append(f"usage.{key} is required")
    comparisons = {
        "provider_calls": "max_provider_calls",
        "max_output_tokens_per_call": "max_output_tokens_per_call",
        "total_tokens": "max_total_tokens",
        "cost_usd": "max_cost_usd",
    }
    for actual_key, limit_key in comparisons.items():
        actual = usage.get(actual_key)
        if isinstance(actual, (int, float)) and actual > limits[limit_key]:
            errors.append(f"usage.{actual_key} exceeds {limits[limit_key]}")

    for index, row in enumerate(outputs):
        raw = row.get("raw_payload")
        if not isinstance(raw, dict):
            errors.append(f"engine_outputs[{index}].raw_payload is required")
            continue
        packet = raw.get("evidence_packet", raw)
        if packet.get("schema_version") != "1.0.0":
            errors.append(f"engine_outputs[{index}] lacks evidence schema 1.0.0")
        if row.get("direction") not in {"bullish", "neutral", "bearish"}:
            errors.append(f"engine_outputs[{index}] has invalid direction")
        confidence = row.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 100:
            errors.append(f"engine_outputs[{index}] has invalid confidence")

    return GateResult(not errors, tuple(errors))
