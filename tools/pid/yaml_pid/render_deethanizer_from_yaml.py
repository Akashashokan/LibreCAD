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
    route_around_equipment,
)
from .config_loader import load_pid_config
from .drafting_standard import DEFAULT_STANDARD, style_from_name
from .engineering_validation import run_engineering_validation
from .grid import GridPoint, snap_point, snap_points
from .instrument_zones import place_instruments
from .models import ConfigError, OffPageConnector
from .ports import register_geometry_ports, register_nozzle_ports
from .scene import SceneRegistry
from .signal_routing import route_signals
from .subsystem_validation import run_e501_subsystem_validation
from .symbol_resolver import SymbolResolver
from .visual_validation import draw_qa_overlay, run_visual_validation

Point = tuple[float, float]


def render_deethanizer_from_yaml(
    *,
    config_dir: Path,
    output: Path,
    block_dir: Path,
    drawing_no: str = "U400-PID-401",
    style: str = "final",
    qa_overlay: bool = False,
    validate: bool = True,
    pdf_output: Path | None = None,
) -> tuple[str, str, str]:
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

    _draw_sheet(ctx, config, drawing_no)

    equipment_origins: dict[str, Point] = {}
    for placement in config.equipment:
        if placement.block_key == "relief_valve":
            registry.mark("equipment", placement.tag)
            continue
        geometry = config.block_geometry.get(placement.block_key)
        origin = GridPoint(placement.x, placement.y).snap()
        snapped_placement = replace(placement, x=origin[0], y=origin[1])
        draw_equipment(ctx, snapped_placement, geometry)
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

    _draw_offpages(ctx)

    route_points = _build_routes(registry)
    route_points = {tag: (service, _orthogonalize(points, registry.nozzle_axes), major) for tag, (service, points, major) in route_points.items()}
    route_points = {
        tag: (service, route_around_equipment(ctx, points, _layer_for_line(tag)), major)
        for tag, (service, points, major) in route_points.items()
    }
    valve_layout: dict[str, tuple[object, Point, str]] = {}
    valve_gaps: dict[str, list[tuple[Point, float]]] = {}
    station_points = _valve_station_points(config.valves, route_points)
    for valve in config.valves:
        point, orientation = station_points[valve.tag]
        valve_layout[valve.tag] = (replace(valve, orientation=orientation), point, orientation)
        valve_gaps.setdefault(valve.pipe_segment, []).append((point, _valve_gap_half(valve.type)))
    crossing_gaps = _route_crossing_gaps(route_points, registry.ports)

    for line_tag, (service, points, major) in route_points.items():
        gaps = [*valve_gaps.get(line_tag, []), *crossing_gaps.get(line_tag, [])]
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
    subsystem_report = run_e501_subsystem_validation(registry)

    if qa_overlay:
        draw_qa_overlay(ctx)

    if validate and style == "final" and (not engineering_report.ok or not visual_report.ok):
        failed_debug = output.with_name(f"{output.stem}-failed-geometry-debug{output.suffix}")
        draw_qa_overlay(ctx)
        failed_debug.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(failed_debug)
        raise ConfigError(engineering_report.format() + "\n\n" + visual_report.format())

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output)
    if pdf_output:
        print("PDF export requested, but LibreCAD CLI export is not configured in this environment.")
    return engineering_report.format(), visual_report.format(), subsystem_report.format()


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


def _draw_sheet(ctx: DrawContext, config, drawing_no: str) -> None:
    s = ctx.standard
    ctx.msp.add_lwpolyline([(s.border_margin, s.border_margin), (s.sheet_w - s.border_margin, s.border_margin), (s.sheet_w - s.border_margin, s.sheet_h - s.border_margin), (s.border_margin, s.sheet_h - s.border_margin), (s.border_margin, s.border_margin)], dxfattribs={"layer": "BORDER"})
    ctx.msp.add_lwpolyline([(s.inner_border_margin, s.inner_border_margin), (s.sheet_w - s.inner_border_margin, s.inner_border_margin), (s.sheet_w - s.inner_border_margin, s.sheet_h - s.inner_border_margin), (s.inner_border_margin, s.sheet_h - s.inner_border_margin), (s.inner_border_margin, s.inner_border_margin)], dxfattribs={"layer": "BORDER"})
    draw_title_block(ctx, "DEETHANIZER COLUMN P&ID", drawing_no, "A", config.package.area_code, config.package.service, "STUDY")
    notes = config.labels.raw.get("labels_and_annotations", {}).get("annotation_notes", {}).get("drafting_notes", [])
    draw_notes_block(ctx, notes)
    draw_legend(ctx)
    draw_revision_table(ctx)


