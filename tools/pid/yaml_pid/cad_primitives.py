from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Sequence

import ezdxf

from .drafting_standard import DEFAULT_STANDARD, DraftingStandard, StyleProfile
from .models import BlockGeometry, EquipmentPlacement, NozzleSpec, OffPageConnector, ValvePlacement
from .ports import abs_nozzle
from .scene import BBox, SceneRegistry, bbox_from_center, text_bbox

Point = tuple[float, float]


@dataclass
class DrawContext:
    doc: ezdxf.EzDxfDocument
    msp: ezdxf.layouts.Modelspace
    registry: SceneRegistry
    standard: DraftingStandard = DEFAULT_STANDARD
    style: StyleProfile | None = None
    block_names: dict[str, str] | None = None
    block_extents: dict[str, tuple[float, float]] | None = None


def draw_text(ctx: DrawContext, text: str, x: float, y: float, height: float | None = None, layer: str = "TEXT", tag: str | None = None, kind: str = "text", rotation: float = 0) -> BBox:
    h = height or ctx.standard.note_text_h
    ent = ctx.msp.add_text(str(text), dxfattribs={"height": h, "layer": layer, "rotation": rotation})
    ent.set_placement((x, y))
    box = text_bbox(str(text), x, y, h, tag or str(text))
    ctx.registry.add_item(kind, tag or str(text), layer, box)
    return box


def draw_symbol(ctx: DrawContext, symbol_key: str, tag: str, x: float, y: float, scale: float = 1.0, rotation: float = 0, xscale: float | None = None, yscale: float | None = None) -> bool:
    block_name = (ctx.block_names or {}).get(symbol_key)
    if not block_name:
        ctx.registry.fallbacks.append(f"{tag}: {symbol_key}")
        return False
    ctx.msp.add_blockref(block_name, (x, y), dxfattribs={"xscale": xscale or scale, "yscale": yscale or scale, "rotation": rotation, "layer": "SYMBOLS"})
    ctx.registry.existing_blocks_used.append(f"{tag}: {symbol_key} -> {block_name}")
    return True


def draw_equipment(ctx: DrawContext, item: EquipmentPlacement, geometry: BlockGeometry | None) -> BBox:
    if item.block_key == "deethanizer_column":
        return draw_column(ctx, item, geometry)
    w = geometry.width if geometry else 36.0
    h = geometry.height if geometry else 24.0
    ext_w, ext_h = _block_extent(ctx, item.block_key)
    used_block = draw_symbol(ctx, item.block_key, item.tag, item.x, item.y, xscale=w / ext_w, yscale=h / ext_h)
    if not used_block:
        if item.block_key in {"reflux_drum"}:
            _horizontal_vessel(ctx, item.x, item.y, w, h)
            primitive = "rounded/rectangular vessel"
        elif item.block_key in {"reboiler", "overhead_condenser", "feed_bottoms_exchanger"}:
            _exchanger(ctx, item.x, item.y, w, h)
            primitive = "rectangular exchanger/vessel body"
        elif item.block_key == "centrifugal_pump":
            _pump(ctx, item.x, item.y, w, h)
            primitive = "circle + triangle pump"
        elif item.block_key == "relief_valve":
            _psv(ctx, item.x, item.y)
            primitive = "triangle PSV"
        else:
            ctx.msp.add_lwpolyline(_rect(item.x, item.y, w, h), dxfattribs={"layer": "EQUIPMENT"})
            primitive = "rectangle"
        ctx.registry.primitive_symbols_created.append(f"{item.tag}: {primitive} for {item.block_key}")
    box = bbox_from_center(item.x, item.y, w, h, item.tag, "equipment")
    ctx.registry.add_item("equipment", item.tag, "EQUIPMENT", box)
    ctx.registry.mark("equipment", item.tag)
    if item.block_key != "relief_valve":
        draw_equipment_tag(ctx, item.tag, item.x - len(item.tag) * 1.1, box.ymin - 11)
    return box


