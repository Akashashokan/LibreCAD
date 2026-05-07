from __future__ import annotations

from pathlib import Path

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
from .label_rules import apply_line_label
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
    ctx = DrawContext(doc, msp, registry, DEFAULT_STANDARD, style_profile, {})

    resolver = SymbolResolver(config, block_dir, style)
    resolver.resolve_all()
    resolver.import_required_blocks(doc)
    ctx.block_names = resolver.imported_blocks
    registry.fallbacks.extend(resolver.fallback_warnings)

    _draw_sheet(ctx, config)
    _draw_offpages(ctx)

    equipment_origins: dict[str, Point] = {}
    for placement in config.equipment:
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
    for line_tag, (service, points, major) in route_points.items():
        if major:
            draw_header(ctx, points, line_tag, service, _layer_for_line(line_tag))
        else:
            draw_branch(ctx, points, line_tag, service, _layer_for_line(line_tag))
        apply_line_label(ctx, line_tag, service, points)

    for valve in config.valves:
        point = _valve_point(valve.pipe_segment, route_points)
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
    }.items():
        if ltype not in doc.linetypes:
            doc.linetypes.add(ltype, pattern=pattern)


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
    routes["500-CD-502"] = ("REFLUX DRUM CLOSED DRAIN", [p["V-501.N5_drain.connection_point"], (858, 90), p["OPC_CLOSED_DRAIN_HEADER.continuation"]], False)
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


def _valve_point(pipe_segment: str, routes: dict[str, tuple[str, list[Point], bool]]) -> Point:
    _, points, _ = routes.get(pipe_segment, next(iter(routes.values())))
    p1, p2 = max(zip(points, points[1:]), key=lambda seg: abs(seg[1][0] - seg[0][0]) + abs(seg[1][1] - seg[0][1]))
    return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