def _draw_offpages(ctx: DrawContext) -> None:
    offpages = [
        OffPageConnector("OPC_FEED_FROM_UPSTREAM_C2_C3_SECTION", "FEED FROM C2/C3 SECTION", "FROM PID-400", 85, 465, "left"),
        OffPageConnector("OPC_C2_OVERHEAD_TO_ACETYLENE_HYDROGENATION_OR_C2_SPLITTER", "C2 OVERHEAD PRODUCT", "TO PID-520 / PID-600", 1115, 650, "right"),
        OffPageConnector("OPC_C3PLUS_BOTTOMS_EXPORT", "C3+ BOTTOMS EXPORT", "TO PID-600 / EXPORT", 85, 290, "left"),
        OffPageConnector("OPC_FLARE_HEADER", "TO FLARE HEADER", "TO PID-700", 1115, 760, "right"),
        OffPageConnector("OPC_CLOSED_DRAIN_HEADER", "TO CLOSED DRAIN", "TO PID-700", 1115, 155, "right"),
        OffPageConnector("OPC_CW_SUPPLY", "COOLING WATER SUPPLY", "FROM PID-800", 1115, 700, "right"),
        OffPageConnector("OPC_CW_RETURN", "COOLING WATER RETURN", "TO PID-800", 1115, 610, "right"),
        OffPageConnector("OPC_HM_SUPPLY", "HEATING MEDIUM SUPPLY", "FROM PID-810", 1115, 330, "right"),
        OffPageConnector("OPC_HM_RETURN", "HEATING MEDIUM RETURN", "TO PID-810", 1115, 300, "right"),
    ]
    for opc in offpages:
        x, y = GridPoint(opc.x, opc.y).snap()
        draw_offpage_connector(ctx, replace(opc, x=x, y=y))


