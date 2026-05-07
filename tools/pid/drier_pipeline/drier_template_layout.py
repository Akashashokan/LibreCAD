from __future__ import annotations

from pathlib import Path

from tools.pid.templates.dual_mol_sieve_drier_template import draw_dual_drier_template


def render_fixed_drier_template(output: Path, *, validate: bool = True, style: str = "final", qa_overlay: bool = False) -> None:
    """Render the production-style fixed molecular sieve drier package template.

    This module is the bridge from the older drier pipeline package into the
    template-first drafting path. It intentionally avoids NetworkX topology,
    center-node placement, and graph routing.
    """

    draw_dual_drier_template(output=output, validate=validate, style_name=style, qa_overlay=qa_overlay)
