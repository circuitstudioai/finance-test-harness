import unittest

from src.harness.engine_adapters import ai_research_engine, fundamentals_engine, technical_engine
from src.harness.evidence import EvidenceItem, EvidenceKind, EvidencePacket, Source
from src.harness.valuation import MultipleScenario, revenue_multiple_scenarios
from src.harness.validators import Claim


class EngineAdapterTests(unittest.TestCase):
    def test_technical_engine_normalizes_output(self):
        output = technical_engine(7, "aapl", range(100, 221), "2026-09-07T00:00:00Z")
        self.assertEqual(output.direction, "bullish")
        self.assertEqual(output.engine_name, "technical_regime")
        self.assertEqual(output.to_dict()["raw_payload"]["evidence_packet"]["schema_version"], "1.0.0")
        self.assertEqual(output.raw_payload["category_views"]["trend"]["direction"], "bullish")

    def test_fundamentals_engine_uses_scenario_range(self):
        packet = EvidencePacket("AAPL", "2026-09-07T00:00:00Z", (), "sec_fundamentals")
        valuations = revenue_multiple_scenarios("AAPL", 1000, 100, (
            MultipleScenario("bear", 0, 2), MultipleScenario("base", .1, 3), MultipleScenario("bull", .2, 4)
        ))
        output = fundamentals_engine(7, packet, valuations, 20)
        self.assertEqual(output.direction, "bullish")
        self.assertEqual(output.engine_name, "fundamentals_valuation")
        self.assertEqual(output.raw_payload["category_views"]["valuation"]["direction"], "bullish")

    def test_ai_research_rejects_uncited_fact(self):
        packet = EvidencePacket("AAPL", "2026-09-07T00:00:00Z", (), "research")
        with self.assertRaisesRegex(ValueError, "requires evidence_ids"):
            ai_research_engine(7, packet, (Claim("Revenue grew", EvidenceKind.FACT),), view="neutral", confidence=50, thesis="Mixed")

    def test_ai_research_accepts_supported_fact(self):
        item = EvidenceItem("fact-1", EvidenceKind.FACT, "revenue", 100, "USD", "AAPL", "FY2025", .9, 0,
                            source=Source("sec", "https://sec.gov", "2026-09-07T00:00:00Z"))
        packet = EvidencePacket("AAPL", "2026-09-07T00:00:00Z", (item,), "research")
        output = ai_research_engine(7, packet, (Claim("Revenue was 100", EvidenceKind.FACT, ("fact-1",)),),
                                    view="neutral", confidence=60, thesis="Mixed")
        self.assertEqual(output.raw_payload["cited_evidence_ids"], ["fact-1"])


if __name__ == "__main__":
    unittest.main()
