from __future__ import annotations

from dataclasses import dataclass, field

from .grid import snap_point

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

    def expanded(self, clearance: float, *, label: str | None = None, kind: str | None = None) -> "BBox":
        return BBox(
            self.xmin - clearance,
            self.ymin - clearance,
            self.xmax + clearance,
            self.ymax + clearance,
            label or self.label,
            kind or self.kind,
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
    port_owners: dict[str, str] = field(default_factory=dict)
    equipment_bboxes: dict[str, BBox] = field(default_factory=dict)
    equipment_forbidden_zones: dict[str, BBox] = field(default_factory=dict)
    nozzle_axes: dict[Point, str] = field(default_factory=dict)
    nozzle_wall_points: dict[str, Point] = field(default_factory=dict)
    nozzle_sides: dict[str, str] = field(default_factory=dict)
    evidence: dict[str, set[str]] = field(default_factory=lambda: {"equipment": set(), "valve": set(), "instrument": set(), "line": set(), "line_label": set(), "offpage": set(), "document": set(), "nozzle": set()})
    route_endpoints: dict[str, tuple[Point, Point]] = field(default_factory=dict)
    route_endpoint_refs: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)
    signal_connections: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    unresolved_connections: list[str] = field(default_factory=list)
    render_errors: list[str] = field(default_factory=list)
    fallbacks: list[str] = field(default_factory=list)
    failed_block_imports: list[str] = field(default_factory=list)
    primitive_symbols_created: list[str] = field(default_factory=list)
    existing_blocks_used: list[str] = field(default_factory=list)
    valve_types: dict[str, str] = field(default_factory=dict)

    def add_item(self, kind: str, tag: str, layer: str, bbox: BBox) -> None:
        self.items.append(PlacedItem(kind, tag, layer, bbox))
        if kind == "equipment":
            self.equipment_bboxes[tag] = bbox
            self.equipment_forbidden_zones[tag] = bbox.expanded(4.0, kind="forbidden_zone")

    def add_line_segment(self, p1: Point, p2: Point, tag: str, layer: str, major: bool = True) -> None:
        self.line_segments.append(LineSegment(snap_point(p1), snap_point(p2), tag, layer, major))

    def add_port(self, ref: str, point: Point, kind: str) -> None:
        self.ports[ref] = snap_point(point)
        self.port_kinds[ref] = kind
        self.port_owners[ref] = ref.split(".", 1)[0]

    def port_ref_at(self, point: Point, allowed_kinds: set[str] | None = None, tol: float = 0.1) -> str | None:
        point = snap_point(point)
        for ref, port in self.ports.items():
            if abs(point[0] - port[0]) > tol or abs(point[1] - port[1]) > tol:
                continue
            kind = self.port_kinds.get(ref, "")
            if allowed_kinds is None or kind in allowed_kinds or any(kind.endswith(suffix) for suffix in allowed_kinds if suffix.startswith(":")):
                return ref
        return None

    def port_refs_at(self, point: Point, allowed_kinds: set[str] | None = None, tol: float = 0.1) -> list[str]:
        point = snap_point(point)
        refs: list[str] = []
        for ref, port in self.ports.items():
            if abs(point[0] - port[0]) > tol or abs(point[1] - port[1]) > tol:
                continue
            kind = self.port_kinds.get(ref, "")
            if allowed_kinds is None or kind in allowed_kinds or any(kind.endswith(suffix) for suffix in allowed_kinds if suffix.startswith(":")):
                refs.append(ref)
        return refs

    def mark(self, category: str, tag: str) -> None:
        self.evidence.setdefault(category, set()).add(tag)


def bbox_from_center(x: float, y: float, w: float, h: float, label: str, kind: str) -> BBox:
    return BBox(x - w / 2, y - h / 2, x + w / 2, y + h / 2, label, kind)


def text_bbox(text: str, x: float, y: float, height: float, label: str) -> BBox:
    return BBox(x, y, x + max(1, len(text)) * height * 0.58, y + height, label, "text")
