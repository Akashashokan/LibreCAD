from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    label: str
    kind: str = "item"

    def expanded(self, margin: float) -> "BBox":
        return BBox(
            self.xmin - margin,
            self.ymin - margin,
            self.xmax + margin,
            self.ymax + margin,
            self.label,
            self.kind,
        )

    def overlaps(self, other: "BBox") -> bool:
        return not (
            self.xmax <= other.xmin
            or self.xmin >= other.xmax
            or self.ymax <= other.ymin
            or self.ymin >= other.ymax
        )

    def outside(self, xmin: float, ymin: float, xmax: float, ymax: float) -> bool:
        return self.xmin < xmin or self.ymin < ymin or self.xmax > xmax or self.ymax > ymax


def text_bbox(text: str, x: float, y: float, height: float, label: str) -> BBox:
    width = max(len(text), 1) * height * 0.62
    return BBox(x, y, x + width, y + height, label, "text")


def line_bbox(points: list[tuple[float, float]], label: str, pad: float = 1.0) -> BBox:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return BBox(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad, label, "line")
