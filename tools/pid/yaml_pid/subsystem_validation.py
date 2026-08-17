from __future__ import annotations

from .engineering_validation import ValidationReport
from .scene import BBox, LineSegment, PlacedItem, SceneRegistry


ROUTED_LAYERS = {"PROCESS", "UTILITY", "FLARE", "DRAIN"}
SIGNAL_LAYERS = {"SIGNAL_ELECTRIC", "SIGNAL_PNEUMATIC", "SIGNAL_SOFTWARE", "SIGNAL_SIS", "IMPULSE_LINE"}
E501_PROCESS_ROUTES = {"500-RB-001", "500-RB-002"}
E501_UTILITY_ROUTES = {"500-HM-001", "500-HM-002"}


def run_e501_subsystem_validation(registry: SceneRegistry) -> ValidationReport:
    report = ValidationReport("SUBSYSTEM 1 QA REPORT - E-501 REBOILER PACKAGE")
    e501_box = registry.equipment_bboxes.get("E-501")
    if e501_box is None:
        report.failures.append("E-501 equipment bbox is not registered")
        return report

    _record(report, "E-501 equipment body registered as forbidden zone", "E-501" in registry.equipment_forbidden_zones)
    _validate_required_nozzles(report, registry)
    _validate_no_crossings(report, registry, e501_box, ROUTED_LAYERS, "no pipe crosses E-501 body")
    _validate_no_crossings(report, registry, e501_box, SIGNAL_LAYERS, "no signal or instrument hookup crosses E-501 body")
    _validate_route_endpoint(report, registry, "500-RB-001", "T-501.N4_reboiler_liquid_draw.connection_point", "E-501.N1_column_liquid_in.connection_point", "C501_REBOILER_DRAW connects to E501_PROCESS_IN")
    _validate_route_endpoint(report, registry, "500-RB-002", "E-501.N2_vapor_return.connection_point", "T-501.N5_reboiler_vapor_return.connection_point", "E501_PROCESS_OUT connects to C501_REBOILER_RETURN")
    _validate_route_endpoint(report, registry, "500-HM-001", "OPC_HM_SUPPLY.continuation", "E-501.N4_hot_utility_in.connection_point", "heating medium supply connects to E501_HM_IN")
    _validate_route_endpoint(report, registry, "500-HM-002", "E-501.N5_hot_utility_out.connection_point", "OPC_HM_RETURN.continuation", "E501_HM_OUT connects to heating medium return")
    _validate_valves_inline(report, registry, {"HV-507", "HV-508", "TV-501"})
    _validate_tv501_signal(report, registry)
    _validate_fic501_signal(report, registry)
    _validate_e501_text(report, registry, e501_box)
    return report


def _validate_required_nozzles(report: ValidationReport, registry: SceneRegistry) -> None:
    required = {
        "E-501.N1_column_liquid_in.connection_point": "E501_PROCESS_IN",
        "E-501.N2_vapor_return.connection_point": "E501_PROCESS_OUT",
        "E-501.N4_hot_utility_in.connection_point": "E501_HM_IN",
        "E-501.N5_hot_utility_out.connection_point": "E501_HM_OUT",
    }
    missing = [name for ref, name in required.items() if ref not in registry.ports]
    if missing:
        report.failures.append("missing E-501 external nozzles: " + ", ".join(missing))
    else:
        report.passes.append("E-501 external process and utility nozzles registered")


def _validate_no_crossings(report: ValidationReport, registry: SceneRegistry, box: BBox, layers: set[str], pass_label: str) -> None:
    offenders = []
    for seg in registry.line_segments:
        if seg.layer not in layers:
            continue
        if _segment_terminates_at_e501_nozzle(seg, registry):
            continue
        if _segment_enters_box(seg.p1, seg.p2, box):
            offenders.append(f"{seg.tag}@{seg.p1}->{seg.p2}")
    if offenders:
        report.failures.append(pass_label.replace("no ", "") + " failures: " + ", ".join(sorted(set(offenders))[:8]))
    else:
        report.passes.append(pass_label)


def _validate_route_endpoint(report: ValidationReport, registry: SceneRegistry, route: str, start_ref: str, end_ref: str, label: str) -> None:
    actual = registry.route_endpoint_refs.get(route)
    if actual == (start_ref, end_ref):
        report.passes.append(label)
    else:
        report.failures.append(f"{label}; expected {start_ref}->{end_ref}, got {actual}")


