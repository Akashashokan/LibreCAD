"""Tests for the module graph_pattern."""

import uuid

import networkx as nx
import pytest

from pydexpi.syndata.graph_pattern import (
    GraphBasicPipingConnector,
    GraphBasicSignalConnector,
    GraphPattern,
)


def make_a_graph_pattern(label: str, connector_label_suffix: str = "0"):
    """Make a dummy graph pattern with a single node graph. The pattern has
    four connectors, one of each type.
    """
    single_node_graph = nx.DiGraph()
    the_node = str(str(uuid.uuid4()))
    single_node_graph.add_node(the_node)
    connectors = []
    connectors.append(GraphBasicPipingConnector(f"PipeIn_{connector_label_suffix}", the_node, True))
    connectors.append(
        GraphBasicPipingConnector(f"PipeOut_{connector_label_suffix}", the_node, False)
    )
    connectors.append(
        GraphBasicSignalConnector(f"SignalIn_{connector_label_suffix}", the_node, True)
    )
    connectors.append(
        GraphBasicSignalConnector(f"SignalOut_{connector_label_suffix}", the_node, False)
    )

    return GraphPattern(label, single_node_graph, connectors)


# Test connector
def test_connector_constructor():
    """Test if a graph connector is instantiated correctly."""
    ref_node_id = str(uuid.uuid4())
    new_connector = GraphBasicPipingConnector("Clabel", ref_node_id, True)
    assert new_connector.label == "Clabel"
    assert new_connector.reference_node_id == ref_node_id
    assert new_connector.is_inlet


def test_assess_valid_counterpart():
    """Test the capability to assess a valid counterpart of graph connectors."""
    pinc = GraphBasicPipingConnector("PipeIn", str(uuid.uuid4()), True)
    poutc = GraphBasicPipingConnector("PipeOut", str(uuid.uuid4()), False)
    sinc = GraphBasicSignalConnector("SignalIn", str(uuid.uuid4()), True)
    soutc = GraphBasicSignalConnector("SignalOut", str(uuid.uuid4()), False)

    # Test valid connections
    assert pinc.assess_valid_counterpart(poutc) is True
    assert poutc.assess_valid_counterpart(pinc) is True
    assert sinc.assess_valid_counterpart(soutc) is True
    assert soutc.assess_valid_counterpart(sinc) is True

    # Test invalid connections
    assert pinc.assess_valid_counterpart(pinc) is False
    assert sinc.assess_valid_counterpart(sinc) is False
    assert pinc.assess_valid_counterpart(sinc) is False
    assert soutc.assess_valid_counterpart(poutc) is False


# Pattern tests
def test_pattern_constructor():
    """Test instantiating a pattern"""
    the_pattern = make_a_graph_pattern("Pattern1")
    assert len(the_pattern.the_graph.nodes) == 1
    assert len(the_pattern.connectors) == 4


def test_incorporate_pattern():
    """Test connecting a pattern"""
    pattern1 = make_a_graph_pattern("Pattern1")
    pattern2 = make_a_graph_pattern("Pattern2", connector_label_suffix="1")

    # First, try connecting via invalid connectors
    with pytest.raises(ValueError):
        pattern1.incorporate_pattern(
            list(pattern1.connectors.values())[0], pattern2, list(pattern2.connectors.values())[2]
        )

    # Try to connect via valid connector pair using dictionary keys
    pattern1.incorporate_pattern(
        pattern1.connectors["PipeIn_0"], pattern2, pattern2.connectors["PipeOut_1"]
    )

    assert len(pattern1.the_graph.nodes) == 2
    assert len(pattern1.the_graph.edges) == 1
    assert len(pattern1.connectors) == 6


def test_copy_pattern():
    """Test copying a graph pattern with the overriden copy method."""
    pattern1 = make_a_graph_pattern("Pattern1")
    copied_pattern = pattern1.copy_pattern()
    assert len(copied_pattern.the_graph.nodes) == 1
    assert len(copied_pattern.connectors) == 4
    for connector in copied_pattern.connectors.values():
        assert connector.reference_node_id in copied_pattern.the_graph.nodes


def test_load_and_save(tmp_path):
    """Test loading and saving a graph pattern"""
    the_pattern = make_a_graph_pattern("Pattern1")
    the_pattern.save(tmp_path, "test")
    loaded_pattern = GraphPattern.load(tmp_path, "test")

    assert the_pattern.label == loaded_pattern.label

    connectors = the_pattern.connectors
    loaded_connectors = loaded_pattern.connectors
    assert len(connectors) == len(loaded_connectors)
    for c, lc in zip(connectors, loaded_connectors):
        assert c == lc
        assert connectors[c].label == loaded_connectors[lc].label
        assert connectors[c].reference_node_id == loaded_connectors[lc].reference_node_id

    observers = the_pattern.observer_patterns
    loaded_observers = loaded_pattern.observer_patterns
    assert len(observers) == len(loaded_observers)
    assert set(observers.keys()) == set(loaded_observers.keys())
