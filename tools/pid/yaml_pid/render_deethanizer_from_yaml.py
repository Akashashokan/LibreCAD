from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import ezdxf

from .cad_primitives import (
    DrawContext,
    draw_branch,
    draw_equipment,
    draw_header,
    draw_legend,
    draw_nozzle,
    draw_notes_block,
    draw_offpage_connector,
    draw_revision_table,
    draw_title_block,
    draw_valve_on_line,
)
from .config_loader import load_pid_config
from .drafting_standard import DEFAULT_STANDARD, style_from_name
from .engineering_validation import run_engineering_validation
from .instrument_zones import place_instruments
from .models import ConfigError, OffPageConnector
from .ports import register_geometry_ports, register_nozzle_ports
from .scene import SceneRegistry
from .signal_routing import route_signals
from .symbol_resolver import SymbolResolver
from .visual_validation import draw_qa_overlay, run_visual_validation

Point = tuple[float, float]


def render_deethanizer_from_yaml(
    *,
    config_dir: Path,
    output: Path,
    block_dir: Path,
    style: str = "final",
    qa_overlay: bool = False,
    validate: bool = True,
    pdf_output: Path | None = None,
) -> tuple[str, str]:
    config = load_pid_config(config_dir)
    style_profile = style_from_name(style)

    doc = ezdxf.new("R2010", setup=True)
    _setup_doc(doc, style_profile)
    msp = doc.modelspace()
    registry = SceneRegistry()
    ctx = DrawContext(doc, msp, registry, DEFAULT_STANDARD, style_profile, {}, {})

    resolver = SymbolResolver(config, block_dir, style)
    resolver.resolve_all()
    resolver.import_required_blocks(doc)
    ctx.block_names = resolver.imported_blocks
    ctx.block_extents = resolver.block_extents
    registry.fallbacks.extend(resolver.fallback_warnings)
    registry.failed_block_imports.extend(resolver.failed_imports)
    registry.failed_block_imports.extend(resolver.missing_blocks)

    _draw_sheet(ctx, config)
    _draw_offpages(ctx)

    equipment_origins: dict[str, Point] = {}
    for placement in config.equipment:
        if placement.block_key == "relief_valve":
            registry.mark("equipment", placement.tag)
            continue
        geometry = config.block_geometry.get(placement.block_key)
        draw_equipment(ctx, placement, geometry)
        origin = (placement.x, placement.y)
        equipment_origins[placement.tag] = origin
        if geometry:
            register_geometry_ports(registry, placement.tag, origin, geometry)
        if placement.tag in config.nozzles:
            register_nozzle_ports(registry, config.nozzles[placement.tag], origin)

    for tag, placement in config.nozzles.items():
        origin = equipment_origins.get(tag)
        if origin is None:
            raise ConfigError(f"No placement found for nozzle owner {tag}")
        for name, nozzle in placement.nozzles.items():
            draw_nozzle(ctx, tag, origin, name, nozzle)

    route_points = _build_routes(registry)
    route_points = {tag: (service, _orthogonalize(points), major) for tag, (service, points, major) in route_points.items()}
    valve_layout: dict[str, tuple[object, Point, str]] = {}
    valve_gaps: dict[str, list[tuple[Point, float]]] = {}
    station_points = _valve_station_points(config.valves, route_points)
    for valve in config.valves:
        point, orientation = station_points[valve.tag]
        valve_layout[valve.tag] = (replace(valve, orientation=orientation), point, orientation)
        valve_gaps.setdefault(valve.pipe_segment, []).append((point, _valve_gap_half(valve.type)))

    for line_tag, (service, points, major) in route_points.items():
        gaps = valve_gaps.get(line_tag, [])
        if major:
            draw_header(ctx, points, line_tag, service, _layer_for_line(line_tag), gaps)
        else:
            draw_branch(ctx, points, line_tag, service, _layer_for_line(line_tag), gaps)

    for valve, point, _orientation in valve_layout.values():
        draw_valve_on_line(ctx, valve, point[0], point[1])

    place_instruments(ctx, config.instruments)
    signal_warnings = route_signals(ctx, config.signals)

    engineering_report = run_engineering_validation(config, registry)
    engineering_report.warnings.extend(config.warnings)
    engineering_report.warnings.extend(signal_warnings)
    visual_report = run_visual_validation(registry, final_mode=style == "final")

    if qa_overlay:
        draw_qa_overlay(ctx)

    if validate and style == "final" and (not engineering_report.ok or not visual_report.ok):
        raise ConfigError(engineering_report.format() + "\n\n" + visual_report.format())

    _apply_epc_drafting_refinements(ctx)

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output)
    if pdf_output:
        print("PDF export requested, but LibreCAD CLI export is not configured in this environment.")
    return engineering_report.format(), visual_report.format()


