from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float]


@dataclass(frozen=True)
class BBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    label: str
    kind: str = "item"

    def outside(self, xmin: float, ymin: float, xmax: float, ymax: float) -> bool:
        return self.xmin < xmin or self.ymin < ymin or self.xmax > xmax or self.ymax > ymax

    def overlaps(self, other: "BBox", clearance: float = 0.0) -> bool:
        return not (
            self.xmax + clearance <= other.xmin
            or self.xmin - clearance >= other.xmax
            or self.ymax + clearance <= other.ymin
            or self.ymin - clearance >= other.ymax
        )


@dataclass(frozen=True)
class PlacedItem:
    kind: str
    tag: str
    layer: str
    bbox: BBox


@dataclass(frozen=True)
class LineSegment:
    p1: Point
    p2: Point
    tag: str
    layer: str
    major: bool = True

    @property
    def diagonal(self) -> bool:
        return self.p1[0] != self.p2[0] and self.p1[1] != self.p2[1]


@dataclass
class SceneRegistry:
    items: list[PlacedItem] = field(default_factory=list)
    line_segments: list[LineSegment] = field(default_factory=list)
    ports: dict[str, Point] = field(default_factory=dict)
    port_kinds: dict[str, str] = field(default_factory=dict)
    evidence: dict[str, set[str]] = field(default_factory=lambda: {"equipment": set(), "valve": set(), "instrument": set(), "line": set(), "line_label": set(), "offpage": set(), "document": set(), "nozzle": set()})
    route_endpoints: dict[str, tuple[Point, Point]] = field(default_factory=dict)
    fallbacks: list[str] = field(default_factory=list)
    failed_block_imports: list[str] = field(default_factory=list)
    primitive_symbols_created: list[str] = field(default_factory=list)
    existing_blocks_used: list[str] = field(default_factory=list)

    def add_item(self, kind: str, tag: str, layer: str, bbox: BBox) -> None:
        self.items.append(PlacedItem(kind, tag, layer, bbox))

    def add_line_segment(self, p1: Point, p2: Point, tag: str, layer: str, major: bool = True) -> None:
        self.line_segments.append(LineSegment(p1, p2, tag, layer, major))

    def add_port(self, ref: str, point: Point, kind: str) -> None:
        self.ports[ref] = point
        self.port_kinds[ref] = kind

    def mark(self, category: str, tag: str) -> None:
        self.evidence.setdefault(category, set()).add(tag)


def bbox_from_center(x: float, y: float, w: float, h: float, label: str, kind: str) -> BBox:
    return BBox(x - w / 2, y - h / 2, x + w / 2, y + h / 2, label, kind)


def text_bbox(text: str, x: float, y: float, height: float, label: str) -> BBox:
    return BBox(x, y, x + max(1, len(text)) * height * 0.58, y + height, label, "text")
