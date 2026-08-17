from __future__ import annotations

from .drafting_standard import DEFAULT_STANDARD, DraftingStandard
from .engineering_validation import ValidationReport
from .scene import BBox, SceneRegistry


def run_visual_validation(registry: SceneRegistry, *, final_mode: bool, standard: DraftingStandard = DEFAULT_STANDARD) -> ValidationReport:
    report = ValidationReport("VISUAL QA REPORT")
    if final_mode and registry.render_errors:
        report.failures.append("renderer geometry ownership failures: " + " | ".join(registry.render_errors[:16]))
    elif registry.render_errors:
        report.warnings.append("debug renderer geometry ownership failures: " + " | ".join(registry.render_errors[:16]))
    else:
        report.passes.append("renderer drew only owned route geometry")

    if final_mode and registry.unresolved_connections:
        report.failures.append("unresolved declared connections: " + " | ".join(registry.unresolved_connections[:16]))
    elif registry.unresolved_connections:
        report.warnings.append("debug unresolved declared connections: " + " | ".join(registry.unresolved_connections[:16]))
    else:
        report.passes.append("declared signal/control routes resolve to registered ports")

    border = BBox(standard.inner_border_margin, standard.inner_border_margin, standard.sheet_w - standard.inner_border_margin, standard.sheet_h - standard.inner_border_margin, "inner_border")
    title_block = BBox(standard.title_block_x, standard.title_block_y, standard.title_block_x + standard.title_block_w, standard.title_block_y + standard.title_block_h, "title_block")
    outside = sorted({item.tag for item in registry.items if item.bbox.outside(border.xmin, border.ymin, border.xmax, border.ymax)})
    if outside:
        report.failures.append("items outside sheet: " + ", ".join(outside))
    else:
        report.passes.append("all registered items inside sheet border")

    title_intrusions = _title_block_intrusions(registry, title_block)
    if final_mode and title_intrusions:
        report.failures.append("items or routed lines intrude into title block: " + ", ".join(title_intrusions[:12]))
    else:
        report.passes.append("drawing content clears title block")

    diagonal_signals = [seg.tag for seg in registry.line_segments if (seg.layer.startswith("SIGNAL") or seg.layer == "IMPULSE_LINE") and seg.diagonal and not _allowed_diagonal_signal(seg.tag)]
    if final_mode and diagonal_signals:
        report.failures.append("diagonal instrument signal/impulse segments in final mode: " + ", ".join(diagonal_signals[:8]))
    else:
        report.passes.append("instrument signal and impulse routes are orthogonal")

    duplicate_signals = _duplicate_signal_segments(registry)
    if final_mode and duplicate_signals:
        report.failures.append("overlapping duplicate signal segments: " + ", ".join(duplicate_signals[:8]))
    else:
        report.passes.append("signal routing has no duplicate overlapping segments")

    diagonal_process = [seg.tag for seg in registry.line_segments if seg.layer in {"PROCESS", "UTILITY", "FLARE", "DRAIN"} and seg.diagonal]
    if final_mode and diagonal_process:
        report.failures.append("diagonal process/utility pipe segments in final mode: " + ", ".join(diagonal_process[:8]))
    else:
        report.passes.append("process and utility routes are orthogonal")

    dangling_process = _dangling_endpoints(registry, {"PROCESS", "UTILITY", "FLARE", "DRAIN"}, {"nozzle", "offpage", "valve", "pipe_junction"}, tol=1.5)
    if final_mode and dangling_process:
        report.failures.append("dangling process/utility endpoints: " + ", ".join(dangling_process[:16]))
    else:
        report.passes.append("process and utility endpoints are connected")

    dangling_signal = _dangling_endpoints(registry, {"SIGNAL_ELECTRIC", "SIGNAL_PNEUMATIC", "SIGNAL_SOFTWARE", "SIGNAL_SIS", "IMPULSE_LINE"}, {"instrument", "actuator", "nozzle", ":port"}, tol=1.5)
    if final_mode and dangling_signal:
        report.failures.append("dangling signal/impulse endpoints: " + ", ".join(dangling_signal[:16]))
    else:
        report.passes.append("signal and impulse endpoints are connected")

    ambiguous_crossings = _ambiguous_crossings(registry)
    if final_mode and ambiguous_crossings:
        report.failures.append("ambiguous un-gapped route crossings: " + ", ".join(ambiguous_crossings[:16]))
    else:
        report.passes.append("route crossings are explicit")

    equipment_crossings = _line_equipment_crossings(registry)
    if final_mode and equipment_crossings:
        report.failures.append("lines pass through equipment bodies: " + ", ".join(equipment_crossings[:12]))
    else:
        report.passes.append("routed lines clear equipment bodies")

    bad_nozzle_departures = _bad_nozzle_departures(registry)
    if final_mode and bad_nozzle_departures:
        report.failures.append("line leaves nozzle in wrong orientation: " + ", ".join(bad_nozzle_departures[:12]))
    else:
        report.passes.append("nozzle-connected lines follow nozzle orientation")

    floating_nozzles = _floating_nozzles(registry)
    if final_mode and floating_nozzles:
        report.failures.append("nozzle wall points not attached to equipment: " + ", ".join(floating_nozzles[:12]))
    else:
        report.passes.append("nozzle wall points attach to equipment")

    bad_endpoints = []
    for tag, (start_ref, end_ref) in registry.route_endpoint_refs.items():
        if start_ref is None:
            start = registry.route_endpoints.get(tag, ((None, None), (None, None)))[0]
            bad_endpoints.append(f"{tag} start {start}")
        if end_ref is None:
            end = registry.route_endpoints.get(tag, ((None, None), (None, None)))[1]
            bad_endpoints.append(f"{tag} end {end}")
    if bad_endpoints:
        report.failures.append("pipe endpoints not on registered ports: " + "; ".join(bad_endpoints[:10]))
    else:
        report.passes.append("all process pipe endpoints connect to registered ports")

    labels = [item for item in registry.items if item.kind == "line_label"]
    valves = [item for item in registry.items if item.kind == "valve"]
    routed_layers = {"PROCESS", "UTILITY", "FLARE", "DRAIN"}
    routed_segments = [seg for seg in registry.line_segments if seg.layer in routed_layers]
    detached_valves = [item.tag for item in valves if not _valve_ports_touch_pipe(item.tag, registry, routed_segments) and not _point_on_any_segment(_center(item.bbox), routed_segments, 16.0)]
    if detached_valves:
        report.failures.append("valves not centered on a routed pipe segment: " + ", ".join(detached_valves[:12]))
    else:
        report.passes.append("valves are centered on routed pipe segments")

    offpages = [item for item in registry.items if item.kind == "offpage"]
    detached_offpages = [item.tag for item in offpages if not _point_on_any_segment(_center(item.bbox), routed_segments)]
    if detached_offpages:
        report.failures.append("off-page connectors not aligned with routed pipe endpoints: " + ", ".join(detached_offpages[:12]))
    else:
        report.passes.append("off-page connectors align with routed pipe endpoints")

    overlaps = [f"{label.tag}/{valve.tag}" for label in labels for valve in valves if label.bbox.overlaps(valve.bbox, 1.0)]
    if overlaps:
        report.warnings.append("line label near valve: " + ", ".join(overlaps[:8]))
    else:
        report.passes.append("line labels clear of valve symbols")

    if registry.fallbacks and final_mode:
        report.failures.append("fallback primitive symbols are not allowed in final mode: " + ", ".join(registry.fallbacks))
    elif registry.fallbacks:
        report.warnings.append("debug primitive fallbacks: " + ", ".join(registry.fallbacks))
    else:
        report.passes.append("no fallback symbols used")

    block_overlaps = _placed_block_overlaps(registry)
    if final_mode and block_overlaps:
        report.failures.append("placed CAD blocks overlap: " + ", ".join(block_overlaps[:12]))
    else:
        report.passes.append("placed CAD blocks clear each other")

    instruments = [item for item in registry.items if item.kind == "instrument"]
    inst_pipe_overlaps = [f"{item.tag}/{seg.tag}" for item in instruments for seg in routed_segments if not _allowed_instrument_pipe_overlap(item.tag) and item.bbox.overlaps(_segment_bbox(seg, 1.5))]
    if inst_pipe_overlaps:
        report.failures.append("instrument symbols overlap process/utility piping: " + ", ".join(inst_pipe_overlaps[:12]))
    else:
        report.passes.append("instrument symbols clear process and utility piping")

    if [seg for seg in registry.line_segments if seg.layer.startswith("SIGNAL") or seg.layer == "IMPULSE_LINE"]:
        report.passes.append("instrument signal routes use explicit short dash segments")

    text_items = [item for item in registry.items if "text" in item.kind or item.kind.endswith("_tag")]
    text_pipe_overlaps = [
        f"{item.tag}/{seg.tag}"
        for item in text_items
        for seg in routed_segments
        if item.bbox.overlaps(_segment_bbox(seg, 0.75))
    ]
    if text_pipe_overlaps:
        report.failures.append("text overlaps process/utility piping: " + ", ".join(text_pipe_overlaps[:12]))
    else:
        report.passes.append("text clears process and utility piping")

    valve_text_overlaps = [
        f"{text.tag}/{valve.tag}"
        for text in text_items
        for valve in valves
        if text.kind != "valve_tag" and text.tag != valve.tag and text.bbox.overlaps(valve.bbox, 1.0)
    ]
    if valve_text_overlaps:
        report.failures.append("text overlaps valve symbols: " + ", ".join(valve_text_overlaps[:12]))
    else:
        report.passes.append("text clears valve symbols")

    unconnected_final_elements = _unconnected_final_elements(registry)
    if final_mode and unconnected_final_elements:
        report.failures.append("control/shutdown final elements missing signal connection: " + ", ".join(unconnected_final_elements[:12]))
    else:
        report.passes.append("control and shutdown valves have signal connections")
    return report