def _setup_doc(doc: ezdxf.EzDxfDocument, style_profile) -> None:
    layers = {
        "BORDER": style_profile.border_color,
        "TABLE": 8,
        "TEXT": style_profile.text_color,
        "EQUIPMENT": style_profile.equipment_color,
        "SYMBOLS": style_profile.equipment_color,
        "NOZZLES": style_profile.process_color,
        "PROCESS": style_profile.process_color,
        "UTILITY": style_profile.utility_color,
        "FLARE": 7,
        "DRAIN": 8,
        "VALVES": style_profile.process_color,
        "INSTRUMENT": style_profile.instrument_color,
        "SIGNAL_ELECTRIC": style_profile.signal_color,
        "SIGNAL_PNEUMATIC": style_profile.signal_color,
        "SIGNAL_SOFTWARE": style_profile.signal_color,
        "SIGNAL_SIS": style_profile.signal_color,
        "IMPULSE_LINE": style_profile.signal_color,
        "OFFPAGE": style_profile.process_color,
        "QA_OVERLAY": style_profile.qa_color,
    }
    for name, color in layers.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    for ltype, pattern in {
        "DASHED": [0.2, 0.12, -0.06],
        "DOTTED": [0.1, 0.01, -0.05],
        "DASHDOT": [0.3, 0.12, -0.05, 0.01, -0.05],
        "SHORT_DASH": [1.5, 1.0, -0.5],
    }.items():
        if ltype not in doc.linetypes:
            doc.linetypes.add(ltype, pattern=pattern)
    doc.header["$LTSCALE"] = 1.0
    doc.header["$CELTSCALE"] = 1.0


def _draw_sheet(ctx: DrawContext, config) -> None:
    s = ctx.standard
    ctx.msp.add_lwpolyline([(s.border_margin, s.border_margin), (s.sheet_w - s.border_margin, s.border_margin), (s.sheet_w - s.border_margin, s.sheet_h - s.border_margin), (s.border_margin, s.sheet_h - s.border_margin), (s.border_margin, s.border_margin)], dxfattribs={"layer": "BORDER"})
    ctx.msp.add_lwpolyline([(s.inner_border_margin, s.inner_border_margin), (s.sheet_w - s.inner_border_margin, s.inner_border_margin), (s.sheet_w - s.inner_border_margin, s.sheet_h - s.inner_border_margin), (s.inner_border_margin, s.sheet_h - s.inner_border_margin), (s.inner_border_margin, s.inner_border_margin)], dxfattribs={"layer": "BORDER"})
    draw_title_block(ctx, "DEETHANIZER COLUMN P&ID", "U400-PID-401", "A", config.package.area_code, config.package.service, "STUDY")
    notes = config.labels.raw.get("labels_and_annotations", {}).get("annotation_notes", {}).get("drafting_notes", [])
    draw_notes_block(ctx, notes)
    draw_legend(ctx)
    draw_revision_table(ctx)


