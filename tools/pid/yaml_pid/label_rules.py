from __future__ import annotations

from collections.abc import Sequence

from .cad_primitives import DrawContext, draw_line_label

Point = tuple[float, float]


def line_label_position(points: Sequence[Point]) -> tuple[float, float]:
    best = max(zip(points, points[1:]), key=lambda seg: abs(seg[1][0] - seg[0][0]) + abs(seg[1][1] - seg[0][1]))
    p1, p2 = best
    x, y = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    if p1[1] == p2[1]:
        return x - 25, y + 6
    return x + 6, y


def apply_line_label(ctx: DrawContext, line_tag: str, service: str, points: Sequence[Point]) -> None:
    x, y = line_label_position(points)
    draw_line_label(ctx, line_tag, x, y, service)