def draw_column(ctx: DrawContext, item: EquipmentPlacement, geometry: BlockGeometry | None) -> BBox:
    if geometry is None:
        raise ValueError(f"Missing column geometry for {item.tag}")
    w, h = geometry.width, geometry.height
    x, y = item.x, item.y
    left, right, bottom, top = x - w / 2, x + w / 2, y - h / 2, y + h / 2
    ext_w, ext_h = _block_extent(ctx, item.block_key)
    used_block = draw_symbol(ctx, item.block_key, item.tag, x, y, xscale=w / ext_w, yscale=h / ext_h)
    if not used_block:
        ctx.registry.primitive_symbols_created.append(f"{item.tag}: controlled primitive deethanizer_column (rectangle + arc heads + trays)")
        ctx.msp.add_lwpolyline([(left, bottom + 14), (left, top - 14), (right, top - 14), (right, bottom + 14)], dxfattribs={"layer": "EQUIPMENT"})
        ctx.msp.add_arc((x, top - 14), w / 2, 0, 180, dxfattribs={"layer": "EQUIPMENT"})
        ctx.msp.add_arc((x, bottom + 14), w / 2, 180, 360, dxfattribs={"layer": "EQUIPMENT"})
    for idx in range(9):
        yy = bottom + 38 + idx * 17
        ctx.msp.add_line((left + 5, yy), (right - 5, yy), dxfattribs={"layer": "EQUIPMENT"})
    box = bbox_from_center(x, y, w, h, item.tag, "equipment")
    ctx.registry.add_item("equipment", item.tag, "EQUIPMENT", box)
    ctx.registry.add_item("forbidden_zone", item.tag, "EQUIPMENT", box)
    ctx.registry.mark("equipment", item.tag)
    draw_equipment_tag(ctx, item.tag, left - 24, bottom - 12)
    return box


def draw_nozzle(ctx: DrawContext, equipment_tag: str, origin: Point, name: str, nozzle: NozzleSpec) -> BBox:
    wall, stub, flange, conn = abs_nozzle(nozzle, origin)
    visual_conn = _draw_reference_nozzle(ctx, wall, stub, flange, conn)
    tag = f"{equipment_tag}.{name}"
    ctx.registry.add_port(f"{tag}.connection_point", visual_conn, "nozzle")
    box = BBox(min(wall[0], visual_conn[0]) - 2, min(wall[1], visual_conn[1]) - 2, max(wall[0], visual_conn[0]) + 2, max(wall[1], visual_conn[1]) + 2, tag, "nozzle")
    ctx.registry.add_item("nozzle", tag, "NOZZLES", box)
    ctx.registry.mark("nozzle", tag)
    return box


def draw_pipe(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS", major: bool = True, gaps: Sequence[tuple[Point, float]] | None = None) -> BBox:
    for p1, p2 in zip(points, points[1:]):
        for a, b in _split_segment_for_gaps(p1, p2, gaps or []):
            if a == b:
                continue
            ctx.msp.add_lwpolyline([a, b], dxfattribs={"layer": layer, "lineweight": ctx.standard.lw_major if major else ctx.standard.lw_minor})
            ctx.registry.add_line_segment(a, b, line_tag, layer, major)
    ctx.registry.mark("line", line_tag)
    ctx.registry.route_endpoints[line_tag] = (points[0], points[-1])
    return BBox(min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points), line_tag, "pipe")


