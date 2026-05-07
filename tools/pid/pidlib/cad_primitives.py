from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, radians, sin
from typing import Sequence

from .drafting_standard import DEFAULT_STANDARD, FINAL_STYLE, DraftingStandard, StyleProfile
from .geometry import BBox, line_bbox, text_bbox
from .label_rules import equipment_tag_position, offpage_text_x, pick_label_segment, line_label_position, valve_fail_text_position, valve_tag_position
from .validation import DrawingAudit
from .visual_validation import SceneRegistry

Point = tuple[float, float]


@dataclass
class DrawContext:
    msp: object
    audit: DrawingAudit = field(default_factory=DrawingAudit)
    registry: SceneRegistry = field(default_factory=SceneRegistry)
    standard: DraftingStandard = DEFAULT_STANDARD
    style: StyleProfile = FINAL_STYLE


def _text(ctx: DrawContext, text: str, x: float, y: float, height: float, layer: str = "TEXT", angle: float = 0.0, label: str | None = None, kind: str = "text") -> BBox:
    ent = ctx.msp.add_text(text, dxfattribs={"height": height, "layer": layer, "rotation": angle})
    ent.set_placement((x, y))
    bbox = text_bbox(text, x, y, height, label or text)
    ctx.audit.add(bbox)
    ctx.registry.add_item(kind, label or text, layer, bbox)
    return bbox


def draw_pipe(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS", width: float = 0.55) -> BBox:
    ctx.msp.add_lwpolyline(list(points), dxfattribs={"layer": layer, "lineweight": int(width * 100)})
    bbox = line_bbox(list(points), f"pipe:{line_tag}:{service}", pad=1.2)
    for idx, (p1, p2) in enumerate(zip(points, points[1:])):
        ctx.audit.add(line_bbox([p1, p2], f"pipe:{line_tag}:{service}:seg{idx + 1}", pad=1.2))
        ctx.registry.add_line_segment(p1, p2, line_tag, layer, major=layer in {"PROCESS", "REGEN", "FLARE_VENT", "DRAIN"})
    return bbox


def draw_header(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS") -> None:
    draw_pipe(ctx, points, line_tag, service, layer, width=ctx.standard.lw_major)
    for p1, p2 in zip(points, points[1:]):
        if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]):
            x = p1[0] + (p2[0] - p1[0]) * 0.72
            y = p1[1]
            draw_flow_arrow(ctx, x, y, "RIGHT" if p2[0] >= p1[0] else "LEFT", layer)


def draw_branch(ctx: DrawContext, points: Sequence[Point], line_tag: str, service: str, layer: str = "PROCESS") -> None:
    draw_pipe(ctx, points, line_tag, service, layer, width=ctx.standard.lw_minor)


def draw_line_label(ctx: DrawContext, tag: str, x: float, y: float, angle: float = 0.0) -> None:
    _text(ctx, tag, x, y, ctx.standard.line_label_h, "TEXT", angle, tag, "line_label")
    ctx.audit.line_labels.add(tag)
    ctx.registry.mark("line_label", tag)


def draw_line_label_for_pipe(ctx: DrawContext, tag: str, points: Sequence[Point]) -> None:
    x, y, angle = line_label_position(pick_label_segment(list(points)), ctx.standard)
    draw_line_label(ctx, tag, x, y, angle)


def draw_flow_arrow(ctx: DrawContext, x: float, y: float, orientation: str = "RIGHT", layer: str = "PROCESS") -> None:
    angles = {"RIGHT": 0, "LEFT": 180, "UP": 90, "DOWN": -90}
    a = radians(angles[orientation])
    arrow_len = ctx.standard.flow_arrow_len
    tip = (x + arrow_len * cos(a), y + arrow_len * sin(a))
    left = (x - 3.5 * cos(a) - 2.6 * sin(a), y - 3.5 * sin(a) + 2.6 * cos(a))
    right = (x - 3.5 * cos(a) + 2.6 * sin(a), y - 3.5 * sin(a) - 2.6 * cos(a))
    ctx.msp.add_solid([tip, left, right], dxfattribs={"layer": layer})
    ctx.audit.add(BBox(min(tip[0], left[0], right[0]), min(tip[1], left[1], right[1]), max(tip[0], left[0], right[0]), max(tip[1], left[1], right[1]), "flow-arrow", "symbol"))


