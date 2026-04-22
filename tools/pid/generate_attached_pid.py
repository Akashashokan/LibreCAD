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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Set, Tuple

import ezdxf
from ezdxf.addons.importer import Importer

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # optional dependency
    cv2 = None
    np = None

try:
    from PIL import Image
except Exception:  # optional dependency
    Image = None

A0_W_MM = 1189.0
A0_H_MM = 841.0
FRAME_MARGIN_MM = 5.0


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
            (FRAME_MARGIN_MM, FRAME_MARGIN_MM),
            (A0_W_MM - FRAME_MARGIN_MM, FRAME_MARGIN_MM),
            (A0_W_MM - FRAME_MARGIN_MM, A0_H_MM - FRAME_MARGIN_MM),
            (FRAME_MARGIN_MM, A0_H_MM - FRAME_MARGIN_MM),
            (FRAME_MARGIN_MM, FRAME_MARGIN_MM),
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


def get_image_size_px(image_path: Path) -> Tuple[int, int]:
    if Image is not None:
        with Image.open(image_path) as img:
            return img.size
    if cv2 is not None:
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            height, width = img.shape
            return width, height
    raise RuntimeError(
        "Image guide requested, but neither Pillow nor OpenCV is available to read image size."
    )


def fit_inside(source_w: float, source_h: float, max_w: float, max_h: float) -> Tuple[float, float]:
    scale = min(max_w / source_w, max_h / source_h)
    return source_w * scale, source_h * scale


def add_image_guide(doc: ezdxf.EzDxf, msp: ezdxf.layouts.Modelspace, image_path: Path) -> None:
    px_w, px_h = get_image_size_px(image_path)
    fit_w, fit_h = fit_inside(
        float(px_w),
        float(px_h),
        A0_W_MM - (2 * FRAME_MARGIN_MM),
        A0_H_MM - (2 * FRAME_MARGIN_MM),
    )
    insert_x = (A0_W_MM - fit_w) / 2.0
    insert_y = (A0_H_MM - fit_h) / 2.0
    image_def = doc.add_image_def(filename=str(image_path), size_in_pixel=(px_w, px_h))
    msp.add_image(
        image_def,
        insert=(insert_x, insert_y),
        size_in_units=(fit_w, fit_h),
        dxfattribs={"layer": "PIP_IMAGE_GUIDE"},
    )


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


def get_script_dir() -> Path:
    """Get the directory where this script is located.
    
    Handles both normal script execution and Databricks execution environments.
    """
    try:
        # Try to use __file__ (works in normal script execution)
        return Path(__file__).parent
    except NameError:
        # Fallback for Databricks or interactive environments
        # Use the known workspace path for this script
        workspace_path = Path("/Workspace/Users/akashashokan@yahoo.com/LibreCAD/tools/pid")
        if workspace_path.exists():
            return workspace_path
        # Last resort: use current directory
        return Path.cwd()


def main() -> None:
    # Get the directory where this script is located
    script_dir = get_script_dir()
    
    parser = argparse.ArgumentParser(description="Generate attached P&ID DXF from block placements")
    parser.add_argument(
        "--layout", 
        default=str(script_dir / "attached_pid_layout.json"), 
        help="Layout JSON file (default: attached_pid_layout.json in script directory)"
    )
    parser.add_argument("--image", default="", help="Optional attached raster image for automatic line extraction")
    parser.add_argument(
        "--image-mode",
        choices=["guide", "extract", "both"],
        default="both",
        help="Use the image as a scaled underlay, for line extraction, or both",
    )
    parser.add_argument(
        "--output", 
        default=str(script_dir / "attached_pid_generated.dxf"), 
        help="Output DXF path (default: attached_pid_generated.dxf in script directory)"
    )
    parser.add_argument(
        "--block-dir",
        action="append",
        default=None,
        help="Block library directory to search (can be repeated)",
    )
    args, unknown = parser.parse_known_args()

    # Set default block directory if none provided (relative to script directory)
    if args.block_dir is None:
        args.block_dir = [str(script_dir / "libreCAD_blocks")]

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
    if args.image and args.image_mode in {"guide", "both"}:
        add_image_guide(doc, msp, Path(args.image))

    draw_a0_frame(msp)

    if args.image and args.image_mode in {"extract", "both"}:
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