def draw_header(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS", gaps: Sequence[tuple[Point, float]] | None = None) -> None:
    draw_pipe(ctx, points, line_tag, service, layer, True, gaps)


def draw_branch(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS", gaps: Sequence[tuple[Point, float]] | None = None) -> None:
    draw_pipe(ctx, points, line_tag, service, layer, False, gaps)


def draw_valve_on_line(ctx: DrawContext, valve: ValvePlacement, x: float, y: float) -> None:
    h = valve.orientation.startswith("h")
    symbol_w, symbol_h = _valve_target_size(valve.type)
    s, hh = symbol_w / 2, symbol_h / 2
    if h:
        pts1, pts2 = [(x - s, y - hh), (x, y), (x - s, y + hh), (x - s, y - hh)], [(x + s, y - hh), (x, y), (x + s, y + hh), (x + s, y - hh)]
        ctx.registry.add_port(f"{valve.tag}.process_in", (x - s, y), "valve")
        ctx.registry.add_port(f"{valve.tag}.process_out", (x + s, y), "valve")
        tagx, tagy = x - 8, y + max(6, symbol_h * 0.8)
    else:
        pts1, pts2 = [(x - hh, y + s), (x, y), (x + hh, y + s), (x - hh, y + s)], [(x - hh, y - s), (x, y), (x + hh, y - s), (x - hh, y - s)]
        ctx.registry.add_port(f"{valve.tag}.process_in", (x, y + s), "valve")
        ctx.registry.add_port(f"{valve.tag}.process_out", (x, y - s), "valve")
        tagx, tagy = x + max(10, symbol_w * 0.8), y
    if valve.type == "relief_valve":
        tagx, tagy = x + symbol_w * 0.65, y - 1.0
    symbol_key = _valve_symbol_key(valve.type)
    ext_w, ext_h = _block_extent(ctx, symbol_key)
    insert_x, insert_y = _mounted_symbol_insert(x, y, valve.type, 0 if h else 90, symbol_w / ext_w, symbol_h / ext_h)
    used_block = draw_symbol(ctx, symbol_key, valve.tag, insert_x, insert_y, rotation=0 if h else 90, xscale=symbol_w / ext_w, yscale=symbol_h / ext_h)
    if not used_block:
        ctx.msp.add_lwpolyline(pts1, dxfattribs={"layer": "VALVES"})
        ctx.msp.add_lwpolyline(pts2, dxfattribs={"layer": "VALVES"})
        ctx.registry.primitive_symbols_created.append(f"{valve.tag}: primitive valve for {valve.type}")
    if valve.type in {"control_valve", "shutdown_valve", "relief_valve"}:
        ctx.msp.add_line((x, y + hh), (x, y + 15), dxfattribs={"layer": "INSTRUMENT"})
        ctx.registry.add_port(f"{valve.tag}.actuator_signal", (x, y + 15), "actuator")
        ctx.registry.add_port(f"{valve.tag}.solenoid_signal", (x, y + 15), "actuator")
        ctx.registry.add_port(f"{valve.tag}.zso_signal", (x - 5, y + 15), "actuator")
        ctx.registry.add_port(f"{valve.tag}.zsc_signal", (x + 5, y + 15), "actuator")
    draw_valve_tag(ctx, valve.tag, tagx, tagy)
    # Fail positions stay in YAML/report evidence; inline fail text is omitted to avoid symbol clutter.
    box = BBox(insert_x - symbol_w / 2, insert_y - symbol_h / 2, insert_x + symbol_w / 2, insert_y + symbol_h / 2, valve.tag, "valve")
    ctx.registry.add_item("valve", valve.tag, "VALVES", box)
    if valve.type == "relief_valve":
        ctx.registry.mark("equipment", valve.tag)
    ctx.registry.mark("valve", valve.tag)


def draw_control_valve(ctx: DrawContext, valve: ValvePlacement, x: float, y: float) -> None:
    draw_valve_on_line(ctx, valve, x, y)


def draw_valve_tag(ctx: DrawContext, tag: str, x: float, y: float) -> None:
    draw_text(ctx, tag, x, y, 1.8, "TEXT", tag, "valve_tag")


def draw_instrument(ctx: DrawContext, tag: str, typ: str, x: float, y: float, alarms: Sequence[str] | None = None) -> None:
    r = ctx.standard.instrument_bubble_radius
    symbol_key = _instrument_symbol_key(typ)
    ext_w, ext_h = _block_extent(ctx, symbol_key)
    target_w, target_h = _instrument_target_size(typ)
    used_block = draw_symbol(ctx, symbol_key, tag, x, y, xscale=target_w / ext_w, yscale=target_h / ext_h)
    if not used_block:
        ctx.msp.add_circle((x, y), r, dxfattribs={"layer": "INSTRUMENT"})
        if typ in {"dcs_controller", "dcs_alarm"}:
            ctx.msp.add_line((x - r, y), (x + r, y), dxfattribs={"layer": "INSTRUMENT"})
        ctx.registry.primitive_symbols_created.append(f"{tag}: primitive instrument bubble for {typ}")
    text_y = y + target_h / 2 + 2.0 if typ == "primary_element" else y - 1.5
    draw_text(ctx, tag, x - max(5, len(tag) * 0.9), text_y, ctx.standard.note_text_h, "TEXT", tag, "instrument_text")
    for idx, alarm in enumerate(alarms or []):
        alarm_y = y + 4.0 - idx * 8.0
        draw_text(ctx, alarm, x + target_w / 2 + 2.0, alarm_y, ctx.standard.note_text_h, "TEXT", f"{tag}:{alarm}", "alarm_indicator")
    box = bbox_from_center(x, y, target_w, target_h, tag, "instrument")
    ctx.registry.add_item("instrument", tag, "INSTRUMENT", box)
    ctx.registry.add_port(f"{tag}.process_tap", (x, y - target_h / 2 - 2), "instrument")
    ctx.registry.add_port(f"{tag}.process_tap_high", (x - target_w * 0.22, y - target_h / 2 - 2), "instrument")
    ctx.registry.add_port(f"{tag}.process_tap_low", (x + target_w * 0.22, y - target_h / 2 - 2), "instrument")
    ctx.registry.add_port(f"{tag}.signal", (x + target_w / 2 + 2, y), "instrument")
    ctx.registry.add_port(f"{tag}.input_signal", (x - target_w / 2 - 2, y), "instrument")
    ctx.registry.add_port(f"{tag}.output_signal", (x + target_w / 2 + 2, y), "instrument")
    ctx.registry.mark("instrument", tag)


def draw_offpage_connector(ctx: DrawContext, connector: OffPageConnector) -> None:
    x, y = connector.x, connector.y
    if connector.direction in {"right", "out"}:
        pts = [(x - 22, y + 8), (x, y), (x - 22, y - 8), (x - 22, y + 8)]
    else:
        pts = [(x + 22, y + 8), (x, y), (x + 22, y - 8), (x + 22, y + 8)]
    conn = (x, y)
    ext_w, ext_h = _block_extent(ctx, "offpage_connector")
    used_block = draw_symbol(ctx, "offpage_connector", connector.tag, x, y, rotation=180 if connector.direction in {"right", "out"} else 0, xscale=24.0 / ext_w, yscale=12.0 / ext_h)
    if not used_block:
        ctx.msp.add_lwpolyline(pts, dxfattribs={"layer": "OFFPAGE"})
        ctx.registry.primitive_symbols_created.append(f"{connector.tag}: primitive off-page connector")
    text_x = x - 100 if connector.direction in {"right", "out"} else x + 30
    draw_text(ctx, connector.service, text_x, y + 18, ctx.standard.note_text_h, "TEXT", connector.tag, "offpage_tag")
    draw_text(ctx, connector.drawing_reference, text_x, y - 18, ctx.standard.note_text_h, "TEXT", f"{connector.tag}:ref", "offpage_ref")
    ctx.registry.add_item("offpage", connector.tag, "OFFPAGE", BBox(x - 24, y - 10, x + 24, y + 10, connector.tag, "offpage"))
    ctx.registry.add_port(f"{connector.tag}.continuation", conn, "offpage")
    ctx.registry.add_port(f"{connector.tag}.line_connection", conn, "offpage")
    ctx.registry.mark("offpage", connector.tag)


def draw_signal_line(ctx: DrawContext, points: Sequence[Point], signal_type: str = "electric_signal") -> None:
    layer = {"pneumatic_signal": "SIGNAL_PNEUMATIC", "software_signal": "SIGNAL_SOFTWARE", "safety_signal": "SIGNAL_SIS", "impulse_line": "IMPULSE_LINE"}.get(signal_type, "SIGNAL_ELECTRIC")
    for p1, p2 in zip(points, points[1:]):
        if signal_type == "impulse_line":
            ctx.msp.add_line(p1, p2, dxfattribs={"layer": layer, "lineweight": ctx.standard.lw_signal})
        elif signal_type == "pneumatic_signal":
            _draw_pneumatic_segment(ctx, p1, p2, layer)
        else:
            _draw_short_dashed_segment(ctx, p1, p2, layer)
        ctx.registry.add_line_segment(p1, p2, f"signal:{signal_type}", layer, False)


def draw_signal_trunk(ctx: DrawContext, points: Sequence[Point], tag: str) -> None:
    draw_signal_line(ctx, points, "electric_signal")
    ctx.registry.add_item("signal_trunk", tag, "SIGNAL_ELECTRIC", BBox(min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points), tag, "signal_trunk"))


def draw_flow_arrow(ctx: DrawContext, point: Point, orientation: str = "RIGHT", layer: str = "PROCESS") -> None:
    x, y = point
    angle = radians({"RIGHT": 0, "LEFT": 180, "UP": 90, "DOWN": -90}.get(orientation, 0))
    tip = (x + ctx.standard.flow_arrow_len * cos(angle), y + ctx.standard.flow_arrow_len * sin(angle))
    left = (x - 4 * cos(angle) - 2.5 * sin(angle), y - 4 * sin(angle) + 2.5 * cos(angle))
    right = (x - 4 * cos(angle) + 2.5 * sin(angle), y - 4 * sin(angle) - 2.5 * cos(angle))
    ctx.msp.add_solid([tip, left, right], dxfattribs={"layer": layer})


def draw_line_jump(ctx: DrawContext, x: float, y: float, orientation: str = "H", layer: str = "PROCESS") -> None:
    ctx.msp.add_arc((x, y), 5, 0 if orientation == "H" else 90, 180 if orientation == "H" else 270, dxfattribs={"layer": layer})


def draw_equipment_tag(ctx: DrawContext, tag: str, x: float, y: float) -> None:
    draw_text(ctx, tag, x, y, DEFAULT_STANDARD.equipment_tag_h, "TEXT", tag, "equipment_tag")


def draw_line_label(ctx: DrawContext, tag: str, x: float, y: float, service: str = "") -> None:
    text = tag if not service else f"{tag} {service}"
    draw_text(ctx, text, x, y, DEFAULT_STANDARD.line_label_h, "TEXT", tag, "line_label")
    ctx.registry.mark("line_label", tag)


def draw_offpage_label(ctx: DrawContext, tag: str, x: float, y: float) -> None:
    draw_text(ctx, tag, x, y, DEFAULT_STANDARD.note_text_h, "TEXT", tag, "offpage_label")


def draw_title_block(ctx: DrawContext, project: str, drawing_no: str, rev: str, unit: str, service: str, status: str) -> None:
    s = ctx.standard
    x, y, w, h = s.title_block_x, s.title_block_y, s.title_block_w, s.title_block_h
    ctx.msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], dxfattribs={"layer": "BORDER"})
    for yy in [y + 24, y + 48, y + 70]:
        ctx.msp.add_line((x, yy), (x + w, yy), dxfattribs={"layer": "BORDER"})
    draw_text(ctx, project, x + 7, y + 75, s.title_text_h, "TEXT", "TITLE_BLOCK", "title")
    draw_text(ctx, f"DWG NO: {drawing_no}", x + 7, y + 54, s.tag_text_h, "TEXT")
    draw_text(ctx, f"REV: {rev}", x + 210, y + 54, s.tag_text_h, "TEXT")
    draw_text(ctx, f"UNIT: {unit}", x + 7, y + 30, s.tag_text_h, "TEXT")
    draw_text(ctx, "SCALE: NTS", x + 210, y + 30, s.tag_text_h, "TEXT")
    draw_text(ctx, f"SERVICE: {service}", x + 7, y + 7, s.note_text_h, "TEXT")
    draw_text(ctx, status, x + 260, y + 7, s.tag_text_h, "TEXT")
    ctx.registry.mark("document", "TITLE_BLOCK")


