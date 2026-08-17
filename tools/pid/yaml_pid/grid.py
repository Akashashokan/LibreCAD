from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

Point = tuple[float, float]

GRID = 5.0


@dataclass(frozen=True)
class GridPoint:
    x: float
    y: float

    @classmethod
    def from_point(cls, point: Point) -> "GridPoint":
        return cls(point[0], point[1])

    def snap(self) -> Point:
        return snap_value(self.x), snap_value(self.y)


def snap_value(value: float, grid: float = GRID) -> float:
    snapped = round(float(value) / grid) * grid
    return int(snapped) if snapped.is_integer() else snapped


def snap_point(point: Point) -> Point:
    return GridPoint(point[0], point[1]).snap() if not isinstance(point, GridPoint) else point.snap()


def snap_points(points: Iterable[Point]) -> list[Point]:
    return [snap_point(point) for point in points]
