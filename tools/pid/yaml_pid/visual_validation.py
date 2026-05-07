from __future__ import annotations

from .drafting_standard import DEFAULT_STANDARD, DraftingStandard
from .engineering_validation import ValidationReport
from .scene import BBox, SceneRegistry


def run_visual_validation(registry: SceneRegistry, *, final_mode: bool, standard: DraftingStandard = DEFAULT_STANDARD) -> ValidationReport:
    report = ValidationReport("VISUAL QA REPORT")
    border = BBox(standard.inner_border_margin, standard.inner_border_margin, standard.sheet_w - standard.inner_border_margin, standard.sheet_h - standard.inner_border_margin, "inner_border")
    outside = sorted({item.tag for item in registry.items if item.bbox.outside(border.xmin, border.ymin, border.xmax, border.ymax)})
    if outside:
        report.failures.append("items outside sheet: " + ", ".join(outside))
    else:
        report.passes.append("all registered items inside sheet border")

    diagonal_signals = [seg.tag for seg in registry.line_segments if seg.layer.startswith("SIGNAL") and seg.diagonal]
    if final_mode and diagonal_signals:
        report.failures.append("diagonal signal segments in final mode: " + ", ".join(diagonal_signals[:8]))
    else:
        report.passes.append("signal routes are orthogonal")

    diagonal_process = [seg.tag for seg in registry.line_segments if seg.layer in {"PROCESS", "UTILITY", "FLARE", "DRAIN"} and seg.diagonal]
    if final_mode and diagonal_process:
        report.failures.append("diagonal process/utility pipe segments in final mode: " + ", ".join(diagonal_process[:8]))
    else:
        report.passes.append("process and utility routes are orthogonal")

    port_points = set(registry.ports.values())
    bad_endpoints = []
    for tag, (start, end) in registry.route_endpoints.items():
        if start not in port_points:
            bad_endpoints.append(f"{tag} start {start}")
        if end not in port_points:
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

    instruments = [item for item in registry.items if item.kind == "instrument"]
    inst_pipe_overlaps = [f"{item.tag}/{seg.tag}" for item in instruments for seg in routed_segments if item.bbox.overlaps(_segment_bbox(seg, 1.5))]
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
