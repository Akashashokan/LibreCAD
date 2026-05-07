from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .geometry import BBox


class PIDValidationError(RuntimeError):
    pass


@dataclass
class DrawingAudit:
    items: list[BBox] = field(default_factory=list)
    line_labels: set[str] = field(default_factory=set)
    equipment_tags: set[str] = field(default_factory=set)
    valves: set[str] = field(default_factory=set)
    xv_feedback: set[str] = field(default_factory=set)
    offpages: dict[str, str] = field(default_factory=dict)
    destinations: dict[str, str] = field(default_factory=dict)
    generic_blocks_used: bool = False

    def add(self, bbox: BBox) -> None:
        self.items.append(bbox)


def validate_visual_audit(
    audit: DrawingAudit,
    *,
    required_line_labels: Iterable[str],
    required_equipment: Iterable[str],
    required_valves: Iterable[str],
    required_destinations: Iterable[str],
    sheet: tuple[float, float, float, float] = (10.0, 10.0, 1179.0, 831.0),
) -> list[str]:
    errors: list[str] = []
    sx0, sy0, sx1, sy1 = sheet

    for item in audit.items:
        if item.kind in {"text", "equipment", "symbol"} and item.outside(sx0, sy0, sx1, sy1):
            errors.append(f"{item.kind} outside sheet: {item.label}")

    texts = [i for i in audit.items if i.kind == "text"]
    lines = [i.expanded(3.0) for i in audit.items if i.kind == "line" and i.label.startswith("pipe:")]
    for text in texts:
        if text.label.startswith(("line-label:", "instrument:", "equipment-label:", "vessel-service", "valve-fail:", "valve-tag:")):
            continue
        for line in lines:
            if text.overlaps(line):
                errors.append(f"text overlaps line: {text.label} / {line.label}")
                break

    symbols = [
        i.expanded(1.0)
        for i in audit.items
        if i.kind in {"equipment", "symbol"} and i.label not in {"flow-arrow", "line-jump"} and not i.label.startswith(("ZSO/", "ZSC/"))
    ]
    for idx, left in enumerate(symbols):
        for right in symbols[idx + 1 :]:
            if left.overlaps(right):
                errors.append(f"symbol overlap: {left.label} / {right.label}")

    missing_labels = set(required_line_labels) - audit.line_labels
    if missing_labels:
        errors.append("missing line labels: " + ", ".join(sorted(missing_labels)))

    missing_equipment = set(required_equipment) - audit.equipment_tags
    if missing_equipment:
        errors.append("missing equipment tags: " + ", ".join(sorted(missing_equipment)))

    missing_valves = set(required_valves) - audit.valves
    if missing_valves:
        errors.append("missing XV valves: " + ", ".join(sorted(missing_valves)))

    missing_feedback = {tag for tag in required_valves if tag.startswith("XV-")} - audit.xv_feedback
    if missing_feedback:
        errors.append("missing XV ZSO/ZSC feedback: " + ", ".join(sorted(missing_feedback)))

    bad_offpages = [tag for tag, ref in audit.offpages.items() if not ref]
    if bad_offpages:
        errors.append("off-page connector missing drawing reference: " + ", ".join(sorted(bad_offpages)))

    missing_destinations = set(required_destinations) - set(audit.destinations)
    if missing_destinations:
        errors.append("missing vent/drain destinations: " + ", ".join(sorted(missing_destinations)))

    if audit.generic_blocks_used:
        errors.append("fallback generic blocks used in production mode")

    return errors
