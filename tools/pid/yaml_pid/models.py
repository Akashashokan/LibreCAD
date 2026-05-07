from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Point = tuple[float, float]


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class PortSpec:
    name: str
    offset: Point


@dataclass(frozen=True)
class NozzleSpec:
    name: str
    service: str
    wall_point: Point
    stub_end: Point
    flange_point: Point
    connection_point: Point
    side: str = ""


@dataclass(frozen=True)
class PackageConfig:
    package_type: str
    service: str
    area_code: str
    template: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class SheetLayoutZones:
    raw: dict[str, Any]


@dataclass(frozen=True)
class SymbolBlock:
    key: str
    object_types: list[str]
    candidates: list[str]


@dataclass(frozen=True)
class BlockGeometry:
    key: str
    block: str
    width: float
    height: float
    ports: dict[str, PortSpec] = field(default_factory=dict)
    nozzles: dict[str, NozzleSpec] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RequiredEquipment:
    equipment: list[str]
    valves: list[str]
    instruments: list[str]
    paths: list[str]
    raw: dict[str, Any]


@dataclass(frozen=True)
class EquipmentPlacement:
    tag: str
    type: str
    x: float
    y: float
    orientation: str = "horizontal"
    block_key: str = ""
    service: str = ""


@dataclass(frozen=True)
class NozzlePlacement:
    equipment_tag: str
    nozzles: dict[str, NozzleSpec]


@dataclass(frozen=True)
class ValvePlacement:
    tag: str
    type: str
    service: str
    pipe_segment: str
    orientation: str
    normal_position: str = ""
    fail_position: str = ""
    controller: str = ""


@dataclass(frozen=True)
class ProcessRoute:
    name: str
    service: str
    from_ref: Any
    to_ref: Any
    labels: list[dict[str, Any]]
    valves: list[str]
    instruments: list[str]
    raw: dict[str, Any]


@dataclass(frozen=True)
class InstrumentPlacement:
    tag: str
    type: str
    service: str
    zone: str
    location: str
    connect_to: Any = None
    input_from: Any = None
    output_to: Any = None
    source: Any = None


@dataclass(frozen=True)
class SignalRoute:
    name: str
    source: Any
    target: Any
    targets: list[Any]
    signal_type: str
    trunk: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class LabelAnnotationRule:
    raw: dict[str, Any]


@dataclass(frozen=True)
class OffPageConnector:
    tag: str
    service: str
    drawing_reference: str
    x: float
    y: float
    direction: str


@dataclass(frozen=True)
class TitleBlockConfig:
    project: str
    drawing_no: str
    rev: str
    unit: str
    service: str
    status: str


@dataclass(frozen=True)
class LayerStyleConfig:
    name: str
    color: int
    linetype: str = "CONTINUOUS"


@dataclass
class PidConfig:
    config_dir: Path
    package: PackageConfig
    sheet_layout_zones: SheetLayoutZones
    symbol_blocks: dict[str, SymbolBlock]
    block_geometry: dict[str, BlockGeometry]
    required: RequiredEquipment
    equipment: list[EquipmentPlacement]
    nozzles: dict[str, NozzlePlacement]
    valves: list[ValvePlacement]
    routes: list[ProcessRoute]
    instruments: list[InstrumentPlacement]
    signals: list[SignalRoute]
    labels: LabelAnnotationRule
    warnings: list[str] = field(default_factory=list)

