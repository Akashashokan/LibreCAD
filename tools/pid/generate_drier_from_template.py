#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from drier_pipeline.drier_template_layout import render_fixed_drier_template


def main() -> None:
    script_dir = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Generate the fixed dual molecular sieve drier P&ID template")
    parser.add_argument("--spec", default=str(script_dir / "specs" / "drier_U300.json"), help="Reserved for Stage 2 tag/line parameterization")
    parser.add_argument("--template", default="dual_mol_sieve", choices=["dual_mol_sieve"])
    parser.add_argument("--output", default=str(script_dir / "outputs" / "U300-PID-301.dxf"))
    parser.add_argument("--style", default="final", choices=["final", "debug"])
    parser.add_argument("--qa-overlay", action="store_true")
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args()

    if args.spec and not Path(args.spec).exists():
        raise FileNotFoundError(f"Spec not found: {args.spec}")

    render_fixed_drier_template(Path(args.output), validate=not args.no_validate, style=args.style, qa_overlay=args.qa_overlay)
    print(f"Wrote DXF: {args.output}")


if __name__ == "__main__":
    main()