def draw_qa_overlay(ctx) -> None:
    if "QA_OVERLAY" not in ctx.doc.layers:
        ctx.doc.layers.add("QA_OVERLAY", color=2)
    for item in ctx.registry.items:
        box = item.bbox
        ctx.msp.add_lwpolyline([(box.xmin, box.ymin), (box.xmax, box.ymin), (box.xmax, box.ymax), (box.xmin, box.ymax), (box.xmin, box.ymin)], dxfattribs={"layer": "QA_OVERLAY"})
    for ref, point in ctx.registry.ports.items():
        x, y = point
        ctx.msp.add_line((x - 2, y), (x + 2, y), dxfattribs={"layer": "QA_OVERLAY"})
        ctx.msp.add_line((x, y - 2), (x, y + 2), dxfattribs={"layer": "QA_OVERLAY"})


def _center(box: BBox) -> tuple[float, float]:
    return (box.xmin + box.xmax) / 2, (box.ymin + box.ymax) / 2


def _point_on_any_segment(point: tuple[float, float], segments, tol: float = 1.0) -> bool:
    x, y = point
    for seg in segments:
        x1, y1 = seg.p1
        x2, y2 = seg.p2
        if x1 == x2 and abs(x - x1) <= tol and min(y1, y2) - tol <= y <= max(y1, y2) + tol:
            return True
        if y1 == y2 and abs(y - y1) <= tol and min(x1, x2) - tol <= x <= max(x1, x2) + tol:
            return True
    return False


