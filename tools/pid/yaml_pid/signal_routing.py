from __future__ import annotations

from .cad_primitives import DrawContext, draw_signal_line
from .grid import snap_point
from .models import SignalRoute

TRUNK_X = {
    "COLUMN_LEFT_SIGNAL_TRUNK": 390,
    "COLUMN_RIGHT_SIGNAL_TRUNK": 745,
    "REFLUX_DRUM_SIGNAL_TRUNK": 950,
    "ANALYZER_SIGNAL_TRUNK": 970,
}
TRUNK_Y = {
    "FEED_CONTROL_SIGNAL_TRUNK": 455,
    "OVERHEAD_SIGNAL_TRUNK": 720,
    "REFLUX_PUMP_SIGNAL_TRUNK": 585,
    "BOTTOMS_SIGNAL_TRUNK": 260,
    "SIS_SIGNAL_TRUNK": 735,
}

SIGNAL_LANE_OFFSET = {
    "electric_signal": 0.0,
    "pneumatic_signal": -10.0,
    "software_signal": 10.0,
    "safety_signal": 15.0,
}


def route_signals(ctx: DrawContext, signals: list[SignalRoute]) -> list[str]:
    warnings: list[str] = []
    trunk_spans: dict[tuple[str, str], list[tuple[float, float]]] = {}
    branch_runs: set[tuple[str, tuple[float, float], tuple[float, float]]] = set()
    for route in signals:
        if route.signal_type == "impulse_line":
            continue
        if _alarm_ref(route.source) or _alarm_ref(route.target) or any(_alarm_ref(target) for target in route.targets):
            continue
        src_ref = _override_source_ref(route.name, route.source)
        targets = route.targets or ([route.target] if route.target else [])
        target_refs = [_override_target_ref(route.name, target) for target in targets]
        src = _point(ctx, src_ref)
        if src is None or not target_refs:
            message = f"signal {route.name} missing source/target"
            warnings.append(message)
            ctx.registry.unresolved_connections.append(message)
            continue
        for target_ref in target_refs:
            dst = _point(ctx, target_ref)
            if dst is None:
                message = f"signal {route.name} missing endpoint {target_ref}"
                warnings.append(message)
                ctx.registry.unresolved_connections.append(message)
                continue
            ctx.registry.signal_connections.setdefault(route.name, []).append((str(src_ref), str(target_ref)))
            for p1, p2 in _branches(src, dst, route.trunk, route.signal_type, trunk_spans):
                run = (route.signal_type, _norm_point(p1), _norm_point(p2))
                reverse = (route.signal_type, _norm_point(p2), _norm_point(p1))
                if run in branch_runs or reverse in branch_runs:
                    continue
                branch_runs.add(run)
                draw_signal_line(ctx, [p1, p2], route.signal_type, route.name)
    for (trunk, signal_type), spans in sorted(trunk_spans.items()):
        points = _trunk_points(trunk, signal_type, spans)
        if points:
            draw_signal_line(ctx, points, signal_type, f"trunk:{trunk}:{signal_type}")
    return warnings


def _point(ctx: DrawContext, ref: object) -> tuple[float, float] | None:
    if not isinstance(ref, str):
        return None
    return ctx.registry.ports.get(ref)


def _override_source_ref(route_name: str, source: object) -> object:
    if route_name == "FT-501_to_FIC-501":
        return "FT-501.top_signal"
    return source


def _override_target_ref(route_name: str, target: object) -> object:
    if route_name == "FT-501_to_FIC-501":
        return "FIC-501.right_signal"
    return target


def _alarm_ref(ref: object) -> bool:
    if not isinstance(ref, str):
        return False
    tag = ref.split(".", 1)[0]
    prefix = tag.split("-", 1)[0]
    return prefix in {"PAH", "PAL", "TAH", "TAL", "LAH", "LAL", "PSHH", "LSHH", "LSL"}