def draw_valve_on_line(ctx: DrawContext, tag: str, x: float, y: float, orientation: str = "H", valve_type: str = "XV", fail: str = "FC", layer: str = "PROCESS") -> None:
    size = ctx.standard.valve_symbol_len
    half_h = ctx.standard.valve_symbol_ht / 2
    if orientation == "H":
        pts1 = [(x - size, y - half_h), (x, y), (x - size, y + half_h), (x - size, y - half_h)]
        pts2 = [(x + size, y - half_h), (x, y), (x + size, y + half_h), (x + size, y - half_h)]
    else:
        pts1 = [(x - half_h, y + size), (x, y), (x + half_h, y + size), (x - half_h, y + size)]
        pts2 = [(x - half_h, y - size), (x, y), (x + half_h, y - size), (x - half_h, y - size)]
    ctx.msp.add_lwpolyline(pts1, dxfattribs={"layer": layer})
    ctx.msp.add_lwpolyline(pts2, dxfattribs={"layer": layer})
    if valve_type == "XV":
        ctx.msp.add_line((x, y + half_h), (x, y + half_h + 8), dxfattribs={"layer": "INSTRUMENT"})
        ctx.msp.add_circle((x, y + half_h + 12), ctx.standard.actuator_bubble_radius, dxfattribs={"layer": "INSTRUMENT"})
    tag_x, tag_y = valve_tag_position(x, y, orientation, ctx.standard)
    fail_x, fail_y = valve_fail_text_position(x, y, orientation, ctx.standard)
    _text(ctx, tag, tag_x, tag_y, ctx.standard.tag_text_h, "TEXT", label=tag, kind="valve_tag")
    _text(ctx, fail, fail_x, fail_y, ctx.standard.note_text_h, "TEXT", label=f"{tag}:{fail}", kind="valve_fail_text")
    ctx.audit.valves.add(tag)
    bbox = BBox(x - 12, y - 12, x + 12, y + 20, tag, "symbol")
    ctx.audit.add(bbox)
    ctx.registry.add_item("valve", tag, layer, bbox)
    ctx.registry.mark("valve", tag)


def draw_instrument_bubble(ctx: DrawContext, tag: str, x: float, y: float, kind: str = "field") -> None:
    radius = ctx.standard.instrument_bubble_radius
    ctx.msp.add_circle((x, y), radius, dxfattribs={"layer": "INSTRUMENT"})
    if kind == "dcs":
        ctx.msp.add_line((x - radius, y), (x + radius, y), dxfattribs={"layer": "INSTRUMENT"})
    text_x = x - max(5.0, len(tag) * ctx.standard.tag_text_h * 0.31)
    text_bbox = _text(ctx, tag, text_x, y - 1.8, ctx.standard.note_text_h, "TEXT", label=tag, kind="instrument_text")
    bubble_bbox = BBox(x - radius, y - radius, x + radius, y + radius, tag, "symbol")
    ctx.audit.add(bubble_bbox)
    ctx.registry.add_item("instrument_bubble", tag, "INSTRUMENT", bubble_bbox)
    ctx.registry.mark("instrument", tag)


def draw_signal_line(ctx: DrawContext, points: Sequence[Point], signal_type: str = "electric") -> None:
    layer = "SIGNAL_ELECTRIC" if signal_type == "electric" else "SIGNAL_PNEUMATIC"
    ltype = "DASHED" if signal_type == "electric" else "DOTTED"
    ctx.msp.add_lwpolyline(list(points), dxfattribs={"layer": layer, "linetype": ltype})
    ctx.audit.add(line_bbox(list(points), f"signal:{signal_type}", pad=0.8))
    for p1, p2 in zip(points, points[1:]):
        ctx.registry.add_line_segment(p1, p2, f"signal:{signal_type}", layer, major=False)


