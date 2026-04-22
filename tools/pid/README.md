# Attached P&ID Reproduction Script

This directory contains a generator for producing a LibreCAD-openable DXF from:

1. A coordinate-based block placement/layout JSON.
2. Your `libreCAD_blocks` P&ID libraries.
3. Optional raster image guide placement and line extraction from the attached P&ID image.

## Files

- `generate_attached_pid.py`: main generator.
- `attached_pid_layout.json`: editable coordinates/specs used by the generator.
- `attached_pid_generated.dxf`: output file (created when you run the script).

## What the script does

- Creates an A0 landscape frame and title area.
- Searches `libreCAD_blocks` for required symbol block DXFs and imports them.
  - By default it searches repository-level `libreCAD_blocks/` first, then `tools/pid/libreCAD_blocks/` as fallback.
- Creates fallback custom blocks for missing symbols (`CUSTOM_*`).
- Places all configured components at explicit X/Y positions.
- Places the source P&ID image on the drawing as a full-sheet guide underlay when `--image` is provided.
- Draws configured lines/text and optionally auto-extracts orthogonal process lines from the image.

## Requirements

```bash
pip install ezdxf
```

Optional (for automatic line extraction from image):

```bash
pip install opencv-python numpy
```

## Run

```bash
python3 tools/pid/generate_attached_pid.py \
  --layout tools/pid/attached_pid_layout.json \
  --output tools/pid/attached_pid_generated.dxf \
  --image /path/to/attached_pid_image.png \
  --image-mode both
```

`--image-mode` options:

- `guide`: place the original raster P&ID on the sheet as a scaled tracing guide.
- `extract`: only attempt automatic orthogonal line extraction from the image.
- `both`: include the image guide and attempt line extraction.

If you don't want any image assistance, omit `--image`.

## Open in LibreCAD

- Launch LibreCAD.
- Open `tools/pid/attached_pid_generated.dxf`.
- Toggle the `PIP_IMAGE_GUIDE` layer on/off while tracing or refining placements.
- If needed, refine `attached_pid_layout.json` and regenerate until fully aligned.

## Adding missing components as library blocks

The script always provides `CUSTOM_*` fallback blocks.
If you want permanent library blocks, save your custom symbols as DXF files inside:

- `libreCAD_blocks/Custom PID/`

Then reference those names in `attached_pid_layout.json`.
