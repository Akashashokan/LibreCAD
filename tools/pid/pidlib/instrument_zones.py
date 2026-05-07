from __future__ import annotations

from dataclasses import dataclass

from .drafting_standard import DraftingStandard, DEFAULT_STANDARD


@dataclass(frozen=True)
class InstrumentZone:
    name: str
    x: float
    y_top: float
    y_bottom: float
    preferred_side: str
    stack_spacing: float


def build_drier_instrument_zones(standard: DraftingStandard = DEFAULT_STANDARD) -> dict[str, InstrumentZone]:
    return {
        "BED_A_LEFT": InstrumentZone("BED_A_LEFT", 250, 640, 520, "left", standard.instrument_stack_spacing),
        "BED_A_RIGHT": InstrumentZone("BED_A_RIGHT", 650, 650, 450, "right", standard.feedback_stack_spacing),
        "BED_B_LEFT": InstrumentZone("BED_B_LEFT", 250, 480, 360, "left", standard.instrument_stack_spacing),
        "BED_B_RIGHT": InstrumentZone("BED_B_RIGHT", 720, 490, 290, "right", standard.feedback_stack_spacing),
        "HEATER_ZONE": InstrumentZone("HEATER_ZONE", 210, 345, 300, "top", standard.instrument_stack_spacing),
        "ANALYZER_ZONE": InstrumentZone("ANALYZER_ZONE", 1060, 620, 560, "right", standard.instrument_stack_spacing),
    }


def place_instrument_stack(zone: InstrumentZone, tags: list[str]) -> dict[str, tuple[float, float]]:
    placements: dict[str, tuple[float, float]] = {}
    y = zone.y_top
    for tag in tags:
        if y < zone.y_bottom:
            raise ValueError(f"Instrument zone {zone.name} overflow while placing {tag}")
        placements[tag] = (zone.x, y)
        y -= zone.stack_spacing
    return placements