def draw_offpage_connector(ctx: DrawContext, tag: str, x: float, y: float, direction: str, drawing_ref: str, layer: str = "PROCESS") -> None:
    if direction in {"in", "right"}:
        pts = [(x, y), (x + 22, y + 8), (x + 22, y - 8), (x, y)]
        text_x = offpage_text_x(x, direction)
    else:
        pts = [(x, y), (x - 22, y + 8), (x - 22, y - 8), (x, y)]
        text_x = offpage_text_x(x, direction)
    ctx.msp.add_lwpolyline(pts, dxfattribs={"layer": layer})
    _text(ctx, tag, text_x, y + 11, ctx.standard.tag_text_h, "TEXT", label=tag, kind="offpage_tag")
    if drawing_ref:
        _text(ctx, drawing_ref, text_x, y - 18, ctx.standard.note_text_h, "TEXT", label=f"{tag}:{drawing_ref}", kind="offpage_ref")
    else:
        ctx.registry.add_item("offpage_ref_missing", tag, "TEXT", BBox(x - 1, y - 1, x + 1, y + 1, tag))
    ctx.audit.offpages[tag] = drawing_ref
    bbox = BBox(x - 24, y - 10, x + 24, y + 10, tag, "symbol")
    ctx.audit.add(bbox)
    ctx.registry.add_item("offpage", tag, layer, bbox)
    ctx.registry.mark("offpage", tag)


def draw_equipment_tag(ctx: DrawContext, tag: str, x: float, y: float) -> None:
    _text(ctx, tag, x, y, ctx.standard.equipment_tag_h, "TEXT", label=tag, kind="equipment_tag")
    ctx.audit.equipment_tags.add(tag)
    ctx.registry.mark("equipment", tag)


