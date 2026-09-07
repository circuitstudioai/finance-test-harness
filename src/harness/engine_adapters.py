"""Stable adapters that normalize heterogeneous engines for Market Desk ingest."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import pstdev
from typing import Any, Iterable

from .evidence import Calculation, EvidenceItem, EvidenceKind, EvidencePacket, validate_packet
from .validators import Claim, validate_claims


@dataclass(frozen=True)
class EngineOutput:
    run_id: int
    ticker: str
    market: str
    run_timestamp: str
    engine_name: str
    direction: str
    confidence: int
    time_horizon: str
    thesis_summary: str
    bull_case: tuple[str, ...]
    bear_case: tuple[str, ...]
    risk_flags: tuple[str, ...]
    catalysts: tuple[str, ...]
    suggested_next_action: str
    raw_payload: dict[str, Any]
    source_tag: str = "finance_test_harness"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_valid(packet: EvidencePacket) -> None:
    errors = validate_packet(packet)
    if errors:
        raise ValueError("invalid evidence packet: " + "; ".join(errors))


def technical_engine(
    run_id: int, ticker: str, closes: Iterable[float], run_timestamp: str, *, market: str = "US"
) -> EngineOutput:
    prices = tuple(float(value) for value in closes)
    if len(prices) < 100 or any(value <= 0 for value in prices):
        raise ValueError("technical engine requires at least 100 positive closing prices")
    ma20 = sum(prices[-20:]) / 20
    ma100 = sum(prices[-100:]) / 100
    momentum20 = prices[-1] / prices[-21] - 1
    returns = [prices[i] / prices[i - 1] - 1 for i in range(len(prices) - 20, len(prices))]
    volatility = pstdev(returns) * sqrt(252)
    score = int(prices[-1] > ma20) + int(ma20 > ma100) + int(momentum20 > 0)
    direction = "bullish" if score == 3 else "bearish" if score == 0 else "neutral"
    confidence = min(90, 50 + abs(score - 1.5) * 20)
    packet = EvidencePacket(ticker.upper(), run_timestamp, (
        EvidenceItem("technical-last", EvidenceKind.CALCULATION, "last_price", prices[-1], "USD", ticker.upper(), "spot", .9, 0,
                     calculation=Calculation("last_observation", "closes[-1]", {"close": prices[-1]})),
        EvidenceItem("technical-ma20", EvidenceKind.CALCULATION, "ma20", round(ma20, 4), "USD", ticker.upper(), "20d", .9, 0,
                     calculation=Calculation("simple_moving_average", "sum(closes[-20:]) / 20", {"closes": list(prices[-20:])})),
        EvidenceItem("technical-ma100", EvidenceKind.CALCULATION, "ma100", round(ma100, 4), "USD", ticker.upper(), "100d", .9, 0,
                     calculation=Calculation("simple_moving_average", "sum(closes[-100:]) / 100", {"closes": list(prices[-100:])})),
        EvidenceItem("technical-momentum20", EvidenceKind.CALCULATION, "momentum20", round(momentum20, 6), "ratio", ticker.upper(), "20d", .9, 0,
                     calculation=Calculation("price_return", "last / lag20 - 1", {"last": prices[-1], "lag20": prices[-21]})),
        EvidenceItem("technical-volatility", EvidenceKind.CALCULATION, "annualized_volatility", round(volatility, 6), "ratio", ticker.upper(), "20d", .85, 0,
                     calculation=Calculation("annualized_population_volatility", "pstdev(daily_returns) * sqrt(252)", {"daily_returns": returns})),
    ), "technical_regime")
    _require_valid(packet)
    return EngineOutput(run_id, ticker.upper(), market, run_timestamp, "technical_regime", direction, int(confidence), "swing",
        f"Trend score {score}/3; 20-day momentum {momentum20:.1%}.",
        ("Price above short trend",) if prices[-1] > ma20 else (),
        ("Price below short trend",) if prices[-1] <= ma20 else (),
        (f"Annualized 20-day volatility {volatility:.1%}",), (), "Monitor trend and momentum confirmation.",
        {"evidence_packet": packet.to_dict(), "category_views": {
            "trend": {"direction": direction, "confidence": int(confidence)},
            "risk": {"direction": "bearish" if volatility >= .4 else "neutral", "confidence": min(90, int(50 + volatility * 50))},
        }})


def fundamentals_engine(
    run_id: int, packet: EvidencePacket, valuation_items: tuple[EvidenceItem, ...], current_price: float
) -> EngineOutput:
    combined = EvidencePacket(packet.ticker, packet.as_of, packet.items + valuation_items, "fundamentals_valuation", metadata=packet.metadata)
    _require_valid(combined)
    values = sorted(float(item.value) for item in valuation_items if item.value is not None)
    if not values or current_price <= 0:
        direction, confidence = "neutral", 30
    else:
        midpoint = values[len(values) // 2]
        gap = midpoint / current_price - 1
        direction = "bullish" if gap >= .15 else "bearish" if gap <= -.15 else "neutral"
        confidence = min(85, int(55 + abs(gap) * 100))
    missing = tuple(item.metric for item in packet.items if item.value is None)
    return EngineOutput(run_id, packet.ticker, "US", packet.as_of, "fundamentals_valuation", direction, confidence, "long_term",
        f"Scenario range {values[0]:.2f}–{values[-1]:.2f} versus current price {current_price:.2f}." if values else "Insufficient valuation evidence.",
        ("Current price is below the base scenario",) if direction == "bullish" else (),
        ("Current price is above the base scenario",) if direction == "bearish" else (),
        tuple(f"Missing SEC metric: {metric}" for metric in missing), (), "Review assumptions and refresh after the next filing.",
        {"evidence_packet": combined.to_dict(), "category_views": {
            "valuation": {"direction": direction, "confidence": confidence},
            "fundamentals": {"direction": "neutral", "confidence": max(20, 80 - len(missing) * 10)},
        }})


def ai_research_engine(
    run_id: int,
    packet: EvidencePacket,
    claims: tuple[Claim, ...],
    *,
    view: str,
    confidence: int,
    thesis: str,
    category_views: dict[str, dict[str, Any]] | None = None,
) -> EngineOutput:
    errors = validate_claims(packet, claims)
    if errors:
        raise ValueError("unsupported research output: " + "; ".join(errors))
    if view not in {"bullish", "neutral", "bearish"} or not 0 <= confidence <= 100:
        raise ValueError("invalid view or confidence")
    category_views = category_views or {"research": {"direction": view, "confidence": confidence}}
    for category, category_view in category_views.items():
        if not category or category_view.get("direction") not in {"bullish", "neutral", "bearish"}:
            raise ValueError("invalid category view")
        category_confidence = category_view.get("confidence")
        if not isinstance(category_confidence, (int, float)) or not 0 <= category_confidence <= 100:
            raise ValueError("invalid category confidence")
    cited = {evidence_id for claim in claims for evidence_id in claim.evidence_ids}
    return EngineOutput(run_id, packet.ticker, "US", packet.as_of, "ai_research", view, confidence, "long_term", thesis,
        tuple(claim.text for claim in claims if claim.kind is EvidenceKind.INTERPRETATION and "bull" in claim.text.lower()),
        tuple(claim.text for claim in claims if claim.kind is EvidenceKind.INTERPRETATION and "bear" in claim.text.lower()),
        (), (), "Investigate disagreements and thesis invalidators.",
        {"evidence_packet": packet.to_dict(), "claims": [asdict(claim) for claim in claims], "cited_evidence_ids": sorted(cited),
         "category_views": category_views})