def _validate_valves_inline(report: ValidationReport, registry: SceneRegistry, tags: set[str]) -> None:
    routed = [seg for seg in registry.line_segments if seg.layer in ROUTED_LAYERS]
    valve_items = {item.tag: item for item in registry.items if item.kind == "valve"}
    missing = []
    for tag in tags:
        ports = [registry.ports.get(f"{tag}.process_in"), registry.ports.get(f"{tag}.process_out")]
        if any(port is None for port in ports):
            missing.append(f"{tag} missing process ports")
            continue
        center = _item_center(valve_items.get(tag))
        ports_touch = all(_point_on_any_segment(port, routed, 1.5) for port in ports if port is not None)
        center_mounted = center is not None and _point_on_any_segment(center, routed, 16.0)
        if not ports_touch and not center_mounted:
            missing.append(f"{tag} not inline")
    if missing:
        report.failures.append("E-501 local valves inline check failed: " + ", ".join(missing))
    else:
        report.passes.append("E-501 local valves are inline on routed pipe segments")


def _validate_tv501_signal(report: ValidationReport, registry: SceneRegistry) -> None:
    port = registry.ports.get("TV-501.actuator_signal")
    signal_segments = [seg for seg in registry.line_segments if seg.layer.startswith("SIGNAL")]
    if port is not None and _point_on_any_segment(port, signal_segments, 1.5):
        report.passes.append("TV-501 actuator signal is registered and connected")
    else:
        report.failures.append("TV-501 actuator signal is missing or not connected")


def _validate_fic501_signal(report: ValidationReport, registry: SceneRegistry) -> None:
    source = registry.ports.get("FIC-501.output_signal")
    target = registry.ports.get("FV-501.actuator_signal")
    signal_segments = [seg for seg in registry.line_segments if seg.tag == "FIC-501_to_FV-501"]
    if source is None or target is None:
        report.failures.append("FIC-501_to_FV-501 source or target port is missing")
    elif _point_on_any_segment(source, signal_segments, 1.5) and _point_on_any_segment(target, signal_segments, 1.5):
        report.passes.append("FIC-501_to_FV-501 has no dangling endpoint")
    else:
        report.failures.append("FIC-501_to_FV-501 endpoint is not snapped to source/target")


def _validate_e501_text(report: ValidationReport, registry: SceneRegistry, box: BBox) -> None:
    local_routes = [seg for seg in registry.line_segments if seg.tag in E501_PROCESS_ROUTES | E501_UTILITY_ROUTES]
    local_items = [item for item in registry.items if item.tag in {"E-501", "TV-501", "HV-507", "HV-508", "TT-503", "TI-503", "TIC-501"} or item.tag.startswith("E-501")]
    collisions = []
    for item in local_items:
        if item.kind in {"equipment", "nozzle"}:
            continue
        if item.kind in {"text", "equipment_tag", "valve_tag", "instrument_text", "instrument", "alarm_indicator"}:
            if item.bbox.overlaps(box, 1.0) and item.tag != "E-501":
                collisions.append(f"{item.tag}/E-501")
            for seg in local_routes:
                if item.bbox.overlaps(_segment_bbox(seg, 0.75)):
                    collisions.append(f"{item.tag}/{seg.tag}")
    if collisions:
        report.failures.append("E-501 local text/bubble collisions: " + ", ".join(sorted(set(collisions))[:8]))
    else:
        report.passes.append("E-501 tag, local valve tags, and local instruments clear local routes")


def _segment_terminates_at_e501_nozzle(seg: LineSegment, registry: SceneRegistry, tol: float = 1.5) -> bool:
    nozzles = [point for ref, point in registry.ports.items() if ref.startswith("E-501.") and ref.endswith(".connection_point")]
    return any(
        abs(seg.p1[0] - point[0]) <= tol and abs(seg.p1[1] - point[1]) <= tol
        or abs(seg.p2[0] - point[0]) <= tol and abs(seg.p2[1] - point[1]) <= tol
        for point in nozzles
    )


def _point_on_any_segment(point: tuple[float, float], segments: list[LineSegment], tol: float) -> bool:
    return any(_point_on_segment(point, seg.p1, seg.p2, tol) for seg in segments)


def _point_on_segment(point: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], tol: float) -> bool:
    x, y = point
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and abs(x - x1) <= tol and min(y1, y2) - tol <= y <= max(y1, y2) + tol:
        return True
    if y1 == y2 and abs(y - y1) <= tol and min(x1, x2) - tol <= x <= max(x1, x2) + tol:
        return True
    return False


def _segment_bbox(seg: LineSegment, pad: float) -> BBox:
    return BBox(min(seg.p1[0], seg.p2[0]) - pad, min(seg.p1[1], seg.p2[1]) - pad, max(seg.p1[0], seg.p2[0]) + pad, max(seg.p1[1], seg.p2[1]) + pad, seg.tag, "line")


def _item_center(item: PlacedItem | None) -> tuple[float, float] | None:
    if item is None:
        return None
    return (item.bbox.xmin + item.bbox.xmax) / 2, (item.bbox.ymin + item.bbox.ymax) / 2


def _segment_enters_box(p1: tuple[float, float], p2: tuple[float, float], box: BBox, clearance: float = 1.0) -> bool:
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


def _record(report: ValidationReport, label: str, ok: bool) -> None:
    if ok:
        report.passes.append(label)
    else:
        report.failures.append(label)
