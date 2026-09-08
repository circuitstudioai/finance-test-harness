import unittest

from scripts.validate_market_desk_run import benchmark_results


def row(ticker, engine, **extra):
    value = {"ticker": ticker, "engine_name": engine, "run_timestamp": "2026-09-08T00:00:00Z", "raw_payload": {"evidence_packet": {"schema_version": "1.0.0"}}}
    value.update(extra)
    return value


class MarketDeskValidationTests(unittest.TestCase):
    def test_benchmarks_require_grounded_outputs(self):
        outputs = [row(ticker, engine) for ticker in ("AMD", "NVDA", "SOFI") for engine in ("technical_regime", "fundamentals_valuation", "ai_research")]
        nvda_ai = next(value for value in outputs if value["ticker"] == "NVDA" and value["engine_name"] == "ai_research")
        nvda_ai.update({"thesis_summary": "Grounded thesis", "raw_payload": {"evidence_packet": {"schema_version": "1.0.0"}, "cited_evidence_ids": ["fact"]}})
        nvda_technical = next(value for value in outputs if value["ticker"] == "NVDA" and value["engine_name"] == "technical_regime")
        nvda_technical.update({"risk_flags": ["risk"], "suggested_next_action": "monitor"})
        outputs.append(row("COST", "fundamentals_valuation", raw_payload={"evidence_packet": {"schema_version": "1.0.0", "items": [{"kind": "calculation", "metric": f"implied_value_{name}"} for name in ("bear", "base", "bull")]}}))
        self.assertEqual(set(benchmark_results(outputs, {"summary": "brief"}).values()), {"pass"})


if __name__ == "__main__":
    unittest.main()
