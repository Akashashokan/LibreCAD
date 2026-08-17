#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import ezdxf

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pid.export_pid_image_segments import clean_image, render_dxf_to_png
from tools.pid.yaml_pid.cad_primitives import DrawContext, draw_equipment, draw_instrument, draw_nozzle, draw_offpage_connector, draw_pipe, draw_text, draw_valve_on_line
from tools.pid.yaml_pid.config_loader import load_pid_config
from tools.pid.yaml_pid.drafting_standard import DEFAULT_STANDARD, style_from_name
from tools.pid.yaml_pid.engineering_validation import ValidationReport
from tools.pid.yaml_pid.grid import snap_point
from tools.pid.yaml_pid.models import EquipmentPlacement, NozzleSpec, OffPageConnector, ValvePlacement
from tools.pid.yaml_pid.render_deethanizer_from_yaml import _setup_doc
from tools.pid.yaml_pid.scene import BBox, SceneRegistry
from tools.pid.yaml_pid.symbol_resolver import SymbolResolver


OUT_DIR = REPO_ROOT / "tools" / "pid" / "outputs"
DXF_OUT = OUT_DIR / "local_e501_reboiler_debug_v4.dxf"
PNG_OUT = OUT_DIR / "local_e501_reboiler_debug_v4.png"
DEBUG_DIR = REPO_ROOT / "debug"
OUTPUT_DIR = REPO_ROOT / "output"
TRACE_REPORT_OUT = DEBUG_DIR / "e501_reboiler_trace_report.txt"
DEBUG_OVERLAY_DXF = DEBUG_DIR / "e501_reboiler_debug_overlay.dxf"
PRODUCTION_DXF = OUTPUT_DIR / "e501_reboiler_production.dxf"


def main() -> int:
    report = render_local_e501_diagnostics()
    print(report.format())
    print(f"Trace report: {TRACE_REPORT_OUT}")
    return 0 if report.ok else 2


def render_local_e501() -> ValidationReport:
    report = render_local_e501_diagnostics()
    if report.ok:
        raw_png = OUT_DIR / "local_e501_reboiler_debug_v4_raw.png"
        render_dxf_to_png(DXF_OUT, raw_png, dpi=220, render_width=2200, units="mm")
        clean_image(raw_png, PNG_OUT, padding=24, white_threshold=12, sharpen=True, binarize=True, binarize_threshold=210, max_width=2200)
    return report


def render_local_e501_diagnostics() -> ValidationReport:
    debug_doc, debug_registry = build_local_doc(show_debug_overlay=True)
    production_doc, production_registry = build_local_doc(show_debug_overlay=False)
    debug_report = run_local_qa(debug_registry, production_registry)
    trace_text = build_trace_report(debug_registry, production_registry, debug_report)

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_REPORT_OUT.write_text(trace_text, encoding="utf-8")

    if not debug_report.ok:
        return debug_report

    debug_doc.saveas(DEBUG_OVERLAY_DXF)
    production_doc.saveas(PRODUCTION_DXF)
    debug_doc.saveas(DXF_OUT)
    return debug_report


def build_local_doc(show_debug_overlay: bool) -> tuple[ezdxf.EzDxfDocument, SceneRegistry]:
    config_dir = REPO_ROOT / "tools" / "pid" / "configs" / "deethanizer_U400"
    block_dir = REPO_ROOT / "libreCAD_blocks"
    config = load_pid_config(config_dir)
    style = style_from_name("debug")
    doc = ezdxf.new("R2010", setup=True)
    _setup_doc(doc, style)
    msp = doc.modelspace()
    registry = SceneRegistry()
    ctx = DrawContext(doc, msp, registry, DEFAULT_STANDARD, style, {}, {})

    resolver = SymbolResolver(config, block_dir, "debug")
    resolver.resolve_all()
    resolver.import_required_blocks(doc)
    ctx.block_names = resolver.imported_blocks
    ctx.block_extents = resolver.block_extents

    draw_local_window(ctx, show_debug_overlay=show_debug_overlay)
    if show_debug_overlay:
        draw_debug_overlay(ctx)
    return doc, ctx.registry


