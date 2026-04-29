from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Nozzle:
    tag: str
    service: str


@dataclass
class Equipment:
    tag: str
    kind: str
    design_pressure: Optional[str] = None
    design_temperature: Optional[str] = None
    nozzles: Dict[str, Nozzle] = field(default_factory=dict)


@dataclass
class OffPageConnector:
    tag: str
    direction: str
    drawing_ref: str


@dataclass
class Valve:
    tag: str
    kind: str
    actuator: str
    fail_position: str
    sequence_ref: str


@dataclass
class Instrument:
    tag: str
    kind: str
    location: str


@dataclass
class Analyzer:
    tag: str
    controller_tag: str
    sample_tap: str
    has_sample_conditioner: bool
    vent_destination: str
    drain_destination: str


@dataclass
class Line:
    tag: str
    src: str
    dst: str
    size: str
    service: str
    spec: str
    flow_direction: str


@dataclass
class PIDModel:
    unit: str
    service: str
    equipment: List[Equipment]
    offpages: List[OffPageConnector]
    valves: List[Valve]
    instruments: List[Instrument]
    analyzers: List[Analyzer]
    lines: List[Line]


def load_model_from_dict(data: dict) -> PIDModel:
    equipment = [
        Equipment(
            tag=e["tag"],
            kind=e["type"],
            design_pressure=e.get("design_pressure"),
            design_temperature=e.get("design_temperature"),
            nozzles={k: Nozzle(tag=f"{e['tag']}.{k}", service=v) for k, v in e.get("nozzles", {}).items()},
        )
        for e in data.get("equipment", [])
    ]
    offpages = [OffPageConnector(**o) for o in data.get("offpages", [])]
    valves = [Valve(**v) for v in data.get("valves", [])]
    instruments = [Instrument(**i) for i in data.get("instruments", [])]
    analyzers = [Analyzer(**a) for a in data.get("analyzers", [])]
    lines = [Line(**l) for l in data.get("lines", [])]
    return PIDModel(
        unit=data["unit"],
        service=data["service"],
        equipment=equipment,
        offpages=offpages,
        valves=valves,
        instruments=instruments,
        analyzers=analyzers,
        lines=lines,
    )