def draw_notes_block(ctx: DrawContext, notes: Sequence[str], x: float = 55, y: float = 118) -> None:
    ctx.msp.add_lwpolyline([(x, y), (x + 560, y), (x + 560, y - 82), (x, y - 82), (x, y)], dxfattribs={"layer": "TABLE"})
    draw_text(ctx, "NOTES", x + 6, y - 12, DEFAULT_STANDARD.equipment_tag_h, "TEXT")
    for idx, note in enumerate(notes[:6], start=1):
        draw_text(ctx, f"{idx}. {note.replace('_', ' ')}", x + 8, y - 13 - idx * 9, DEFAULT_STANDARD.note_text_h, "TEXT")
    ctx.registry.mark("document", "NOTES")


def draw_legend(ctx: DrawContext, x: float = 650, y: float = 118) -> None:
    draw_text(ctx, "LEGEND", x, y, DEFAULT_STANDARD.equipment_tag_h, "TEXT")
    draw_text(ctx, "Solid: process / utility piping", x, y - 12, DEFAULT_STANDARD.note_text_h, "TEXT")
    draw_text(ctx, "Dashed/dotted: instrument signals", x, y - 22, DEFAULT_STANDARD.note_text_h, "TEXT")
    ctx.registry.mark("document", "LEGEND")


