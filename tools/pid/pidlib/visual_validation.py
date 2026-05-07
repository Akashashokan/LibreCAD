from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .drafting_standard import DraftingStandard, DEFAULT_STANDARD
from .geometry import BBox


@dataclass(frozen=True)
class PlacedItem:
    kind: str
    tag: str
    layer: str
    bbox: BBox


@dataclass(frozen=True)
class LineSegment:
    p1: tuple[float, float]
    p2: tuple[float, float]
    tag: str
    layer: str
    major: bool = True

    def bbox(self, clearance: float = 0.0) -> BBox:
        return BBox(
            min(self.p1[0], self.p2[0]) - clearance,
            min(self.p1[1], self.p2[1]) - clearance,
            max(self.p1[0], self.p2[0]) + clearance,
            max(self.p1[1], self.p2[1]) + clearance,
            self.tag,
            "line_segment",
        )


@dataclass
class SceneRegistry:
    items: list[PlacedItem] = field(default_factory=list)
    line_segments: list[LineSegment] = field(default_factory=list)
    required_seen: dict[str, set[str]] = field(default_factory=lambda: {"valve": set(), "equipment": set(), "line_label": set(), "offpage": set()})

    def add_item(self, kind: str, tag: str, layer: str, bbox: BBox) -> None:
        self.items.append(PlacedItem(kind, tag, layer, bbox))

    def add_line_segment(self, p1: tuple[float, float], p2: tuple[float, float], tag: str, layer: str, major: bool = True) -> None:
        self.line_segments.append(LineSegment(p1, p2, tag, layer, major))

    def mark(self, category: str, tag: str) -> None:
        self.required_seen.setdefault(category, set()).add(tag)


@dataclass
class QAReport:
    passes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def format(self) -> str:
        lines = ["VISUAL QA REPORT", "----------------"]
        lines.extend(f"PASS: {item}" for item in self.passes)
        lines.extend(f"WARN: {item}" for item in self.warnings)
        lines.extend(f"FAIL: {item}" for item in self.failures)
        return "\n".join(lines)


def bboxes_overlap(a: BBox, b: BBox, clearance: float = 0.0) -> bool:
    return not (
        a.xmax + clearance <= b.xmin
        or a.xmin - clearance >= b.xmax
        or a.ymax + clearance <= b.ymin
        or a.ymin - clearance >= b.ymax
    )


def run_visual_qa(
    registry: SceneRegistry,
    *,
    required_valves: Iterable[str],
    required_equipment: Iterable[str],
    required_line_labels: Iterable[str],
    standard: DraftingStandard = DEFAULT_STANDARD,
) -> QAReport:
    report = QAReport()
    border = BBox(standard.inner_border_margin, standard.inner_border_margin, standard.sheet_w - standard.inner_border_margin, standard.sheet_h - standard.inner_border_margin, "inner_border")

    outside = [item.tag for item in registry.items if item.bbox.outside(border.xmin, border.ymin, border.xmax, border.ymax)]
    if outside:
        report.failures.append("items outside border: " + ", ".join(sorted(set(outside))))
    else:
        report.passes.append("all registered items inside border")

    text_items = [i for i in registry.items if "text" in i.kind or i.kind.endswith("_tag") or i.kind == "line_label"]
    symbol_items = [i for i in registry.items if i.kind in {"valve", "equipment", "instrument_bubble", "offpage", "sample_conditioner"}]

    text_overlaps = _pair_overlaps(text_items, clearance=0.5)
    _extend_limited(report.warnings, text_overlaps, "text-text overlap")

    text_symbol = []
    for text in text_items:
        if text.kind in {"instrument_text", "equipment_label", "valve_fail_text"} or text.tag.startswith("vessel-service"):
            continue
        for symbol in symbol_items:
            if text.tag == symbol.tag:
                continue
            if _same_base_tag(text.tag, symbol.tag):
                continue
            if bboxes_overlap(text.bbox, symbol.bbox, clearance=1.0):
                text_symbol.append(f"{text.tag} near {symbol.tag}")
                break
    _extend_limited(report.warnings, text_symbol, "text-symbol overlap")

    symbol_overlaps = _pair_overlaps(symbol_items, clearance=standard.min_symbol_clearance * 0.35)
    _extend_limited(report.warnings, symbol_overlaps, "symbol-symbol overlap")

    close_to_lines = []
    for text in text_items:
        if text.kind in {"line_label", "instrument_text", "valve_tag", "valve_fail_text"}:
            continue
        for segment in registry.line_segments:
            if not segment.major:
                continue
            if bboxes_overlap(text.bbox, segment.bbox(standard.min_text_clearance)):
                close_to_lines.append(f"{text.tag} close to {segment.tag}")
                break
    _extend_limited(report.warnings, close_to_lines, "text too close to major line")

    _check_required(report, "XV valves", set(required_valves), registry.required_seen.get("valve", set()))
    _check_required(report, "equipment tags", set(required_equipment), registry.required_seen.get("equipment", set()))
    _check_required(report, "line labels", set(required_line_labels), registry.required_seen.get("line_label", set()))

    offpage_missing_ref = [i.tag for i in registry.items if i.kind == "offpage_ref_missing"]
    if offpage_missing_ref:
        report.failures.append("off-page connectors missing refs: " + ", ".join(offpage_missing_ref))
    else:
        report.passes.append("all off-page connectors have drawing references")

    return report


def draw_qa_overlay(msp, registry: SceneRegistry) -> None:
    if "QA_OVERLAY" not in msp.doc.layers:
        msp.doc.layers.add("QA_OVERLAY", color=2)
    for item in registry.items:
        box = item.bbox
        msp.add_lwpolyline(
            [(box.xmin, box.ymin), (box.xmax, box.ymin), (box.xmax, box.ymax), (box.xmin, box.ymax), (box.xmin, box.ymin)],
            dxfattribs={"layer": "QA_OVERLAY"},
        )


def _pair_overlaps(items: list[PlacedItem], clearance: float) -> list[str]:
    overlaps: list[str] = []
    for idx, left in enumerate(items):
        for right in items[idx + 1 :]:
            if left.tag == right.tag:
                continue
            if bboxes_overlap(left.bbox, right.bbox, clearance=clearance):
                overlaps.append(f"{left.tag} / {right.tag}")
    return overlaps


def _extend_limited(target: list[str], values: list[str], label: str, limit: int = 8) -> None:
    if not values:
        return
    for value in values[:limit]:
        target.append(f"{label}: {value}")
    if len(values) > limit:
        target.append(f"{label}: {len(values) - limit} additional occurrences")


def _check_required(report: QAReport, label: str, required: set[str], seen: set[str]) -> None:
    missing = required - seen
    if missing:
        report.failures.append(f"missing {label}: " + ", ".join(sorted(missing)))
    else:
        report.passes.append(f"all required {label} present")


def _same_base_tag(left: str, right: str) -> bool:
    for prefix in ["valve-tag:", "valve-fail:", "equipment-tag:", "instrument:"]:
        left = left.removeprefix(prefix)
        right = right.removeprefix(prefix)
    return left == right
