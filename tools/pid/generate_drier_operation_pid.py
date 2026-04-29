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
    args = parser.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    model = load_model_from_dict(spec)
    graph = build_topology(model)
    assert_valid(model, graph)

    registry = default_registry(dev_mode=args.dev_mode)
    positions = calculate_layout()

    render_to_dxf(
        model=model,
        graph=graph,
        positions=positions,
        registry=registry,
        output=Path(args.output),
    )
    print(f"Wrote DXF: {args.output}")
    print(export_pdf_if_available(Path(args.output), Path(args.pdf_output)))


if __name__ == "__main__":
    main()
