"""Versioned, provider-neutral evidence contracts for finance engines."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


SCHEMA_VERSION = "1.0.0"


class EvidenceKind(str, Enum):
    FACT = "fact"
    CALCULATION = "calculation"
    INTERPRETATION = "interpretation"
    ASSUMPTION = "assumption"


class MissingStatus(str, Enum):
    PRESENT = "present"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class Source:
    provider: str
    url: str
    retrieved_at: str
    published_at: str | None = None
    observed_at: str | None = None


@dataclass(frozen=True)
class Calculation:
    method: str
    formula: str
    inputs: dict[str, Any]


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    kind: EvidenceKind
    metric: str
    value: Any
    unit: str
    ticker: str
    period: str
    confidence: float
    freshness_seconds: int | None
    missing_status: MissingStatus = MissingStatus.PRESENT
    source: Source | None = None
    calculation: Calculation | None = None
    notes: str | None = None


@dataclass(frozen=True)
class EvidencePacket:
    ticker: str
    as_of: str
    items: tuple[EvidenceItem, ...]
    engine: str
    schema_version: str = SCHEMA_VERSION
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_packet(packet: EvidencePacket) -> list[str]:
    """Return contract violations without throwing, so engines can abstain."""
    errors: list[str] = []
    if packet.schema_version != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {packet.schema_version}")
    if not packet.ticker.strip():
        errors.append("ticker is required")
    if not packet.engine.strip():
        errors.append("engine is required")
    ids: set[str] = set()
    for index, item in enumerate(packet.items):
        prefix = f"items[{index}]"
        if not item.id or item.id in ids:
            errors.append(f"{prefix}.id must be non-empty and unique")
        ids.add(item.id)
        if item.ticker.upper() != packet.ticker.upper():
            errors.append(f"{prefix}.ticker does not match packet ticker")
        if not 0 <= item.confidence <= 1:
            errors.append(f"{prefix}.confidence must be between 0 and 1")
        if item.missing_status is MissingStatus.PRESENT and item.value is None:
            errors.append(f"{prefix}.value is required when present")
        if item.kind is EvidenceKind.FACT and item.missing_status is MissingStatus.PRESENT and item.source is None:
            errors.append(f"{prefix}.source is required for facts")
        if item.kind is EvidenceKind.CALCULATION and item.calculation is None:
            errors.append(f"{prefix}.calculation is required for calculations")
        if item.source and (not item.source.provider or not item.source.retrieved_at):
            errors.append(f"{prefix}.source provider and retrieved_at are required")
    return errors
