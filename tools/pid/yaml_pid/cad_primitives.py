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


def draw_text(ctx: DrawContext, text: str, x: float, y: float, height: float | None = None, layer: str = "TEXT", tag: str | None = None, kind: str = "text", rotation: float = 0) -> BBox:
    h = height or ctx.standard.note_text_h
    ent = ctx.msp.add_text(str(text), dxfattribs={"height": h, "layer": layer, "rotation": rotation})
    ent.set_placement((x, y))
    box = text_bbox(str(text), x, y, h, tag or str(text))
    ctx.registry.add_item(kind, tag or str(text), layer, box)
    return box


def draw_symbol(ctx: DrawContext, symbol_key: str, tag: str, x: float, y: float, scale: float = 1.0, rotation: float = 0) -> bool:
    block_name = (ctx.block_names or {}).get(symbol_key)
    if not block_name:
        ctx.registry.fallbacks.append(f"{tag}: {symbol_key}")
        return False
    ctx.msp.add_blockref(block_name, (x, y), dxfattribs={"xscale": scale, "yscale": scale, "rotation": rotation, "layer": "SYMBOLS"})
    return True


def draw_equipment(ctx: DrawContext, item: EquipmentPlacement, geometry: BlockGeometry | None) -> BBox:
    if item.block_key == "deethanizer_column":
        return draw_column(ctx, item, geometry)
    w = geometry.width if geometry else 36.0
    h = geometry.height if geometry else 24.0
    used_block = draw_symbol(ctx, item.block_key, item.tag, item.x, item.y, scale=1.0)
    if not used_block:
        if item.block_key in {"reflux_drum"}:
            _horizontal_vessel(ctx, item.x, item.y, w, h)
        elif item.block_key in {"reboiler", "overhead_condenser", "feed_bottoms_exchanger"}:
            _exchanger(ctx, item.x, item.y, w, h)
        elif item.block_key == "centrifugal_pump":
            _pump(ctx, item.x, item.y, w, h)
        elif item.block_key == "relief_valve":
            _psv(ctx, item.x, item.y)
        else:
            ctx.msp.add_lwpolyline(_rect(item.x, item.y, w, h), dxfattribs={"layer": "EQUIPMENT"})
    box = bbox_from_center(item.x, item.y, w, h, item.tag, "equipment")
    ctx.registry.add_item("equipment", item.tag, "EQUIPMENT", box)
    ctx.registry.mark("equipment", item.tag)
    draw_equipment_tag(ctx, item.tag, item.x - len(item.tag) * 1.1, box.ymin - 11)
    return box


def draw_column(ctx: DrawContext, item: EquipmentPlacement, geometry: BlockGeometry | None) -> BBox:
    if geometry is None:
        raise ValueError(f"Missing column geometry for {item.tag}")
    w, h = geometry.width, geometry.height
    x, y = item.x, item.y
    left, right, bottom, top = x - w / 2, x + w / 2, y - h / 2, y + h / 2
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
    draw_equipment_tag(ctx, item.tag, x - 7, bottom - 12)
    return box


def draw_nozzle(ctx: DrawContext, equipment_tag: str, origin: Point, name: str, nozzle: NozzleSpec) -> BBox:
    wall, stub, flange, conn = abs_nozzle(nozzle, origin)
    ctx.msp.add_line(wall, stub, dxfattribs={"layer": "NOZZLES", "lineweight": 25})
    ctx.msp.add_circle(flange, 2.0, dxfattribs={"layer": "NOZZLES"})
    ctx.msp.add_line((conn[0] - 1.8, conn[1]), (conn[0] + 1.8, conn[1]), dxfattribs={"layer": "NOZZLES"})
    ctx.msp.add_line((conn[0], conn[1] - 1.8), (conn[0], conn[1] + 1.8), dxfattribs={"layer": "NOZZLES"})
    tag = f"{equipment_tag}.{name}"
    box = BBox(min(wall[0], stub[0], flange[0], conn[0]) - 2, min(wall[1], stub[1], flange[1], conn[1]) - 2, max(wall[0], stub[0], flange[0], conn[0]) + 2, max(wall[1], stub[1], flange[1], conn[1]) + 2, tag, "nozzle")
    ctx.registry.add_item("nozzle", tag, "NOZZLES", box)
    ctx.registry.mark("nozzle", tag)
    return box


