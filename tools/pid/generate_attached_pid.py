#!/usr/bin/env python3
"""Generate a LibreCAD-openable DXF for the attached P&ID drawing.

This script builds a base A0 drawing, defines fallback custom P&ID blocks
(if they do not exist in the local block library), and places components using
explicit X/Y coordinates from a layout JSON file.

It also supports optional raster line extraction from the attached image to help
recreate interconnecting lines.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import ezdxf

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # optional dependency
    cv2 = None
    np = None

A0_W_MM = 1189.0
A0_H_MM = 841.0


@dataclass
class Placement:
    block: str
    x: float
    y: float
    scale: float = 1.0
    rotation: float = 0.0
    layer: str = "PIP_SYMBOLS"


def add_default_layers(doc: ezdxf.EzDxf) -> None:
    layers = {
        "BORDER": 7,
        "PIP_LINES": 7,
        "PIP_SYMBOLS": 7,
        "PIP_TEXT": 7,
        "PIP_IMAGE_GUIDE": 8,
    }
    for name, color in layers.items():
        if name not in doc.layers:
            doc.layers.add(name=name, color=color)


def create_custom_block_definitions(doc: ezdxf.EzDxf) -> None:
    """Add a small fallback custom block set for missing P&ID parts."""

    blocks = doc.blocks

    if "CUSTOM_INSTRUMENT_BUBBLE" not in blocks:
        b = blocks.new("CUSTOM_INSTRUMENT_BUBBLE")
        b.add_circle((0, 0), radius=3.0)
        b.add_line((-3, 0), (3, 0))
        b.add_line((0, -3), (0, 3))

    if "CUSTOM_VALVE_MANUAL" not in blocks:
        b = blocks.new("CUSTOM_VALVE_MANUAL")
        b.add_lwpolyline([(-4, 0), (0, 3), (4, 0), (0, -3), (-4, 0)])

    if "CUSTOM_CONTROL_VALVE" not in blocks:
        b = blocks.new("CUSTOM_CONTROL_VALVE")
        b.add_lwpolyline([(-5, 0), (0, 3.5), (5, 0), (0, -3.5), (-5, 0)])
        b.add_line((-5, 4.5), (5, -4.5))

    if "CUSTOM_ARROW" not in blocks:
        b = blocks.new("CUSTOM_ARROW")
        b.add_line((-6, 0), (6, 0))
        b.add_lwpolyline([(6, 0), (3.5, 1.8), (3.5, -1.8), (6, 0)])



def draw_a0_frame(msp: ezdxf.layouts.Modelspace) -> None:
    # Outer border
    msp.add_lwpolyline(
        [
            (5, 5),
            (A0_W_MM - 5, 5),
            (A0_W_MM - 5, A0_H_MM - 5),
            (5, A0_H_MM - 5),
            (5, 5),
        ],
        dxfattribs={"layer": "BORDER"},
    )

    # Simplified title area in lower-right (approx.)
    x0 = A0_W_MM - 300
    y0 = 5
    msp.add_lwpolyline(
        [(x0, y0), (A0_W_MM - 5, y0), (A0_W_MM - 5, 260), (x0, 260), (x0, y0)],
        dxfattribs={"layer": "BORDER"},
    )
    for yy in [30, 45, 60, 75, 90, 110, 130, 160, 200, 230]:
        msp.add_line((x0, yy), (A0_W_MM - 5, yy), dxfattribs={"layer": "BORDER"})


def load_layout(path: Path) -> Tuple[List[Placement], List[Tuple[Tuple[float, float], Tuple[float, float]]], List[Tuple[str, float, float, float]]]:
    data = json.loads(path.read_text())
    placements = [Placement(**item) for item in data.get("placements", [])]
    lines = [((ln["x1"], ln["y1"]), (ln["x2"], ln["y2"])) for ln in data.get("lines", [])]
    texts = [(t["text"], t["x"], t["y"], t.get("height", 2.5)) for t in data.get("texts", [])]
    return placements, lines, texts


def maybe_find_library_block(block_name: str, block_dirs: Iterable[Path]) -> Path | None:
    target = block_name.lower().replace("_", "-")
    for root in block_dirs:
        if not root.exists():
            continue
        for entry in root.rglob("*.dxf"):
            stem = entry.stem.lower()
            if target in stem or stem in target:
                return entry
    return None


def import_block_from_file(doc: ezdxf.EzDxf, path: Path, target_name: str) -> None:
    source = ezdxf.readfile(path)
    src_msp = source.modelspace()
    if target_name in doc.blocks:
        return
    newb = doc.blocks.new(target_name)
    for e in src_msp:
        newb.add_foreign_entity(e.copy())


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


def extract_lines_from_image(image_path: Path) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    if cv2 is None or np is None:
        return []

    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    edges = cv2.Canny(img, threshold1=80, threshold2=180, apertureSize=3)
    raw = cv2.HoughLinesP(edges, 1, math.pi / 180, threshold=120, minLineLength=80, maxLineGap=6)
    if raw is None:
        return []

    h, w = img.shape
    lines = []
    for seg in raw[:, 0, :]:
        x1, y1, x2, y2 = map(float, seg)
        mmx1 = (x1 / w) * A0_W_MM
        mmx2 = (x2 / w) * A0_W_MM
        mmy1 = A0_H_MM - ((y1 / h) * A0_H_MM)
        mmy2 = A0_H_MM - ((y2 / h) * A0_H_MM)

        # keep near-orthogonal lines typical for P&ID
        if abs(mmx1 - mmx2) < 1.0 or abs(mmy1 - mmy2) < 1.0:
            lines.append(((mmx1, mmy1), (mmx2, mmy2)))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate attached P&ID DXF from block placements")
    parser.add_argument("--layout", default="tools/pid/attached_pid_layout.json", help="Layout JSON file")
    parser.add_argument("--image", default="", help="Optional attached raster image for automatic line extraction")
    parser.add_argument("--output", default="tools/pid/attached_pid_generated.dxf", help="Output DXF path")
    parser.add_argument(
        "--block-dir",
        action="append",
        default=["libreCAD_blocks"],
        help="Block library directory to search (can be repeated)",
    )
    args = parser.parse_args()

    doc = ezdxf.new("R2010")
    add_default_layers(doc)
    create_custom_block_definitions(doc)

    placements, lines, texts = load_layout(Path(args.layout))
    block_dirs = [Path(d) for d in args.block_dir]

    # Import external block geometry when matching files are found; fallback to custom blocks otherwise.
    for p in placements:
        if p.block in doc.blocks:
            continue
        source_file = maybe_find_library_block(p.block, block_dirs)
        if source_file:
            import_block_from_file(doc, source_file, p.block)
        elif p.block not in doc.blocks:
            # fallback map for common unavailability
            fallback = {
                "INSTRUMENT_BUBBLE": "CUSTOM_INSTRUMENT_BUBBLE",
                "VALVE_MANUAL": "CUSTOM_VALVE_MANUAL",
                "CONTROL_VALVE": "CUSTOM_CONTROL_VALVE",
                "FLOW_ARROW": "CUSTOM_ARROW",
            }
            p.block = fallback.get(p.block, "CUSTOM_INSTRUMENT_BUBBLE")

    msp = doc.modelspace()
    draw_a0_frame(msp)

    if args.image:
        auto_lines = extract_lines_from_image(Path(args.image))
        lines.extend(auto_lines)

    draw_lines_and_text(msp, lines, texts)
    place_blocks(msp, placements)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out)
    print(f"Wrote DXF: {out}")


if __name__ == "__main__":
    main()