def _branches(src: tuple[float, float], dst: tuple[float, float], trunk: str, signal_type: str, trunk_spans: dict[tuple[str, str], list[tuple[float, float]]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    src = snap_point(src)
    dst = snap_point(dst)
    if src == snap_point((370.0, 445.0)) and dst == snap_point((348.0, 455.0)):
        return _clean_segments([(src, (src[0], dst[1])), ((src[0], dst[1]), dst)])
    if src[1] < 380 and dst[1] < 410 and src[0] <= 240 and dst[0] <= 240:
        y = min(src[1], dst[1]) - 15.0
        x = min(src[0], dst[0]) - 20.0
        return _clean_segments([(src, (x, src[1])), ((x, src[1]), (x, y)), ((x, y), (dst[0], y)), ((dst[0], y), dst)])
    if trunk == "REFLUX_DRUM_SIGNAL_TRUNK" and signal_type == "pneumatic_signal":
        x = snap_point((TRUNK_X[trunk] + SIGNAL_LANE_OFFSET.get(signal_type, 0.0), 0))[0]
        y = 640.0
        trunk_spans.setdefault((trunk, signal_type), []).append((y, dst[1]))
        return _clean_segments([(src, (src[0], y)), ((src[0], y), (x, y)), ((x, dst[1]), dst)])
    if trunk == "FEED_CONTROL_SIGNAL_TRUNK" and signal_type == "pneumatic_signal":
        y = 545.0
        x = 190.0
        target_drop_x = snap_point((dst[0] + 30.0, y))[0]
        source_lane_y = snap_point((src[0], y))[1]
        return _clean_segments([(src, (src[0], source_lane_y)), ((src[0], source_lane_y), (target_drop_x, source_lane_y)), ((target_drop_x, source_lane_y), (target_drop_x, y)), ((target_drop_x, y), (x, y)), ((x, y), (dst[0], y)), ((dst[0], y), dst)])
    if trunk == "BOTTOMS_SIGNAL_TRUNK" and signal_type == "pneumatic_signal":
        y = 230.0
        if src[0] <= 260:
            x = 180.0
            return _clean_segments([(src, (x, src[1])), ((x, src[1]), (x, y)), ((x, y), (dst[0], y)), ((dst[0], y), dst)])
        if dst[0] <= 260:
            x = 180.0
            return _clean_segments([(src, (src[0], y)), ((src[0], y), (x, y)), ((x, y), (x, dst[1])), ((x, dst[1]), dst)])
        return _clean_segments([(src, (src[0], y)), ((src[0], y), (dst[0], y)), ((dst[0], y), dst)])
    if trunk == "ANALYZER_SIGNAL_TRUNK" and src[0] < 400 and dst[0] < 400:
        x = snap_point((max(src[0], dst[0]) + 20.0, 0))[0]
        return _clean_segments([(src, (x, src[1])), ((x, src[1]), (x, dst[1])), ((x, dst[1]), dst)])
    if trunk in TRUNK_X:
        if src[1] == dst[1]:
            return _clean_segments([(src, dst)])
        x = snap_point((TRUNK_X[trunk] + SIGNAL_LANE_OFFSET.get(signal_type, 0.0), 0))[0]
        trunk_spans.setdefault((trunk, signal_type), []).append((src[1], dst[1]))
        return _clean_segments([(src, (x, src[1])), ((x, dst[1]), dst)])
    if trunk in TRUNK_Y:
        if src[0] == dst[0]:
            return _clean_segments([(src, dst)])
        y = snap_point((0, TRUNK_Y[trunk] + SIGNAL_LANE_OFFSET.get(signal_type, 0.0)))[1]
        trunk_spans.setdefault((trunk, signal_type), []).append((src[0], dst[0]))
        return _clean_segments([(src, (src[0], y)), ((dst[0], y), dst)])
    midx = snap_point(((src[0] + dst[0]) / 2, src[1]))[0]
    return _clean_segments([(src, (midx, src[1])), ((midx, src[1]), (midx, dst[1])), ((midx, dst[1]), dst)])


def _trunk_points(trunk: str, signal_type: str, spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not spans:
        return []
    low = min(min(a, b) for a, b in spans)
    high = max(max(a, b) for a, b in spans)
    if abs(high - low) < 0.1:
        return []
    offset = SIGNAL_LANE_OFFSET.get(signal_type, 0.0)
    if trunk in TRUNK_X:
        x = snap_point((TRUNK_X[trunk] + offset, 0))[0]
        return [(x, low), (x, high)]
    if trunk in TRUNK_Y:
        y = snap_point((0, TRUNK_Y[trunk] + offset))[1]
        return [(low, y), (high, y)]
    return []


def _clean_segments(segments: list[tuple[tuple[float, float], tuple[float, float]]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return [(a, b) for a, b in segments if _norm_point(a) != _norm_point(b)]


def _norm_point(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], 3), round(point[1], 3))
