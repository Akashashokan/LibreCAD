from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import (
    BlockGeometry,
    ConfigError,
    EquipmentPlacement,
    InstrumentPlacement,
    NozzlePlacement,
    NozzleSpec,
    PackageConfig,
    PidConfig,
    PortSpec,
    ProcessRoute,
    RequiredEquipment,
    SheetLayoutZones,
    SignalRoute,
    SymbolBlock,
    ValvePlacement,
    LabelAnnotationRule,
)

REQUIRED_FILES = [
    "package.yaml",
    "sheet_layout_zones.yaml",
    "symbol_blocks.yaml",
    "block_geometry.yaml",
    "required_equipment.yaml",
    "equipment_placement_order.yaml",
    "nozzle_placement_order.yaml",
    "valve_placements.yaml",
    "route_main_process_line.yaml",
    "instrument_placements.yaml",
    "signal_routing.yaml",
    "labels_and_annotations.yaml",
]

TYPO_COMPAT = {
    "nozzle_placement_order.yaml": "nozzle_palcement_order.yaml",
    "instrument_placements.yaml": "instrument_palcements.yaml",
}


def load_pid_config(config_dir: Path) -> PidConfig:
    warnings: list[str] = []
    raw: dict[str, Any] = {}
    for filename in REQUIRED_FILES:
        path = config_dir / filename
        if not path.exists() and filename in TYPO_COMPAT:
            typo = config_dir / TYPO_COMPAT[filename]
            if typo.exists():
                path = typo
                warnings.append(f"Deprecated YAML filename used: {typo.name}; rename to {filename}")
        if not path.exists():
            raise ConfigError(f"Missing required YAML file: {path}")
        raw[filename] = _load_yaml(path)

    package = _parse_package(raw["package.yaml"])
    symbols = _parse_symbols(raw["symbol_blocks.yaml"])
    geometry = _parse_geometry(raw["block_geometry.yaml"])
    equipment = _parse_equipment(raw["equipment_placement_order.yaml"], symbols, geometry)
    nozzles = _parse_nozzles(raw["nozzle_placement_order.yaml"])
    valves = _parse_valves(raw["valve_placements.yaml"])
    routes = _parse_routes(raw["route_main_process_line.yaml"])
    instruments = _parse_instruments(raw["instrument_placements.yaml"])
    signals = _parse_signals(raw["signal_routing.yaml"])
    required = _parse_required(raw["required_equipment.yaml"])
    return PidConfig(
        config_dir=config_dir,
        package=package,
        sheet_layout_zones=SheetLayoutZones(raw["sheet_layout_zones.yaml"]),
        symbol_blocks=symbols,
        block_geometry=geometry,
        required=required,
        equipment=equipment,
        nozzles=nozzles,
        valves=valves,
        routes=routes,
        instruments=instruments,
        signals=signals,
        labels=LabelAnnotationRule(raw["labels_and_annotations.yaml"]),
        warnings=warnings,
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"YAML file must contain a mapping: {path}")
    return data


def _parse_package(data: dict[str, Any]) -> PackageConfig:
    for key in ["package_type", "service", "area_code", "template"]:
        if key not in data:
            raise ConfigError(f"package.yaml missing required key: {key}")
    if "deethanizer" not in str(data["package_type"]):
        raise ConfigError(f"package.yaml package_type must be deethanizer, got {data['package_type']!r}")
    return PackageConfig(str(data["package_type"]), str(data["service"]), str(data["area_code"]), str(data["template"]), data)


def _parse_symbols(data: dict[str, Any]) -> dict[str, SymbolBlock]:
    root = data.get("symbols")
    if not isinstance(root, dict):
        raise ConfigError("symbol_blocks.yaml missing symbols mapping")
    symbols: dict[str, SymbolBlock] = {}
    for key, value in root.items():
        candidates = value.get("candidates", [])
        if not candidates:
            raise ConfigError(f"symbol_blocks.yaml symbol {key} has no candidates")
        symbols[key] = SymbolBlock(key, list(value.get("object_types", [])), [str(c) for c in candidates])
    return symbols


