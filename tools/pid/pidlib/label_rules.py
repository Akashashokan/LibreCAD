from __future__ import annotations

from .drafting_standard import DraftingStandard, DEFAULT_STANDARD
from .geometry import BBox

Point = tuple[float, float]


def equipment_tag_position(eq_bbox: BBox, standard: DraftingStandard = DEFAULT_STANDARD) -> tuple[float, float]:
    x = (eq_bbox.xmin + eq_bbox.xmax) / 2
    y = eq_bbox.ymin - standard.equipment_tag_offset
    return x, y


def valve_tag_position(x: float, y: float, orientation: str, standard: DraftingStandard = DEFAULT_STANDARD) -> tuple[float, float]:
    if orientation == "H":
        return x - 12, y + standard.valve_tag_offset
    return x + standard.valve_tag_offset, y - 2


def valve_fail_text_position(x: float, y: float, orientation: str, standard: DraftingStandard = DEFAULT_STANDARD) -> tuple[float, float]:
    if orientation == "H":
        return x - 4, y - standard.valve_fail_offset - standard.tag_text_h
    return x - standard.valve_fail_offset - 9, y - 2


def pick_label_segment(points: list[Point]) -> tuple[Point, Point]:
    best = (points[0], points[1])
    best_len = -1.0
    for p1, p2 in zip(points, points[1:]):
        horizontal = abs(p1[1] - p2[1]) < 0.001
        vertical = abs(p1[0] - p2[0]) < 0.001
        if not (horizontal or vertical):
            continue
        seg_len = abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])
        if seg_len > best_len:
            best = (p1, p2)
            best_len = seg_len
    return best


def line_label_position(segment: tuple[Point, Point], standard: DraftingStandard = DEFAULT_STANDARD) -> tuple[float, float, float]:
    (x1, y1), (x2, y2) = segment
    if abs(y1 - y2) < 0.001:
        return (x1 + x2) / 2, y1 + standard.line_label_offset, 0.0
    return x1 + standard.line_label_offset, (y1 + y2) / 2, 90.0


def offpage_text_x(x: float, direction: str) -> float:
    return x + 2 if direction in {"in", "right"} else x - 54
