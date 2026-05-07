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
    resolved: dict[str, Path] = field(default_factory=dict)
    imported_blocks: dict[str, str] = field(default_factory=dict)
    fallback_warnings: list[str] = field(default_factory=list)

    def resolve_all(self) -> None:
        for key in sorted(self.config.symbol_blocks):
            if key in {"signal_electric", "signal_pneumatic", "impulse_line", "flow_arrow", "nozzle"}:
                continue
            self.resolve(key)

    def resolve(self, symbol_key: str) -> Path | None:
        if symbol_key in self.resolved:
            return self.resolved[symbol_key]
        symbol = self.config.symbol_blocks.get(symbol_key)
        if symbol is None:
            if self.style == "final":
                raise ConfigError(f"Missing symbol mapping for {symbol_key}")
            self.fallback_warnings.append(f"No symbol mapping for {symbol_key}; debug primitive fallback used")
            return None
        for candidate in symbol.candidates:
            path = self.block_dir / candidate
            if path.exists():
                self.resolved[symbol_key] = path
                return path
        message = f"Missing required block for {symbol_key}: expected {symbol.candidates[0]}"
        if self.style == "final":
            raise ConfigError(message)
        self.fallback_warnings.append(message + "; debug primitive fallback used")
        return None

    def import_required_blocks(self, doc: ezdxf.EzDxfDocument) -> None:
        for key, path in sorted(self.resolved.items()):
            name = _block_name(key)
            if name in doc.blocks:
                self.imported_blocks[key] = name
                continue
            try:
                src = ezdxf.readfile(path)
                target = doc.blocks.new(name=name)
                for entity in src.modelspace():
                    target.add_foreign_entity(entity.copy())
                self.imported_blocks[key] = name
            except Exception as exc:
                if self.style == "final":
                    raise ConfigError(f"Failed to import block for {key} from {path}: {exc}") from exc
                self.fallback_warnings.append(f"Could not import {path}; debug primitive fallback used: {exc}")

    def block_name(self, symbol_key: str) -> str | None:
        return self.imported_blocks.get(symbol_key)


def _block_name(symbol_key: str) -> str:
    return "YAML_PID_" + "".join(ch if ch.isalnum() else "_" for ch in symbol_key).upper()
