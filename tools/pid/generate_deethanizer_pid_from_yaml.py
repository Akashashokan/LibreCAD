#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pid.yaml_pid.models import ConfigError
from tools.pid.yaml_pid.render_deethanizer_from_yaml import render_deethanizer_from_yaml


def main() -> int:
    script_dir = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Generate a YAML-driven deethanizer column P&ID")
    parser.add_argument("--config-dir", default=str(script_dir / "configs" / "deethanizer_U400"))
    parser.add_argument("--output", default=str(script_dir / "outputs" / "U400-PID-401-REBUILD.dxf"))
    parser.add_argument("--drawing-no", default="U400-PID-401-REBUILD")
    parser.add_argument("--pdf-output", default=None)
    parser.add_argument("--style", default="final", choices=["final", "debug"])
    parser.add_argument("--qa-overlay", action="store_true")
    parser.add_argument("--no-validate", action="store_true")
    parser.add_argument("--block-dir", default=str(REPO_ROOT / "libreCAD_blocks"))
    args = parser.parse_args()

    try:
        engineering, visual, subsystem = render_deethanizer_from_yaml(
            config_dir=Path(args.config_dir),
            output=Path(args.output),
            pdf_output=Path(args.pdf_output) if args.pdf_output else None,
            drawing_no=args.drawing_no,
            style=args.style,
            qa_overlay=args.qa_overlay,
            validate=not args.no_validate,
            block_dir=Path(args.block_dir),
        )
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(engineering)
    print()
    print(visual)
    print()
    print(subsystem)
    print()
    print(f"Wrote DXF: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