def draw_vessel(ctx: DrawContext, tag: str, x: float, y: float, height: float = 110.0, width: float = 38.0) -> dict[str, Point]:
    left, right = x - width / 2, x + width / 2
    bottom, top = y - height / 2, y + height / 2
    ctx.msp.add_line((left, bottom + 10), (left, top - 10), dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_line((right, bottom + 10), (right, top - 10), dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_arc((x, top - 10), width / 2, 0, 180, dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_arc((x, bottom + 10), width / 2, 180, 360, dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_line((left + 4, y + 22), (right - 4, y + 22), dxfattribs={"layer": "EQUIPMENT"})
    ctx.msp.add_line((left + 4, y - 22), (right - 4, y - 22), dxfattribs={"layer": "EQUIPMENT"})
    _text(ctx, "MOLECULAR", x - 16, y + 4, ctx.standard.note_text_h, "TEXT", label=f"vessel-service:{tag}")
    _text(ctx, "SIEVE BED", x - 15, y - 4, ctx.standard.note_text_h, "TEXT", label=f"vessel-service2:{tag}")
    eq_bbox = BBox(left, bottom, right, top, tag, "equipment")
    tag_x, tag_y = equipment_tag_position(eq_bbox, ctx.standard)
    draw_equipment_tag(ctx, tag, tag_x - 15, tag_y)
    ctx.audit.add(eq_bbox)
    ctx.registry.add_item("equipment", tag, "EQUIPMENT", eq_bbox)
    return {
        "TOP_IN": (x, top),
        "BOTTOM_OUT": (x, bottom),
        "REGEN_IN": (left, y - 22),
        "REGEN_OUT": (right, y + 22),
        "VENT": (x, top + 14),
        "DRAIN": (x, bottom - 14),
    }


def draw_equipment_box(ctx: DrawContext, tag: str, x: float, y: float, w: float, h: float, label: str) -> None:
    ctx.msp.add_lwpolyline([(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2), (x - w / 2, y - h / 2)], dxfattribs={"layer": "EQUIPMENT"})
    _text(ctx, label, x - len(label) * 1.0, y - 2, ctx.standard.note_text_h, "TEXT", label=f"{tag}:{label}", kind="equipment_label")
    eq_bbox = BBox(x - w / 2, y - h / 2, x + w / 2, y + h / 2, tag, "equipment")
    tag_x = (eq_bbox.xmin + eq_bbox.xmax) / 2
    tag_y = eq_bbox.ymax + ctx.standard.valve_tag_offset
    draw_equipment_tag(ctx, tag, tag_x - 8, tag_y)
    ctx.audit.add(eq_bbox)
    kind = "sample_conditioner" if tag.startswith("SC-") else "equipment"
    ctx.registry.add_item(kind, tag, "EQUIPMENT", eq_bbox)


def draw_line_jump(ctx: DrawContext, x: float, y: float, orientation: str = "H", layer: str = "PROCESS") -> None:
    if orientation == "H":
        ctx.msp.add_arc((x, y), 6, 0, 180, dxfattribs={"layer": layer})
    else:
        ctx.msp.add_arc((x, y), 6, 90, 270, dxfattribs={"layer": layer})
    ctx.audit.add(BBox(x - 6, y - 6, x + 6, y + 6, "line-jump", "symbol"))


def draw_title_block(ctx: DrawContext, project: str, drawing_no: str, rev: str, unit: str, service: str, status: str) -> None:
    x0, y0, w, h = ctx.standard.title_block_x, ctx.standard.title_block_y, ctx.standard.title_block_w, ctx.standard.title_block_h
    ctx.msp.add_lwpolyline([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h), (x0, y0)], dxfattribs={"layer": "BORDER"})
    for y in [y0 + 24, y0 + 48, y0 + 70]:
        ctx.msp.add_line((x0, y), (x0 + w, y), dxfattribs={"layer": "BORDER"})
    for x in [x0 + 82, x0 + 205, x0 + 252]:
        ctx.msp.add_line((x, y0), (x, y0 + 70), dxfattribs={"layer": "BORDER"})
    _text(ctx, project, x0 + 8, y0 + 75, ctx.standard.title_text_h, "TEXT", label="title")
    _text(ctx, "DWG NO", x0 + 5, y0 + 52, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, drawing_no, x0 + 87, y0 + 52, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, "REV", x0 + 210, y0 + 52, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, rev, x0 + 260, y0 + 52, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, "UNIT", x0 + 5, y0 + 28, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, unit, x0 + 87, y0 + 28, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, "SCALE", x0 + 210, y0 + 28, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, "NTS", x0 + 260, y0 + 28, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, "SERVICE", x0 + 5, y0 + 5, ctx.standard.tag_text_h, "TEXT")
    _text(ctx, service, x0 + 87, y0 + 5, ctx.standard.note_text_h, "TEXT")
    _text(ctx, status, x0 + 260, y0 + 5, ctx.standard.tag_text_h, "TEXT")
    ctx.registry.mark("document", "TITLE_BLOCK")


def draw_notes_block(ctx: DrawContext, notes: Sequence[str], x: float = 55, y: float = 120) -> None:
    ctx.msp.add_lwpolyline([(x, y), (x + 430, y), (x + 430, y - 90), (x, y - 90), (x, y)], dxfattribs={"layer": "TABLE"})
    _text(ctx, "NOTES", x + 6, y - 12, ctx.standard.equipment_tag_h, "TEXT")
    for idx, note in enumerate(notes, start=1):
        _text(ctx, f"{idx}. {note}", x + 8, y - 12 - idx * 11, ctx.standard.note_text_h, "TEXT", label=f"note:{idx}")
    ctx.registry.mark("document", "NOTES")
