import unittest

from src.harness.promotion_gate import evaluate_artifact


CONFIG = {
    "required_engines": ["technical_regime", "fundamentals_valuation", "ai_research"],
    "required_benchmarks": ["q1", "q2"],
    "multi_stock_universe": ["AAPL", "NVDA"],
    "limits": {"max_provider_calls": 6, "max_output_tokens_per_call": 1200, "max_total_tokens": 12000, "max_cost_usd": .5},
}


def row(engine, ticker):
    return {"engine_name": engine, "ticker": ticker, "direction": "neutral", "confidence": 60,
            "raw_payload": {"schema_version": "1.0.0"}}


class PromotionGateTests(unittest.TestCase):
    def test_complete_artifact_passes(self):
        artifact = {
            "engine_outputs": [row(engine, ticker) for engine in CONFIG["required_engines"] for ticker in ("AAPL", "NVDA")],
            "benchmarks": {"q1": "pass", "q2": "pass"},
            "usage": {"provider_calls": 4, "max_output_tokens_per_call": 1000, "total_tokens": 8000, "cost_usd": .2},
        }
        self.assertTrue(evaluate_artifact(artifact, CONFIG).passed)

    def test_incomplete_and_over_budget_artifact_fails(self):
        artifact = {"engine_outputs": [row("technical_regime", "AAPL")], "benchmarks": {"q1": "pass"},
                    "usage": {"provider_calls": 7, "max_output_tokens_per_call": 1000, "total_tokens": 8000, "cost_usd": .2}}
        result = evaluate_artifact(artifact, CONFIG)
        self.assertFalse(result.passed)
        self.assertTrue(any("missing engines" in error for error in result.errors))
        self.assertTrue(any("benchmarks" in error for error in result.errors))
        self.assertTrue(any("exceeds" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
