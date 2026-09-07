import unittest

from src.harness.evidence import EvidenceKind, EvidencePacket
from src.harness.sec_fundamentals import SecClient
from src.harness.valuation import MultipleScenario, revenue_multiple_scenarios
from src.harness.validators import Claim, validate_claims


class Response:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload


class Session:
    def get(self, url, **kwargs):
        if "company_tickers" in url:
            return Response({"0": {"ticker": "AAPL", "cik_str": 320193}})
        return Response({"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [
            {"val": 100, "filed": "2026-08-01", "end": "2026-06-30", "fy": 2026, "form": "10-Q", "accn": "x"}
        ]}}}}})


class FundamentalsValuationTests(unittest.TestCase):
    def test_sec_adapter_emits_present_and_missing_evidence(self):
        packet = SecClient("test@example.com", Session()).evidence_packet(
            "aapl", retrieved_at="2026-09-07T00:00:00Z"
        )
        income = next(item for item in packet.items if item.metric == "net_income")
        revenue = next(item for item in packet.items if item.metric == "revenue")
        self.assertEqual(income.value, 100)
        self.assertEqual(income.source.provider, "sec_companyfacts")
        self.assertEqual(revenue.missing_status.value, "unavailable")

    def test_valuation_is_reproducible(self):
        items = revenue_multiple_scenarios("AAPL", 1000, 100, (
            MultipleScenario("bear", 0, 2),
            MultipleScenario("base", .1, 3),
            MultipleScenario("bull", .2, 4),
        ))
        self.assertEqual([item.value for item in items], [20.0, 33.0, 48.0])
        self.assertEqual(items[1].calculation.inputs["growth_rate"], .1)

    def test_claim_validator_rejects_unsupported_fact(self):
        item = revenue_multiple_scenarios("AAPL", 1000, 100, (MultipleScenario("base", .1, 3),))[0]
        packet = EvidencePacket("AAPL", "2026-09-07T00:00:00Z", (item,), "valuation")
        errors = validate_claims(packet, (Claim("Revenue rose", EvidenceKind.FACT, ("missing",)),))
        self.assertIn("claims[0] references unknown evidence missing", errors)

    def test_supported_calculation_passes(self):
        item = revenue_multiple_scenarios("AAPL", 1000, 100, (MultipleScenario("base", .1, 3),))[0]
        packet = EvidencePacket("AAPL", "2026-09-07T00:00:00Z", (item,), "valuation")
        self.assertEqual(validate_claims(packet, (Claim("Base value is $33", EvidenceKind.CALCULATION, (item.id,)),)), [])


if __name__ == "__main__":
    unittest.main()
