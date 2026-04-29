from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


class MissingSymbolError(RuntimeError):
    pass


@dataclass
class SymbolRegistry:
    symbols: Dict[str, str]
    dev_mode: bool = False

    def resolve(self, key: str) -> str:
        if key in self.symbols:
            return self.symbols[key]
        if self.dev_mode:
            print(f"[warn] missing symbol mapping for {key}; using field-mounted-discrete-instrument")
            return "field-mounted-discrete-instrument"
        raise MissingSymbolError(f"Missing symbol mapping for '{key}'")

    def ensure_blocks_available(self, block_dirs: Iterable[Path]) -> None:
        all_dxf = []
        for d in block_dirs:
            if d.exists():
                all_dxf.extend(d.rglob("*.dxf"))
        names = {p.stem.lower() for p in all_dxf}
        for key, blk in self.symbols.items():
            if blk.lower() not in names and not self.dev_mode:
                raise MissingSymbolError(f"Block '{blk}' for '{key}' not found in block library")


def default_registry(dev_mode: bool = False) -> SymbolRegistry:
    return SymbolRegistry(
        symbols={
            "molecular_sieve_drier": "vessel-dished-ends",
            "switch_valve": "VALVE_MANUAL",
            "control_valve": "CONTROL_VALVE",
            "heater": "heat-exchanger-steam-boiler",
            "cooler": "heat-exchanger-tema-type-bem",
            "ko_drum": "vessel-dished-ends",
            "field_instrument": "field-mounted-discrete-instrument",
            "shared_control": "shared-display-shared-control",
            "flow_arrow": "FLOW_ARROW",
            "offpage": "FLOW_ARROW",
        },
        dev_mode=dev_mode,
    )