def _draw_offpages(ctx: DrawContext) -> None:
    offpages = [
        OffPageConnector("OPC_FEED_FROM_UPSTREAM_C2_C3_SECTION", "FEED FROM C2/C3 SECTION", "FROM PID-400", 85, 392, "left"),
        OffPageConnector("OPC_C2_OVERHEAD_TO_ACETYLENE_HYDROGENATION_OR_C2_SPLITTER", "C2 OVERHEAD PRODUCT", "TO PID-520 / PID-600", 1115, 610, "right"),
        OffPageConnector("OPC_C3PLUS_BOTTOMS_EXPORT", "C3+ BOTTOMS EXPORT", "TO PID-600 / EXPORT", 85, 268, "left"),
        OffPageConnector("OPC_FLARE_HEADER", "TO FLARE HEADER", "TO PID-700", 1115, 735, "right"),
        OffPageConnector("OPC_CLOSED_DRAIN_HEADER", "TO CLOSED DRAIN", "TO PID-700", 1115, 90, "right"),
        OffPageConnector("OPC_CW_SUPPLY", "COOLING WATER SUPPLY", "FROM PID-800", 1115, 690, "right"),
        OffPageConnector("OPC_CW_RETURN", "COOLING WATER RETURN", "TO PID-800", 1115, 560, "right"),
        OffPageConnector("OPC_HM_SUPPLY", "HEATING MEDIUM SUPPLY", "FROM PID-810", 1115, 370, "right"),
        OffPageConnector("OPC_HM_RETURN", "HEATING MEDIUM RETURN", "TO PID-810", 1115, 335, "right"),
    ]
    for opc in offpages:
        draw_offpage_connector(ctx, opc)