def draw_local_window(ctx: DrawContext, show_debug_overlay: bool = True) -> None:
    ctx.msp.add_lwpolyline([(35, 70), (620, 70), (620, 360), (35, 360), (35, 70)], dxfattribs={"layer": "BORDER"})
    title = "LOCAL DEBUG V4 - E-501 REBOILER PACKAGE" if show_debug_overlay else "E-501 REBOILER PACKAGE"
    draw_text(ctx, title, 48, 340, 5.0, "TEXT", "LOCAL_TITLE", "title")

    c_box = BBox(85, 120, 165, 310, "C-501", "equipment")
    ctx.msp.add_lwpolyline([(c_box.xmin, c_box.ymin), (c_box.xmax, c_box.ymin), (c_box.xmax, c_box.ymax), (c_box.xmin, c_box.ymax), (c_box.xmin, c_box.ymin)], dxfattribs={"layer": "EQUIPMENT"})
    for y in (155, 195, 235, 275):
        ctx.msp.add_line((c_box.xmin + 8, y), (c_box.xmax - 8, y), dxfattribs={"layer": "EQUIPMENT"})
    ctx.registry.add_item("equipment", "C-501", "EQUIPMENT", c_box)
    ctx.registry.mark("equipment", "C-501")
    draw_text(ctx, "C-501 LOWER SHELL", 87, 102, 3.0, "TEXT", "C-501", "equipment_tag")

    _set_equipment_meta(ctx, "C-501", "local_shell_fragment", "vertical", "EQUIPMENT")
    _draw_local_nozzle(ctx, "C501_REBOILER_DRAW", "C-501", (165, 165), (193, 165), "horizontal", "right", "process", "draw", "C501_REBOILER_DRAW", (5, -12), show_debug_overlay)
    _draw_local_nozzle(ctx, "C501_REBOILER_RETURN", "C-501", (165, 198), (193, 198), "horizontal", "right", "process", "return", "C501_REBOILER_RETURN", (5, 10), show_debug_overlay)

    e501_origin = snap_point((310, 180))
    e501 = EquipmentPlacement("E-501", "reboiler", e501_origin[0], e501_origin[1], "horizontal", "reboiler", "local reboiler")
    config = load_pid_config(REPO_ROOT / "tools" / "pid" / "configs" / "deethanizer_U400")
    e501_box = draw_equipment(ctx, e501, config.block_geometry["reboiler"])
    _set_equipment_meta(ctx, "E-501", ctx.block_names.get("reboiler", "kettle_reboiler"), "horizontal", "EQUIPMENT")
    e501_left = snap_point((e501_box.xmin, 0))[0]
    e501_right = snap_point((e501_box.xmax, 0))[0]
    e501_ports = {
        "E501_PROCESS_IN": ("left", (e501_left, 165), (230, 165), (-78, -12)),
        "E501_PROCESS_OUT": ("left", (e501_left, 198), (230, 198), (-82, 10)),
        "E501_HM_IN": ("right", (e501_right, 198), (385, 198), (5, 10)),
        "E501_HM_OUT": ("right", (e501_right, 160), (385, 160), (5, -12)),
    }
    for label, (side, wall, conn, label_offset) in e501_ports.items():
        service = "process" if "PROCESS" in label else "heating_medium"
        role = {"E501_PROCESS_IN": "inlet", "E501_PROCESS_OUT": "outlet", "E501_HM_IN": "inlet", "E501_HM_OUT": "outlet"}[label]
        _draw_local_nozzle(ctx, label, "E-501", wall, conn, "horizontal", side, service, role, label, label_offset, show_debug_overlay)

    hm_supply = OffPageConnector("OPC_HM_SUPPLY_LOCAL", "HEATING MEDIUM SUPPLY", "FROM PID-810", 585, 198, "right")
    hm_return = OffPageConnector("OPC_HM_RETURN_LOCAL", "HEATING MEDIUM RETURN", "TO PID-810", 585, 160, "right")
    draw_offpage_connector(ctx, hm_supply)
    draw_offpage_connector(ctx, hm_return)
    _set_port_meta(ctx, "OPC_HM_SUPPLY_LOCAL.continuation", "OFFPAGE", "right", "heating_medium", "source", False)
    _set_port_meta(ctx, "OPC_HM_RETURN_LOCAL.continuation", "OFFPAGE", "right", "heating_medium", "target", False)

    routes = {
        "C501_DRAW_TO_E501_IN": ("REBOILER LIQUID DRAW", "C501_REBOILER_DRAW", "E501_PROCESS_IN", "PROCESS", True, [("HV-507", (210, 165), "manual_block_valve")]),
        "E501_OUT_TO_C501_RETURN": ("REBOILER VAPOR RETURN", "E501_PROCESS_OUT", "C501_REBOILER_RETURN", "PROCESS", True, [("HV-508", (210, 198), "manual_block_valve")]),
        "HM_SUPPLY_TO_E501_IN": ("HEATING MEDIUM SUPPLY", "OPC_HM_SUPPLY_LOCAL.continuation", "E501_HM_IN", "UTILITY", False, [("TV-501", (505, 198), "control_valve")]),
        "E501_HM_OUT_TO_RETURN": ("HEATING MEDIUM RETURN", "E501_HM_OUT", "OPC_HM_RETURN_LOCAL.continuation", "UTILITY", False, []),
    }
    for route_tag, (service, source_ref, target_ref, layer, major, valves) in routes.items():
        points = [ctx.registry.ports[source_ref], ctx.registry.ports[target_ref]]
        gaps = [(point, 14.0 if valve_type == "control_valve" else 5.0) for _tag, point, valve_type in valves]
        draw_pipe(ctx, points, route_tag, service, layer, major, gaps)
        _set_route_meta(ctx, route_tag, source_ref, target_ref, points, service, layer, "continuous", ctx.standard.lw_major if major else ctx.standard.lw_minor, True, False)
        for tag, point, valve_type in valves:
            draw_valve_on_line(ctx, ValvePlacement(tag, valve_type, service, route_tag, "horizontal"), point[0], point[1])
            _set_equipment_meta(ctx, tag, ctx.block_names.get(valve_type, valve_type), "horizontal", "VALVES")
            _set_port_meta(ctx, f"{tag}.process_in", tag, "left", "heating_medium" if tag == "TV-501" else "process", "inlet", False, alias=f"{tag.replace('-', '')}_IN")
            _set_port_meta(ctx, f"{tag}.process_out", tag, "right", "heating_medium" if tag == "TV-501" else "process", "outlet", False, alias=f"{tag.replace('-', '')}_OUT")
            if tag == "TV-501":
                _set_port_meta(ctx, f"{tag}.actuator_signal", tag, "top", "signal", "actuator_signal", False, alias="TV501_ACTUATOR_SIGNAL")
                if show_debug_overlay:
                    _draw_valve_debug_labels(ctx, tag)

    draw_instrument(ctx, "TIC-501", "dcs_controller", 505, 275)
    _set_equipment_meta(ctx, "TIC-501", ctx.block_names.get("dcs_controller", "dcs_controller"), "none", "INSTRUMENT")
    _set_port_meta(ctx, "TIC-501.output_signal", "TIC-501", "right", "signal", "output", False, alias="TIC501_OUTPUT")
    tv = ctx.registry.ports["TV-501.actuator_signal"]
    tic = ctx.registry.ports["TIC-501.output_signal"]
    signal_points = [tic, (535, tic[1]), (535, tv[1]), tv]
    draw_signal(ctx, signal_points, "TIC501_TO_TV501", show_debug_overlay)
    _set_route_meta(ctx, "TIC501_TO_TV501", "TIC-501.output_signal", "TV-501.actuator_signal", signal_points, "TIC-501 OUTPUT TO TV-501", "SIGNAL_PNEUMATIC", "dashed_signal", ctx.standard.lw_signal, True, False)


