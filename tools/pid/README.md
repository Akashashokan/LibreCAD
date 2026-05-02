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

## Dual-drier process gas P&ID generator

A second script is included for a realistic **two-driers-in-parallel** operation:

- `generate_drier_operation_pid.py`

It generates `tools/pid/drier_operation_pid.dxf` and includes calculated geometry for:

- Process gas inlet/outlet headers
- Two adsorption driers in parallel
- Regeneration supply and return lines
- Common bypass line
- Pressure / temperature / analyzer instrument bubbles and callouts
- Simple dimensional annotation labels derived from computed coordinates

Run:

```bash
python3 tools/pid/generate_drier_operation_pid.py
```


## Dual-drier process gas P&ID generator (production-style pipeline)

The dual-drier generator was refactored into a multi-module pipeline under `tools/pid/drier_pipeline/`:

- `engineering_model.py`: dataclasses for equipment, nozzles, lines, valves, instruments, analyzers, and off-page connectors
- `symbol_registry.py`: engineering-object to ISA/ISO/PIP/LibreCAD block mapping with strict production checks
- `topology.py`: NetworkX topology graph builder for piping and signal edges
- `validation.py`: design checks (tag uniqueness, line metadata completeness, analyzer conditioning, off-page references, valve sequence data)
- `layout_engine.py`: coordinate rules for A0 left-to-right process and lower regeneration section
- `renderer_dxf.py`: DXF rendering with dedicated process/instrument/signal layers
- `export.py`: optional `librecad dxf2pdf` conversion and non-empty PDF verification
- `drier_pid_spec.json`: engineering input model (not hard-coded drawing content)

Run:

```bash
python3 tools/pid/generate_drier_operation_pid.py
```

Use `--dev-mode` only for development fallback behavior when symbols are incomplete.


Additional options:

- `--block-dir <path>` (repeatable) to point to block libraries such as `./LibreCAD_Blocks` or `./libreCAD_blocks`.
- The pipeline now imports required symbol blocks into the output DXF and uses orthogonal route polylines between routed topology nodes.