def draw_revision_table(ctx: DrawContext, x: float = 650, y: float = 75) -> None:
    ctx.msp.add_lwpolyline([(x, y), (x + 145, y), (x + 145, y - 38), (x, y - 38), (x, y)], dxfattribs={"layer": "TABLE"})
    draw_text(ctx, "REV  DATE        STATUS", x + 4, y - 10, DEFAULT_STANDARD.note_text_h, "TEXT")
    draw_text(ctx, "A    2026-05-07  STUDY", x + 4, y - 22, DEFAULT_STANDARD.note_text_h, "TEXT")
    ctx.registry.mark("document", "REVISION_TABLE")


def draw_qa_overlay_box(ctx: DrawContext, box: BBox) -> None:
    ctx.msp.add_lwpolyline([(box.xmin, box.ymin), (box.xmax, box.ymin), (box.xmax, box.ymax), (box.xmin, box.ymax), (box.xmin, box.ymin)], dxfattribs={"layer": "QA_OVERLAY"})


def _rect(x: float, y: float, w: float, h: float) -> list[Point]:
    return [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2), (x - w / 2, y - h / 2)]


def _horizontal_vessel(ctx: DrawContext, x: float, y: float, w: float, h: float) -> None:
    ctx.msp.add_lwpolyline([(x - w/2, y - h/2), (x + w/2, y - h/2), (x + w/2, y + h/2), (x - w/2, y + h/2), (x - w/2, y - h/2)], dxfattribs={"layer": "EQUIPMENT"})