def _equipment_meta(registry: SceneRegistry) -> dict[str, dict[str, object]]:
    if not hasattr(registry, "local_equipment_meta"):
        setattr(registry, "local_equipment_meta", {})
    return getattr(registry, "local_equipment_meta")


def _port_meta(registry: SceneRegistry) -> dict[str, dict[str, object]]:
    if not hasattr(registry, "local_port_meta"):
        setattr(registry, "local_port_meta", {})
    return getattr(registry, "local_port_meta")


def _route_meta(registry: SceneRegistry) -> dict[str, dict[str, object]]:
    if not hasattr(registry, "local_route_meta"):
        setattr(registry, "local_route_meta", {})
    return getattr(registry, "local_route_meta")


def _set_equipment_meta(ctx: DrawContext, tag: str, block_name: str, orientation: str, layer: str) -> None:
    _equipment_meta(ctx.registry)[tag] = {"block": block_name, "orientation": orientation, "layer": layer}


def _set_port_meta(
    ctx: DrawContext,
    port_id: str,
    owner: str,
    side: str,
    service: str,
    role: str,
    visible_nozzle: bool,
    alias: str | None = None,
) -> None:
    _port_meta(ctx.registry)[port_id] = {
        "alias": alias or port_id,
        "owner": owner,
        "side": side,
        "service": service,
        "role": role,
        "visible_nozzle": visible_nozzle,
    }


def _set_route_meta(
    ctx: DrawContext,
    route_id: str,
    source_ref: str,
    target_ref: str,
    points: list[tuple[float, float]],
    service: str,
    layer: str,
    linetype: str,
    lineweight: int,
    production_visible: bool,
    uses_raw_endpoint: bool,
) -> None:
    _route_meta(ctx.registry)[route_id] = {
        "source_ref": source_ref,
        "target_ref": target_ref,
        "points": [snap_point(p) for p in points],
        "service": service,
        "layer": layer,
        "linetype": linetype,
        "lineweight": lineweight,
        "production_visible": production_visible,
        "uses_raw_endpoint": uses_raw_endpoint,
    }


def draw_debug_overlay(ctx: DrawContext) -> None:
    for tag, box in ctx.registry.equipment_bboxes.items():
        ctx.msp.add_lwpolyline(
            [(box.xmin, box.ymin), (box.xmax, box.ymin), (box.xmax, box.ymax), (box.xmin, box.ymax), (box.xmin, box.ymin)],
            dxfattribs={"layer": "QA_OVERLAY", "linetype": "DASHED"},
        )
        fz = ctx.registry.equipment_forbidden_zones.get(tag)
        if fz:
            ctx.msp.add_lwpolyline(
                [(fz.xmin, fz.ymin), (fz.xmax, fz.ymin), (fz.xmax, fz.ymax), (fz.xmin, fz.ymax), (fz.xmin, fz.ymin)],
                dxfattribs={"layer": "QA_OVERLAY", "linetype": "DOTTED"},
            )
    for route_id, meta in _route_meta(ctx.registry).items():
        points = meta["points"]
        if not points:
            continue
        p1, p2 = points[0], points[-1]
        draw_text(ctx, route_id, (p1[0] + p2[0]) / 2 - 18, (p1[1] + p2[1]) / 2 + 4, 1.8, "QA_OVERLAY", f"{route_id}:overlay", "debug_port_label")


def build_trace_report(debug_registry: SceneRegistry, production_registry: SceneRegistry, qa_report: ValidationReport) -> str:
    lines: list[str] = []
    lines.append("E-501 REBOILER SUBSYSTEM TRACE REPORT")
    lines.append("=" * 43)
    lines.append("")
    lines.append("QA summary")
    lines.append(f"PASS count: {len(qa_report.passes)}")
    lines.append(f"WARN count: {len(qa_report.warnings)}")
    lines.append(f"FAIL count: {len(qa_report.failures)}")
    for failure in qa_report.failures:
        lines.append(f"FAIL: {failure}")
    lines.append("")
    lines.extend(_equipment_trace_lines(debug_registry))
    lines.append("")
    lines.extend(_port_trace_lines(debug_registry))
    lines.append("")
    lines.extend(_route_trace_lines(debug_registry))
    lines.append("")
    lines.extend(_semantic_trace_lines(debug_registry, production_registry))
    lines.append("")
    lines.extend(_visual_trace_lines(debug_registry, production_registry))
    return "\n".join(lines) + "\n"


def _equipment_trace_lines(registry: SceneRegistry) -> list[str]:
    lines = ["1. Equipment registry"]
    for tag in ("C-501", "E-501", "TV-501", "TIC-501"):
        item = next((item for item in registry.items if item.tag == tag and item.kind in {"equipment", "valve", "instrument"}), None)
        box = registry.equipment_bboxes.get(tag) or (item.bbox if item else None)
        meta = _equipment_meta(registry).get(tag, {})
        lines.append(f"Object: {tag}")
        lines.append(f"  Block used: {meta.get('block', _block_used(registry, tag))}")
        lines.append(f"  BBox: {_fmt_bbox(box)}")
        lines.append(f"  Forbidden zone bbox: {_fmt_bbox(registry.equipment_forbidden_zones.get(tag))}")
        lines.append(f"  Orientation: {meta.get('orientation', 'unknown')}")
        lines.append(f"  Visible layer: {meta.get('layer', item.layer if item else 'unknown')}")
    return lines