def draw_pipe(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS", major: bool = True) -> BBox:
    ctx.msp.add_lwpolyline(list(points), dxfattribs={"layer": layer, "lineweight": ctx.standard.lw_major if major else ctx.standard.lw_minor})
    for p1, p2 in zip(points, points[1:]):
        ctx.registry.add_line_segment(p1, p2, line_tag, layer, major)
    ctx.registry.mark("line", line_tag)
    ctx.registry.route_endpoints[line_tag] = (points[0], points[-1])
    return BBox(min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points), line_tag, "pipe")


def draw_header(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS") -> None:
    draw_pipe(ctx, points, line_tag, service, layer, True)
    draw_flow_arrow(ctx, _midpoint(points), _orientation(points[-2], points[-1]), layer)


def draw_branch(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS") -> None:
    draw_pipe(ctx, points, line_tag, service, layer, False)


def draw_valve_on_line(ctx: DrawContext, valve: ValvePlacement, x: float, y: float) -> None:
    h = valve.orientation.startswith("h")
    s, hh = ctx.standard.valve_symbol_len, ctx.standard.valve_symbol_ht / 2
    if h:
        pts1, pts2 = [(x - s, y - hh), (x, y), (x - s, y + hh), (x - s, y - hh)], [(x + s, y - hh), (x, y), (x + s, y + hh), (x + s, y - hh)]
        ctx.registry.add_port(f"{valve.tag}.process_in", (x - s, y), "valve")
        ctx.registry.add_port(f"{valve.tag}.process_out", (x + s, y), "valve")
        tagx, tagy = x - 8, y + 10
    else:
        pts1, pts2 = [(x - hh, y + s), (x, y), (x + hh, y + s), (x - hh, y + s)], [(x - hh, y - s), (x, y), (x + hh, y - s), (x - hh, y - s)]
        ctx.registry.add_port(f"{valve.tag}.process_in", (x, y + s), "valve")
        ctx.registry.add_port(f"{valve.tag}.process_out", (x, y - s), "valve")
        tagx, tagy = x + 8, y
    ctx.msp.add_lwpolyline(pts1, dxfattribs={"layer": "VALVES"})
    ctx.msp.add_lwpolyline(pts2, dxfattribs={"layer": "VALVES"})
    if valve.type in {"control_valve", "shutdown_valve", "relief_valve"}:
        ctx.msp.add_line((x, y + hh), (x, y + 15), dxfattribs={"layer": "INSTRUMENT"})
        ctx.registry.add_port(f"{valve.tag}.actuator_signal", (x, y + 15), "actuator")
        ctx.registry.add_port(f"{valve.tag}.solenoid_signal", (x, y + 15), "actuator")
        ctx.registry.add_port(f"{valve.tag}.zso_signal", (x - 5, y + 15), "actuator")
        ctx.registry.add_port(f"{valve.tag}.zsc_signal", (x + 5, y + 15), "actuator")
    draw_valve_tag(ctx, valve.tag, tagx, tagy)
    if valve.fail_position and valve.fail_position != "none":
        draw_text(ctx, valve.fail_position, tagx, tagy - 8, ctx.standard.note_text_h, "TEXT", f"{valve.tag}:{valve.fail_position}", "valve_fail_text")
    box = BBox(x - 14, y - 14, x + 14, y + 18, valve.tag, "valve")
    ctx.registry.add_item("valve", valve.tag, "VALVES", box)
    ctx.registry.mark("valve", valve.tag)


def draw_control_valve(ctx: DrawContext, valve: ValvePlacement, x: float, y: float) -> None:
    draw_valve_on_line(ctx, valve, x, y)


def draw_valve_tag(ctx: DrawContext, tag: str, x: float, y: float) -> None:
    draw_text(ctx, tag, x, y, DEFAULT_STANDARD.tag_text_h, "TEXT", tag, "valve_tag")


def draw_instrument(ctx: DrawContext, tag: str, typ: str, x: float, y: float) -> None:
    r = ctx.standard.instrument_bubble_radius
    ctx.msp.add_circle((x, y), r, dxfattribs={"layer": "INSTRUMENT"})
    if typ in {"dcs_controller", "dcs_alarm"}:
        ctx.msp.add_line((x - r, y), (x + r, y), dxfattribs={"layer": "INSTRUMENT"})
    draw_text(ctx, tag, x - max(5, len(tag) * 0.9), y - 1.5, ctx.standard.note_text_h, "TEXT", tag, "instrument_text")
    box = bbox_from_center(x, y, r * 2, r * 2, tag, "instrument")
    ctx.registry.add_item("instrument", tag, "INSTRUMENT", box)
    ctx.registry.add_port(f"{tag}.process_tap", (x, y - r - 2), "instrument")
    ctx.registry.add_port(f"{tag}.signal", (x + r + 2, y), "instrument")
    ctx.registry.add_port(f"{tag}.input_signal", (x - r - 2, y), "instrument")
    ctx.registry.add_port(f"{tag}.output_signal", (x + r + 2, y), "instrument")
    ctx.registry.mark("instrument", tag)


def draw_offpage_connector(ctx: DrawContext, connector: OffPageConnector) -> None:
    x, y = connector.x, connector.y
    if connector.direction in {"right", "out"}:
        pts = [(x - 22, y + 8), (x, y), (x - 22, y - 8), (x - 22, y + 8)]
        conn = (x - 22, y)
    else:
        pts = [(x + 22, y + 8), (x, y), (x + 22, y - 8), (x + 22, y + 8)]
        conn = (x + 22, y)
    ctx.msp.add_lwpolyline(pts, dxfattribs={"layer": "OFFPAGE"})
    draw_text(ctx, connector.service, x - 35, y + 12, ctx.standard.note_text_h, "TEXT", connector.tag, "offpage_tag")
    draw_text(ctx, connector.drawing_reference, x - 24, y - 16, ctx.standard.note_text_h, "TEXT", f"{connector.tag}:ref", "offpage_ref")
    ctx.registry.add_item("offpage", connector.tag, "OFFPAGE", BBox(x - 24, y - 10, x + 24, y + 10, connector.tag, "offpage"))
    ctx.registry.add_port(f"{connector.tag}.continuation", conn, "offpage")
    ctx.registry.add_port(f"{connector.tag}.line_connection", conn, "offpage")
    ctx.registry.mark("offpage", connector.tag)


def draw_signal_line(ctx: DrawContext, points: Sequence[Point], signal_type: str = "electric_signal") -> None:
    layer = {"pneumatic_signal": "SIGNAL_PNEUMATIC", "software_signal": "SIGNAL_SOFTWARE", "safety_signal": "SIGNAL_SIS", "impulse_line": "IMPULSE_LINE"}.get(signal_type, "SIGNAL_ELECTRIC")
    ltype = "DASHED" if layer != "IMPULSE_LINE" else "DOTTED"
    ctx.msp.add_lwpolyline(list(points), dxfattribs={"layer": layer, "linetype": ltype, "lineweight": ctx.standard.lw_signal})
    for p1, p2 in zip(points, points[1:]):
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
    ctx.msp.add_circle((x, y), min(w, h) / 2, dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_line((x - w / 2, y), (x + w / 2, y), dxfattribs={"layer": "EQUIPMENT"})


def _psv(ctx: DrawContext, x: float, y: float) -> None:
    ctx.msp.add_lwpolyline([(x - 8, y - 8), (x, y + 8), (x + 8, y - 8), (x - 8, y - 8)], dxfattribs={"layer": "VALVES"})


def _midpoint(points: Sequence[Point]) -> Point:
    p1, p2 = points[-2], points[-1]
    return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2


def _orientation(p1: Point, p2: Point) -> str:
    if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]):
        return "RIGHT" if p2[0] >= p1[0] else "LEFT"
    return "UP" if p2[1] >= p1[1] else "DOWN"
