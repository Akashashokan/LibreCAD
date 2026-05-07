from __future__ import annotations

from .cad_primitives import DrawContext, draw_signal_line
from .models import SignalRoute

TRUNK_X = {
    "COLUMN_LEFT_SIGNAL_TRUNK": 385,
    "COLUMN_RIGHT_SIGNAL_TRUNK": 650,
    "REFLUX_DRUM_SIGNAL_TRUNK": 715,
    "ANALYZER_SIGNAL_TRUNK": 990,
}
TRUNK_Y = {
    "FEED_CONTROL_SIGNAL_TRUNK": 485,
    "OVERHEAD_SIGNAL_TRUNK": 720,
    "REFLUX_PUMP_SIGNAL_TRUNK": 535,
    "BOTTOMS_SIGNAL_TRUNK": 285,
    "SIS_SIGNAL_TRUNK": 735,
}


def route_signals(ctx: DrawContext, signals: list[SignalRoute]) -> list[str]:
    warnings: list[str] = []
    for route in signals:
        src = _point(ctx, route.source)
        targets = route.targets or ([route.target] if route.target else [])
        if src is None or not targets:
            warnings.append(f"signal {route.name} missing source/target")
            continue
        for target_ref in targets:
            dst = _point(ctx, target_ref)
            if dst is None:
                warnings.append(f"signal {route.name} missing endpoint {target_ref}")
                continue
            points = _orthogonal(src, dst, route.trunk)
            draw_signal_line(ctx, points, route.signal_type)
    return warnings


def _point(ctx: DrawContext, ref: object) -> tuple[float, float] | None:
    if not isinstance(ref, str):
        return None
    return ctx.registry.ports.get(ref)


def _orthogonal(src: tuple[float, float], dst: tuple[float, float], trunk: str) -> list[tuple[float, float]]:
    if trunk in TRUNK_X:
        x = TRUNK_X[trunk]
        return [src, (x, src[1]), (x, dst[1]), dst]
    if trunk in TRUNK_Y:
        y = TRUNK_Y[trunk]
        return [src, (src[0], y), (dst[0], y), dst]
    midx = (src[0] + dst[0]) / 2
    return [src, (midx, src[1]), (midx, dst[1]), dst]