def _parse_geometry(data: dict[str, Any]) -> dict[str, BlockGeometry]:
    root = data.get("block_geometry")
    if not isinstance(root, dict):
        raise ConfigError("block_geometry.yaml missing block_geometry mapping")
    out: dict[str, BlockGeometry] = {}
    for key, value in root.items():
        size = value.get("size")
        if not isinstance(size, dict) or "width" not in size or "height" not in size:
            raise ConfigError(f"block_geometry.{key} missing size.width/height")
        ports = {name: PortSpec(name, _point(pt, f"block_geometry.{key}.ports.{name}")) for name, pt in value.get("ports", {}).items()}
        nozzles = {name: _nozzle(name, spec, f"block_geometry.{key}.nozzles.{name}") for name, spec in value.get("nozzles", {}).items()}
        out[key] = BlockGeometry(key, str(value.get("block", key)), float(size["width"]), float(size["height"]), ports, nozzles, value)
    return out


def _parse_equipment(data: dict[str, Any], symbols: dict[str, SymbolBlock], geometry: dict[str, BlockGeometry]) -> list[EquipmentPlacement]:
    root = data.get("equipment_placement_order")
    if not isinstance(root, list):
        raise ConfigError("equipment_placement_order.yaml missing equipment_placement_order list")
    anchors = {
        "T-501": (520, 430), "E-501": (700, 315), "E-502": (650, 650), "V-501": (840, 610),
        "P-501A": (820, 495), "P-501B": (820, 450), "E-503": (300, 400),
        "P-502A": (470, 205), "P-502B": (470, 160), "PSV-501A": (430, 660), "PSV-501B": (465, 660), "PSV-502": (820, 690),
    }
    out: list[EquipmentPlacement] = []
    for row in sorted(root, key=lambda r: r.get("step", 0)):
        tag = str(row.get("equipment", ""))
        if not tag:
            raise ConfigError("equipment_placement_order entry missing equipment tag")
        x, y = anchors.get(tag, (100, 100))
        key = _symbol_key_for_tag(tag, symbols)
        if key and key not in geometry and key not in {"relief_valve"}:
            raise ConfigError(f"No block_geometry entry for equipment {tag} symbol {key}")
        out.append(EquipmentPlacement(tag, key or "equipment", x, y, block_key=key, service=str(row.get("description", ""))))
    return out


def _parse_nozzles(data: dict[str, Any]) -> dict[str, NozzlePlacement]:
    root = data.get("nozzle_placement")
    if not isinstance(root, dict):
        raise ConfigError("nozzle_placement_order.yaml missing nozzle_placement mapping")
    out: dict[str, NozzlePlacement] = {}
    for key, spec in root.items():
        if key == "sequence" or not isinstance(spec, dict) or "tag" not in spec:
            continue
        tag = str(spec["tag"])
        out[tag] = NozzlePlacement(tag, {name: _nozzle(name, noz, f"nozzle_placement.{key}.{name}") for name, noz in spec.get("nozzles", {}).items()})
    pumps = root.get("pumps", {})
    if isinstance(pumps, dict):
        for tag, spec in pumps.items():
            out[str(tag)] = NozzlePlacement(str(tag), {name: _nozzle(name, noz, f"nozzle_placement.pumps.{tag}.{name}") for name, noz in spec.get("nozzles", {}).items()})
    return out


def _parse_valves(data: dict[str, Any]) -> list[ValvePlacement]:
    root = data.get("valve_placements")
    if not isinstance(root, dict):
        raise ConfigError("valve_placements.yaml missing valve_placements mapping")
    out: list[ValvePlacement] = []
    for group, rows in root.items():
        if group == "insertion_rule":
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            for key in ["tag", "type", "pipe_segment", "orientation"]:
                if key not in row:
                    raise ConfigError(f"valve_placements.{group} entry missing {key}")
            out.append(ValvePlacement(str(row["tag"]), str(row["type"]), str(row.get("service", "")), str(row["pipe_segment"]), str(row["orientation"]), str(row.get("station", "")), str(row.get("normal_position", "")), str(row.get("fail_position", "")), str(row.get("controller", ""))))
    return out


def _parse_routes(data: dict[str, Any]) -> list[ProcessRoute]:
    root = data.get("route_main_process_lines", {}).get("routes")
    if not isinstance(root, dict):
        raise ConfigError("route_main_process_line.yaml missing route_main_process_lines.routes")
    out: list[ProcessRoute] = []
    for name, row in root.items():
        labels = row.get("labels", [])
        if not labels:
            raise ConfigError(f"route {name} missing labels/line_number")
        out.append(ProcessRoute(str(name), str(row.get("service", "")), row.get("from"), row.get("to"), list(labels), list(row.get("valves", [])), list(row.get("instruments", [])), row))
    return out


