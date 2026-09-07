import unittest

from src.harness.evidence import (
    Calculation,
    EvidenceItem,
    EvidenceKind,
    EvidencePacket,
    MissingStatus,
    Source,
    validate_packet,
)


class EvidencePacketTests(unittest.TestCase):
    def test_valid_packet(self):
        packet = EvidencePacket(
            ticker="AAPL",
            as_of="2026-09-07T00:00:00Z",
            engine="fundamentals",
            items=(EvidenceItem(
                id="revenue-fy2025",
                kind=EvidenceKind.FACT,
                metric="revenue",
                value=100,
                unit="USD",
                ticker="AAPL",
                period="FY2025",
                confidence=0.95,
                freshness_seconds=100,
                source=Source("sec", "https://www.sec.gov/", "2026-09-07T00:00:00Z"),
            ),),
        )
        self.assertEqual(validate_packet(packet), [])
        self.assertEqual(packet.to_dict()["schema_version"], "1.0.0")

    def test_contract_violations_are_reported(self):
        packet = EvidencePacket(
            ticker="AAPL",
            as_of="2026-09-07T00:00:00Z",
            engine="test",
            items=(
                EvidenceItem("x", EvidenceKind.FACT, "price", None, "USD", "MSFT", "spot", 2, None),
                EvidenceItem("x", EvidenceKind.CALCULATION, "value", 1, "USD", "AAPL", "spot", 1, 0),
            ),
        )
        errors = validate_packet(packet)
        self.assertGreaterEqual(len(errors), 5)

    def test_missing_fact_can_abstain_without_source(self):
        packet = EvidencePacket(
            ticker="AAPL",
            as_of="2026-09-07T00:00:00Z",
            engine="fundamentals",
            items=(EvidenceItem(
                "missing-debt", EvidenceKind.FACT, "debt", None, "USD", "AAPL", "FY2025", 0, None,
                missing_status=MissingStatus.UNAVAILABLE,
            ),),
        )
        self.assertEqual(validate_packet(packet), [])

    def test_calculation_requires_reproducible_inputs(self):
        item = EvidenceItem(
            "fair-value", EvidenceKind.CALCULATION, "fair_value", 120, "USD/share", "AAPL", "FY2026E", .7, 0,
            calculation=Calculation("multiple", "eps * pe", {"eps": 6, "pe": 20}),
        )
        packet = EvidencePacket("AAPL", "2026-09-07T00:00:00Z", (item,), "valuation")
        self.assertEqual(validate_packet(packet), [])


if __name__ == "__main__":
    unittest.main()