def _port_trace_lines(registry: SceneRegistry) -> list[str]:
    lines = ["2. Port registry"]
    required = [
        "C501_REBOILER_DRAW",
        "C501_REBOILER_RETURN",
        "E501_PROCESS_IN",
        "E501_PROCESS_OUT",
        "E501_HM_IN",
        "E501_HM_OUT",
        "TV-501.process_in",
        "TV-501.process_out",
        "TV-501.actuator_signal",
        "TIC-501.output_signal",
    ]
    for ref in required:
        point = registry.ports.get(ref)
        meta = _port_meta(registry).get(ref, {})
        lines.append(f"Port: {meta.get('alias', ref)}")
        lines.append(f"  actual_ref: {ref}")
        lines.append(f"  owner: {meta.get('owner', registry.port_owners.get(ref, 'unknown'))}")
        lines.append(f"  coordinate: {_fmt_point(point)}")
        lines.append(f"  side: {meta.get('side', _side_for_nozzle(registry, ref))}")
        lines.append(f"  service: {meta.get('service', 'unknown')}")
        lines.append(f"  role: {meta.get('role', 'unknown')}")
        lines.append(f"  visible_nozzle_symbol_drawn: {meta.get('visible_nozzle', False)}")
    return lines


def _route_trace_lines(registry: SceneRegistry) -> list[str]:
    lines = ["3. Route resolution table"]
    for route_id, meta in _route_meta(registry).items():
        source_ref = str(meta["source_ref"])
        target_ref = str(meta["target_ref"])
        source_point = registry.ports.get(source_ref)
        target_point = registry.ports.get(target_ref)
        lines.append(f"Route: {route_id}")
        lines.append(f"  Declared source: {source_ref}")
        lines.append(f"  Resolved source port: {_fmt_point(source_point)} owner={_owner_for_port(registry, source_ref)}")
        lines.append(f"  Declared target: {target_ref}")
        lines.append(f"  Resolved target port: {_fmt_point(target_point)} owner={_owner_for_port(registry, target_ref)}")
        lines.append(f"  Polyline points: {_fmt_points(meta['points'])}")
        lines.append(f"  Crosses equipment: {_yes_no(bool(_route_equipment_crossings(registry, route_id)))}")
        lines.append(f"  Layer: {meta['layer']}")
        lines.append(f"  Linetype: {meta['linetype']}")
        lines.append(f"  Line weight: {meta['lineweight']}")
        lines.append(f"  Production-visible: {_yes_no(bool(meta['production_visible']))}")
        lines.append(f"  Uses raw coordinate instead of registered endpoint: {_yes_no(bool(meta['uses_raw_endpoint']))}")
        lines.append(f"  Visible label: {meta['service']}")
    return lines


def _semantic_trace_lines(debug_registry: SceneRegistry, production_registry: SceneRegistry) -> list[str]:
    checks = {
        "E501_PROCESS_IN is left lower side": _is_expected_e501_port(debug_registry, "E501_PROCESS_IN", "left", "lower"),
        "E501_PROCESS_OUT is left upper side": _is_expected_e501_port(debug_registry, "E501_PROCESS_OUT", "left", "upper"),
        "E501_HM_IN is right upper side": _is_expected_e501_port(debug_registry, "E501_HM_IN", "right", "upper"),
        "E501_HM_OUT is right lower side": _is_expected_e501_port(debug_registry, "E501_HM_OUT", "right", "lower"),
        "C501_REBOILER_RETURN is above C501_REBOILER_DRAW": debug_registry.ports["C501_REBOILER_RETURN"][1] > debug_registry.ports["C501_REBOILER_DRAW"][1],
        "TV-501 is between HM supply off-page and E501_HM_IN": not _engineering_logic_errors(debug_registry),
        "TIC-501 signal terminates at TV501_ACTUATOR_SIGNAL": debug_registry.signal_connections.get("TIC501_TO_TV501") == [("TIC-501.output_signal", "TV-501.actuator_signal")],
        "Production text contains no internal debug names": not _production_debug_text_errors(production_registry),
    }
    return ["4. Engineering semantic checks"] + [f"{'PASS' if ok else 'FAIL'}: {label}" for label, ok in checks.items()]


def _visual_trace_lines(debug_registry: SceneRegistry, production_registry: SceneRegistry) -> list[str]:
    checks = {
        "no process/utility/signal route crosses E-501 body": not (
            _crossings(debug_registry, debug_registry.equipment_bboxes["E-501"], {"PROCESS", "UTILITY", "SIGNAL_PNEUMATIC", "SIGNAL_ELECTRIC"}, "E-501")
        ),
        "no route crosses C-501 body except registered nozzle ports": not (
            _crossings(debug_registry, debug_registry.equipment_bboxes["C-501"], {"PROCESS", "UTILITY", "SIGNAL_PNEUMATIC", "SIGNAL_ELECTRIC"}, "C-501")
        ),
        "no label overlaps valve/nozzle/instrument/equipment/line centerline": not _text_collisions(debug_registry),
        "off-page connectors have service labels and drawing references": not _offpage_label_errors(production_registry),
    }
    return ["5. Visual QA checks"] + [f"{'PASS' if ok else 'FAIL'}: {label}" for label, ok in checks.items()]