def _build_routes(registry: SceneRegistry) -> dict[str, tuple[str, list[Point], bool]]:
    p = registry.ports
    for name, point in {
        "J_RFLX_SUC_HEADER": (755, 545),
        "J_RFLX_DIS_HEADER": (900, 525),
        "J_RFLX_MIN_TAKEOFF": (820, 525),
        "J_BTM_SUC_HEADER": (390, 240),
        "J_BTM_DIS_HEADER": (555, 268),
    }.items():
        registry.add_port(name, point, "pipe_junction")
    routes: dict[str, tuple[str, list[Point], bool]] = {}
    routes["500-FEED-001"] = ("DEETHANIZER FEED", [p["OPC_FEED_FROM_UPSTREAM_C2_C3_SECTION.continuation"], (220, 392), p["E-503.N1_cold_feed_in.connection_point"]], True)
    routes["500-FEED-002"] = ("PREHEATED FEED TO T-501", [p["E-503.N2_cold_feed_out.connection_point"], (390, 392), p["T-501.N1_feed_inlet.connection_point"]], True)
    routes["500-OVHD-001"] = ("COLUMN OVERHEAD VAPOR", [p["T-501.N2_overhead_vapor_outlet.connection_point"], (520, 650), p["E-502.N1_overhead_vapor_in.connection_point"]], True)
    routes["500-COND-001"] = ("CONDENSATE TO REFLUX DRUM", [p["E-502.N2_condensate_out.connection_point"], p["V-501.N1_condensate_inlet.connection_point"]], True)
    routes["500-C2-PROD-001"] = ("C2 OVERHEAD PRODUCT", [p["V-501.N3_distillate_outlet.connection_point"], (1000, 610), p["OPC_C2_OVERHEAD_TO_ACETYLENE_HYDROGENATION_OR_C2_SPLITTER.continuation"]], True)
    routes["500-RFLX-SUC-001"] = ("REFLUX PUMP SUCTION", [p["V-501.N4_reflux_pump_suction.connection_point"], (858, 545), p["J_RFLX_SUC_HEADER"]], True)
    routes["500-RFLX-SUC-001A"] = ("REFLUX PUMP SUCTION", [p["J_RFLX_SUC_HEADER"], (755, 495), p["P-501A.N1_suction.connection_point"]], False)
    routes["500-RFLX-SUC-001B"] = ("REFLUX PUMP SUCTION", [p["J_RFLX_SUC_HEADER"], (755, 450), p["P-501B.N1_suction.connection_point"]], False)
    routes["500-RFLX-DIS-001A"] = ("REFLUX PUMP DISCHARGE", [p["P-501A.N2_discharge.connection_point"], (900, 495), p["J_RFLX_DIS_HEADER"]], False)
    routes["500-RFLX-DIS-001B"] = ("REFLUX PUMP DISCHARGE", [p["P-501B.N2_discharge.connection_point"], (900, 450), p["J_RFLX_DIS_HEADER"]], False)
    routes["500-RFLX-001"] = ("REFLUX RETURN TO COLUMN", [p["J_RFLX_DIS_HEADER"], (690, 525), (690, 508), p["T-501.N3_reflux_return.connection_point"]], True)
    routes["500-RFLX-MIN-001"] = ("REFLUX MINIMUM FLOW RECYCLE", [p["J_RFLX_MIN_TAKEOFF"], (820, 570), p["V-501.N1_condensate_inlet.connection_point"]], False)
    routes["500-RB-001"] = ("REBOILER LIQUID DRAW", [p["T-501.N4_reboiler_liquid_draw.connection_point"], p["E-501.N1_column_liquid_in.connection_point"]], True)
    routes["500-RB-002"] = ("REBOILER VAPOR RETURN", [p["E-501.N2_vapor_return.connection_point"], p["T-501.N5_reboiler_vapor_return.connection_point"]], True)
    routes["500-BTM-SUC-001"] = ("COLUMN BOTTOMS TO PUMPS", [p["T-501.N6_bottoms_outlet.connection_point"], (520, 240), p["J_BTM_SUC_HEADER"]], True)
    routes["500-BTM-SUC-001A"] = ("BOTTOMS PUMP SUCTION", [p["J_BTM_SUC_HEADER"], (390, 205), p["P-502A.N1_suction.connection_point"]], False)
    routes["500-BTM-SUC-001B"] = ("BOTTOMS PUMP SUCTION", [p["J_BTM_SUC_HEADER"], (390, 160), p["P-502B.N1_suction.connection_point"]], False)
    routes["500-BTM-DIS-001A"] = ("BOTTOMS PUMP DISCHARGE", [p["P-502A.N2_discharge.connection_point"], (555, 205), p["J_BTM_DIS_HEADER"]], False)
    routes["500-BTM-DIS-001B"] = ("BOTTOMS PUMP DISCHARGE", [p["P-502B.N2_discharge.connection_point"], (555, 160), p["J_BTM_DIS_HEADER"]], False)
    routes["500-C3PLUS-001"] = ("HOT C3+ BOTTOMS TO E-503", [p["J_BTM_DIS_HEADER"], (390, 268), p["E-503.N3_hot_bottoms_in.connection_point"]], True)
    routes["500-C3PLUS-002"] = ("C3+ BOTTOMS EXPORT", [p["E-503.N4_hot_bottoms_out.connection_point"], (170, 268), p["OPC_C3PLUS_BOTTOMS_EXPORT.continuation"]], True)
    routes["500-FL-501A"] = ("COLUMN RELIEF TO FLARE", [p["T-501.N9_psv_tap.connection_point"], (430, 650), (430, 720), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-FL-501B"] = ("COLUMN RELIEF TO FLARE", [p["T-501.N9_psv_tap.connection_point"], (465, 650), (465, 720), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-FL-502"] = ("REFLUX DRUM RELIEF TO FLARE", [p["V-501.N6_psv_tap.connection_point"], (820, 720), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-VT-501"] = ("COLUMN VENT TO FLARE", [p["T-501.N7_column_vent_to_flare.connection_point"], (600, 735), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-VT-502"] = ("REFLUX DRUM VENT TO FLARE", [p["V-501.N2_vapor_vent_to_flare.connection_point"], (840, 735), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-CD-501"] = ("COLUMN CLOSED DRAIN", [p["T-501.N8_column_drain.connection_point"], (720, 90), p["OPC_CLOSED_DRAIN_HEADER.continuation"]], False)
    routes["500-CD-502"] = ("REFLUX DRUM CLOSED DRAIN", [p["V-501.N5_drain.connection_point"], (1080, 90), p["OPC_CLOSED_DRAIN_HEADER.continuation"]], False)
    routes["500-CD-503"] = ("REBOILER DRAIN", [p["E-501.N7_reboiler_drain.connection_point"], (734, 90), p["OPC_CLOSED_DRAIN_HEADER.continuation"]], False)
    routes["500-CD-504"] = ("CONDENSER DRAIN", [p["E-502.N6_condenser_drain.connection_point"], (680, 560), p["OPC_CW_RETURN.continuation"]], False)
    routes["500-CW-001"] = ("COOLING WATER SUPPLY", [p["OPC_CW_SUPPLY.continuation"], (700, 690), p["E-502.N3_cooling_utility_in.connection_point"]], False)
    routes["500-CW-002"] = ("COOLING WATER RETURN", [p["E-502.N4_cooling_utility_out.connection_point"], (700, 560), p["OPC_CW_RETURN.continuation"]], False)
    routes["500-HM-001"] = ("REBOILER HEATING MEDIUM SUPPLY", [p["OPC_HM_SUPPLY.continuation"], (720, 370), p["E-501.N4_hot_utility_in.connection_point"]], False)
    routes["500-HM-002"] = ("REBOILER HEATING MEDIUM RETURN", [p["E-501.N5_hot_utility_out.connection_point"], (720, 335), p["OPC_HM_RETURN.continuation"]], False)
    return routes


def _layer_for_line(tag: str) -> str:
    if "-FL-" in tag or "-VT-" in tag:
        return "FLARE"
    if "-CD-" in tag:
        return "DRAIN"
    if "-CW-" in tag or "-HM-" in tag:
        return "UTILITY"
    return "PROCESS"


def _orthogonalize(points: list[Point]) -> list[Point]:
    if len(points) < 2:
        return points
    out: list[Point] = [points[0]]
    for next_point in points[1:]:
        prev = out[-1]
        if prev[0] != next_point[0] and prev[1] != next_point[1]:
            elbow = (next_point[0], prev[1])
            if elbow != prev:
                out.append(elbow)
        if next_point != out[-1]:
            out.append(next_point)
    return out


def _valve_station_points(valves, routes: dict[str, tuple[str, list[Point], bool]]) -> dict[str, tuple[Point, str]]:
    by_segment: dict[str, list] = {}
    for valve in valves:
        by_segment.setdefault(valve.pipe_segment, []).append(valve)
    out: dict[str, tuple[Point, str]] = {}
    for pipe_segment, group in by_segment.items():
        for idx, valve in enumerate(group, start=1):
            out[valve.tag] = _valve_point(valve.tag, pipe_segment, routes, valve.orientation, valve.station, idx, len(group))
    return out


def _valve_point(tag: str, pipe_segment: str, routes: dict[str, tuple[str, list[Point], bool]], requested_orientation: str = "horizontal", station: str = "", index: int = 1, count: int = 1) -> tuple[Point, str]:
    if tag in _EXPLICIT_VALVE_STATIONS:
        return _EXPLICIT_VALVE_STATIONS[tag]
    _, points, _ = routes.get(pipe_segment, next(iter(routes.values())))
    segments = list(zip(points, points[1:]))
    wants_vertical = requested_orientation.startswith("v")
    matching = [seg for seg in segments if (seg[0][0] == seg[1][0]) == wants_vertical]
    candidates = matching or segments
    p1, p2 = _station_segment(candidates, station)
    orientation = "vertical" if p1[0] == p2[0] else "horizontal"
    fraction = _station_fraction(station, index, count)
    return (p1[0] + (p2[0] - p1[0]) * fraction, p1[1] + (p2[1] - p1[1]) * fraction), orientation


def _station_segment(segments: list[tuple[Point, Point]], station: str) -> tuple[Point, Point]:
    if not segments:
        return ((0.0, 0.0), (0.0, 0.0))
    station_l = station.lower()
    if "immediately_downstream" in station_l or "upstream_of_p-" in station_l or "upstream_of_e-" in station_l:
        return segments[-1]
    if "connected_to" in station_l or "downstream_of_t-" in station_l or "downstream_of_v-" in station_l:
        return segments[0]
    return max(segments, key=lambda seg: abs(seg[1][0] - seg[0][0]) + abs(seg[1][1] - seg[0][1]))


def _station_fraction(station: str, index: int, count: int) -> float:
    station_l = station.lower()
    if "immediately_downstream" in station_l:
        return 0.35
    if "upstream_of_p-" in station_l or "upstream_of_e-" in station_l:
        return 0.70
    if "upstream_of_opc" in station_l:
        return 0.78
    if "downstream_of_nrv" in station_l:
        return 0.72
    if "connected_to" in station_l:
        return 0.55
    if "downstream_of_t-" in station_l or "downstream_of_v-" in station_l:
        return 0.38
    if "takeoff" in station_l:
        return 0.30
    return index / (count + 1)


def _valve_gap_half(valve_type: str) -> float:
    if valve_type in {"manual_block_valve", "check_valve"}:
        return 5.0
    if valve_type == "restriction_orifice":
        return 4.0
    if valve_type == "relief_valve":
        return 7.0
    return 14.0


_EXPLICIT_VALVE_STATIONS: dict[str, tuple[Point, str]] = {
    "XV-501": ((230.0, 392.0), "horizontal"),
    "HV-503": ((1040.0, 610.0), "horizontal"),
    "HV-515": ((600.0, 710.0), "vertical"),
    "HV-516": ((840.0, 710.0), "vertical"),
    "PSV-502": ((820.0, 665.0), "vertical"),
    "HV-517": ((720.0, 120.0), "vertical"),
    "HV-518": ((1080.0, 120.0), "vertical"),
    "HV-519": ((734.0, 120.0), "vertical"),
}


def _apply_epc_drafting_refinements(ctx: DrawContext) -> None:
    """Final deterministic drafting pass for EPC-style readability.

    The YAML-driven renderer establishes topology. This pass enforces local
    drafting rules that are easier to express against concrete CAD entities:
    signal corridors, enlarged impulse root valves, vertical nozzle takeoffs,
    and clean utility drops.
    """
    msp = ctx.msp
    signal_layers = {"SIGNAL_ELECTRIC", "SIGNAL_PNEUMATIC", "SIGNAL_SOFTWARE", "SIGNAL_SIS", "IMPULSE_LINE"}

    def near(a: float, b: float, tol: float = 0.35) -> bool:
        return abs(float(a) - float(b)) <= tol

    def midpoint(entity) -> Point:
        p1 = entity.dxf.start
        p2 = entity.dxf.end
        return ((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)

    def in_box(entity, box: tuple[float, float, float, float]) -> bool:
        x, y = midpoint(entity)
        xmin, ymin, xmax, ymax = box
        return xmin <= x <= xmax and ymin <= y <= ymax

    def delete_lines(*, layer: str | None = None, box: tuple[float, float, float, float] | None = None, layers: set[str] | None = None) -> None:
        for entity in list(msp.query("LINE")):
            if layer and entity.dxf.layer != layer:
                continue
            if layers and entity.dxf.layer not in layers:
                continue
            if box and not in_box(entity, box):
                continue
            msp.delete_entity(entity)

    def delete_polys(*, layer: str, box: tuple[float, float, float, float]) -> None:
        xmin, ymin, xmax, ymax = box
        for entity in list(msp.query("LWPOLYLINE")):
            if entity.dxf.layer != layer:
                continue
            points = [(p[0], p[1]) for p in entity.get_points()]
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            cx = (min(xs) + max(xs)) / 2
            cy = (min(ys) + max(ys)) / 2
            if xmin <= cx <= xmax and ymin <= cy <= ymax:
                msp.delete_entity(entity)

    def add_line(layer: str, p1: Point, p2: Point, lineweight: int = 13) -> None:
        if p1 != p2:
            msp.add_line(p1, p2, dxfattribs={"layer": layer, "lineweight": lineweight})

    def add_poly(layer: str, points: list[Point], lineweight: int = 18) -> None:
        msp.add_lwpolyline(points, dxfattribs={"layer": layer, "lineweight": lineweight})

    def dashed(layer: str, points: list[Point], dash: float = 4.0, gap: float = 2.0) -> None:
        for p1, p2 in zip(points, points[1:]):
            x1, y1 = p1
            x2, y2 = p2
            if near(x1, x2, 1e-6):
                direction = 1 if y2 >= y1 else -1
                pos = y1
                while (pos - y2) * direction < 0:
                    end = pos + direction * min(dash, abs(y2 - pos))
                    add_line(layer, (x1, pos), (x1, end))
                    pos = end + direction * gap
            elif near(y1, y2, 1e-6):
                direction = 1 if x2 >= x1 else -1
                pos = x1
                while (pos - x2) * direction < 0:
                    end = pos + direction * min(dash, abs(x2 - pos))
                    add_line(layer, (pos, y1), (end, y1))
                    pos = end + direction * gap
            else:
                add_line(layer, p1, p2)

    def move_insert(name: str, old: Point, new: Point) -> None:
        for entity in msp.query("INSERT"):
            p = entity.dxf.insert
            if entity.dxf.name == name and near(p.x, old[0]) and near(p.y, old[1]):
                entity.dxf.insert = (new[0], new[1], p.z)

    def move_text(text: str, new: Point) -> None:
        for entity in msp.query("TEXT"):
            if entity.dxf.text == text:
                p = entity.dxf.insert
                entity.dxf.insert = (new[0], new[1], p.z)

    def add_jump(x: float, y: float) -> None:
        msp.add_arc((x, y), 3.0, 0, 180, dxfattribs={"layer": "SIGNAL_ELECTRIC"})

    # No process flow arrow layer in final EPC-style drawing.
    for entity in list(msp):
        if entity.dxf.layer == "FLOW_DIRECTION":
            msp.delete_entity(entity)

    # Off-page arrows point with service direction, not just sheet side.
    offpage_rotations = {
        (85, 392): 180, (85, 268): 0, (1115, 610): 180,
        (1115, 735): 180, (1115, 90): 180, (1115, 690): 0,
        (1115, 560): 180, (1115, 370): 0, (1115, 335): 180,
    }
    for entity in msp.query("INSERT"):
        if entity.dxf.name != "YAML_PID_OFFPAGE_CONNECTOR":
            continue
        p = entity.dxf.insert
        rotation = offpage_rotations.get((round(p.x), round(p.y)))
        if rotation is not None:
            entity.dxf.rotation = rotation

    # Small impulse-line root valves are intentionally legible.
    for entity in msp.query("INSERT"):
        if entity.dxf.name == "YAML_PID_MANUAL_BLOCK_VALVE" and entity.dxf.xscale < 1 and entity.dxf.yscale < 1:
            entity.dxf.xscale = float(entity.dxf.xscale) * 5
            entity.dxf.yscale = float(entity.dxf.yscale) * 5

    # Column DPI/DPT and LT/LIC lanes.
    delete_lines(layers=signal_layers, box=(418, 278, 506, 448))
    add_line("IMPULSE_LINE", (488, 358), (476, 358))
    add_line("IMPULSE_LINE", (476, 358), (476, 430))
    add_line("IMPULSE_LINE", (476, 430), (469, 430))
    add_line("IMPULSE_LINE", (488, 348), (476, 348))
    add_line("IMPULSE_LINE", (476, 348), (476, 337))
    add_line("IMPULSE_LINE", (476, 337), (472, 337))
    add_line("IMPULSE_LINE", (488, 326), (476, 326))
    add_line("IMPULSE_LINE", (476, 326), (476, 337))
    dashed("SIGNAL_ELECTRIC", [(455, 430), (455, 445), (430, 445), (430, 435)])
    dashed("SIGNAL_ELECTRIC", [(447, 337), (456, 337)])

    # PT-501 signal goes to PIC only.
    delete_lines(layers=signal_layers, box=(388, 500, 540, 692))
    add_line("IMPULSE_LINE", (488, 522), (469, 522))
    dashed("SIGNAL_ELECTRIC", [(455, 522), (390, 522), (390, 690), (539, 690)])

    # Shutdown feedback is split left/right of XV-501 stem.
    move_insert("YAML_PID_FIELD_INSTRUMENT", (210, 450), (205, 450))
    move_insert("YAML_PID_FIELD_INSTRUMENT", (210, 432), (238, 450))
    move_text("ZSO-501", (198.7, 448.5))
    move_text("ZSC-501", (231.7, 448.5))
    delete_lines(layer="SIGNAL_ELECTRIC", box=(198, 410, 260, 458))
    dashed("SIGNAL_ELECTRIC", [(212, 450), (225, 450), (225, 408)])
    dashed("SIGNAL_ELECTRIC", [(231, 450), (235, 450), (235, 408)])

    # Reflux drum level/control: LIC left of LT, signal routes over vessel.
    for alarm, pos in {"H": (751, 614), "L": (751, 606), "HH": (751, 598)}.items():
        move_text(alarm, pos)
    delete_lines(layers=signal_layers, box=(748, 570, 970, 615))
    add_line("IMPULSE_LINE", (790, 620), (784, 620))
    add_line("IMPULSE_LINE", (775, 620), (766.9, 620))
    add_line("IMPULSE_LINE", (790, 600), (786.8, 600))
    add_line("IMPULSE_LINE", (778, 600), (773.1, 600))
    add_line("IMPULSE_LINE", (755, 620), (755, 601))
    dashed("SIGNAL_ELECTRIC", [(763, 610), (749, 610), (749, 640), (932, 640), (932, 625)])
    for x in (790, 858, 890):
        add_jump(x, 640)

    # PSV-502 and PT/PI-502 vertical nozzle discipline.
    delete_lines(layer="FLARE", box=(812, 630, 824, 722))
    move_insert("YAML_PID_RELIEF_VALVE", (820, 665), (816, 665))
    move_text("PSV-502", (825.1, 664))
    add_line("FLARE", (816, 633), (816, 658))
    add_line("FLARE", (816, 672), (816, 720))
    delete_lines(layers=signal_layers, box=(868, 630, 914, 672))
    move_insert("YAML_PID_MANUAL_BLOCK_VALVE", (877.85, 633), (872, 638))
    for entity in msp.query("INSERT"):
        p = entity.dxf.insert
        if entity.dxf.name == "YAML_PID_MANUAL_BLOCK_VALVE" and near(p.x, 872) and near(p.y, 638):
            entity.dxf.rotation = 90
    add_line("IMPULSE_LINE", (872, 633), (872, 638))
    add_line("IMPULSE_LINE", (872, 638), (872, 648))
    add_line("IMPULSE_LINE", (872, 662), (872, 671))
    dashed("SIGNAL_ELECTRIC", [(881, 655), (895, 655), (895, 682), (883, 682)])
    add_poly("INSTRUMENT", [(861, 671), (883, 671), (883, 693), (861, 693), (861, 671)], 13)

    # E-502 utility segregation: top inlet, bottom return/drop.
    delete_polys(layer="UTILITY", box=(620, 555, 705, 695))
    add_poly("UTILITY", [(700, 690), (680, 690), (680, 670)])
    add_poly("UTILITY", [(632, 630), (632, 560), (700, 560)])
    add_line("NOZZLES", (680, 667), (680, 670))
    add_line("NOZZLES", (632, 633), (632, 630))

    # E-501 local thermosiphon/reboiler drafting: stepped branches and clear TT/TI taps.
    delete_polys(layer="PROCESS", box=(548, 310, 660, 382))
    delete_lines(layer="IMPULSE_LINE", box=(645, 320, 790, 375))
    add_poly("PROCESS", [(552.8, 370), (625, 370), (625, 348), (653.6, 348), (653.6, 336), (661.3, 336)])
    add_poly("PROCESS", [(552.8, 348), (598.2, 348)])
    add_poly("PROCESS", [(608.2, 348), (625, 348)])
    add_poly("PROCESS", [(552.8, 327), (598.2, 327)])
    add_poly("PROCESS", [(608.2, 327), (625, 327), (625, 315), (661.3, 315)])
    add_line("IMPULSE_LINE", (653.6, 348), (653.6, 371))
    add_line("IMPULSE_LINE", (653.6, 371), (782, 371))
    add_line("IMPULSE_LINE", (760, 371), (760, 364))
    add_line("IMPULSE_LINE", (782, 371), (782, 364))

    # Pneumatic routes that would otherwise cross the feed control valve and DCS block.
    delete_lines(layer="SIGNAL_PNEUMATIC", box=(205, 286, 482, 426))
    add_line("SIGNAL_PNEUMATIC", (214.4, 292), (190, 292))
    add_line("SIGNAL_PNEUMATIC", (190, 292), (190, 423))
    add_line("SIGNAL_PNEUMATIC", (190, 423), (214.4, 423))
    add_line("SIGNAL_PNEUMATIC", (214.4, 292), (214.4, 270))
    add_line("SIGNAL_PNEUMATIC", (214.4, 270), (476, 270))
    add_line("SIGNAL_PNEUMATIC", (476, 270), (476, 292))

    # Remove exact duplicates introduced by local redraws.
    seen: set[tuple[str, Point, Point]] = set()
    for entity in list(msp.query("LINE")):
        if entity.dxf.layer not in signal_layers | {"UTILITY", "FLARE", "NOZZLES"}:
            continue
        a = (round(entity.dxf.start.x, 3), round(entity.dxf.start.y, 3))
        b = (round(entity.dxf.end.x, 3), round(entity.dxf.end.y, 3))
        key = (entity.dxf.layer, min(a, b), max(a, b))
        if key in seen:
            msp.delete_entity(entity)
        else:
            seen.add(key)
