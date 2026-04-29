from __future__ import annotations

from typing import List

import networkx as nx

from .engineering_model import PIDModel


class ValidationError(RuntimeError):
    pass


def validate_model(model: PIDModel, graph: nx.DiGraph) -> List[str]:
    errors: List[str] = []

    tags = [e.tag for e in model.equipment] + [v.tag for v in model.valves] + [i.tag for i in model.instruments] + [a.tag for a in model.analyzers]
    if len(tags) != len(set(tags)):
        errors.append("Duplicate equipment/valve/instrument/analyzer tags")

    line_tags = [ln.tag for ln in model.lines]
    if len(line_tags) != len(set(line_tags)):
        errors.append("Duplicate line tags")

    for ln in model.lines:
        for field_name in ["tag", "src", "dst", "size", "service", "spec", "flow_direction"]:
            if not getattr(ln, field_name):
                errors.append(f"Line missing '{field_name}': {ln}")

    for v in model.valves:
        if not v.fail_position or not v.sequence_ref:
            errors.append(f"Valve missing fail position/sequence: {v.tag}")

    for a in model.analyzers:
        if not a.has_sample_conditioner:
            errors.append(f"Analyzer missing sample conditioner: {a.tag}")
        if not a.vent_destination or not a.drain_destination:
            errors.append(f"Analyzer missing vent/drain destination: {a.tag}")

    for o in model.offpages:
        if not o.drawing_ref:
            errors.append(f"Off-page connector missing drawing ref: {o.tag}")

    for u, v, data in graph.edges(data=True):
        if data.get("edge_type") == "piping" and (u not in graph.nodes or v not in graph.nodes):
            errors.append(f"Unconnected piping edge: {u}->{v}")

    return errors


def assert_valid(model: PIDModel, graph: nx.DiGraph) -> None:
    errors = validate_model(model, graph)
    if errors:
        msg = "Validation failed:\n" + "\n".join(f"- {e}" for e in errors)
        raise ValidationError(msg)