def _build_routes(registry: SceneRegistry) -> dict[str, tuple[str, list[Point], bool]]:
    p = registry.ports
    for name, point in {
        "J_RFLX_SUC_HEADER": (858, 522),
        "J_RFLX_DIS_HEADER": (900, 525),
        "J_RFLX_MIN_TAKEOFF": (900, 525),
        "J_BTM_SUC_HEADER": (555, 215),
        "J_BTM_DIS_HEADER": (700, 225),
        "J_C3PLUS_TO_E503": (250, 140),
    }.items():
        registry.add_port(name, snap_point(point), "pipe_junction")
    routes: dict[str, tuple[str, list[Point], bool]] = {}
    routes["500-FEED-001"] = ("DEETHANIZER FEED", [p["OPC_FEED_FROM_UPSTREAM_C2_C3_SECTION.continuation"], p["E-503.N1_cold_feed_in.connection_point"]], True)
    routes["500-FEED-002"] = ("PREHEATED FEED TO T-501", [p["E-503.N2_cold_feed_out.connection_point"], p["T-501.N1_feed_inlet.connection_point"]], True)
    routes["500-OVHD-001"] = ("COLUMN OVERHEAD VAPOR", [p["T-501.N2_overhead_vapor_outlet.connection_point"], (500, 650), p["E-502.N1_overhead_vapor_in.connection_point"]], True)
    routes["500-COND-001"] = ("CONDENSATE TO REFLUX DRUM", [p["E-502.N2_condensate_out.connection_point"], p["V-501.N1_condensate_inlet.connection_point"]], True)
    routes["500-C2-PROD-001"] = ("C2 OVERHEAD PRODUCT", [p["V-501.N3_distillate_outlet.connection_point"], p["OPC_C2_OVERHEAD_TO_ACETYLENE_HYDROGENATION_OR_C2_SPLITTER.continuation"]], True)
    routes["500-RFLX-SUC-001"] = ("REFLUX PUMP SUCTION", [p["V-501.N4_reflux_pump_suction.connection_point"], (858, 522), p["J_RFLX_SUC_HEADER"]], True)
    routes["500-RFLX-SUC-001A"] = ("REFLUX PUMP SUCTION", [p["J_RFLX_SUC_HEADER"], (760, 522), (760, 545), p["P-501A.N1_suction.connection_point"]], False)
    routes["500-RFLX-SUC-001B"] = ("REFLUX PUMP SUCTION", [p["J_RFLX_SUC_HEADER"], (760, 522), (760, 500), p["P-501B.N1_suction.connection_point"]], False)
    routes["500-RFLX-DIS-001A"] = ("REFLUX PUMP DISCHARGE", [p["P-501A.N2_discharge.connection_point"], (900, 553), p["J_RFLX_DIS_HEADER"]], False)
    routes["500-RFLX-DIS-001B"] = ("REFLUX PUMP DISCHARGE", [p["P-501B.N2_discharge.connection_point"], (900, 508), p["J_RFLX_DIS_HEADER"]], False)
    routes["500-RFLX-001"] = ("REFLUX RETURN TO COLUMN", [p["J_RFLX_DIS_HEADER"], (900, 508), p["T-501.N3_reflux_return.connection_point"]], True)
    routes["500-RFLX-MIN-001"] = ("REFLUX MINIMUM FLOW RECYCLE", [p["J_RFLX_MIN_TAKEOFF"], (930, 690), (796, 690), p["V-501.N1_condensate_inlet.connection_point"]], False)
    routes["500-RB-001"] = ("REBOILER LIQUID DRAW", [p["T-501.N4_reboiler_liquid_draw.connection_point"], (350, 348), (350, 280), p["E-501.N1_column_liquid_in.connection_point"]], True)
    routes["500-RB-002"] = ("REBOILER VAPOR RETURN", [p["E-501.N2_vapor_return.connection_point"], (460, 292), (460, 382), p["T-501.N5_reboiler_vapor_return.connection_point"]], True)
    routes["500-BTM-SUC-001"] = ("COLUMN BOTTOMS TO PUMPS", [p["T-501.N6_bottoms_outlet.connection_point"], (500, 215), p["J_BTM_SUC_HEADER"]], True)
    routes["500-BTM-SUC-001A"] = ("BOTTOMS PUMP SUCTION", [p["J_BTM_SUC_HEADER"], (560, 215), (560, 240), p["P-502A.N1_suction.connection_point"]], False)
    routes["500-BTM-SUC-001B"] = ("BOTTOMS PUMP SUCTION", [p["J_BTM_SUC_HEADER"], (560, 215), (560, 190), p["P-502B.N1_suction.connection_point"]], False)
    routes["500-BTM-DIS-001A"] = ("BOTTOMS PUMP DISCHARGE", [p["P-502A.N2_discharge.connection_point"], (700, 248), p["J_BTM_DIS_HEADER"]], False)
    routes["500-BTM-DIS-001B"] = ("BOTTOMS PUMP DISCHARGE", [p["P-502B.N2_discharge.connection_point"], (700, 198), p["J_BTM_DIS_HEADER"]], False)
    routes["500-C3PLUS-001"] = ("HOT C3+ BOTTOMS TO E-503", [p["J_BTM_DIS_HEADER"], (700, 140), p["J_C3PLUS_TO_E503"], (250, 500), (390, 500), (390, 480), p["E-503.N3_hot_bottoms_in.connection_point"]], True)
    routes["500-C3PLUS-002"] = ("C3+ BOTTOMS EXPORT", [p["E-503.N4_hot_bottoms_out.connection_point"], (210, 481), (210, 290), p["OPC_C3PLUS_BOTTOMS_EXPORT.continuation"]], True)
    routes["500-FL-501A"] = ("COLUMN RELIEF TO FLARE", [p["T-501.N9_psv_tap.connection_point"], (430, 760), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-FL-501B"] = ("COLUMN RELIEF TO FLARE", [p["T-501.N9_psv_tap.connection_point"], (465, 760), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-FL-502"] = ("REFLUX DRUM RELIEF TO FLARE", [p["V-501.N6_psv_tap.connection_point"], (805, 760), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-VT-501"] = ("COLUMN VENT TO FLARE", [p["T-501.N7_column_vent_to_flare.connection_point"], (600, 760), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-VT-502"] = ("REFLUX DRUM VENT TO FLARE", [p["V-501.N2_vapor_vent_to_flare.connection_point"], (840, 760), p["OPC_FLARE_HEADER.continuation"]], False)
    routes["500-CD-501"] = ("COLUMN CLOSED DRAIN", [p["T-501.N8_column_drain.connection_point"], (720, 155), p["OPC_CLOSED_DRAIN_HEADER.continuation"]], False)
    routes["500-CD-502"] = ("REFLUX DRUM CLOSED DRAIN", [p["V-501.N5_drain.connection_point"], (820, 580), (1060, 580), (1060, 155), p["OPC_CLOSED_DRAIN_HEADER.continuation"]], False)
    routes["500-CD-504"] = ("CONDENSER DRAIN", [p["E-502.N6_condenser_drain.connection_point"], (680, 610), p["OPC_CW_RETURN.continuation"]], False)
    routes["500-CW-001"] = ("COOLING WATER SUPPLY", [p["OPC_CW_SUPPLY.continuation"], (780, 700), (660, 700), p["E-502.N3_cooling_utility_in.connection_point"]], False)
    routes["500-CW-002"] = ("COOLING WATER RETURN", [p["E-502.N4_cooling_utility_out.connection_point"], p["OPC_CW_RETURN.continuation"]], False)
    routes["500-HM-001"] = ("REBOILER HEATING MEDIUM SUPPLY", [p["OPC_HM_SUPPLY.continuation"], (560, 330), (560, 250), (440, 250), p["E-501.N4_hot_utility_in.connection_point"]], False)
    routes["500-HM-002"] = ("REBOILER HEATING MEDIUM RETURN", [p["E-501.N5_hot_utility_out.connection_point"], (400, 330), (350, 330), (350, 285), (1115, 285), p["OPC_HM_RETURN.continuation"]], False)
    return {tag: (service, snap_points(points), major) for tag, (service, points, major) in routes.items()}


def _layer_for_line(tag: str) -> str:
    if "-FL-" in tag or "-VT-" in tag:
        return "FLARE"
    if "-CD-" in tag:
        return "DRAIN"
    if "-CW-" in tag or "-HM-" in tag:
        return "UTILITY"
    return "PROCESS"


def _route_crossing_gaps(routes: dict[str, tuple[str, list[Point], bool]], ports: dict[str, Point]) -> dict[str, list[tuple[Point, float]]]:
    port_points = set(ports.values())
    segments: list[tuple[str, Point, Point]] = []
    for tag, (_service, points, _major) in routes.items():
        for p1, p2 in zip(points, points[1:]):
            if p1 != p2:
                segments.append((tag, p1, p2))
    gaps: dict[str, list[tuple[Point, float]]] = {}
    for idx, (left_tag, a1, a2) in enumerate(segments):
        for right_tag, b1, b2 in segments[idx + 1:]:
            if left_tag == right_tag:
                continue
            crossing = _orthogonal_crossing(a1, a2, b1, b2)
            if crossing is None or crossing in port_points:
                continue
            if crossing in {a1, a2, b1, b2}:
                continue
            gap_tag = left_tag if a1[1] == a2[1] else right_tag
            gaps.setdefault(gap_tag, []).append((crossing, 3.0))
    return gaps


def _orthogonal_crossing(a1: Point, a2: Point, b1: Point, b2: Point) -> Point | None:
    a_horizontal = a1[1] == a2[1]
    b_horizontal = b1[1] == b2[1]
    if a_horizontal == b_horizontal:
        return None
    h1, h2, v1, v2 = (a1, a2, b1, b2) if a_horizontal else (b1, b2, a1, a2)
    hx0, hx1 = sorted((h1[0], h2[0]))
    vy0, vy1 = sorted((v1[1], v2[1]))
    x, y = v1[0], h1[1]
    if hx0 < x < hx1 and vy0 < y < vy1:
        return snap_point((x, y))
    return None


def _orthogonalize(points: list[Point], nozzle_axes: dict[Point, str] | None = None) -> list[Point]:
    points = snap_points(points)
    if len(points) < 2:
        return points
    nozzle_axes = nozzle_axes or {}
    if len(points) == 2 and points[0] in nozzle_axes and points[1] in nozzle_axes and points[0][0] != points[1][0] and points[0][1] != points[1][1]:
        return _orthogonalize_between_nozzles(points[0], points[1], nozzle_axes)
    out: list[Point] = [points[0]]
    for idx, next_point in enumerate(points[1:], start=1):
        prev = out[-1]
        if prev[0] != next_point[0] and prev[1] != next_point[1]:
            elbow = _nozzle_aware_elbow(prev, next_point, idx == 1, idx == len(points) - 1, nozzle_axes)
            if elbow != prev:
                out.append(elbow)
        if next_point != out[-1]:
            out.append(next_point)
    return snap_points(out)


def _nozzle_aware_elbow(prev: Point, next_point: Point, first_leg: bool, last_leg: bool, nozzle_axes: dict[Point, str]) -> Point:
    if first_leg and nozzle_axes.get(prev) == "vertical":
        return snap_point((prev[0], next_point[1]))
    if first_leg and nozzle_axes.get(prev) == "horizontal":
        return snap_point((next_point[0], prev[1]))
    if last_leg and nozzle_axes.get(next_point) == "horizontal":
        return snap_point((prev[0], next_point[1]))
    if last_leg and nozzle_axes.get(next_point) == "vertical":
        return snap_point((next_point[0], prev[1]))
    return snap_point((next_point[0], prev[1]))


def _orthogonalize_between_nozzles(start: Point, end: Point, nozzle_axes: dict[Point, str]) -> list[Point]:
    start_axis = nozzle_axes[start]
    end_axis = nozzle_axes[end]
    if start_axis == "vertical" and end_axis == "horizontal":
        return snap_points([start, (start[0], end[1]), end])
    if start_axis == "horizontal" and end_axis == "vertical":
        return snap_points([start, (end[0], start[1]), end])
    direction_x = 1 if end[0] >= start[0] else -1
    direction_y = 1 if end[1] >= start[1] else -1
    if start_axis == "horizontal" and end_axis == "horizontal":
        offset_x = start[0] + direction_x * 20
        return snap_points([start, (offset_x, start[1]), (offset_x, end[1]), end])
    offset_y = start[1] + direction_y * 20
    return snap_points([start, (start[0], offset_y), (end[0], offset_y), end])


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
        point, orientation = _EXPLICIT_VALVE_STATIONS[tag]
        return snap_point(point), orientation
    _, points, _ = routes.get(pipe_segment, next(iter(routes.values())))
    segments = list(zip(points, points[1:]))
    wants_vertical = requested_orientation.startswith("v")
    matching = [seg for seg in segments if (seg[0][0] == seg[1][0]) == wants_vertical]
    candidates = matching or segments
    p1, p2 = _station_segment(candidates, station)
    orientation = "vertical" if p1[0] == p2[0] else "horizontal"
    fraction = _station_fraction(station, index, count)
    return snap_point((p1[0] + (p2[0] - p1[0]) * fraction, p1[1] + (p2[1] - p1[1]) * fraction)), orientation


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
    "XV-501": ((175.0, 465.0), "horizontal"),
    "FV-501": ((390.0, 465.0), "horizontal"),
    "HV-507": ((430.0, 348.0), "horizontal"),
    "HV-508": ((454.0, 382.0), "horizontal"),
    "HV-503": ((1040.0, 650.0), "horizontal"),
    "HV-515": ((600.0, 745.0), "vertical"),
    "HV-516": ((840.0, 745.0), "vertical"),
    "PSV-502": ((805.0, 730.0), "vertical"),
    "HV-517": ((530.0, 165.0), "vertical"),
    "HV-518": ((1080.0, 165.0), "vertical"),
    "HV-520": ((680.0, 610.0), "vertical"),
    "HV-513": ((780.0, 685.0), "vertical"),
    "TV-502": ((780.0, 655.0), "vertical"),
}