def _valve_ports_touch_pipe(tag: str, registry: SceneRegistry, segments) -> bool:
    ports = [registry.ports.get(f"{tag}.process_in"), registry.ports.get(f"{tag}.process_out")]
    return all(port is not None and _point_touches_segment_endpoint_or_body(port, segments) for port in ports)


def _point_touches_segment_endpoint_or_body(point: tuple[float, float], segments, tol: float = 1.0) -> bool:
    return _point_on_any_segment(point, segments, tol)


def _segment_bbox(seg, pad: float = 0.0) -> BBox:
    return BBox(min(seg.p1[0], seg.p2[0]) - pad, min(seg.p1[1], seg.p2[1]) - pad, max(seg.p1[0], seg.p2[0]) + pad, max(seg.p1[1], seg.p2[1]) + pad, seg.tag, "line")


def _title_block_intrusions(registry: SceneRegistry, title_block: BBox) -> list[str]:
    intrusions = [
        item.tag
        for item in registry.items
        if item.kind not in {"title", "text"} and item.bbox.overlaps(title_block, 0.0)
    ]
    routed_layers = {"PROCESS", "UTILITY", "FLARE", "DRAIN", "SIGNAL_ELECTRIC", "SIGNAL_PNEUMATIC", "SIGNAL_SOFTWARE", "SIGNAL_SIS", "IMPULSE_LINE"}
    intrusions.extend(seg.tag for seg in registry.line_segments if seg.layer in routed_layers and _segment_enters_box(seg.p1, seg.p2, title_block, 0.0))
    return sorted(set(intrusions))


