"""Pre-display trust checks for claims derived from evidence packets."""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceKind, EvidencePacket, MissingStatus, validate_packet


@dataclass(frozen=True)
class Claim:
    text: str
    kind: EvidenceKind
    evidence_ids: tuple[str, ...] = ()


def validate_claims(packet: EvidencePacket, claims: tuple[Claim, ...]) -> list[str]:
    errors = validate_packet(packet)
    items = {item.id: item for item in packet.items}
    for index, claim in enumerate(claims):
        prefix = f"claims[{index}]"
        if not claim.text.strip():
            errors.append(f"{prefix}.text is required")
        if claim.kind in (EvidenceKind.FACT, EvidenceKind.CALCULATION) and not claim.evidence_ids:
            errors.append(f"{prefix} requires evidence_ids")
        for evidence_id in claim.evidence_ids:
            item = items.get(evidence_id)
            if item is None:
                errors.append(f"{prefix} references unknown evidence {evidence_id}")
                continue
            if item.missing_status is not MissingStatus.PRESENT:
                errors.append(f"{prefix} references unavailable evidence {evidence_id}")
            if claim.kind is EvidenceKind.FACT and item.source is None:
                errors.append(f"{prefix} fact lacks a source")
            if claim.kind is EvidenceKind.CALCULATION and item.calculation is None:
                errors.append(f"{prefix} calculation is not reproducible")
    return errors
