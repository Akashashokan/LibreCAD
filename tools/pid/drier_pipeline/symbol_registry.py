from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set

import ezdxf
from ezdxf.addons.importer import Importer


class MissingSymbolError(RuntimeError):
    pass


@dataclass
class SymbolRegistry:
    aliases: Dict[str, List[str]]
    dev_mode: bool = False

    def candidates(self, key: str) -> List[str]:
        if key in self.aliases:
            return self.aliases[key]
        if self.dev_mode:
            return ["0_field-mounted-discrete-instrument"]
        raise MissingSymbolError(f"Missing symbol mapping for '{key}'")

    def resolve(self, key: str, block_dirs: Iterable[Path]) -> str:
        for name in self.candidates(key):
            if self.find_block_path(name, block_dirs) is not None:
                return name
        if self.dev_mode:
            return self.candidates("field_instrument")[0]
        raise MissingSymbolError(f"None of symbol aliases found for '{key}': {self.candidates(key)}")

    def find_block_path(self, block_name: str, block_dirs: Iterable[Path]) -> Path | None:
        target = normalize(block_name)
        for root in block_dirs:
            if not root.exists():
                continue
            for entry in root.rglob("*.dxf"):
                if normalize(entry.stem) == target:
                    return entry
        return None

    def ensure_blocks_available(self, block_dirs: Iterable[Path]) -> None:
        for key in self.aliases:
            self.resolve(key, block_dirs)


def normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def collect_referenced_layers(source: ezdxf.EzDxf) -> Set[str]:
    seen_blocks: Set[str] = set()
    layer_names: Set[str] = set()

    def visit_entities(entities) -> None:
        for entity in entities:
            layer_name = entity.dxf.get("layer", "0")
            layer_names.add(layer_name)
            if entity.dxftype() != "INSERT":
                continue
            block_name = entity.dxf.name
            if block_name in seen_blocks or block_name not in source.blocks:
                continue
            seen_blocks.add(block_name)
            visit_entities(source.blocks.get(block_name))

    visit_entities(source.modelspace())
    return layer_names


def import_block_from_file(doc: ezdxf.EzDxf, path: Path, target_name: str) -> None:
    source = ezdxf.readfile(path)
    if target_name in doc.blocks:
        return
    for layer_name in collect_referenced_layers(source):
        if layer_name not in source.layers:
            source.layers.add(name=layer_name, color=7)
        if layer_name not in doc.layers:
            doc.layers.add(name=layer_name, color=7)
    newb = doc.blocks.new(target_name)
    importer = Importer(source, doc)
    importer.import_entities(source.modelspace(), newb)
    importer.finalize()


def import_required_block(doc: ezdxf.EzDxf, block_name: str, block_dirs: Iterable[Path], registry: SymbolRegistry) -> str:
    found = registry.find_block_path(block_name, block_dirs)
    if found is None:
        raise MissingSymbolError(f"Block file for '{block_name}' not found in {list(block_dirs)}")
    import_block_from_file(doc, found, block_name)
    return block_name


def default_registry(dev_mode: bool = False) -> SymbolRegistry:
    return SymbolRegistry(
        aliases={
            "molecular_sieve_drier": ["10_vessel-dished-ends", "vessel-dished-ends"],
            "switch_valve": ["0_general-valve-no", "8_gate-valve-no", "gate-valve-no"],
            "control_valve": ["22_control-valve", "control-valve"],
            "heater": ["32_heat-exchanger-tema-type-bem", "21_heat-exchanger-general-1"],
            "cooler": ["32_heat-exchanger-tema-type-bem", "21_heat-exchanger-general-1"],
            "ko_drum": ["9_vessel-vertical", "vessel-vertical"],
            "dust_filter": ["10_strainer", "strainer"],
            "field_instrument": ["3_field-discrete-instrument", "0_field-mounted-discrete-instrument"],
            "shared_control": ["1_aux-accessible-dcs", "shared-display-shared-control"],
            "offpage": ["17_off-page-connector", "18_off-page-connector"],
        },
        dev_mode=dev_mode,
    )