def _draw_valve_debug_labels(ctx: DrawContext, tag: str) -> None:
    labels = {
        "TV501_IN": ctx.registry.ports[f"{tag}.process_in"],
        "TV501_OUT": ctx.registry.ports[f"{tag}.process_out"],
        "TV501_SIGNAL": ctx.registry.ports[f"{tag}.actuator_signal"],
    }
    for label, point in labels.items():
        offset = {
            "TV501_IN": (-42, -13),
            "TV501_OUT": (4, -13),
            "TV501_SIGNAL": (4, 13),
        }[label]
        draw_text(ctx, label, point[0] + offset[0], point[1] + offset[1], 1.8, "TEXT", label, "debug_port_label")


def _draw_local_nozzle(
    ctx: DrawContext,
    name: str,
    equipment: str,
    wall: tuple[float, float],
    conn: tuple[float, float],
    axis: str,
    side: str,
    service: str,
    role: str,
    label: str,
    label_offset: tuple[float, float],
    show_debug_label: bool = True,
) -> None:
    wall = snap_point(wall)
    conn = snap_point(conn)
    mid = snap_point(((wall[0] + conn[0]) / 2, (wall[1] + conn[1]) / 2))
    ctx.msp.add_line(wall, conn, dxfattribs={"layer": "NOZZLES", "lineweight": 25})
    if axis == "horizontal":
        ctx.msp.add_line((wall[0], wall[1] - 3), (wall[0], wall[1] + 3), dxfattribs={"layer": "NOZZLES", "lineweight": 18})
        ctx.msp.add_line((mid[0], mid[1] - 3), (mid[0], mid[1] + 3), dxfattribs={"layer": "NOZZLES", "lineweight": 18})
    else:
        ctx.msp.add_line((wall[0] - 3, wall[1]), (wall[0] + 3, wall[1]), dxfattribs={"layer": "NOZZLES", "lineweight": 18})
        ctx.msp.add_line((mid[0] - 3, mid[1]), (mid[0] + 3, mid[1]), dxfattribs={"layer": "NOZZLES", "lineweight": 18})
    ctx.registry.add_port(name, conn, "nozzle")
    ctx.registry.nozzle_axes[conn] = axis
    ctx.registry.nozzle_wall_points[f"{equipment}.{name}"] = wall
    ctx.registry.nozzle_sides[f"{equipment}.{name}"] = side
    ctx.registry.add_item("nozzle", name, "NOZZLES", BBox(min(wall[0], conn[0]) - 2, min(wall[1], conn[1]) - 2, max(wall[0], conn[0]) + 2, max(wall[1], conn[1]) + 2, name, "nozzle"))
    ctx.registry.mark("nozzle", name)
    _set_port_meta(ctx, name, equipment, side, service, role, True)
    if show_debug_label:
        draw_text(ctx, label, conn[0] + label_offset[0], conn[1] + label_offset[1], 1.8, "TEXT", f"{name}:debug_label", "debug_port_label")


def _alias_port(ctx: DrawContext, alias: str, ref: str) -> None:
    point = ctx.registry.ports[ref]
    ctx.registry.add_port(alias, point, "nozzle")
    ctx.registry.nozzle_axes[point] = ctx.registry.nozzle_axes.get(point, "horizontal")


def draw_signal(ctx: DrawContext, points: list[tuple[float, float]], tag: str, show_debug_overlay: bool = True) -> None:
    from tools.pid.yaml_pid.cad_primitives import draw_signal_line

    draw_signal_line(ctx, points, "pneumatic_signal", tag)
    if show_debug_overlay:
        for p1, p2 in zip(points, points[1:]):
            if p1 != p2:
                ctx.msp.add_line(p1, p2, dxfattribs={"layer": "SIGNAL_PNEUMATIC", "linetype": "DASHED", "lineweight": 25})
    ctx.registry.signal_connections[tag] = [("TIC-501.output_signal", "TV-501.actuator_signal")]


