from __future__ import annotations

from .models import BlockGeometry, NozzlePlacement, NozzleSpec
from .grid import snap_point
from .scene import SceneRegistry

Point = tuple[float, float]


def absolute(point: Point, origin: Point) -> Point:
    return snap_point((origin[0] + point[0], origin[1] + point[1]))


def register_geometry_ports(registry: SceneRegistry, tag: str, origin: Point, geometry: BlockGeometry) -> None:
    for name, port in geometry.ports.items():
        registry.add_port(f"{tag}.{name}", absolute(port.offset, origin), f"{tag}:port")


def register_nozzle_ports(registry: SceneRegistry, placement: NozzlePlacement, origin: Point) -> None:
    for name, noz in placement.nozzles.items():
        conn = absolute(noz.connection_point, origin)
        axis = _nozzle_axis(noz)
        registry.add_port(f"{placement.equipment_tag}.{name}.wall_point", absolute(noz.wall_point, origin), "nozzle_wall")
        registry.add_port(f"{placement.equipment_tag}.{name}.stub_end", absolute(noz.stub_end, origin), "nozzle_stub")
        registry.add_port(f"{placement.equipment_tag}.{name}.connection_point", conn, "nozzle_connection")
        registry.add_port(f"{placement.equipment_tag}.{name}.connection", conn, "nozzle_connection")
        registry.nozzle_axes[conn] = axis


def abs_nozzle(noz: NozzleSpec, origin: Point) -> tuple[Point, Point, Point, Point]:
    return absolute(noz.wall_point, origin), absolute(noz.stub_end, origin), absolute(noz.flange_point, origin), absolute(noz.connection_point, origin)


def resolve_port(registry: SceneRegistry, ref: object) -> Point | None:
    if ref is None:
        return None
    if isinstance(ref, str):
        key = ref.replace(".connection_point", ".connection_point").replace(".continuation", ".continuation")
        return registry.ports.get(key)
    return None


def _nozzle_axis(noz: NozzleSpec) -> str:
    dx = noz.connection_point[0] - noz.wall_point[0]
    dy = noz.connection_point[1] - noz.wall_point[1]
    return "horizontal" if abs(dx) >= abs(dy) else "vertical"
