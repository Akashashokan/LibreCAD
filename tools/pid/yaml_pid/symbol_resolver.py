from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import ezdxf

from .models import ConfigError, PidConfig


@dataclass
class SymbolResolver:
    config: PidConfig
    block_dir: Path
    style: str
    resolved: dict[str, tuple[Path, str | None]] = field(default_factory=dict)
    imported_blocks: dict[str, str] = field(default_factory=dict)
    block_extents: dict[str, tuple[float, float]] = field(default_factory=dict)
    fallback_warnings: list[str] = field(default_factory=list)
    failed_imports: list[str] = field(default_factory=list)
    missing_blocks: list[str] = field(default_factory=list)

    def resolve_all(self) -> None:
        for key in sorted(self.config.symbol_blocks):
            if key in {"signal_electric", "signal_pneumatic", "impulse_line", "flow_arrow"}:
                continue
            self.resolve(key)

    def resolve(self, symbol_key: str) -> Path | None:
        if symbol_key in self.resolved:
            return self.resolved[symbol_key][0]
        symbol = self.config.symbol_blocks.get(symbol_key)
        if symbol is None:
            if self.style == "final":
                raise ConfigError(f"Missing symbol mapping for {symbol_key}")
            self.fallback_warnings.append(f"No symbol mapping for {symbol_key}; debug primitive fallback used")
            return None
        for candidate in symbol.candidates:
            candidate_path, block_name = _split_candidate(candidate)
            path = self.block_dir / candidate_path
            if path.exists():
                self.resolved[symbol_key] = (path, block_name)
                return path
        message = f"Missing required block for {symbol_key}: expected {symbol.candidates[0]}"
        if self.style == "final":
            raise ConfigError(message)
        self.missing_blocks.append(message)
        self.fallback_warnings.append(message + "; debug primitive fallback used")
        return None

    def import_required_blocks(self, doc: ezdxf.EzDxfDocument) -> None:
        for key, (path, source_block_name) in sorted(self.resolved.items()):
            name = _block_name(key)
            if name in doc.blocks:
                self.imported_blocks[key] = name
                continue
            try:
                src = ezdxf.readfile(path)
                source_layout = _source_layout(src, source_block_name)
                center, size = _layout_center_and_size(source_layout)
                target = doc.blocks.new(name=name)
                for entity in source_layout:
                    copied = entity.copy()
                    try:
                        copied.translate(-center[0], -center[1], 0)
                    except Exception:
                        pass
                    target.add_foreign_entity(copied)
                self.imported_blocks[key] = name
                self.block_extents[key] = size
            except Exception as exc:
                if self.style == "final":
                    raise ConfigError(f"Failed to import block for {key} from {path}: {exc}") from exc
                self.failed_imports.append(f"{key}: {path} ({exc})")
                self.fallback_warnings.append(f"Could not import {path}; debug primitive fallback used: {exc}")

    def block_name(self, symbol_key: str) -> str | None:
        return self.imported_blocks.get(symbol_key)


def _block_name(symbol_key: str) -> str:
    return "YAML_PID_" + "".join(ch if ch.isalnum() else "_" for ch in symbol_key).upper()


def _split_candidate(candidate: str) -> tuple[str, str | None]:
    if "::" not in candidate:
        return candidate, None
    path, block_name = candidate.split("::", 1)
    return path, block_name


def _source_layout(doc: ezdxf.EzDxfDocument, block_name: str | None):
    if block_name:
        if block_name not in doc.blocks:
            raise ConfigError(f"Block {block_name} not found in {doc.filename}")
        return doc.blocks[block_name]
    return doc.modelspace()


def _layout_center_and_size(layout) -> tuple[tuple[float, float], tuple[float, float]]:
    xs: list[float] = []
    ys: list[float] = []
    for entity in layout:
        for x, y in _entity_points(entity):
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return (0.0, 0.0), (1.0, 1.0)
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    return ((xmin + xmax) / 2, (ymin + ymax) / 2), (max(xmax - xmin, 1.0), max(ymax - ymin, 1.0))


def _entity_points(entity) -> list[tuple[float, float]]:
    kind = entity.dxftype()
    if kind == "LINE":
        return [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
    if kind in {"CIRCLE", "ARC"}:
        center = entity.dxf.center
        radius = float(entity.dxf.radius)
        return [(center.x - radius, center.y - radius), (center.x + radius, center.y + radius)]
    if kind == "ELLIPSE":
        center = entity.dxf.center
        major = entity.dxf.major_axis
        ratio = float(entity.dxf.ratio)
        rx = (major.x**2 + major.y**2) ** 0.5
        ry = rx * ratio
        return [(center.x - rx, center.y - ry), (center.x + rx, center.y + ry)]
    if kind == "LWPOLYLINE":
        return [(point[0], point[1]) for point in entity.get_points()]
    if kind == "POLYLINE":
        return [(vertex.dxf.location.x, vertex.dxf.location.y) for vertex in entity.vertices]
    if kind == "INSERT":
        return [(entity.dxf.insert.x, entity.dxf.insert.y)]
    if kind in {"TEXT", "MTEXT"}:
        return [(entity.dxf.insert.x, entity.dxf.insert.y)]
    return []
