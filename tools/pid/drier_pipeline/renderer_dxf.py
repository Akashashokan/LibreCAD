from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import ezdxf
import networkx as nx

from .engineering_model import PIDModel
from .symbol_registry import SymbolRegistry, import_required_block


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


def render_to_dxf(
    model: PIDModel,
    graph: nx.DiGraph,
    positions: Dict[str, Tuple[float, float]],
    route_table: Dict[Tuple[str, str], List[Tuple[float, float]]],
    registry: SymbolRegistry,
    block_dirs: List[Path],
    output: Path,
) -> None:
    doc = ezdxf.new("R2010")
    for layer in LAYERS:
        if layer not in doc.layers:
            doc.layers.add(layer)
    msp = doc.modelspace()

    msp.add_lwpolyline([(10, 10), (1179, 10), (1179, 831), (10, 831), (10, 10)], dxfattribs={"layer": "BORDER"})

    resolved = {
        "molecular_sieve_drier": registry.resolve("molecular_sieve_drier", block_dirs),
        "switch_valve": registry.resolve("switch_valve", block_dirs),
        "control_valve": registry.resolve("control_valve", block_dirs),
        "heater": registry.resolve("heater", block_dirs),
        "cooler": registry.resolve("cooler", block_dirs),
        "ko_drum": registry.resolve("ko_drum", block_dirs),
        "dust_filter": registry.resolve("dust_filter", block_dirs),
        "field_instrument": registry.resolve("field_instrument", block_dirs),
        "offpage": registry.resolve("offpage", block_dirs),
    }
    for block in resolved.values():
        import_required_block(doc, block, block_dirs, registry)

    for node, data in graph.nodes(data=True):
        if node not in positions:
            continue
        x, y = positions[node]
        ntype = data.get("node_type")

        if ntype == "equipment":
            block = resolved["molecular_sieve_drier"] if node.startswith("DR-") else resolved["heater"]
            if node.startswith("E-"):
                block = resolved["cooler"]
            if node.startswith("V-"):
                block = resolved["ko_drum"]
            if node.startswith("F-"):
                block = resolved["dust_filter"]
            msp.add_blockref(block, (x, y), dxfattribs={"layer": "EQUIPMENT"})
            msp.add_text(node, dxfattribs={"height": 3.0, "layer": "TEXT"}).set_placement((x - 20, y + 32))
        elif ntype == "valve":
            block = resolved["control_valve"] if node.startswith("FCV") else resolved["switch_valve"]
            msp.add_blockref(block, (x, y), dxfattribs={"layer": "PROCESS_MAJOR"})
            msp.add_text(node, dxfattribs={"height": 2.5, "layer": "TEXT"}).set_placement((x - 15, y + 8))
        elif ntype in {"instrument", "analyzer"}:
            msp.add_blockref(resolved["field_instrument"], (x, y), dxfattribs={"layer": "INSTRUMENT"})
            msp.add_text(node, dxfattribs={"height": 2.5, "layer": "TEXT"}).set_placement((x - 20, y - 12))
        elif ntype == "offpage":
            msp.add_blockref(resolved["offpage"], (x, y), dxfattribs={"layer": "PROCESS_MINOR"})
            msp.add_text(node, dxfattribs={"height": 2.5, "layer": "TEXT"}).set_placement((x - 28, y + 8))

    for src, dst, data in graph.edges(data=True):
        if data.get("edge_type") == "ownership":
            continue
        layer = "SIGNAL_ELECTRIC" if data.get("edge_type") == "signal" else "PROCESS_MAJOR"
        points = route_table.get((src, dst))
        if points is None:
            if src not in positions or dst not in positions:
                continue
            points = [positions[src], positions[dst]]
        msp.add_lwpolyline(points, dxfattribs={"layer": layer})
        if data.get("edge_type") == "piping":
            x1, y1 = points[0]
            x2, y2 = points[-1]
            msp.add_text(data["tag"], dxfattribs={"height": 2.3, "layer": "TEXT"}).set_placement(((x1 + x2) / 2, (y1 + y2) / 2 + 4))

    msp.add_text(f"{model.unit} {model.service} P&ID", dxfattribs={"height": 5, "layer": "TEXT"}).set_placement((40, 800))
    msp.add_text("Bypass XV-30190 normally closed, car-sealed", dxfattribs={"height": 2.5, "layer": "TEXT"}).set_placement((40, 70))

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output)
