#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import ezdxf
import fitz
from ezdxf import bbox as ezdxf_bbox
from ezdxf.addons.drawing import matplotlib as ezdxf_matplotlib
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


SUPPORTED_RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def render_dxf_to_png(input_path: Path, output_path: Path, dpi: int, render_width: int, units: str) -> Path:
    doc = ezdxf.readfile(input_path)
    layout = doc.modelspace()
    size_inches = (render_width / dpi, 0.0) if render_width > 0 else dxf_size_inches(doc, layout, units)
    ezdxf_matplotlib.qsave(
        layout,
        output_path,
        bg="#FFFFFF",
        fg="#000000",
        dpi=dpi,
        size_inches=size_inches,
    )
    return output_path


def dxf_size_inches(doc: ezdxf.EzDxfDocument, layout: ezdxf.layouts.Modelspace, units: str) -> tuple[float, float] | None:
    extents = ezdxf_bbox.extents(layout)
    width = float(extents.size.x)
    height = float(extents.size.y)
    if width <= 0 or height <= 0:
        return None

    units_per_inch = dxf_units_per_inch(doc, units, width)
    if units_per_inch is None:
        return None
    return (width / units_per_inch, height / units_per_inch)


def dxf_units_per_inch(doc: ezdxf.EzDxfDocument, units: str, width: float) -> float | None:
    unit = units.lower()
    if unit == "auto":
        insunits = doc.header.get("$INSUNITS")
        if insunits == 1:
            unit = "inch"
        elif insunits == 4:
            unit = "mm"
        elif insunits == 5:
            unit = "cm"
        elif insunits == 6:
            unit = "m"
        else:
            unit = "mm" if width > 200 else "inch"

    units_per_inch = {
        "inch": 1.0,
        "in": 1.0,
        "mm": 25.4,
        "millimeter": 25.4,
        "cm": 2.54,
        "centimeter": 2.54,
        "m": 0.0254,
        "meter": 0.0254,
        "unit": None,
    }.get(unit)
    if unit not in {"inch", "in", "mm", "millimeter", "cm", "centimeter", "m", "meter", "unit"}:
        raise ValueError(f"Unsupported --dxf-units value: {units}")
    return units_per_inch


def render_pdf_to_png(input_path: Path, output_path: Path, dpi: int, page_number: int) -> Path:
    doc = fitz.open(input_path)
    try:
        if page_number < 1 or page_number > len(doc):
            raise ValueError(f"PDF page {page_number} is outside 1..{len(doc)}")
        page = doc[page_number - 1]
        scale = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pix.save(output_path)
    finally:
        doc.close()
    return output_path


def copy_raster_to_png(input_path: Path, output_path: Path) -> Path:
    with Image.open(input_path) as img:
        image = flatten_to_white(img)
        image.save(output_path)
    return output_path


def flatten_to_white(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or ("transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def crop_to_content(image: Image.Image, padding: int, white_threshold: int) -> Image.Image:
    rgb = flatten_to_white(image)
    white = Image.new("RGB", rgb.size, "white")
    diff = ImageChops.difference(rgb, white).convert("L")
    mask = diff.point(lambda p: 255 if p > white_threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return rgb

    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(rgb.width, right + padding)
    bottom = min(rgb.height, bottom + padding)
    return rgb.crop((left, top, right, bottom))


def clean_image(
    input_path: Path,
    output_path: Path,
    *,
    padding: int,
    white_threshold: int,
    sharpen: bool,
    binarize: bool,
    binarize_threshold: int,
    max_width: int | None,
) -> Image.Image:
    with Image.open(input_path) as img:
        image = crop_to_content(img, padding=padding, white_threshold=white_threshold)
        image = ImageOps.autocontrast(image, cutoff=1)
        if sharpen:
            image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=150, threshold=3))
        if binarize:
            image = binarize_lines(image, threshold=binarize_threshold)
        if max_width and image.width > max_width:
            height = round(image.height * max_width / image.width)
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)
        image.save(output_path)
        return image


def binarize_lines(image: Image.Image, threshold: int) -> Image.Image:
    gray = flatten_to_white(image).convert("L")
    mask = gray.point(lambda p: 0 if p < threshold else 255)
    return mask.convert("RGB")