def _dangling_endpoints(registry: SceneRegistry, layers: set[str], allowed_port_kinds: set[str], tol: float = 1.0) -> list[str]:
    segments = [seg for seg in registry.line_segments if seg.layer in layers]
    out: list[str] = []
    for seg in segments:
        if seg.tag.startswith(("flow_impulse:", "flow_impulse_tap:")):
            continue
        for endpoint in (seg.p1, seg.p2):
            if _endpoint_degree(endpoint, segments, tol) > 1:
                continue
            if _point_near_allowed_port(endpoint, registry, allowed_port_kinds, tol):
                continue
            if _has_intentional_gap_partner(endpoint, seg, segments):
                continue
            out.append(f"{seg.tag}@{endpoint}")
    return sorted(set(out))


def _endpoint_degree(point: tuple[float, float], segments, tol: float) -> int:
    return sum(1 for seg in segments if _point_on_segment(point, seg.p1, seg.p2, tol))


def _point_near_allowed_port(point: tuple[float, float], registry: SceneRegistry, allowed_kinds: set[str], tol: float) -> bool:
    for ref, port in registry.ports.items():
        kind = registry.port_kinds.get(ref)
        kind_allowed = kind in allowed_kinds or (":port" in allowed_kinds and isinstance(kind, str) and kind.endswith(":port"))
        if kind_allowed and abs(point[0] - port[0]) <= tol and abs(point[1] - port[1]) <= tol:
            return True
    return False


def _has_intentional_gap_partner(point: tuple[float, float], source_seg, segments, max_gap: float = 15.0) -> bool:
    for seg in segments:
        if seg is source_seg or seg.tag != source_seg.tag:
            continue
        for other in (seg.p1, seg.p2):
            if source_seg.p1[0] == source_seg.p2[0] == seg.p1[0] == seg.p2[0]:
                if abs(point[0] - other[0]) <= 0.1 and 0.1 < abs(point[1] - other[1]) <= max_gap:
                    return True
            if source_seg.p1[1] == source_seg.p2[1] == seg.p1[1] == seg.p2[1]:
                if abs(point[1] - other[1]) <= 0.1 and 0.1 < abs(point[0] - other[0]) <= max_gap:
                    return True
    return False


def _point_on_segment(point: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], tol: float = 1.0) -> bool:
    x, y = point
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and abs(x - x1) <= tol and min(y1, y2) - tol <= y <= max(y1, y2) + tol:
        return True
    if y1 == y2 and abs(y - y1) <= tol and min(x1, x2) - tol <= x <= max(x1, x2) + tol:
        return True
    return False