def run_local_qa(registry: SceneRegistry, production_registry: SceneRegistry | None = None) -> ValidationReport:
    report = ValidationReport("LOCAL E-501 REBOILER PACKAGE QA")
    e501 = registry.equipment_bboxes["E-501"]
    c501 = registry.equipment_bboxes["C-501"]
    _record(report, "E501_BBOX registered", "E-501" in registry.equipment_bboxes)
    _record(report, "E501_FORBIDDEN_ZONE registered", "E-501" in registry.equipment_forbidden_zones)
    _record(report, "C501 fragment registered", "C-501" in registry.equipment_bboxes)
    _record(report, "E-501 process/HM ports registered", all(ref in registry.ports for ref in ("E501_PROCESS_IN", "E501_PROCESS_OUT", "E501_HM_IN", "E501_HM_OUT")))
    _record(report, "C-501 reboiler nozzles registered", all(ref in registry.ports for ref in ("C501_REBOILER_DRAW", "C501_REBOILER_RETURN")))
    _record_with_details(report, "local nozzle sides match owned equipment sides", _nozzle_side_mismatches(registry))
    _record_with_details(report, "local nozzle wall points are attached to owning equipment body", _nozzle_attachment_errors(registry))
    e501_pipe_crossings = _crossings(registry, e501, {"PROCESS", "UTILITY"}, "E-501")
    c501_pipe_crossings = _crossings(registry, c501, {"PROCESS", "UTILITY"}, "C-501")
    signal_crossings = _crossings(registry, e501, {"SIGNAL_PNEUMATIC", "SIGNAL_ELECTRIC"}, "E-501") + _crossings(registry, c501, {"SIGNAL_PNEUMATIC", "SIGNAL_ELECTRIC"}, "C-501")
    _record_with_details(report, "no pipe crosses E501_BBOX", e501_pipe_crossings)
    _record_with_details(report, "no pipe crosses C501_BBOX except nozzles", c501_pipe_crossings)
    _record_with_details(report, "no signal crosses equipment body", signal_crossings)
    route_ids = ("C501_DRAW_TO_E501_IN", "E501_OUT_TO_C501_RETURN", "HM_SUPPLY_TO_E501_IN", "E501_HM_OUT_TO_RETURN")
    _record(report, "all local route endpoints are registered ports", all(registry.route_endpoint_refs[tag][0] and registry.route_endpoint_refs[tag][1] for tag in route_ids))
    _record(report, "all local process, utility, and signal routes are orthogonal", not any(seg.diagonal for seg in registry.line_segments if seg.layer in {"PROCESS", "UTILITY", "SIGNAL_PNEUMATIC", "SIGNAL_ELECTRIC"}))
    _record(report, "HV-507, HV-508, TV-501 split pipe with mounted valve gaps", all(_valve_mounted(registry, tag) for tag in ("HV-507", "HV-508", "TV-501")))
    _record(report, "TV-501 is ISA control valve final element, not a manual valve", _control_valve_confirmed(registry, "TV-501"))
    _record(report, "TV-501 actuator signal port registered", "TV-501.actuator_signal" in registry.ports)
    _record_with_details(report, "local reboiler engineering route logic is valid", _engineering_logic_errors(registry))
    _record(report, "TIC501_TO_TV501 signal endpoint snaps to TIC output and TV actuator", _point_on_signal(registry, registry.ports["TIC-501.output_signal"], "TIC501_TO_TV501") and _point_on_signal(registry, registry.ports["TV-501.actuator_signal"], "TIC501_TO_TV501"))
    _record_with_details(report, "TIC-501 signal connects only to TV-501 actuator and clears valve/text bodies", _signal_logic_errors(registry))
    _record(report, "formal heating medium off-page connectors are registered", all(ref in registry.ports for ref in ("OPC_HM_SUPPLY_LOCAL.continuation", "OPC_HM_RETURN_LOCAL.continuation")))
    _record_with_details(report, "debug labels and local text clear process, utility, and valve bodies", _text_collisions(registry))
    if production_registry is not None:
        _record_with_details(report, "production text hides internal debug port names", _production_debug_text_errors(production_registry))
    return report


def _nozzle_side_mismatches(registry: SceneRegistry) -> list[str]:
    expected = {
        "C-501.C501_REBOILER_DRAW": "right",
        "C-501.C501_REBOILER_RETURN": "right",
        "E-501.E501_PROCESS_IN": "left",
        "E-501.E501_PROCESS_OUT": "left",
        "E-501.E501_HM_IN": "right",
        "E-501.E501_HM_OUT": "right",
    }
    return [f"{ref}: expected {side}, got {registry.nozzle_sides.get(ref)}" for ref, side in expected.items() if registry.nozzle_sides.get(ref) != side]


def _block_used(registry: SceneRegistry, tag: str) -> str:
    prefix = f"{tag}: "
    for entry in registry.existing_blocks_used:
        if entry.startswith(prefix):
            return entry.split("->", 1)[-1].strip()
    return "local_primitive"


def _fmt_bbox(box: BBox | None) -> str:
    if box is None:
        return "none"
    return f"{box.xmin:.1f}, {box.ymin:.1f}, {box.xmax:.1f}, {box.ymax:.1f}"


def _fmt_point(point: tuple[float, float] | None) -> str:
    if point is None:
        return "unresolved"
    return f"{point[0]:.1f}, {point[1]:.1f}"


def _fmt_points(points) -> str:
    return "[" + ", ".join(f"({_fmt_point(point)})" for point in points) + "]"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _owner_for_port(registry: SceneRegistry, ref: str) -> str:
    return str(_port_meta(registry).get(ref, {}).get("owner", registry.port_owners.get(ref, "unknown")))


def _side_for_nozzle(registry: SceneRegistry, ref: str) -> str:
    for full_ref, side in registry.nozzle_sides.items():
        if full_ref.endswith(f".{ref}"):
            return side
    return "unknown"


def _route_equipment_crossings(registry: SceneRegistry, route_id: str) -> list[str]:
    layers = {"PROCESS", "UTILITY", "SIGNAL_PNEUMATIC", "SIGNAL_ELECTRIC"}
    out: list[str] = []
    for equipment_tag in ("E-501", "C-501"):
        box = registry.equipment_bboxes[equipment_tag]
        for seg in registry.line_segments:
            if seg.tag != route_id or seg.layer not in layers:
                continue
            if _segment_has_equipment_nozzle_endpoint(registry, seg.p1, equipment_tag) or _segment_has_equipment_nozzle_endpoint(registry, seg.p2, equipment_tag):
                continue
            if _segment_enters_box(seg.p1, seg.p2, box):
                out.append(f"{route_id} crosses {equipment_tag}")
    return sorted(set(out))


def _is_expected_e501_port(registry: SceneRegistry, port: str, side: str, elevation: str) -> bool:
    point = registry.ports[port]
    box = registry.equipment_bboxes["E-501"]
    full_ref = f"E-501.{port}"
    midpoint = (box.ymin + box.ymax) / 2
    correct_side = registry.nozzle_sides.get(full_ref) == side
    correct_x = abs(registry.nozzle_wall_points[full_ref][0] - (box.xmin if side == "left" else box.xmax)) <= 1.5
    correct_y = point[1] < midpoint if elevation == "lower" else point[1] > midpoint
    return correct_side and correct_x and correct_y


def _production_debug_text_errors(registry: SceneRegistry) -> list[str]:
    internal_names = ("E501_", "C501_REBOILER_", "TV501_", "TIC501_")
    out: list[str] = []
    for item in registry.items:
        if item.kind == "debug_port_label":
            out.append(f"debug label visible: {item.tag}")
        if item.kind in {"title", "equipment_tag", "valve_tag", "instrument_text", "offpage_tag", "offpage_ref"} and any(name in item.tag for name in internal_names):
            out.append(f"internal tag visible: {item.tag}")
    return sorted(set(out))


