from __future__ import annotations

from .cad_primitives import DrawContext, draw_instrument, draw_signal_line, draw_symbol, draw_text
from .models import InstrumentPlacement
from .scene import BBox

ZONE_ANCHORS: dict[str, tuple[float, float]] = {
    "COLUMN_LEFT_PRESSURE_DP_ZONE": (365, 585),
    "COLUMN_LEFT_BOTTOM_LEVEL_ZONE": (365, 360),
    "COLUMN_RIGHT_TEMPERATURE_PROFILE_ZONE": (720, 505),
    "FEED_CONTROL_ZONE": (300, 505),
    "OVERHEAD_PRESSURE_CONTROL_ZONE": (540, 710),
    "REFLUX_DRUM_LEVEL_PRESSURE_ZONE": (1010, 545),
    "REFLUX_FLOW_CONTROL_ZONE": (560, 625),
    "REBOILER_CONTROL_ZONE": (780, 415),
    "OVERHEAD_ANALYZER_ZONE": (1010, 655),
    "BOTTOMS_ANALYZER_ZONE": (250, 310),
    "PUMP_STATUS_ZONE": (600, 125),
    "SHUTDOWN_VALVE_FEEDBACK_ZONE": (210, 450),
}

EXPLICIT_POINTS: dict[str, tuple[float, float]] = {
    "PT-501": (462, 522),
    "DPI-501": (444, 452),
    "DPT-501": (462, 430),
    "LT-502": (465, 325),
    "LIC-502": (465, 303),
    "TT-501A": (604, 480),
    "TI-501A": (626, 480),
    "TT-501B": (604, 430),
    "TIC-501": (626, 430),
    "TT-501C": (604, 392),
    "TI-501C": (626, 392),
    "PIC-501": (548, 690),
    "FE-501": (370, 392),
    "FT-501": (370, 435),
    "FIC-501": (414, 435),
    "LT-501": (770, 610),
    "LIC-501": (740, 610),
    "PT-502": (872, 655),
    "PI-502": (872, 675),
    "FE-502": (715, 525),
    "FT-502": (715, 505),
    "FIC-502": (735, 505),
    "TT-503": (760, 355),
    "TI-503": (782, 355),
    "AIT-501": (1010, 700),
    "AIC-501": (1010, 675),
    "AS-501": (1010, 650),
    "AIT-502": (250, 310),
    "AIC-502": (250, 285),
    "AS-502": (250, 260),
}

ALARM_LETTERS = {
    "PAH": "H",
    "PAL": "L",
    "TAH": "H",
    "TAL": "L",
    "LAH": "H",
    "LAL": "L",
    "PSHH": "HH",
    "LSHH": "HH",
    "LSL": "L",
}


def place_instruments(ctx: DrawContext, instruments: list[InstrumentPlacement]) -> None:
    per_zone: dict[str, int] = {}
    by_tag = {inst.tag: inst for inst in instruments}
    alarms_by_source = _alarm_map(instruments)
    process_ref_sources = _process_ref_sources(instruments)
    drawn: set[str] = set()

    for inst in instruments:
        if _is_alarm_or_switch(inst):
            ctx.registry.mark("instrument", inst.tag)
            continue
        if _prefix(inst.tag) == "FE":
            ctx.registry.mark("instrument", inst.tag)
            continue
        if inst.tag in drawn:
            continue
        drawn.add(inst.tag)
        idx = per_zone.get(inst.zone, 0)
        per_zone[inst.zone] = idx + 1
        x0, y0 = ZONE_ANCHORS.get(inst.zone, (100, 100))
        if inst.tag in EXPLICIT_POINTS:
            x, y = EXPLICIT_POINTS[inst.tag]
        elif inst.zone in {"FEED_CONTROL_ZONE", "OVERHEAD_PRESSURE_CONTROL_ZONE", "REFLUX_FLOW_CONTROL_ZONE", "PUMP_STATUS_ZONE"}:
            x, y = x0 + idx * 28, y0
        else:
            x, y = x0, y0 - idx * 18
        if _prefix(inst.tag) == "FIC":
            _draw_flow_controller(ctx, inst.tag, x, y)
            continue
        alarms = _alarms_for(inst, alarms_by_source, process_ref_sources)
        draw_instrument(ctx, inst.tag, _symbol_type(inst.type, inst.location), x, y, alarms)
        if _prefix(inst.tag) in {"DPT", "DPIT"}:
            ctx.registry.add_port(f"{inst.tag}.process_tap_high", (x, y + 9.0), "instrument")
            ctx.registry.add_port(f"{inst.tag}.process_tap_low", (x, y - 9.0), "instrument")

    _draw_process_hookups(ctx, by_tag, instruments)
    _draw_local_indicator_signals(ctx, instruments)