def _ambiguous_crossings(registry: SceneRegistry) -> list[str]:
    routed_layers = {"PROCESS", "UTILITY", "FLARE", "DRAIN"}
    segments = [seg for seg in registry.line_segments if seg.layer in routed_layers]
    port_points = set(registry.ports.values())
    out: list[str] = []
    for idx, left in enumerate(segments):
        for right in segments[idx + 1:]:
            if left.tag == right.tag:
                continue
            crossing = _orthogonal_intersection(left.p1, left.p2, right.p1, right.p2)
            if crossing is None or crossing in port_points:
                continue
            if crossing in {left.p1, left.p2, right.p1, right.p2}:
                continue
            out.append(f"{left.tag}/{right.tag}@{crossing}")
    return sorted(set(out))


def _orthogonal_intersection(a1, a2, b1, b2):
    a_horizontal = a1[1] == a2[1]
    b_horizontal = b1[1] == b2[1]
    if a_horizontal == b_horizontal:
        return None
    h1, h2, v1, v2 = (a1, a2, b1, b2) if a_horizontal else (b1, b2, a1, a2)
    hx0, hx1 = sorted((h1[0], h2[0]))
    vy0, vy1 = sorted((v1[1], v2[1]))
    x, y = v1[0], h1[1]
    if hx0 < x < hx1 and vy0 < y < vy1:
        return (x, y)
    return None


def _unconnected_final_elements(registry: SceneRegistry) -> list[str]:
    signal_segments = [seg for seg in registry.line_segments if seg.layer.startswith("SIGNAL")]
    out: list[str] = []
    for tag, valve_type in sorted(registry.valve_types.items()):
        if valve_type not in {"control_valve", "shutdown_valve"}:
            continue
        ports = [
            point
            for ref, point in registry.ports.items()
            if ref.startswith(f"{tag}.") and ref.endswith("_signal")
        ]
        if not ports or not any(_point_on_any_segment(port, signal_segments, 1.5) for port in ports):
            out.append(tag)
    return out


def _duplicate_signal_segments(registry: SceneRegistry) -> list[str]:
    seen: dict[tuple[str, tuple[float, float], tuple[float, float]], str] = {}
    duplicates: list[str] = []
    for seg in registry.line_segments:
        if not seg.layer.startswith("SIGNAL"):
            continue
        a = (round(seg.p1[0], 3), round(seg.p1[1], 3))
        b = (round(seg.p2[0], 3), round(seg.p2[1], 3))
        key = (seg.layer, min(a, b), max(a, b))
        if key in seen:
            duplicates.append(f"{seen[key]}/{seg.tag}")
        else:
            seen[key] = seg.tag
    return duplicates


def _line_equipment_crossings(registry: SceneRegistry) -> list[str]:
    checked_layers = {"PROCESS", "UTILITY", "FLARE", "DRAIN", "SIGNAL_ELECTRIC", "SIGNAL_PNEUMATIC", "SIGNAL_SOFTWARE", "SIGNAL_SIS", "IMPULSE_LINE"}
    equipment = [item for item in registry.items if item.kind == "equipment"]
    crossings: list[str] = []
    for seg in registry.line_segments:
        if seg.layer not in checked_layers:
            continue
        for item in equipment:
            if _segment_terminates_at_equipment_nozzle(seg, item.tag, registry):
                continue
            if _segment_enters_box(seg.p1, seg.p2, item.bbox):
                crossings.append(f"{seg.tag}/{item.tag}")
    return sorted(set(crossings))


def _segment_terminates_at_equipment_nozzle(seg, equipment_tag: str, registry: SceneRegistry, tol: float = 1.5) -> bool:
    nozzle_ports = [
        point
        for ref, point in registry.ports.items()
        if ref.startswith(f"{equipment_tag}.") and ref.endswith(".connection_point")
    ]
    return any(
        (abs(seg.p1[0] - port[0]) <= tol and abs(seg.p1[1] - port[1]) <= tol)
        or (abs(seg.p2[0] - port[0]) <= tol and abs(seg.p2[1] - port[1]) <= tol)
        for port in nozzle_ports
    )


