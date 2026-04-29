from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import ezdxf
import networkx as nx

from .engineering_model import PIDModel
from .symbol_registry import SymbolRegistry


LAYERS = [
    "PROCESS_MAJOR",
    "PROCESS_MINOR",
    "REGEN",
    "VENT_FLARE",
    "DRAIN",
    "INSTRUMENT",
    "SIGNAL_PNEUMATIC",
    "SIGNAL_ELECTRIC",
    "TEXT",
    "EQUIPMENT",
    "BORDER",
]


def render_to_dxf(model: PIDModel, graph: nx.DiGraph, positions: Dict[str, Tuple[float, float]], registry: SymbolRegistry, output: Path) -> None:
    doc = ezdxf.new("R2010")
    for layer in LAYERS:
        if layer not in doc.layers:
            doc.layers.add(layer)
    msp = doc.modelspace()

    # border
    msp.add_lwpolyline([(10, 10), (1179, 10), (1179, 831), (10, 831), (10, 10)], dxfattribs={"layer": "BORDER"})

    for node, data in graph.nodes(data=True):
        if node not in positions:
            continue
        x, y = positions[node]
        ntype = data.get("node_type")

        if ntype == "equipment":
            block = registry.resolve("molecular_sieve_drier") if node.startswith("DR-") else registry.resolve("heater")
            if node.startswith("E-"):
                block = registry.resolve("cooler")
            if node.startswith("V-"):
                block = registry.resolve("ko_drum")
            if node.startswith("F-"):
                block = "filter-general"
            msp.add_blockref(block, (x, y), dxfattribs={"layer": "EQUIPMENT"})
            msp.add_text(node, dxfattribs={"height": 3.0, "layer": "TEXT"}).set_placement((x - 20, y + 32))
        elif ntype in {"instrument", "analyzer"}:
            msp.add_blockref(registry.resolve("field_instrument"), (x, y), dxfattribs={"layer": "INSTRUMENT"})
            msp.add_text(node, dxfattribs={"height": 2.5, "layer": "TEXT"}).set_placement((x - 20, y - 12))
        elif ntype == "offpage":
            msp.add_blockref(registry.resolve("offpage"), (x, y), dxfattribs={"layer": "PROCESS_MINOR"})
            msp.add_text(node, dxfattribs={"height": 2.5, "layer": "TEXT"}).set_placement((x - 28, y + 8))

    for src, dst, data in graph.edges(data=True):
        if src not in positions or dst not in positions:
            continue
        layer = "SIGNAL_ELECTRIC" if data.get("edge_type") == "signal" else "PROCESS_MAJOR"
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})
        if data.get("edge_type") == "piping":
            msp.add_text(data["tag"], dxfattribs={"height": 2.3, "layer": "TEXT"}).set_placement(((x1 + x2) / 2, (y1 + y2) / 2 + 4))

    msp.add_text("U-300 PROCESS GAS DEHYDRATION P&ID", dxfattribs={"height": 5, "layer": "TEXT"}).set_placement((40, 800))
    msp.add_text("Bypass XV-30190 normally closed, car-sealed", dxfattribs={"height": 2.5, "layer": "TEXT"}).set_placement((40, 70))

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output)
