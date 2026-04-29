from __future__ import annotations

import networkx as nx

from .engineering_model import PIDModel


def build_topology(model: PIDModel) -> nx.DiGraph:
    graph = nx.DiGraph()

    for eq in model.equipment:
        graph.add_node(eq.tag, node_type="equipment", kind=eq.kind)
        for noz in eq.nozzles.values():
            graph.add_node(noz.tag, node_type="nozzle", service=noz.service)
            graph.add_edge(eq.tag, noz.tag, edge_type="ownership")

    for v in model.valves:
        graph.add_node(v.tag, node_type="valve", kind=v.kind, fail_position=v.fail_position, sequence_ref=v.sequence_ref)

    for inst in model.instruments:
        graph.add_node(inst.tag, node_type="instrument", kind=inst.kind, location=inst.location)

    for a in model.analyzers:
        graph.add_node(a.tag, node_type="analyzer", conditioner=a.has_sample_conditioner, vent=a.vent_destination, drain=a.drain_destination)
        graph.add_node(a.controller_tag, node_type="instrument", kind="analyzer_controller")
        graph.add_edge(a.tag, a.controller_tag, edge_type="signal")

    for o in model.offpages:
        graph.add_node(o.tag, node_type="offpage", direction=o.direction, drawing_ref=o.drawing_ref)

    for ln in model.lines:
        graph.add_edge(
            ln.src,
            ln.dst,
            edge_type="piping",
            tag=ln.tag,
            size=ln.size,
            service=ln.service,
            spec=ln.spec,
            flow_direction=ln.flow_direction,
        )

    return graph
