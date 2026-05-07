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
