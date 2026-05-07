from __future__ import annotations

from .cad_primitives import DrawContext, draw_instrument
from .models import InstrumentPlacement

ZONE_ANCHORS: dict[str, tuple[float, float]] = {
    "COLUMN_LEFT_PRESSURE_DP_ZONE": (410, 535),
    "COLUMN_LEFT_BOTTOM_LEVEL_ZONE": (405, 330),
    "COLUMN_RIGHT_TEMPERATURE_PROFILE_ZONE": (615, 435),
    "FEED_CONTROL_ZONE": (360, 460),
    "OVERHEAD_PRESSURE_CONTROL_ZONE": (540, 710),
    "REFLUX_DRUM_LEVEL_PRESSURE_ZONE": (735, 610),
    "REFLUX_FLOW_CONTROL_ZONE": (690, 525),
    "REBOILER_CONTROL_ZONE": (760, 370),
    "OVERHEAD_ANALYZER_ZONE": (1010, 610),
    "BOTTOMS_ANALYZER_ZONE": (260, 260),
    "PUMP_STATUS_ZONE": (710, 180),
    "SHUTDOWN_VALVE_FEEDBACK_ZONE": (210, 450),
}


def place_instruments(ctx: DrawContext, instruments: list[InstrumentPlacement]) -> None:
    per_zone: dict[str, int] = {}
    for inst in instruments:
        idx = per_zone.get(inst.zone, 0)
        per_zone[inst.zone] = idx + 1
        x0, y0 = ZONE_ANCHORS.get(inst.zone, (100, 100))
        if inst.zone in {"FEED_CONTROL_ZONE", "OVERHEAD_PRESSURE_CONTROL_ZONE", "REFLUX_FLOW_CONTROL_ZONE", "PUMP_STATUS_ZONE"}:
            x, y = x0 + idx * 28, y0
        else:
            x, y = x0, y0 - idx * 18
        draw_instrument(ctx, inst.tag, _symbol_type(inst.type, inst.location), x, y)


def _symbol_type(typ: str, location: str) -> str:
    if location == "dcs/shared_control":
        return "dcs_controller"
    return typ