def _symbol_type(typ: str, location: str) -> str:
    if location == "dcs/shared_control":
        return "dcs_controller"
    return typ


def _is_alarm_or_switch(inst: InstrumentPlacement) -> bool:
    prefix = _prefix(inst.tag)
    return inst.type == "dcs_alarm" or prefix in {"PAH", "PAL", "TAH", "TAL", "LAH", "LAL", "PSHH", "LSHH", "LSL"}


def _alarm_map(instruments: list[InstrumentPlacement]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for inst in instruments:
        if not _is_alarm_or_switch(inst) or not isinstance(inst.source, str):
            continue
        letter = ALARM_LETTERS.get(_prefix(inst.tag))
        if letter:
            out.setdefault(inst.source, []).append(letter)
    return out


def _process_ref_sources(instruments: list[InstrumentPlacement]) -> dict[str, str]:
    out: dict[str, str] = {}
    for inst in instruments:
        if _prefix(inst.tag) in {"PT", "TT", "LT", "FT"} and isinstance(inst.connect_to, str):
            out[inst.connect_to] = inst.tag
    return out


def _alarms_for(inst: InstrumentPlacement, alarms_by_source: dict[str, list[str]], process_ref_sources: dict[str, str]) -> list[str]:
    if _is_transmitter_tag(inst.tag):
        return []
    source = inst.input_from if isinstance(inst.input_from, str) else None
    if source is None and isinstance(inst.connect_to, str):
        source = process_ref_sources.get(inst.connect_to)
    if source is None:
        source = inst.tag
    seen: list[str] = []
    for alarm in alarms_by_source.get(source, []):
        if alarm not in seen:
            seen.append(alarm)
    return seen


def _draw_process_hookups(ctx: DrawContext, by_tag: dict[str, InstrumentPlacement], instruments: list[InstrumentPlacement]) -> None:
    for inst in instruments:
        if f"{inst.tag}.process_tap" not in ctx.registry.ports or _is_alarm_or_switch(inst):
            continue
        prefix = _prefix(inst.tag)
        if prefix in {"PT"} and isinstance(inst.connect_to, str):
            _draw_solid_hookup(ctx, inst.connect_to, f"{inst.tag}.process_tap", gate_count=1)
        elif prefix in {"TT"} and isinstance(inst.connect_to, str):
            _draw_temperature_well(ctx, inst)
        elif prefix in {"LT"} and isinstance(inst.connect_to, dict):
            _draw_level_hookup(ctx, inst)
        elif prefix in {"FT"} and isinstance(inst.connect_to, str):
            fe = by_tag.get(inst.connect_to)
            if fe:
                _draw_flow_transmitter_hookup(ctx, fe.tag, inst.tag)
        elif prefix in {"DPT", "DPIT"} and isinstance(inst.connect_to, dict):
            _draw_level_hookup(ctx, inst)


def _draw_local_indicator_signals(ctx: DrawContext, instruments: list[InstrumentPlacement]) -> None:
    transmitters_by_ref: dict[str, str] = {}
    for inst in instruments:
        if _prefix(inst.tag) in {"PT", "TT", "LT", "FT"} and isinstance(inst.connect_to, str):
            transmitters_by_ref[inst.connect_to] = inst.tag
    for inst in instruments:
        if _prefix(inst.tag) in {"PI", "TI"} and isinstance(inst.connect_to, str):
            source = transmitters_by_ref.get(inst.connect_to)
            if source:
                _draw_signal_ref(ctx, f"{source}.signal", f"{inst.tag}.input_signal")


def _draw_temperature_well(ctx: DrawContext, inst: InstrumentPlacement) -> None:
    src = _point(ctx, inst.connect_to)
    dst = _point(ctx, f"{inst.tag}.process_tap")
    if src is None or dst is None:
        return
    tw_tag = "TW-" + inst.tag.split("-", 1)[1]
    tw = (src[0] + (12 if dst[0] >= src[0] else -12), src[1])
    draw_symbol(ctx, "field_instrument", tw_tag, tw[0], tw[1], scale=0.65)
    ctx.registry.mark("instrument", tw_tag)
    _draw_text_at(ctx, tw_tag, tw[0] - 8, tw[1] - 10)
    _draw_polyline(ctx, [src, tw, (dst[0], tw[1]), dst])


def _draw_level_hookup(ctx: DrawContext, inst: InstrumentPlacement) -> None:
    high_ref = inst.connect_to.get("high_tap")
    low_ref = inst.connect_to.get("low_tap")
    high_dst = f"{inst.tag}.process_tap_high"
    low_dst = f"{inst.tag}.process_tap_low"
    if high_ref:
        _draw_solid_hookup(ctx, high_ref, high_dst, gate_count=1)
    if low_ref:
        _draw_solid_hookup(ctx, low_ref, low_dst, gate_count=1)


def _draw_flow_transmitter_hookup(ctx: DrawContext, fe_tag: str, ft_tag: str) -> None:
    fe = EXPLICIT_POINTS.get(fe_tag) or _point(ctx, f"{fe_tag}.process_tap")
    ft = EXPLICIT_POINTS.get(ft_tag)
    hi = _point(ctx, f"{ft_tag}.process_tap_high")
    lo = _point(ctx, f"{ft_tag}.process_tap_low")
    if fe is None or ft is None or hi is None or lo is None:
        return
    direction = 1 if ft[1] >= fe[1] else -1
    left_tap, right_tap = _draw_flow_element(ctx, fe_tag, fe, direction)
    ft_left = (ft[0] - 7.0, ft[1])
    ft_right = (ft[0] + 7.0, ft[1])
    left_riser_x = fe[0] - 22.0
    right_riser_x = fe[0] + 22.0
    valve_in_y = fe[1] + direction * 14.0
    valve_out_y = fe[1] + direction * 31.0
    segment_tag = f"flow_impulse:{fe_tag}:{ft_tag}"
    _draw_polyline(ctx, [left_tap, (left_riser_x, valve_in_y), (left_riser_x, valve_out_y), ft_left], segment_tag)
    _draw_polyline(ctx, [right_tap, (right_riser_x, valve_in_y), (right_riser_x, valve_out_y), ft_right], segment_tag)
    _draw_bowtie_valve(ctx, (left_riser_x, fe[1] + direction * 22.5), "vertical")
    _draw_bowtie_valve(ctx, (right_riser_x, fe[1] + direction * 22.5), "vertical")


def _draw_solid_hookup(ctx: DrawContext, src_ref: str, dst_ref: str, gate_count: int = 0) -> None:
    src = _point(ctx, src_ref)
    dst = _point(ctx, dst_ref)
    if src is None or dst is None:
        return
    elbow = (dst[0], src[1])
    points = [src, elbow, dst] if elbow != src and elbow != dst else [src, dst]
    _draw_polyline(ctx, points)
    if gate_count:
        first, second = points[0], points[1]
        gate = (first[0] + (second[0] - first[0]) * 0.45, first[1] + (second[1] - first[1]) * 0.45)
        orientation = "vertical" if first[0] == second[0] else "horizontal"
        _draw_gate(ctx, gate, orientation)


def _draw_polyline(ctx: DrawContext, points: list[tuple[float, float]], tag: str = "instrument_hookup") -> None:
    for p1, p2 in zip(points, points[1:]):
        ctx.msp.add_line(p1, p2, dxfattribs={"layer": "IMPULSE_LINE", "lineweight": ctx.standard.lw_signal})
        ctx.registry.add_line_segment(p1, p2, tag, "IMPULSE_LINE", False)


def _draw_signal_ref(ctx: DrawContext, src_ref: str, dst_ref: str) -> None:
    src = _point(ctx, src_ref)
    dst = _point(ctx, dst_ref)
    if src is not None and dst is not None:
        if abs(src[1] - dst[1]) < 0.1 or abs(src[0] - dst[0]) < 0.1:
            draw_signal_line(ctx, [src, dst], "electric_signal")
            return
        midx = (src[0] + dst[0]) / 2
        draw_signal_line(ctx, [src, (midx, src[1]), (midx, dst[1]), dst], "electric_signal")


def _draw_flow_element(ctx: DrawContext, tag: str, point: tuple[float, float], direction: int) -> tuple[tuple[float, float], tuple[float, float]]:
    x, line_y = point
    plate_half = 7.0
    tap_y = line_y + direction * 6.0
    for offset in (-2.2, 2.2):
        ctx.msp.add_line((x + offset, line_y - plate_half), (x + offset, line_y + plate_half), dxfattribs={"layer": "INSTRUMENT", "lineweight": ctx.standard.lw_signal})
        ctx.registry.add_line_segment((x + offset, line_y - plate_half), (x + offset, line_y + plate_half), f"orifice_plate:{tag}", "INSTRUMENT", False)
    for offset in (-6.0, 6.0):
        ctx.msp.add_line((x + offset, line_y), (x + offset, tap_y), dxfattribs={"layer": "IMPULSE_LINE", "lineweight": ctx.standard.lw_signal})
        ctx.registry.add_line_segment((x + offset, line_y), (x + offset, tap_y), f"flow_impulse_tap:{tag}", "IMPULSE_LINE", False)
    tag_y = line_y - direction * 13.0
    draw_text(ctx, tag, x - max(5, len(tag) * 0.9), tag_y, ctx.standard.note_text_h, "TEXT", tag, "instrument_text")
    box = BBox(x - 9.0, line_y - plate_half, x + 9.0, line_y + plate_half, tag, "instrument")
    ctx.registry.add_item("instrument", tag, "INSTRUMENT", box)
    ctx.registry.add_port(f"{tag}.process_tap", (x, line_y), "instrument")
    ctx.registry.mark("instrument", tag)
    return (x - 6.0, tap_y), (x + 6.0, tap_y)


def _draw_gate(ctx: DrawContext, point: tuple[float, float], orientation: str, scale: float = 0.15) -> None:
    rotation = 90 if orientation == "vertical" else 0
    draw_symbol(ctx, "manual_block_valve", "instrument_root_valve", point[0], point[1], rotation=rotation, scale=scale)


def _draw_bowtie_valve(ctx: DrawContext, point: tuple[float, float], orientation: str) -> None:
    x, y = point
    half_w = 4.5
    half_h = 5.8
    ctx.msp.add_lwpolyline([(x - half_w, y + half_h), (x, y), (x + half_w, y + half_h), (x - half_w, y + half_h)], dxfattribs={"layer": "VALVES"})
    ctx.msp.add_lwpolyline([(x - half_w, y - half_h), (x, y), (x + half_w, y - half_h), (x - half_w, y - half_h)], dxfattribs={"layer": "VALVES"})


def _draw_flow_controller(ctx: DrawContext, tag: str, x: float, y: float) -> None:
    width = 22.0
    height = 14.0
    left, right = x - width / 2, x + width / 2
    bottom, top = y - height / 2, y + height / 2
    ctx.msp.add_lwpolyline([(left, bottom), (right, bottom), (right, top), (left, top), (left, bottom)], dxfattribs={"layer": "INSTRUMENT"})
    draw_text(ctx, tag, x - max(5, len(tag) * 0.9), y - 1.5, ctx.standard.note_text_h, "TEXT", tag, "instrument_text")
    ctx.registry.add_item("instrument", tag, "INSTRUMENT", BBox(left, bottom, right, top, tag, "instrument"))
    ctx.registry.add_port(f"{tag}.input_signal", (left - 2.0, y), "instrument")
    ctx.registry.add_port(f"{tag}.output_signal", (right + 2.0, y), "instrument")
    ctx.registry.add_port(f"{tag}.signal", (right + 2.0, y), "instrument")
    ctx.registry.mark("instrument", tag)


def _draw_text_at(ctx: DrawContext, text: str, x: float, y: float) -> None:
    draw_text(ctx, text, x, y, ctx.standard.note_text_h, "TEXT", text, "instrument_text")


def _point(ctx: DrawContext, ref: object) -> tuple[float, float] | None:
    if not isinstance(ref, str):
        return None
    return ctx.registry.ports.get(ref)


def _prefix(tag: str) -> str:
    return tag.split("-", 1)[0]


def _is_transmitter_tag(tag: str) -> bool:
    return _prefix(tag).endswith("T")