def _exchanger(ctx: DrawContext, x: float, y: float, w: float, h: float) -> None:
    _horizontal_vessel(ctx, x, y, w, h)
    ctx.msp.add_line((x - w / 2 + 8, y - h / 2), (x - w / 2 + 8, y + h / 2), dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_line((x + w / 2 - 8, y - h / 2), (x + w / 2 - 8, y + h / 2), dxfattribs={"layer": "EQUIPMENT"})


def _pump(ctx: DrawContext, x: float, y: float, w: float, h: float) -> None:
    r = min(w, h) / 2
    ctx.msp.add_circle((x, y), r, dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_lwpolyline([(x - r * 0.45, y - r * 0.65), (x + r * 0.75, y), (x - r * 0.45, y + r * 0.65), (x - r * 0.45, y - r * 0.65)], dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_line((x - w / 2, y), (x - r, y), dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_line((x + r, y), (x + w / 2, y), dxfattribs={"layer": "EQUIPMENT"})


def _psv(ctx: DrawContext, x: float, y: float) -> None:
    ctx.msp.add_lwpolyline([(x - 8, y - 8), (x, y + 8), (x + 8, y - 8), (x - 8, y - 8)], dxfattribs={"layer": "VALVES"})


def _midpoint(points: Sequence[Point]) -> Point:
    p1, p2 = points[-2], points[-1]
    return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2


def _orientation(p1: Point, p2: Point) -> str:
    if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]):
        return "RIGHT" if p2[0] >= p1[0] else "LEFT"
    return "UP" if p2[1] >= p1[1] else "DOWN"


def _split_segment_for_gaps(p1: Point, p2: Point, gaps: Sequence[tuple[Point, float]]) -> list[tuple[Point, Point]]:
    x1, y1 = p1
    x2, y2 = p2
    if x1 != x2 and y1 != y2:
        return [(p1, p2)]
    intervals: list[tuple[float, float]] = []
    axis_start, axis_end = (x1, x2) if y1 == y2 else (y1, y2)
    lo, hi = sorted((axis_start, axis_end))
    for (gx, gy), half in gaps:
        if y1 == y2 and abs(gy - y1) <= 0.1 and lo <= gx <= hi:
            intervals.append((gx - half, gx + half))
        elif x1 == x2 and abs(gx - x1) <= 0.1 and lo <= gy <= hi:
            intervals.append((gy - half, gy + half))
    if not intervals:
        return [(p1, p2)]
    cuts = [(max(lo, a), min(hi, b)) for a, b in intervals if b > lo and a < hi]
    cuts.sort()
    spans: list[tuple[float, float]] = []
    cursor = lo
    for a, b in cuts:
        if a > cursor:
            spans.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < hi:
        spans.append((cursor, hi))
    if axis_start > axis_end:
        spans.reverse()
    if y1 == y2:
        return [((a, y1), (b, y1)) for a, b in spans]
    return [((x1, a), (x1, b)) for a, b in spans]


def _draw_short_dashed_segment(ctx: DrawContext, p1: Point, p2: Point, layer: str) -> None:
    x1, y1 = p1
    x2, y2 = p2
    dash = 4.0
    gap = 2.0
    if x1 == x2:
        direction = 1 if y2 >= y1 else -1
        pos = y1
        while (pos - y2) * direction < 0:
            end = pos + direction * min(dash, abs(y2 - pos))
            ctx.msp.add_line((x1, pos), (x1, end), dxfattribs={"layer": layer, "lineweight": ctx.standard.lw_signal})
            pos = end + direction * gap
    elif y1 == y2:
        direction = 1 if x2 >= x1 else -1
        pos = x1
        while (pos - x2) * direction < 0:
            end = pos + direction * min(dash, abs(x2 - pos))
            ctx.msp.add_line((pos, y1), (end, y1), dxfattribs={"layer": layer, "lineweight": ctx.standard.lw_signal})
            pos = end + direction * gap
    else:
        ctx.msp.add_line(p1, p2, dxfattribs={"layer": layer, "lineweight": ctx.standard.lw_signal})


def _draw_pneumatic_segment(ctx: DrawContext, p1: Point, p2: Point, layer: str) -> None:
    ctx.msp.add_line(p1, p2, dxfattribs={"layer": layer, "lineweight": ctx.standard.lw_signal})
    x1, y1 = p1
    x2, y2 = p2
    length = abs(x2 - x1) + abs(y2 - y1)
    if length < 14:
        return
    mark_spacing = 28.0
    first = min(18.0, length / 2)
    count = max(1, int((length - first) // mark_spacing) + 1)
    for idx in range(count):
        offset = first + idx * mark_spacing
        if offset >= length - 4:
            break
        if y1 == y2:
            direction = 1 if x2 >= x1 else -1
            mx = x1 + direction * offset
            _draw_slash_pair(ctx, (mx, y1), layer)
        elif x1 == x2:
            direction = 1 if y2 >= y1 else -1
            my = y1 + direction * offset
            _draw_slash_pair(ctx, (x1, my), layer)


def _draw_slash_pair(ctx: DrawContext, point: Point, layer: str) -> None:
    x, y = point
    for delta in (-1.8, 1.8):
        ctx.msp.add_line((x + delta - 2.0, y - 3.0), (x + delta + 2.0, y + 3.0), dxfattribs={"layer": layer, "lineweight": ctx.standard.lw_signal})


def _valve_symbol_key(valve_type: str) -> str:
    return {
        "control_valve": "control_valve",
        "shutdown_valve": "shutdown_valve",
        "manual_block_valve": "manual_block_valve",
        "check_valve": "check_valve",
        "relief_valve": "relief_valve",
        "restriction_orifice": "restriction_orifice",
    }.get(valve_type, "manual_block_valve")


def _valve_target_size(valve_type: str) -> tuple[float, float]:
    if valve_type in {"manual_block_valve", "check_valve"}:
        return (9.0, 4.0)
    if valve_type == "restriction_orifice":
        return (7.0, 4.0)
    if valve_type == "relief_valve":
        return (14.0, 6.0)
    return (28.0, 12.0)


def _mounted_symbol_insert(x: float, y: float, valve_type: str, rotation: float, xscale: float, yscale: float) -> Point:
    # Source block definitions are centered on their full extents. Some include
    # actuator/stem geometry above the valve body, so their process center is not
    # the imported block center.
    offsets = {
        "control_valve": (0.0, 3.313),
        "shutdown_valve": (0.0, -0.529),
        "check_valve": (0.0, 0.132),
    }
    ox, oy = offsets.get(valve_type, (0.0, 0.0))
    dx, dy = ox * xscale, oy * yscale
    if abs(rotation) == 90:
        return (x - dy, y + dx)
    return (x + dx, y + dy)


def _instrument_symbol_key(instrument_type: str) -> str:
    if instrument_type in {"dcs_controller", "dcs_alarm"}:
        return "dcs_controller"
    if instrument_type == "analyzer":
        return "analyzer"
    if instrument_type == "sample_system":
        return "sample_point"
    if instrument_type == "primary_element":
        return "restriction_orifice"
    return "field_instrument"


def _instrument_target_size(instrument_type: str) -> tuple[float, float]:
    if instrument_type in {"dcs_controller", "dcs_alarm"}:
        return (18.0, 18.0)
    if instrument_type == "primary_element":
        return (7.0, 4.0)
    if instrument_type == "sample_system":
        return (14.0, 10.0)
    if instrument_type == "analyzer":
        return (16.0, 16.0)
    return (14.0, 14.0)


def _block_extent(ctx: DrawContext, symbol_key: str) -> tuple[float, float]:
    return (ctx.block_extents or {}).get(symbol_key, (1.0, 1.0))


def _fit_scale(ctx: DrawContext, symbol_key: str, width: float, height: float) -> float:
    ext_w, ext_h = _block_extent(ctx, symbol_key)
    return min(width / ext_w, height / ext_h)


def _draw_reference_nozzle(ctx: DrawContext, wall: Point, stub: Point, flange: Point, conn: Point) -> Point:
    dx, dy = conn[0] - wall[0], conn[1] - wall[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    tick_half = 1.3
    tick_gap = 0.75
    line_start = wall
    line_end = (wall[0] + dx * 0.20, wall[1] + dy * 0.20)
    ctx.msp.add_line(line_start, line_end, dxfattribs={"layer": "NOZZLES", "lineweight": 13})
    for offset in (0.0, tick_gap):
        cx, cy = line_end[0] + ux * offset, line_end[1] + uy * offset
        ctx.msp.add_line((cx - px * tick_half, cy - py * tick_half), (cx + px * tick_half, cy + py * tick_half), dxfattribs={"layer": "NOZZLES", "lineweight": 13})
    return line_end


def _nozzle_rotation(side: str, wall: Point, conn: Point) -> float:
    side_l = side.lower()
    if "left" in side_l:
        return 180.0
    if "top" in side_l:
        return 90.0
    if "bottom" in side_l:
        return -90.0
    if "right" in side_l:
        return 0.0
    dx, dy = conn[0] - wall[0], conn[1] - wall[1]
    if abs(dx) >= abs(dy):
        return 0.0 if dx >= 0 else 180.0
    return 90.0 if dy >= 0 else -90.0