def _parse_instruments(data: dict[str, Any]) -> list[InstrumentPlacement]:
    root = data.get("instrument_placements", {}).get("zones")
    if not isinstance(root, dict):
        raise ConfigError("instrument_placements.yaml missing instrument_placements.zones")
    out: list[InstrumentPlacement] = []
    seen: set[str] = set()
    for zone, zdata in root.items():
        for row in zdata.get("instruments", []):
            tag = str(row.get("tag", ""))
            if not tag:
                raise ConfigError(f"instrument zone {zone} contains entry without tag")
            if tag in seen:
                continue
            seen.add(tag)
            typ = str(row.get("type", ""))
            location = _instrument_location(typ)
            out.append(InstrumentPlacement(tag, typ, str(row.get("service", "")), str(zone), location, row.get("connect_to"), row.get("input_from"), row.get("output_to"), row.get("source")))
    return out


def _parse_signals(data: dict[str, Any]) -> list[SignalRoute]:
    root = data.get("signal_routing", {}).get("routes")
    if not isinstance(root, dict):
        raise ConfigError("signal_routing.yaml missing signal_routing.routes")
    out: list[SignalRoute] = []
    for name, row in root.items():
        if "routes" in row:
            for idx, sub in enumerate(row["routes"], start=1):
                out.append(SignalRoute(f"{name}_{idx}", sub.get("source"), sub.get("target"), [], str(row.get("signal_type", "electric_signal")), str(row.get("trunk", "")), sub))
            continue
        if "sources" in row and "targets" in row:
            sources = list(row.get("sources", []))
            targets = list(row.get("targets", []))
            for idx, (source, target) in enumerate(zip(sources, targets), start=1):
                out.append(SignalRoute(f"{name}_{idx}", source, target, [], str(row.get("signal_type", "electric_signal")), str(row.get("trunk", "")), row))
            continue
        target = row.get("target")
        targets = list(row.get("targets", []))
        out.append(SignalRoute(str(name), row.get("source"), target, targets, str(row.get("signal_type", "electric_signal")), str(row.get("trunk", "")), row))
    return out


def _parse_required(data: dict[str, Any]) -> RequiredEquipment:
    return RequiredEquipment(
        [str(x) for x in data.get("required_equipment", [])],
        [str(x) for x in data.get("required_valves", [])],
        [str(x) for x in data.get("required_instruments", [])],
        [str(x) for x in data.get("required_process_paths", [])],
        data,
    )


def _point(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ConfigError(f"Malformed coordinate at {label}: expected [x, y]")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Malformed coordinate at {label}: {value}") from exc


def _nozzle(name: str, spec: dict[str, Any], label: str) -> NozzleSpec:
    if "connection_point" not in spec and "pipe_connection" in spec:
        spec = dict(spec)
        spec["connection_point"] = spec["pipe_connection"]
    for key in ["wall_point", "stub_end", "connection_point"]:
        if key not in spec:
            raise ConfigError(f"{label} missing {key}")
    return NozzleSpec(name, str(spec.get("service", "")), _point(spec["wall_point"], f"{label}.wall_point"), _point(spec["stub_end"], f"{label}.stub_end"), _point(spec.get("flange_point", spec["stub_end"]), f"{label}.flange_point"), _point(spec["connection_point"], f"{label}.connection_point"), str(spec.get("side", "")))


def _symbol_key_for_tag(tag: str, symbols: dict[str, SymbolBlock]) -> str:
    exact = {"T-501": "deethanizer_column", "E-501": "reboiler", "E-502": "overhead_condenser", "V-501": "reflux_drum", "E-503": "feed_bottoms_exchanger"}
    if tag in exact:
        return exact[tag]
    if tag.startswith("P-"):
        return "centrifugal_pump"
    if tag.startswith("PSV-"):
        return "relief_valve"
    for key, symbol in symbols.items():
        if tag in symbol.object_types:
            return key
    return ""


def _instrument_location(typ: str) -> str:
    if typ in {"dcs_controller", "dcs_alarm"}:
        return "dcs/shared_control"
    if typ in {"safety_switch", "valve_open_feedback", "valve_closed_feedback"}:
        return "plc/sis"
    if typ in {"field_instrument", "primary_element", "analyzer", "sample_system", "motor_status_feedback"}:
        return "field"
    return "field"
