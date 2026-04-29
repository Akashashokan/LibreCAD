#!/usr/bin/env python3
"""Generate a realistic dual-drier process gas P&ID DXF.

The layout models two molecular sieve driers in parallel with:
- Inlet and outlet headers
- Individual drier isolation and switching valves
- Common bypass line
- Regeneration gas supply and return/vent headers
- Temperature, pressure, and analyzer instruments with ISA-like bubbles

The script prioritizes importing ISA/ISO/PIP blocks from repository block libraries,
and gracefully falls back to simple custom symbols when a requested block is not found.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Set, Tuple

import ezdxf
from ezdxf.addons.importer import Importer

A0_W_MM = 1189.0
A0_H_MM = 841.0
FRAME_MARGIN_MM = 8.0


@dataclass
class Placement:
    block: str
    x: float
    y: float
    scale: float = 1.0
    rotation: float = 0.0
    layer: str = "PIP_SYMBOLS"


@dataclass
class LayoutBuild:
    placements: List[Placement]
    lines: List[Tuple[Tuple[float, float], Tuple[float, float]]]
    texts: List[Tuple[str, float, float, float]]


def add_default_layers(doc: ezdxf.EzDxf) -> None:
    layers = {
        "BORDER": 7,
        "PIP_LINES": 7,
        "PIP_SYMBOLS": 7,
        "PIP_TEXT": 7,
        "PIP_DIM": 8,
        "PIP_INSTR": 3,
    }
    for name, color in layers.items():
        if name not in doc.layers:
            doc.layers.add(name=name, color=color)


def create_custom_block_definitions(doc: ezdxf.EzDxf) -> None:
    blocks = doc.blocks

    if "CUSTOM_INSTRUMENT_BUBBLE" not in blocks:
        b = blocks.new("CUSTOM_INSTRUMENT_BUBBLE")
        b.add_circle((0, 0), radius=5.0)

    if "CUSTOM_VALVE_MANUAL" not in blocks:
        b = blocks.new("CUSTOM_VALVE_MANUAL")
        b.add_lwpolyline([(-6, 0), (0, 4), (6, 0), (0, -4), (-6, 0)])

    if "CUSTOM_CONTROL_VALVE" not in blocks:
        b = blocks.new("CUSTOM_CONTROL_VALVE")
        b.add_lwpolyline([(-7, 0), (0, 4.5), (7, 0), (0, -4.5), (-7, 0)])
        b.add_line((-8, 6), (8, -6))

    if "CUSTOM_ARROW" not in blocks:
        b = blocks.new("CUSTOM_ARROW")
        b.add_line((-8, 0), (8, 0))
        b.add_lwpolyline([(8, 0), (4, 2.5), (4, -2.5), (8, 0)])

    if "CUSTOM_VERTICAL_VESSEL" not in blocks:
        b = blocks.new("CUSTOM_VERTICAL_VESSEL")
        body_w = 46
        body_h = 120
        r = body_w / 2
        b.add_line((-r, -body_h / 2), (-r, body_h / 2))
        b.add_line((r, -body_h / 2), (r, body_h / 2))
        b.add_arc((0, body_h / 2), r, 0, 180)
        b.add_arc((0, -body_h / 2), r, 180, 360)


def draw_a0_frame(msp: ezdxf.layouts.Modelspace) -> None:
    msp.add_lwpolyline(
        [
            (FRAME_MARGIN_MM, FRAME_MARGIN_MM),
            (A0_W_MM - FRAME_MARGIN_MM, FRAME_MARGIN_MM),
            (A0_W_MM - FRAME_MARGIN_MM, A0_H_MM - FRAME_MARGIN_MM),
            (FRAME_MARGIN_MM, A0_H_MM - FRAME_MARGIN_MM),
            (FRAME_MARGIN_MM, FRAME_MARGIN_MM),
        ],
        dxfattribs={"layer": "BORDER"},
    )


def maybe_find_library_block(block_name: str, block_dirs: Iterable[Path]) -> Path | None:
    def normalize(name: str) -> str:
        return "".join(ch for ch in name.lower() if ch.isalnum())

    target = normalize(block_name)
    for root in block_dirs:
        if not root.exists():
            continue
        for entry in root.rglob("*.dxf"):
            stem = normalize(entry.stem)
            if target == stem or target in stem:
                return entry
    return None


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


def build_layout() -> LayoutBuild:
    placements: List[Placement] = []
    lines: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    texts: List[Tuple[str, float, float, float]] = []

    # Calculated drawing envelope inside frame
    left = FRAME_MARGIN_MM + 55
    right = A0_W_MM - FRAME_MARGIN_MM - 55
    center_x = (left + right) / 2
    width = right - left

    # Process headers (carefully spaced for readability + realistic routing)
    y_inlet = 610.0
    y_outlet = 470.0
    y_regen_supply = 260.0
    y_regen_return = 165.0

    # Two parallel driers, symmetric around sheet center.
    vessel_pitch = 300.0
    drier1_x = center_x - vessel_pitch / 2
    drier2_x = center_x + vessel_pitch / 2
    vessel_center_y = 540.0

    # Vessel geometry assumption for nozzle tie-ins (for line dimensions)
    vessel_nozzle_left = 23.0
    vessel_nozzle_right = 23.0
    nozzle_top_offset = 35.0
    nozzle_bottom_offset = 35.0

    # Main headers
    lines.extend([
        ((left, y_inlet), (right, y_inlet)),
        ((left, y_outlet), (right, y_outlet)),
        ((left + 50, y_regen_supply), (right - 50, y_regen_supply)),
        ((left + 50, y_regen_return), (right - 50, y_regen_return)),
    ])

    texts.extend([
        ("WET PROCESS GAS INLET 12\"-PG-1001", left + 5, y_inlet + 10, 3.2),
        ("DRY PROCESS GAS OUTLET 12\"-PG-1002", left + 5, y_outlet + 10, 3.2),
        ("REGENERATION GAS SUPPLY 4\"-RG-2001", left + 55, y_regen_supply + 10, 3.0),
        ("REGENERATION RETURN TO FUEL/VENT 4\"-RG-2002", left + 55, y_regen_return - 15, 3.0),
    ])

    # Common bypass around driers
    bypass_y = y_inlet + 70
    lines.extend([
        ((drier1_x - 100, y_inlet), (drier1_x - 100, bypass_y)),
        ((drier1_x - 100, bypass_y), (drier2_x + 100, bypass_y)),
        ((drier2_x + 100, bypass_y), (drier2_x + 100, y_outlet)),
    ])
    placements.extend([
        Placement("VALVE_MANUAL", drier1_x - 100, y_inlet + 22),
        Placement("VALVE_MANUAL", center_x, bypass_y),
        Placement("VALVE_MANUAL", drier2_x + 100, y_outlet + 22),
    ])
    texts.append(("BYPASS", center_x - 16, bypass_y + 10, 2.8))

    # Drier vessels
    for i, x in enumerate([drier1_x, drier2_x], start=1):
        placements.append(Placement("vessel-dished-ends", x, vessel_center_y, scale=0.95))
        texts.append((f"V-30{i}A ADSORPTION DRIER {'A' if i == 1 else 'B'}", x - 70, vessel_center_y + 92, 3.0))

        # Inlet downcomer to side nozzle with inlet/outlet block valves
        inlet_nozzle_y = vessel_center_y + nozzle_top_offset
        outlet_nozzle_y = vessel_center_y - nozzle_top_offset
        x_left_noz = x - vessel_nozzle_left
        x_right_noz = x + vessel_nozzle_right

        lines.extend([
            ((x_left_noz, y_inlet), (x_left_noz, inlet_nozzle_y)),
            ((x_left_noz, inlet_nozzle_y), (x, inlet_nozzle_y)),
            ((x_right_noz, outlet_nozzle_y), (x_right_noz, y_outlet)),
            ((x, outlet_nozzle_y), (x_right_noz, outlet_nozzle_y)),
        ])

        placements.extend([
            Placement("VALVE_MANUAL", x_left_noz, y_inlet - 20),
            Placement("VALVE_MANUAL", x_right_noz, y_outlet + 20),
        ])

        # Regen supply into bottom, return from top
        bottom_nozzle_y = vessel_center_y - nozzle_bottom_offset
        top_nozzle_y = vessel_center_y + nozzle_bottom_offset
        lines.extend([
            ((x - 40, y_regen_supply), (x - 40, bottom_nozzle_y)),
            ((x - 40, bottom_nozzle_y), (x, bottom_nozzle_y)),
            ((x + 40, top_nozzle_y), (x + 40, y_regen_return)),
            ((x, top_nozzle_y), (x + 40, top_nozzle_y)),
        ])
        placements.extend([
            Placement("CONTROL_VALVE", x - 40, y_regen_supply + 20),
            Placement("VALVE_MANUAL", x + 40, y_regen_return + 20),
        ])

        # Instruments (bubble + leader + text) PI/TI/AI
        pi_x, pi_y = x - 90, y_inlet - 42
        ti_x, ti_y = x + 90, y_outlet + 42
        ai_x, ai_y = x + 102, y_outlet - 55

        placements.extend([
            Placement("field-mounted-discrete-instrument", pi_x, pi_y, layer="PIP_INSTR"),
            Placement("field-mounted-discrete-instrument", ti_x, ti_y, layer="PIP_INSTR"),
            Placement("field-mounted-discrete-instrument", ai_x, ai_y, layer="PIP_INSTR"),
        ])
        lines.extend([
            ((pi_x + 7, pi_y + 7), (x_left_noz, y_inlet - 5)),
            ((ti_x - 7, ti_y - 7), (x_right_noz, y_outlet + 5)),
            ((ai_x - 7, ai_y + 7), (x_right_noz + 25, y_outlet - 10)),
        ])
        texts.extend([
            (f"PI-30{i} {'INLET P' if i == 1 else 'INLET P(B)'}", pi_x - 28, pi_y - 16, 2.5),
            (f"TI-30{i} {'OUTLET T' if i == 1 else 'OUTLET T(B)'}", ti_x - 30, ti_y - 16, 2.5),
            (f"AI-30{i} H2O ppm", ai_x - 24, ai_y - 16, 2.5),
        ])

    # Flow direction arrows
    placements.extend([
        Placement("FLOW_ARROW", left + 110, y_inlet, rotation=0),
        Placement("FLOW_ARROW", left + 110, y_outlet, rotation=0),
        Placement("FLOW_ARROW", left + 140, y_regen_supply, rotation=0),
        Placement("FLOW_ARROW", right - 140, y_regen_return, rotation=180),
    ])

    # Operating note and dimensions
    texts.extend([
        (
            "DESIGN BASIS: 52,000 Nm3/h @ 42 barg, adsorption 8 h / regeneration 8 h",
            left,
            95,
            3.0,
        ),
        (
            "Switching valves shown manual for clarity; typically actuated with sequence control.",
            left,
            82,
            2.7,
        ),
    ])

    # Dimensional references (calculated from coordinates)
    pitches = [
        (drier1_x, drier2_x, f"C/C DRIERS = {drier2_x - drier1_x:.0f} mm"),
        (left, right, f"PROCESS HEADER SPAN = {width:.0f} mm"),
    ]
    for x1, x2, label in pitches:
        lines.extend([
            ((x1, 128), (x1, 118)),
            ((x2, 128), (x2, 118)),
            ((x1, 118), (x2, 118)),
        ])
        texts.append((label, (x1 + x2) / 2 - 42, 106, 2.8))

    return LayoutBuild(placements=placements, lines=lines, texts=texts)


def place_blocks(msp: ezdxf.layouts.Modelspace, placements: List[Placement]) -> None:
    for p in placements:
        msp.add_blockref(
            p.block,
            (p.x, p.y),
            dxfattribs={
                "layer": p.layer,
                "xscale": p.scale,
                "yscale": p.scale,
                "rotation": p.rotation,
            },
        )


def draw_lines_and_text(msp: ezdxf.layouts.Modelspace, lines, texts) -> None:
    for (x1, y1), (x2, y2) in lines:
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "PIP_LINES"})
    for text, x, y, h in texts:
        msp.add_text(text, dxfattribs={"height": h, "layer": "PIP_TEXT"}).set_placement((x, y))


def get_script_dir() -> Path:
    return Path(__file__).parent


def get_repo_root(script_dir: Path) -> Path:
    return script_dir.parent.parent.resolve()


def main() -> None:
    script_dir = get_script_dir()
    parser = argparse.ArgumentParser(description="Generate dual-drier process gas P&ID")
    parser.add_argument(
        "--output",
        default=str(script_dir / "drier_operation_pid.dxf"),
        help="Output DXF path",
    )
    parser.add_argument(
        "--block-dir",
        action="append",
        default=None,
        help="Block library directory to search (can be repeated)",
    )
    args = parser.parse_args()

    if args.block_dir is None:
        repo_root = get_repo_root(script_dir)
        args.block_dir = [
            str(repo_root / "libreCAD_blocks"),
            str(script_dir / "libreCAD_blocks"),
        ]

    doc = ezdxf.new("R2010")
    add_default_layers(doc)
    create_custom_block_definitions(doc)

    layout = build_layout()

    block_dirs = [Path(d) for d in args.block_dir]
    for p in layout.placements:
        if p.block in doc.blocks:
            continue
        source_file = maybe_find_library_block(p.block, block_dirs)
        if source_file:
            import_block_from_file(doc, source_file, p.block)
        elif p.block not in doc.blocks:
            fallback = {
                "field-mounted-discrete-instrument": "CUSTOM_INSTRUMENT_BUBBLE",
                "VALVE_MANUAL": "CUSTOM_VALVE_MANUAL",
                "CONTROL_VALVE": "CUSTOM_CONTROL_VALVE",
                "FLOW_ARROW": "CUSTOM_ARROW",
                "vessel-dished-ends": "CUSTOM_VERTICAL_VESSEL",
            }
            p.block = fallback.get(p.block, "CUSTOM_INSTRUMENT_BUBBLE")

    msp = doc.modelspace()
    draw_a0_frame(msp)
    draw_lines_and_text(msp, layout.lines, layout.texts)
    place_blocks(msp, layout.placements)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out)
    print(f"Wrote DXF: {out}")


if __name__ == "__main__":
    main()