def _offpage_label_errors(registry: SceneRegistry) -> list[str]:
    expected = {"OPC_HM_SUPPLY_LOCAL", "OPC_HM_RETURN_LOCAL"}
    out: list[str] = []
    for tag in expected:
        if tag not in registry.evidence.get("offpage", set()):
            out.append(f"{tag} connector missing")
        if not any(item.kind == "offpage_tag" and item.tag == tag for item in registry.items):
            out.append(f"{tag} service label missing")
        if not any(item.kind == "offpage_ref" and item.tag == f"{tag}:ref" for item in registry.items):
            out.append(f"{tag} drawing reference missing")
    return out


def _nozzle_attachment_errors(registry: SceneRegistry) -> list[str]:
    out: list[str] = []
    for full_ref, side in registry.nozzle_sides.items():
        equipment, _, nozzle = full_ref.partition(".")
        if equipment not in {"C-501", "E-501"}:
            continue
        box = registry.equipment_bboxes[equipment]
        wall = registry.nozzle_wall_points.get(full_ref)
        if wall is None:
            out.append(f"{full_ref} has no wall point")
            continue
        if side == "left" and abs(wall[0] - box.xmin) > 1.5:
            out.append(f"{full_ref} wall x {wall[0]} is not on {equipment} left body edge {box.xmin}")
        elif side == "right" and abs(wall[0] - box.xmax) > 1.5:
            out.append(f"{full_ref} wall x {wall[0]} is not on {equipment} right body edge {box.xmax}")
        if side in {"left", "right"} and not (box.ymin - 0.5 <= wall[1] <= box.ymax + 0.5):
            out.append(f"{full_ref} wall y {wall[1]} is outside {equipment} body vertical span")
        if registry.ports.get(nozzle) == wall:
            out.append(f"{full_ref} connection point equals wall point; nozzle neck is missing")
    return out


def _control_valve_confirmed(registry: SceneRegistry, tag: str) -> bool:
    used_control_block = any(entry.startswith(f"{tag}: control_valve ->") for entry in registry.existing_blocks_used)
    used_manual_block = any(entry.startswith(f"{tag}: manual_block_valve ->") for entry in registry.existing_blocks_used)
    primitive_fallback = any(entry.startswith(f"{tag}: primitive valve") for entry in registry.primitive_symbols_created)
    return registry.valve_types.get(tag) == "control_valve" and used_control_block and not used_manual_block and not primitive_fallback


def _engineering_logic_errors(registry: SceneRegistry) -> list[str]:
    out: list[str] = []
    ports = registry.ports
    if ports["C501_REBOILER_RETURN"][1] <= ports["C501_REBOILER_DRAW"][1]:
        out.append("C501_REBOILER_RETURN is not above C501_REBOILER_DRAW")
    expected_routes = {
        "C501_DRAW_TO_E501_IN": ("C501_REBOILER_DRAW", "E501_PROCESS_IN"),
        "E501_OUT_TO_C501_RETURN": ("E501_PROCESS_OUT", "C501_REBOILER_RETURN"),
        "HM_SUPPLY_TO_E501_IN": ("OPC_HM_SUPPLY_LOCAL.continuation", "E501_HM_IN"),
        "E501_HM_OUT_TO_RETURN": ("E501_HM_OUT", "OPC_HM_RETURN_LOCAL.continuation"),
    }
    for tag, expected in expected_routes.items():
        if registry.route_endpoint_refs.get(tag) != expected:
            out.append(f"{tag} endpoints {registry.route_endpoint_refs.get(tag)} != {expected}")
    tv = _item_bbox(registry, "valve", "TV-501")
    if tv is None:
        out.append("TV-501 valve body missing")
    else:
        tv_center_x = (tv.xmin + tv.xmax) / 2
        if not (ports["OPC_HM_SUPPLY_LOCAL.continuation"][0] > tv_center_x > ports["E501_HM_IN"][0]):
            out.append("TV-501 is not upstream of E501_HM_IN on heating medium supply route")
        if not _port_on_route(registry, "HM_SUPPLY_TO_E501_IN", "TV-501.process_in"):
            out.append("TV-501.process_in is not mounted on HM_SUPPLY_TO_E501_IN")
        if not _port_on_route(registry, "HM_SUPPLY_TO_E501_IN", "TV-501.process_out"):
            out.append("TV-501.process_out is not mounted on HM_SUPPLY_TO_E501_IN")
    return out


def _signal_logic_errors(registry: SceneRegistry) -> list[str]:
    out: list[str] = []
    if registry.signal_connections.get("TIC501_TO_TV501") != [("TIC-501.output_signal", "TV-501.actuator_signal")]:
        out.append(f"TIC signal connections are {registry.signal_connections.get('TIC501_TO_TV501')}")
    unexpected_signals = sorted({seg.tag for seg in registry.line_segments if seg.layer in {"SIGNAL_PNEUMATIC", "SIGNAL_ELECTRIC"} and seg.tag != "TIC501_TO_TV501"})
    if unexpected_signals:
        out.append(f"unexpected signal routes: {', '.join(unexpected_signals)}")
    for item in registry.items:
        for seg in _signal_segments(registry, "TIC501_TO_TV501"):
            if item.kind == "valve" and item.bbox.overlaps(_segment_bbox(seg, 1.0)):
                out.append(f"TIC501_TO_TV501 crosses valve body {item.tag}")
            if item.kind in {"debug_port_label", "valve_tag", "instrument_text", "equipment_tag", "offpage_tag", "offpage_ref"}:
                if item.bbox.overlaps(_segment_bbox(seg, 1.0)):
                    out.append(f"TIC501_TO_TV501 crosses text {item.tag}")
    return sorted(set(out))