def content_ratio(image: Image.Image, white_threshold: int) -> float:
    rgb = flatten_to_white(image)
    white = Image.new("RGB", rgb.size, "white")
    diff = ImageChops.difference(rgb, white).convert("L")
    mask = diff.point(lambda p: 1 if p > white_threshold else 0)
    non_white = sum(mask.getdata())
    return non_white / float(image.width * image.height)


def tile_bounds(width: int, height: int, tile_size: int, overlap: int) -> list[tuple[int, int, int, int, int, int]]:
    if tile_size <= 0:
        raise ValueError("--tile-size must be positive")
    if overlap < 0 or overlap >= tile_size:
        raise ValueError("--overlap must be >= 0 and smaller than --tile-size")

    stride = tile_size - overlap
    cols = max(1, math.ceil(max(1, width - overlap) / stride))
    rows = max(1, math.ceil(max(1, height - overlap) / stride))
    bounds: list[tuple[int, int, int, int, int, int]] = []

    for row in range(rows):
        for col in range(cols):
            x0 = min(col * stride, max(0, width - tile_size))
            y0 = min(row * stride, max(0, height - tile_size))
            x1 = min(width, x0 + tile_size)
            y1 = min(height, y0 + tile_size)
            bounds.append((row, col, x0, y0, x1, y1))

    return sorted(set(bounds), key=lambda item: (item[0], item[1], item[2], item[3]))


def save_segments(
    image: Image.Image,
    segments_dir: Path,
    *,
    tile_size: int,
    overlap: int,
    white_threshold: int,
    min_content_ratio: float,
    keep_empty: bool,
) -> list[dict[str, Any]]:
    segments_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    for index, (row, col, x0, y0, x1, y1) in enumerate(tile_bounds(image.width, image.height, tile_size, overlap), start=1):
        crop = image.crop((x0, y0, x1, y1))
        ratio = content_ratio(crop, white_threshold)
        if not keep_empty and ratio < min_content_ratio:
            continue

        name = f"segment_{len(records) + 1:03d}_r{row:02d}_c{col:02d}_x{x0}_y{y0}.png"
        output = segments_dir / name
        crop.save(output)
        records.append(
            {
                "id": f"segment_{len(records) + 1:03d}",
                "file": str(output),
                "row": row,
                "col": col,
                "bbox_px": [x0, y0, x1, y1],
                "bbox_normalized": [
                    round(x0 / image.width, 6),
                    round(y0 / image.height, 6),
                    round(x1 / image.width, 6),
                    round(y1 / image.height, 6),
                ],
                "width": x1 - x0,
                "height": y1 - y0,
                "content_ratio": round(ratio, 6),
            }
        )

    return records


def save_overview(image: Image.Image, segments: list[dict[str, Any]], output_path: Path) -> None:
    max_width = 1800
    scale = min(1.0, max_width / image.width)
    overview = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(overview)

    for segment in segments:
        x0, y0, x1, y1 = segment["bbox_px"]
        box = [round(x0 * scale), round(y0 * scale), round(x1 * scale), round(y1 * scale)]
        draw.rectangle(box, outline="#D21F3C", width=max(2, round(3 * scale)))
        label = segment["id"].replace("segment_", "S")
        draw.rectangle([box[0], box[1], box[0] + 58, box[1] + 22], fill="white", outline="#D21F3C")
        draw.text((box[0] + 4, box[1] + 3), label, fill="#D21F3C")

    overview.save(output_path)


def source_to_image(input_path: Path, output_dir: Path, dpi: int, pdf_page: int, render_width: int, dxf_units: str) -> Path:
    suffix = input_path.suffix.lower()
    rendered_path = output_dir / "rendered_full.png"
    if suffix == ".dxf":
        return render_dxf_to_png(input_path, rendered_path, dpi, render_width, dxf_units)
    if suffix == ".pdf":
        return render_pdf_to_png(input_path, rendered_path, dpi, pdf_page)
    if suffix in SUPPORTED_RASTER_SUFFIXES:
        return copy_raster_to_png(input_path, rendered_path)
    raise ValueError(f"Unsupported input type: {input_path.suffix}")