def _segment_enters_box(p1, p2, box: BBox, clearance: float = 1.0) -> bool:
    xmin = box.xmin + clearance
    xmax = box.xmax - clearance
    ymin = box.ymin + clearance
    ymax = box.ymax - clearance
    if xmin >= xmax or ymin >= ymax:
        return False
    x1, y1 = p1
    x2, y2 = p2
    if y1 == y2:
        if not ymin < y1 < ymax:
            return False
        return max(min(x1, x2), xmin) < min(max(x1, x2), xmax)
    if x1 == x2:
        if not xmin < x1 < xmax:
            return False
        return max(min(y1, y2), ymin) < min(max(y1, y2), ymax)
    return not (max(x1, x2) <= xmin or min(x1, x2) >= xmax or max(y1, y2) <= ymin or min(y1, y2) >= ymax)


def _bad_nozzle_departures(registry: SceneRegistry) -> list[str]:
    checked_layers = {"PROCESS", "UTILITY", "FLARE", "DRAIN", "IMPULSE_LINE"}
    out: list[str] = []
    for seg in registry.line_segments:
        if seg.layer not in checked_layers:
            continue
        for point, other in ((seg.p1, seg.p2), (seg.p2, seg.p1)):
            axis = registry.nozzle_axes.get(point)
            if axis == "horizontal" and point[1] != other[1]:
                out.append(f"{seg.tag}@{point}")
            elif axis == "vertical" and point[0] != other[0]:
                out.append(f"{seg.tag}@{point}")
    return sorted(set(out))


def _floating_nozzles(registry: SceneRegistry) -> list[str]:
    equipment = {item.tag: item.bbox for item in registry.items if item.kind == "equipment"}
    out: list[str] = []
    for tag, wall in registry.nozzle_wall_points.items():
        owner = tag.split(".", 1)[0]
        box = equipment.get(owner)
        if box is None:
            continue
        x, y = wall
        tol = 2.5
        side = registry.nozzle_sides.get(tag, "").lower()
        inside_span = box.xmin - tol <= x <= box.xmax + tol and box.ymin - tol <= y <= box.ymax + tol
        if "_" in side and inside_span:
            continue
        on_vertical_edge = abs(x - box.xmin) <= tol or abs(x - box.xmax) <= tol
        on_horizontal_edge = abs(y - box.ymin) <= tol or abs(y - box.ymax) <= tol
        if not inside_span or not (on_vertical_edge or on_horizontal_edge):
            out.append(f"{tag}@{wall}")
    return sorted(out)


def _placed_block_overlaps(registry: SceneRegistry) -> list[str]:
    block_kinds = {"equipment", "instrument", "valve", "offpage"}
    placed = [item for item in registry.items if item.kind in block_kinds]
    overlaps: list[str] = []
    for idx, left in enumerate(placed):
        for right in placed[idx + 1:]:
            if _allowed_block_overlap(left, right):
                continue
            if left.bbox.overlaps(right.bbox, 1.5):
                overlaps.append(f"{left.tag}/{right.tag}")
    return overlaps


def _allowed_block_overlap(left, right) -> bool:
    if left.kind == "valve" and right.kind == "valve":
        return True
    left_tag, right_tag = left.tag, right.tag
    return {left_tag[:2], right_tag[:2]} == {"FE", "FT"} and left_tag.split("-", 1)[1] == right_tag.split("-", 1)[1]


def _allowed_diagonal_signal(tag: str) -> bool:
    return tag.startswith("flow_impulse:")


def _allowed_instrument_pipe_overlap(tag: str) -> bool:
    return tag.startswith("FE-")