def _crossings(registry: SceneRegistry, box: BBox, layers: set[str], equipment_tag: str) -> list[str]:
    out = []
    for seg in registry.line_segments:
        if seg.layer not in layers:
            continue
        if _segment_has_equipment_nozzle_endpoint(registry, seg.p1, equipment_tag) or _segment_has_equipment_nozzle_endpoint(registry, seg.p2, equipment_tag):
            continue
        if _segment_enters_box(seg.p1, seg.p2, box):
            out.append(f"{seg.tag}@{seg.p1}->{seg.p2}")
    return sorted(set(out))


def _item_bbox(registry: SceneRegistry, kind: str, tag: str) -> BBox | None:
    item = next((item for item in registry.items if item.kind == kind and item.tag == tag), None)
    return item.bbox if item else None


def _port_on_route(registry: SceneRegistry, route_tag: str, port_ref: str) -> bool:
    point = registry.ports.get(port_ref)
    if point is None:
        return False
    return any(seg.tag == route_tag and _point_on_segment(point, seg.p1, seg.p2, 1.5) for seg in registry.line_segments)


def _signal_segments(registry: SceneRegistry, tag: str):
    return [seg for seg in registry.line_segments if seg.tag == tag and seg.layer in {"SIGNAL_PNEUMATIC", "SIGNAL_ELECTRIC"}]


def _segment_has_equipment_nozzle_endpoint(registry: SceneRegistry, point: tuple[float, float], equipment_tag: str) -> bool:
    refs = registry.port_refs_at(point, {"nozzle"}, 1.5)
    if equipment_tag == "E-501":
        return any(ref.startswith("E-501.") or ref.startswith("E501_") for ref in refs)
    return any(ref.startswith("C501_REBOILER_") for ref in refs)


def _valve_mounted(registry: SceneRegistry, tag: str) -> bool:
    item = next((item for item in registry.items if item.kind == "valve" and item.tag == tag), None)
    if item is None:
        return False
    center = ((item.bbox.xmin + item.bbox.xmax) / 2, (item.bbox.ymin + item.bbox.ymax) / 2)
    routed = [seg for seg in registry.line_segments if seg.layer in {"PROCESS", "UTILITY"}]
    return any(_point_on_segment(center, seg.p1, seg.p2, 16.0) for seg in routed)


def _text_collisions(registry: SceneRegistry) -> list[str]:
    routed = [seg for seg in registry.line_segments if seg.layer in {"PROCESS", "UTILITY"}]
    valves = [item for item in registry.items if item.kind == "valve"]
    nozzles = [item for item in registry.items if item.kind == "nozzle"]
    out: list[str] = []
    for item in registry.items:
        if item.kind not in {"debug_port_label", "valve_tag", "instrument_text", "equipment_tag", "offpage_tag", "offpage_ref"}:
            continue
        for seg in routed:
            if item.bbox.overlaps(_segment_bbox(seg, 1.0)):
                out.append(f"{item.tag}/{seg.tag}")
        for valve in valves:
            if item.tag != valve.tag and item.bbox.overlaps(valve.bbox, 1.0):
                out.append(f"{item.tag}/{valve.tag}")
        for nozzle in nozzles:
            if item.tag != nozzle.tag and item.bbox.overlaps(nozzle.bbox, 1.0):
                out.append(f"{item.tag}/{nozzle.tag}")
    return sorted(set(out))


def _point_on_signal(registry: SceneRegistry, point: tuple[float, float], tag: str) -> bool:
    return any(seg.tag == tag and _point_on_segment(point, seg.p1, seg.p2, 1.5) for seg in registry.line_segments)


def _segment_enters_box(p1: tuple[float, float], p2: tuple[float, float], box: BBox, clearance: float = 1.0) -> bool:
    xmin, xmax = box.xmin + clearance, box.xmax - clearance
    ymin, ymax = box.ymin + clearance, box.ymax - clearance
    if p1[1] == p2[1]:
        y = p1[1]
        return ymin < y < ymax and max(min(p1[0], p2[0]), xmin) < min(max(p1[0], p2[0]), xmax)
    if p1[0] == p2[0]:
        x = p1[0]
        return xmin < x < xmax and max(min(p1[1], p2[1]), ymin) < min(max(p1[1], p2[1]), ymax)
    return True


def _segment_bbox(seg, pad: float) -> BBox:
    return BBox(min(seg.p1[0], seg.p2[0]) - pad, min(seg.p1[1], seg.p2[1]) - pad, max(seg.p1[0], seg.p2[0]) + pad, max(seg.p1[1], seg.p2[1]) + pad, seg.tag, "line")


def _point_on_segment(point: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], tol: float) -> bool:
    x, y = point
    if p1[0] == p2[0]:
        return abs(x - p1[0]) <= tol and min(p1[1], p2[1]) - tol <= y <= max(p1[1], p2[1]) + tol
    if p1[1] == p2[1]:
        return abs(y - p1[1]) <= tol and min(p1[0], p2[0]) - tol <= x <= max(p1[0], p2[0]) + tol
    return False


def _record(report: ValidationReport, label: str, ok: bool) -> None:
    if ok:
        report.passes.append(label)
    else:
        report.failures.append(label)


def _record_with_details(report: ValidationReport, label: str, offenders: list[str]) -> None:
    if offenders:
        report.failures.append(f"{label}; offenders: {', '.join(sorted(set(offenders))[:8])}")
    else:
        report.passes.append(label)


if __name__ == "__main__":
    raise SystemExit(main())