def build_manifest(
    *,
    source: Path,
    rendered: Path,
    cleaned: Path,
    overview: Path,
    image: Image.Image,
    segments: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "source": str(source),
        "rendered_image": str(rendered),
        "cleaned_image": str(cleaned),
        "overview_image": str(overview),
        "image_width": image.width,
        "image_height": image.height,
        "segment_count": len(segments),
        "settings": {
            "dpi": args.dpi,
            "render_width": args.render_width,
            "dxf_units": args.dxf_units,
            "pdf_page": args.pdf_page,
            "tile_size": args.tile_size,
            "overlap": args.overlap,
            "min_content_ratio": args.min_content_ratio,
            "keep_empty": args.keep_empty,
            "binarize": not args.no_binarize,
            "binarize_threshold": args.binarize_threshold,
            "max_width": args.max_width,
        },
        "model_instruction": (
            "Review each segment for P&ID drafting, tag, routing, symbol, and readability issues. "
            "Return comments keyed by segment id and bbox_px so they can be mapped back to the full sheet."
        ),
        "segments": segments,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a P&ID to a clear PNG and split it into model-reviewable image segments."
    )
    parser.add_argument("input", help="P&ID file to process: DXF, PDF, PNG, JPG, TIFF, BMP, or WebP")
    parser.add_argument("--output-dir", default="tools/pid/outputs/pid_image_segments")
    parser.add_argument("--dpi", type=int, default=300, help="DXF/PDF render resolution")
    parser.add_argument(
        "--render-width",
        type=int,
        default=5000,
        help="Target DXF render width in pixels; use 0 to size from --dxf-units and sheet extents",
    )
    parser.add_argument(
        "--dxf-units",
        default="auto",
        choices=["auto", "mm", "cm", "m", "inch", "in", "unit"],
        help="DXF drawing units used only when --render-width is 0; 'unit' keeps Matplotlib's default figure size",
    )
    parser.add_argument("--pdf-page", type=int, default=1, help="1-based PDF page number")
    parser.add_argument("--tile-size", type=int, default=1600, help="Segment size in pixels")
    parser.add_argument("--overlap", type=int, default=220, help="Pixel overlap between neighboring segments")
    parser.add_argument("--padding", type=int, default=30, help="Whitespace padding retained around content")
    parser.add_argument("--white-threshold", type=int, default=12, help="Difference from white treated as content")
    parser.add_argument("--min-content-ratio", type=float, default=0.002, help="Skip near-empty tiles below this ratio")
    parser.add_argument("--keep-empty", action="store_true", help="Keep blank/near-empty tiles")
    parser.add_argument("--no-sharpen", action="store_true", help="Disable light sharpening on the cleaned image")
    parser.add_argument("--no-binarize", action="store_true", help="Keep antialiased grayscale output instead of black/white lines")
    parser.add_argument("--binarize-threshold", type=int, default=248, help="Pixels darker than this become black")
    parser.add_argument("--max-width", type=int, default=None, help="Optional downscale width for very large sheets")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    segments_dir = output_dir / "segments"
    rendered = source_to_image(input_path, output_dir, args.dpi, args.pdf_page, args.render_width, args.dxf_units)
    cleaned = output_dir / "cleaned_full.png"
    image = clean_image(
        rendered,
        cleaned,
        padding=args.padding,
        white_threshold=args.white_threshold,
        sharpen=not args.no_sharpen,
        binarize=not args.no_binarize,
        binarize_threshold=args.binarize_threshold,
        max_width=args.max_width,
    )
    segments = save_segments(
        image,
        segments_dir,
        tile_size=args.tile_size,
        overlap=args.overlap,
        white_threshold=args.white_threshold,
        min_content_ratio=args.min_content_ratio,
        keep_empty=args.keep_empty,
    )

    overview = output_dir / "segment_overview.png"
    save_overview(image, segments, overview)
    manifest = build_manifest(
        source=input_path,
        rendered=rendered,
        cleaned=cleaned,
        overview=overview,
        image=image,
        segments=segments,
        args=args,
    )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Wrote cleaned image: {cleaned}")
    print(f"Wrote segment overview: {overview}")
    print(f"Wrote {len(segments)} segments: {segments_dir}")
    print(f"Wrote manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
