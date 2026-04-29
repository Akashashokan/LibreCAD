#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from drier_pipeline.engineering_model import load_model_from_dict
from drier_pipeline.export import export_pdf_if_available
from drier_pipeline.layout_engine import calculate_layout
from drier_pipeline.renderer_dxf import render_to_dxf
from drier_pipeline.symbol_registry import default_registry
from drier_pipeline.topology import build_topology
from drier_pipeline.validation import assert_valid


def main() -> None:
    script_dir = Path(__file__).parent

    parser = argparse.ArgumentParser(description="Production-style dual-drier P&ID generator")
    parser.add_argument("--spec", default=str(script_dir / "drier_pipeline" / "drier_pid_spec.json"))
    parser.add_argument("--output", default=str(script_dir / "drier_operation_pid.dxf"))
    parser.add_argument("--pdf-output", default=str(script_dir / "drier_operation_pid.pdf"))
    parser.add_argument("--dev-mode", action="store_true", help="Allow symbol fallback warnings")
    parser.add_argument("--block-dir", action="append", default=None, help="Block library directory; can repeat")
    args = parser.parse_args()

    if args.block_dir is None:
        repo_root = script_dir.parent.parent
        args.block_dir = [
            str(repo_root / "LibreCAD_Blocks"),
            str(repo_root / "libreCAD_blocks"),
        ]
    block_dirs = [Path(p) for p in args.block_dir]

    spec = json.loads(Path(args.spec).read_text())
    model = load_model_from_dict(spec)
    graph = build_topology(model)
    assert_valid(model, graph)

    registry = default_registry(dev_mode=args.dev_mode)
    registry.ensure_blocks_available(block_dirs)

    positions, route_table = calculate_layout()

    render_to_dxf(
        model=model,
        graph=graph,
        positions=positions,
        route_table=route_table,
        registry=registry,
        block_dirs=block_dirs,
        output=Path(args.output),
    )
    print(f"Wrote DXF: {args.output}")
    print(export_pdf_if_available(Path(args.output), Path(args.pdf_output)))


if __name__ == "__main__":
    main()
