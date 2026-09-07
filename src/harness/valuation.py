"""Deterministic valuation scenarios with fully visible inputs."""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import Calculation, EvidenceItem, EvidenceKind


@dataclass(frozen=True)
class MultipleScenario:
    name: str
    growth_rate: float
    multiple: float


def revenue_multiple_scenarios(
    ticker: str,
    revenue: float,
    shares: float,
    scenarios: tuple[MultipleScenario, ...],
    *,
    period: str = "NTM",
) -> tuple[EvidenceItem, ...]:
    if revenue <= 0 or shares <= 0:
        raise ValueError("revenue and shares must be positive")
    items: list[EvidenceItem] = []
    for scenario in scenarios:
        if scenario.growth_rate <= -1 or scenario.multiple <= 0:
            raise ValueError(f"invalid assumptions for {scenario.name}")
        forward_revenue = revenue * (1 + scenario.growth_rate)
        enterprise_value = forward_revenue * scenario.multiple
        value_per_share = enterprise_value / shares
        inputs = {
            "revenue": revenue,
            "growth_rate": scenario.growth_rate,
            "multiple": scenario.multiple,
            "shares": shares,
        }
        items.append(EvidenceItem(
            id=f"valuation-{scenario.name.lower()}",
            kind=EvidenceKind.CALCULATION,
            metric=f"implied_value_{scenario.name.lower()}",
            value=round(value_per_share, 2),
            unit="USD/share",
            ticker=ticker.upper(),
            period=period,
            confidence=0.65,
            freshness_seconds=0,
            calculation=Calculation(
                "forward_revenue_multiple",
                "revenue * (1 + growth_rate) * multiple / shares",
                inputs,
            ),
            notes="Scenario assumption, not a price prediction",
        ))
    return tuple(items)
